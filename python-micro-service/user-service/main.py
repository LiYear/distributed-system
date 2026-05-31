import logging
import os
import sys

import jwt
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from nacos import NacosClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# 将项目根目录加入路径，以导入共享 config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    NACOS_SERVER, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS,
    SERVICE_IP, USER_SERVICE_PORT, CORS_ORIGINS,
    validate_config,
:)
validate_config("User-Service", ["DB_PASSWORD", "JWT_SECRET"])

from database import get_db, engine, Base
from models import User
from schemas import UserCreate, UserInfo, UserLogin, LoginResponse
from utils.password import hash_password, verify_password
from exceptions import (
    register_exception_handlers,
    NotFoundError, ConflictError, UnauthorizedError,
)

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
)
logger = logging.getLogger("user-service")

app = FastAPI(title="用户微服务", version="1.0")


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


def register_nacos():
    server_addrs = NACOS_SERVER
    client = NacosClient(server_addrs)
    client.add_naming_instance(service_name="user-service", ip=SERVICE_IP, port=USER_SERVICE_PORT, heartbeat_interval=5)
    logger.info("用户服务已注册到 Nacos")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    register_nacos()


@app.post("/user/register", response_model=UserInfo, summary="用户注册")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user.username))
    exist_user = result.scalar_one_or_none()
    if exist_user:
        raise ConflictError("用户名已存在")

    new_user = User(
        username=user.username,
        password=hash_password(user.password),
        phone=user.phone,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@app.post("/user/login", response_model=LoginResponse, summary="用户登录")
async def login(login_req: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == login_req.username))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("用户名或密码错误")

    if not verify_password(login_req.password, user.password):
        raise UnauthorizedError("用户名或密码错误")

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    logger.info("[登录成功] username=%s user_id=%s", user.username, user.id)
    return LoginResponse(user_id=user.id, username=user.username, token=token)


@app.get("/user/{user_id}", response_model=UserInfo, summary="查询用户信息")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError(f"用户不存在 (id={user_id})")
    return user


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=USER_SERVICE_PORT)
