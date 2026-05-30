from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from nacos import NacosClient
import uvicorn

from database import get_db, engine, Base
from models import User
from schemas import UserCreate, UserInfo

# 1. 初始化 FastAPI
app = FastAPI(title="用户微服务", version="1.0")


# 2. 启动时创建数据表
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# 3. Nacos 服务注册（核心：服务发现）
def register_nacos():
    server_addrs = "localhost:8848"
    client = NacosClient(server_addrs)
    client.add_naming_instance(service_name="user-service", ip="127.0.0.1", port=8001)
    print("用户服务已注册到 Nacos")


# 4. 接口
@app.post("/user/register", response_model=UserInfo, summary="用户注册")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # 判断用户名是否存在
    result = await db.execute(select(User).where(User.username == user.username))
    exist_user = result.scalar_one_or_none()
    if exist_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    new_user = User(
        username=user.username,
        password=user.password,
        phone=user.phone
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@app.get("/user/{user_id}", response_model=UserInfo, summary="查询用户信息")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


# 5. 启动入口
if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8001)
