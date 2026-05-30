from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import aioredis
from nacos import NacosClient
import json
import uvicorn

from database import get_db, engine, Base
from models import Goods
from schemas import GoodsCreate, GoodsInfo

app = FastAPI(title="商品微服务", version="1.0")

# Redis 全局连接
redis: aioredis.Redis | None = None


@app.on_event("startup")
async def startup():
    # 创建数据表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 连接 Redis
    global redis
    redis = await aioredis.from_url("redis://localhost:6379")


@app.on_event("shutdown")
async def shutdown():
    await redis.close()


# Nacos 注册
def register_nacos():
    client = NacosClient("localhost:8848")
    client.add_naming_instance(service_name="goods-service", ip="127.0.0.1", port=8002)
    print("商品服务已注册到 Nacos")


# 接口：新增商品
@app.post("/goods/add", response_model=GoodsInfo)
async def add_goods(goods: GoodsCreate, db: AsyncSession = Depends(get_db)):
    new_goods = Goods(name=goods.name, price=goods.price, stock=goods.stock)
    db.add(new_goods)
    await db.commit()
    await db.refresh(new_goods)
    return new_goods


# 接口：查询商品（优先走 Redis 缓存）
@app.get("/goods/{goods_id}", response_model=GoodsInfo)
async def get_goods(goods_id: int, db: AsyncSession = Depends(get_db)):
    # 1. 查缓存
    cache_key = f"goods:{goods_id}"
    cache_data = await redis.get(cache_key)
    if cache_data:
        return json.loads(cache_data)

    # 2. 缓存没有，查数据库
    result = await db.execute(select(Goods).where(Goods.id == goods_id))
    goods = result.scalar_one_or_none()
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 3. 写入缓存（过期时间 5 分钟）
    goods_dict = {"id": goods.id, "name": goods.name, "price": goods.price, "stock": goods.stock}
    await redis.setex(cache_key, 300, json.dumps(goods_dict))
    return goods


# 扣库存（订单服务调用）
@app.put("/goods/stock/{goods_id}")
async def deduct_stock(goods_id: int, num: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goods).where(Goods.id == goods_id))
    goods = result.scalar_one_or_none()
    if not goods or goods.stock < num:
        raise HTTPException(status_code=400, detail="库存不足")
    goods.stock -= num
    await db.commit()
    return {"code": 200, "msg": "扣库存成功"}


if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8002)
