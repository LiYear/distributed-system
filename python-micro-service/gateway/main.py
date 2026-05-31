"""
微服务网关 - 增强版

功能：
1. 从 Nacos 动态发现服务地址
2. JWT 鉴权/认证
3. 请求限流（基于 IP）
4. 熔断器（下游故障快速失败）
5. 请求日志和监控（耗时统计）

配置：全部从环境变量 / .env 文件读取，启动时校验必填项
"""

import os
import sys
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Dict

# 将项目根目录加入路径，以导入共享 config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    NACOS_SERVER, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS,
    RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS,
    CB_FAILURE_THRESHOLD, CB_TIMEOUT_SECONDS,
    SERVICE_IP, GATEWAY_PORT,
    CORS_ORIGINS,
    validate_config,
)
from exceptions import register_exception_handlers, set_trace_id, ResponseModel
validate_config("Gateway", ["JWT_SECRET"])

import httpx
import jwt
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from nacos import NacosClient
from pydantic import BaseModel

# ============ 白名单路径（不需要鉴权）============
AUTH_WHITE_LIST = [
    "/user/register",
    "/user/login",
    "/health",
    "/docs",
    "/openapi.json",
]

# 服务路由映射（服务名 -> 路径前缀）
SERVICE_ROUTES = {
    "user-service": "/user",
    "goods-service": "/goods",
    "order-service": "/order",
}

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
)
logger = logging.getLogger("gateway")

app = FastAPI(title="微服务网关 (增强版)")


@app.get("/health")
async def health():
    return {"status": "ok"}

# ============ 全局异常处理器 ============
register_exception_handlers(app)

# ============ CORS 跨域中间件 ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Nacos 服务发现 ============
class ServiceDiscovery:
    """从 Nacos 动态发现服务地址"""

    def __init__(self):
        self.client = NacosClient(NACOS_SERVER)
        self._cache: Dict[str, str] = {}

    # 当 Nacos 返回 0.0.0.0 时，使用 Docker Compose 服务名作为主机名
    _DOCKER_HOSTNAME_FALLBACK = {
        "user-service": "user-service",
        "goods-service": "goods-service",
        "order-service": "order-service",
    }

    def get_service_url(self, service_name: str) -> Optional[str]:
        if service_name in self._cache:
            return self._cache[service_name]
        try:
            instances = self.client.list_naming_instance(service_name)
            if instances and len(instances["hosts"]) > 0:
                instance = instances["hosts"][0]
                host = instance["ip"]
                if host in ("0.0.0.0", "127.0.0.1"):
                    host = self._DOCKER_HOSTNAME_FALLBACK.get(service_name, host)
                url = f"http://{host}:{instance['port']}"
                self._cache[service_name] = url
                logger.info(f"服务发现: {service_name} -> {url}")
                return url
            else:
                logger.warning(f"Nacos 中未找到服务: {service_name}")
                return None
        except Exception as e:
            logger.error(f"服务发现异常 [{service_name}]: {e}")
            return None

    def refresh_cache(self):
        self._cache.clear()
        for service in SERVICE_ROUTES.keys():
            self.get_service_url(service)


discovery = ServiceDiscovery()


def register_nacos():
    discovery.    client.add_naming_instance(
        service_name="gateway", ip=SERVICE_IP, port=GATEWAY_PORT, heartbeat_interval=5
    )
    logger.info("网关已注册到 Nacos")


# ============ JWT 鉴权 ============
class AuthMiddleware:
    @staticmethod
    def verify_token(request: Request) -> Dict:
        path = request.url.path
        for white_path in AUTH_WHITE_LIST:
            if path.startswith(white_path) or path == white_path:
                return {"sub": None, "skip": True}
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="未提供认证 Token")
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return {"sub": payload.get("sub"), "exp": payload.get("exp")}
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token 已过期")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"无效的 Token: {e}")


def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class TokenRequest(BaseModel):
    user_id: str


@app.post("/auth/token")
async def login(req: TokenRequest):
    """模拟登录，返回 Token（实际应调用 user-service /user/login）"""
    token = create_token(req.user_id)
    return {"access_token": token, "token_type": "Bearer"}


# ============ 限流器 ============
class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        self.requests[ip] = [
            t for t in self.requests[ip] if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(self.requests[ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        self.requests[ip].append(now)
        return True


rate_limiter = RateLimiter()


# ============ 熔断器 ============
class CircuitBreaker:
    def __init__(self):
        self.failure_counts: Dict[int] = defaultdict(int)
        self.breaker_states: Dict[int] = {}

    def can_execute(self, port: int) -> bool:
        state_info = self.breaker_states.get(port)
        if state_info is None:
            return True
        state, open_time = state_info
        if state == "closed":
            return True
        elif state == "open":
            if time.time() - open_time > CB_TIMEOUT_SECONDS:
                self.breaker_states[port] = ("half_open", time.time())
                return True
            return False
        elif state == "half_open":
            return True
        return True

    def record_success(self, port: int):
        self.failure_counts[port] = 0
        if port in self.breaker_states:
            self.breaker_states[port] = ("closed", time.time())
            logger.info(f"[熔断器] 端口 {port} 恢复正常")

    def record_failure(self, port: int):
        self.failure_counts[port] += 1
        count = self.failure_counts[port]
        if count >= CB_FAILURE_THRESHOLD:
            old_state = self.breaker_states.get(port, ("closed", 0))[0]
            if old_state != "open":
                self.breaker_states[port] = ("open", time.time())
                logger.warning(f"[熔断器] 端口 {port} 触发熔断！连续失败 {count} 次")


circuit_breaker = CircuitBreaker()


# ============ 健康检查 & 监控接口 ============
@app.get("/metrics/gateway")
async def gateway_metrics():
    cb_status = {}
    for port, info in circuit_breaker.breaker_states.items():
        state, t = info
        cb_status[f"port_{port}"] = {"state": state, "failures": circuit_breaker.failure_counts.get(port, 0)}
    return {
        "circuit_breakers": cb_status,
        "service_cache": list(discovery._cache.keys()),
        "rate_limiter": {
            "tracked_ips": len(rate_limiter.requests),
            "limit": f"{RATE_LIMIT_MAX_REQUESTS}/{RATE_LIMIT_WINDOW_SECONDS}s",
        },
    }


# ============ 统一路由转发 ============
@app.api_route("/{service_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway_route(
    request: Request,
    auth_result: Dict = Depends(AuthMiddleware.verify_token),
):
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = f"/{request.path_params.get('service_path', '')}"
    logger.info(f"[请求] {client_ip} {method} {path}")

    # 1. 限流检查
    if not rate_limiter.is_allowed(client_ip):
        elapsed = (time.time() - start_time) * 1000
        logger.warning(f"[限流拒绝] {client_ip} {path} ({elapsed:.1f}ms)")
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    # 2. 匹配目标服务
    target_service = None
    for svc_name, prefix in SERVICE_ROUTES.items():
        if path.startswith(prefix + "/") or path == prefix:
            target_service = svc_name
            break
    if not target_service:
        raise HTTPException(status_code=404, detail=f"无匹配的服务: {path}")

    if not path.startswith("/auth"):
        pass

    # 3. 服务发现
    service_url = discovery.get_service_url(target_service)
    if not service_url:
        raise HTTPException(status_code=503, detail=f"服务 {target_service} 不可用")

    target_port = int(service_url.split(":")[-1])

    # 4. 熔断检查
    if not circuit_breaker.can_execute(target_port):
        raise HTTPException(status_code=503, detail=f"服务 {target_service} 暂时不可用")

    # 5. 转发请求
    target_url = f"{service_url}{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.request(method=method, url=target_url,
                                       content=await request.body(), headers=dict(request.headers))
        circuit_breaker.record_success(target_port)
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"[响应] {method} {path} -> {resp.status_code} ({elapsed:.1f}ms)")
        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))
    except httpx.ConnectError:
        circuit_breaker.record_failure(target_port)
        raise HTTPException(status_code=503, detail=f"无法连接到服务 {target_service}")
    except httpx.TimeoutException:
        circuit_breaker.record_failure(target_port)
        raise HTTPException(status_code=504, detail=f"服务 {target_service} 响应超时")




@app.on_event("startup")
async def startup():
    register_nacos()


# ============ 启动 ============
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
