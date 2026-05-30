"""
微服务网关 - 增强版

功能：
1. 从 Nacos 动态发现服务地址
2. JWT 鉴权/认证
3. 请求限流（基于 IP）
4. 熔断器（下游故障快速失败）
5. 请求日志和监控（耗时统计）
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

import httpx
import jwt
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware import Middleware
from nacos import NacosClient
from pydantic import BaseModel

# ============ 配置 ============
NACOS_SERVER = "localhost:8848"
JWT_SECRET = "your-secret-key-change-in-production"  # 生产环境请使用环境变量
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# 限流配置：每 IP 每秒最大请求数
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 1

# 熔断配置
CB_FAILURE_THRESHOLD = 5      # 连续失败次数阈值
CB_TIMEOUT_SECONDS = 30       # 熔断恢复等待时间（秒）

# 白名单路径（不需要鉴权）
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


# ============ Nacos 服务发现 ============
class ServiceDiscovery:
    """从 Nacos 动态发现服务地址"""
    
    def __init__(self):
        self.client = NacosClient(NACOS_SERVER)
        self._cache: Dict[str, str] = {}  # service_name -> url
    
    def get_service_url(self, service_name: str) -> Optional[str]:
        """获取服务地址，带缓存"""
        # 先查缓存
        if service_name in self._cache:
            return self._cache[service_name]
        
        # 从 Nacos 发现
        try:
            instances = self.client.list_naming_instances(service_name)
            if instances and len(instances["hosts"]) > 0:
                instance = instances["hosts"][0]
                url = f"http://{instance['ip']}:{instance['port']}"
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
        """刷新所有服务的缓存"""
        self._cache.clear()
        for service in SERVICE_ROUTES.keys():
            self.get_service_url(service)


discovery = ServiceDiscovery()


def register_nacos():
    """注册网关到 Nacos"""
    discovery.client.add_naming_instance(
        service_name="gateway", ip="127.0.0.1", port=8000
    )
    logger.info("网关服务已注册到 Nacos")


# ============ JWT 鉴权 ============
class AuthMiddleware:
    """JWT 认证中间件"""
    
    @staticmethod
    def verify_token(request: Request) -> Dict:
        """
        验证 JWT Token，白名单路径跳过验证。
        作为依赖注入使用，按需鉴权。
        """
        path = request.url.path
        
        # 检查白名单
        for white_path in AUTH_WHITE_LIST:
            if path.startswith(white_path) or path == white_path:
                return {"sub": None, "skip": True}
        
        # 提取 Token
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
    """生成 JWT Token（供登录接口调用）"""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class TokenRequest(BaseModel):
    user_id: str


@app.post("/auth/token")
async def login(req: TokenRequest):
    """模拟登录，返回 Token（实际项目中应校验用户名密码）"""
    token = create_token(req.user_id)
    return {"access_token": token, "token_type": "Bearer"}


# ============ 限流器 ============
class RateLimiter:
    """基于滑动窗口的 IP 限流器"""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
    
    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        # 清理过期记录
        self.requests[ip] = [
            t for t in self.requests[ip]
            if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]
        # 判断是否超限
        if len(self.requests[ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        self.requests[ip].append(now)
        return True


rate_limiter = RateLimiter()


# ============ 熔断器 ============
class CircuitBreaker:
    """简单的熔断器实现"""
    
    def __init__(self):
        self.failure_counts: Dict[int] = defaultdict(int)
        self.breaker_states: Dict[int] = {}  # service_port -> (state, open_time)
        # state: "closed"(正常) | "open"(熔断中) | "half_open"(半开探测)
    
    def can_execute(self, port: int) -> bool:
        """判断是否允许执行请求"""
        state_info = self.breaker_states.get(port)
        
        if state_info is None:
            # 首次访问，正常状态
            return True
        
        state, open_time = state_info
        
        if state == "closed":
            return True
        elif state == "open":
            # 检查是否超过冷却时间
            if time.time() - open_time > CB_TIMEOUT_SECONDS:
                self.breaker_states[port] = ("half_open", time.time())
                return True  # 半开放一个请求试探
            else:
                return False
        elif state == "half_open":
            return True  # 半开状态下只允许一个请求通过
        return True
    
    def record_success(self, port: int):
        """记录成功"""
        self.failure_counts[port] = 0
        if port in self.breaker_states:
            self.breaker_states[port] = ("closed", time.time())
            logger.info(f"[熔断器] 端口 {port} 恢复正常")
    
    def record_failure(self, port: int):
        """记录失败"""
        self.failure_counts[port] += 1
        count = self.failure_counts[port]
        
        if count >= CB_FAILURE_THRESHOLD:
            old_state = self.breaker_states.get(port, ("closed", 0))[0]
            if old_state != "open":
                self.breaker_states[port] = ("open", time.time())
                logger.warning(f"[熔断器] 端口 {port} 触发熔断！连续失败 {count} 次")


circuit_breaker = CircuitBreaker()


# ============ 通用路由转发函数 ============
@app.api_route("/{service_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway_route(
    request: Request,
    auth_result: Dict = Depends(AuthMiddleware.verify_token),
):
    """
    统一入口：根据路径前缀动态路由到对应微服务
    
    流程：
    1. 日志记录开始
    2. 限流检查
    3. 鉴权（白名单除外）
    4. 服务发现 + 熔断检查
    5. 转发请求
    6. 日志记录结束
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = f"/{request.path_params.get('service_path', '')}"
    
    logger.info(f"[请求] {client_ip} {method} {path}")
    
    # --- 1. 限流检查 ---
    if not rate_limiter.is_allowed(client_ip):
        elapsed = (time.time() - start_time) * 1000
        logger.warning(f"[限流拒绝] {client_ip} {path} ({elapsed:.1f}ms)")
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁，请稍后再试 (每{RATE_LIMIT_WINDOW_SECONDS}秒最多{RATE_LIMIT_MAX_REQUESTS}次)"
        )
    
    # --- 2. 匹配目标服务 ---
    target_service = None
    target_prefix = None
    for svc_name, prefix in SERVICE_ROUTES.items():
        if path.startswith(prefix + "/") or path == prefix:
            target_service = svc_name
            target_prefix = prefix
            break
    
    if not target_service:
        elapsed = (time.time() - start_time) * 1000
        logger.warning(f"[路由失败] 无匹配服务: {path} ({elapsed:.1f}ms)")
        raise HTTPException(status_code=404, detail=f"无匹配的服务: {path}")
    
    # /auth 路径是网关自身处理，不转发
    if path.startswith("/auth"):
        pass
    
    # --- 3. 服务发现 ---
    service_url = discovery.get_service_url(target_service)
    if not service_url:
        raise HTTPException(
            status_code=503,
            detail=f"服务 {target_service} 不可用（未在 Nacos 注册）"
        )
    
    # 提取端口号用于熔断
    target_port = int(service_url.split(":")[-1])
    
    # --- 4. 熔断检查 ---
    if not circuit_breaker.can_execute(target_port):
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"[熔断拦截] {target_service}:{target_port} ({elapsed:.1f}ms)")
        raise HTTPException(
            status_code=503,
            detail=f"服务 {target_service} 暂时不可用，请稍后再试"
        )
    
    # --- 5. 转发请求 ---
    target_url = f"{service_url}{path}"
    
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.request(
                method=method,
                url=target_url,
                content=await request.body(),
                headers=dict(request.headers),
            )
            
        circuit_breaker.record_success(target_port)
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(
            f"[响应] {method} {path} -> {resp.status_code} "
            f"({elapsed:.1f}ms) [上游:{service_url}]"
        )
        
        return resp.content, resp.status_code, resp.headers.items()
        
    except httpx.ConnectError:
        circuit_breaker.record_failure(target_port)
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"[连接失败] 无法连接 {service_url} ({elapsed:.1f}ms)")
        raise HTTPException(status_code=503, detail=f"无法连接到服务 {target_service}")
    
    except httpx.TimeoutException:
        circuit_breaker.record_failure(target_port)
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"[超时] {service_url} 响应超时 ({elapsed:.1f}ms)")
        raise HTTPException(status_code=504, detail=f"服务 {target_service} 响应超时")


# ============ 健康检查 & 监控接口 ============
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "service": "gateway",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/metrics/gateway")
async def gateway_metrics():
    """网关运行指标"""
    cb_status = {}
    for port, info in circuit_breaker.breaker_states.items():
        state, t = info
        cb_status[f"port_{port}"] = {
            "state": state,
            "failures": circuit_breaker.failure_counts.get(port, 0),
            "since": datetime.fromtimestamp(t).isoformat() if t else None,
        }
    
    return {
        "circuit_breakers": cb_status,
        "service_cache": discovery._cache,
        "rate_limiter": {
            "tracked_ips": len(rate_limiter.requests),
            "limit": f"{RATE_LIMIT_MAX_REQUESTS}/{RATE_LIMIT_WINDOW_SECONDS}s",
        },
    }


# ============ 启动 ============
if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8000)
