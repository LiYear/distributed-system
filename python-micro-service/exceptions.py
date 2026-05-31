"""
微服务统一异常处理模块

提供：
1. 标准响应格式 (ResponseModel)
2. 异常分类体系 — 基类 + 领域子类
3. 全局异常处理器注册函数（含标准 logging）
4. 请求 TraceID 生成与传递
"""

import logging
import traceback
import uuid
from datetime import datetime
from typing import Any, Optional, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


# ============ 日志配置 ============

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
)
logger = logging.getLogger("exception-handler")


# ============ 标准 API 响应格式 ============

class ResponseModel:
    """统一响应格式封装"""

    @staticmethod
    def success(data: Any = None, message: str = "success") -> Dict:
        """成功响应"""
        return {
            "code": 200,
            "message": message,
            "data": data,
            "trace_id": _get_trace_id(),
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def error(code: int, message: str, data: Any = None) -> Dict:
        """错误响应"""
        return {
            "code": code,
            "message": message,
            "data": data,
            "trace_id": _get_trace_id(),
            "timestamp": datetime.now().isoformat(),
        }


# ============ 异常分类体系 ============

class BizException(Exception):
    """
    业务逻辑异常基类（由代码主动抛出）

    子类按领域细分：
      - NotFoundError     资源不存在 (404)
      - ValidationError   参数校验失败 (400)
      - UnauthorizedError 未授权/未登录 (401)
      - ForbiddenError     无权限 (403)
      - ConflictError     资源冲突 (409)
      - ExternalServiceError 外部服务调用失败 (502)
      - DatabaseError     数据库操作错误 (500)
    """

    def __init__(self, code: int = 400, message: str = "业务处理失败", http_status: int = None):
        self.code = code
        self.message = message
        # 允许子类显式指定 HTTP 状态码；默认根据 code 映射
        self.http_status = http_status or _map_code_to_http_status(code)
        super().__init__(message)


def _map_code_to_http_status(biz_code: int) -> int:
    """将业务错误码映射为语义正确的 HTTP 状态码"""
    mapping = {
        400: 400,   # Bad Request
        401: 401,   # Unauthorized
        403: 403,   # Forbidden
        404: 404,   # Not Found
        409: 409,   # Conflict
        500: 500,   # Internal Server Error
        502: 502,   # Bad Gateway
        503: 503,   # Service Unavailable
        504: 504,   # Gateway Timeout
    }
    # 对于未明确映射的 code，4xx 范围返回对应值，其他返回 400 或 500
    if biz_code in mapping:
        return mapping[biz_code]
    if 400 <= biz_code < 500:
        return biz_code
    if biz_code >= 500:
        return 500
    return 400  # 默认


# ---------- 领域子异常类 ----------

class NotFoundError(BizException):
    """资源未找到 — HTTP 404"""
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=404, message=message)


class ValidationError(BizException):
    """请求参数校验失败 — HTTP 400"""
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(code=400, message=message)


class UnauthorizedError(BizException):
    """未授权/Token 无效 — HTTP 401"""
    def __init__(self, message: str = "未授权，请先登录"):
        super().__init__(code=401, message=message)


class ForbiddenError(BizException):
    """无权访问 — HTTP 403"""
    def __init__(self, message: str = "无权执行此操作"):
        super().__init__(code=403, message=message)


class ConflictError(BizException):
    """资源冲突（如重复创建）— HTTP 409"""
    def __init__(self, message: str = "资源冲突"):
        super().__init__(code=409, message=message)


class ExternalServiceError(BizException):
    """外部服务调用失败 — HTTP 502"""
    def __init__(self, service_name: str = "", message: str = "外部服务不可用"):
        msg = f"{service_name}: {message}" if service_name else message
        super().__init__(code=502, message=msg)


class DatabaseError(BizException):
    """数据库操作异常 — HTTP 500"""
    def __init__(self, message: str = "数据库操作失败"):
        super().__init__(code=500, message=message)


# ============ TraceID 工具 ============

_trace_id_ctx: Optional[str] = None


def set_trace_id(trace_id: Optional[str] = None):
    """设置当前请求的 TraceID（每个请求开始时调用）"""
    global _trace_id_ctx
    _trace_id_ctx = trace_id or f"{uuid.uuid4().hex[:16]}"


def get_trace_id() -> str:
    """获取当前请求的 TraceID"""
    return _trace_id_ctx or "-"


def _get_trace_id() -> str:
    """内部使用：获取 TraceID（兼容未设置场景）"""
    return _trace_id_ctx or "-"


# ============ 全局异常处理器工厂 ============

def register_exception_handlers(app: FastAPI):
    """
    为 FastAPI 注册全局异常处理器。

    捕获四类异常：
    1. BizException 及其子类 — 业务异常，返回对应的 HTTP 状态码
    2. RequestValidationError — Pydantic 校验失败，返回 422 + 字段级错误详情
    3. HTTPException          — FastAPI 内置 HTTP 异常透传
    4. Exception              — 所有未预期异常，返回 500 + 隐藏堆栈（仅日志记录）
    """

    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException):
        logger.warning(
            "[业务异常] trace=%s | %s %s | code=%d | msg=%s",
            get_trace_id(), request.method, request.url.path,
            exc.code, exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,  # 使用语义正确的 HTTP 状态码
            content=ResponseModel.error(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            errors.append({"field": loc, "message": err.get("msg"), "type": err.get("type")})
        logger.warning(
            "[参数校验失败] trace=%s | %s %s | errors=%s",
            get_trace_id(), request.method, request.url.path, errors,
        )
        return JSONResponse(
            status_code=422,
            content=ResponseModel.error(422, "请求参数校验失败", errors),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # 记录完整堆栈到日志（不返回给客户端）
        request_id = getattr(getattr(request, "state", None), "trace_id", "?")
        logger.error(
            "[系统异常] trace=%s | %s %s | Exception=%s: %s",
            request_id, request.method, request.url.path,
            type(exc).__name__, exc,
            exc_info=True,
        )
        # 返回安全信息给客户端
        return JSONResponse(
            status_code=500,
            content=ResponseModel.error(500, "服务器内部错误，请稍后重试"),
        )
