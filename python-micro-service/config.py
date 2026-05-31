"""
微服务统一配置模块

所有服务共用，从 .env 环境变量读取配置
启动时自动校验必填项，缺失则拒绝启动
"""

import os
import sys

# ---- 1. 加载 .env 文件（必须最先执行）----
try:
    from dotenv import load_dotenv
    # 从项目根目录加载 .env
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except ImportError:
    print("[WARNING] python-dotenv 未安装，将仅读取系统环境变量")

# ---- 2. Nacos 注册中心 ----
NACOS_SERVER: str = os.getenv("NACOS_SERVER", "localhost:8848")

# ---- 3. JWT 认证配置 ----
JWT_SECRET: str = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# ---- 4. MySQL 数据库 ----
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME_USER: str = os.getenv("DB_NAME_USER", "db_user")
DB_NAME_GOODS: str = os.getenv("DB_NAME_GOODS", "db_goods")
DB_NAME_ORDER: str = os.getenv("DB_NAME_ORDER", "db_order")


def get_db_url(db_name: str) -> str:
    """根据数据库名生成 MySQL 异步连接 URL"""
    return f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db_name}"


# ---- 5. Redis 缓存 ----
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# ---- 6. RabbitMQ 消息队列 ----
RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "")

# ---- 7. 网关限流 ----
RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))
RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "1"))

# ---- 8. 网关熔断 ----
CB_FAILURE_THRESHOLD: int = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
CB_TIMEOUT_SECONDS: int = int(os.getenv("CB_TIMEOUT_SECONDS", "30"))

# ---- 9. CORS 跨域配置（逗号分隔的允许来源列表）----
_CORS_ORIGINS_RAW: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000")
CORS_ORIGINS: list[str] = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

# ---- 10. 服务注册信息 ----
SERVICE_IP: str = os.getenv("SERVICE_IP", "127.0.0.1")
GATEWAY_PORT: int = int(os.getenv("GATEWAY_PORT", "8000"))
USER_SERVICE_PORT: int = int(os.getenv("USER_SERVICE_PORT", "8001"))
GOODS_SERVICE_PORT: int = int(os.getenv("GOODS_SERVICE_PORT", "8002"))
ORDER_SERVICE_PORT: int = int(os.getenv("ORDER_SERVICE_PORT", "8003"))


def validate_config(service_name: str, required_vars: list):
    """
    启动时校验关键配置项。
    缺失必填项 → 打印错误信息并退出进程（不静默使用默认值）
    """
    errors = []
    for var_name in required_vars:
        value = globals().get(var_name, "")
        if value is None or (isinstance(value, str) and value.strip() == ""):
            errors.append(f"  - {var_name}")

    if errors:
        print("=" * 50)
        print(f"[FATAL] {service_name} 配置不完整，缺少以下必要环境变量：")
        for e in errors:
            print(e)
        print()
        print("请检查 .env 文件或设置对应环境变量后重试。")
        print("参考模板：cp .env.example .env")
        print("=" * 50)
        sys.exit(1)
