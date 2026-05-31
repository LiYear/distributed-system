import json
import logging
import os
import sys
import random
import asyncio

import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from nacos import NacosClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# 将项目根目录加入路径，以导入共享 config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    NACOS_SERVER, REDIS_URL, CORS_ORIGINS,
    SERVICE_IP, GOODS_SERVICE_PORT,
    validate_config,
:)
validate_config("Goods-Service", ["REDIS_URL"])

from database import get_db, engine, Base
from models import Goods
from schemas import GoodsCreate, GoodsInfo
from exceptions import (
    register_exception_handlers,
    NotFoundError, ValidationError,
)

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
)
logger = logging.getLogger("goods-service")

app = FastAPI(title="商品微服务", version="1.0")


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

redis: aioredis.Redis | None = None


def register_nacos():
    client = NacosClient(NACOS_SERVER)
    client.add_naming_instance(service_name="goods-service", ip=SERVICE_IP, port=GOODS_SERVICE_PORT, heartbeat_interval=5)
    logger.info("商品服务已注册到 Nacos")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    global redis
    # Redis 地址从环境变量读取
    redis = await aioredis.from_url(REDIS_URL)
    logger.info("Redis 连接成功: %s", REDIS_URL)
    register_nacos()


@app.on_event("shutdown")
async def shutdown():
    await redis.close()


@app.post("/goods/add", response_model=GoodsInfo)
async def add_goods(goods: GoodsCreate, db: AsyncSession = Depends(get_db)):
    new_goods = Goods(name=goods.name, price=goods.price, stock=goods.stock)
    db.add(new_goods)
    await db.commit()
    await db.refresh(new_goods)
    # Cache-Aside 写路径：写 DB 后删除缓存（延迟双删策略）
    cache_key = f"goods:{new_goods.id}"
    await redis.delete(cache_key)
    logger.info("[新增商品] id=%s name=%s price=%.2f stock=%d",
                new_goods.id, new_goods.name, new_goods.price, new_goods.stock)
    return new_goods


@app.get("/goods/{goods_id}", response_model=GoodsInfo)
async def get_goods(goods_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = f"goods:{goods_id}"

    # 1. 先查缓存
    cache_data = await redis.get(cache_key)
    if cache_data:
        # 检查是否为空值标记（防止缓存穿透）
        data = json.loads(cache_data)
        if data.get("_empty"):
            raise NotFoundError(f"商品不存在 (id={goods_id})")
        return data

    # 2. 缓存未命中 → 加分布式锁（防止缓存击穿）
    lock_key = f"lock:{cache_key}"
    lock_acquired = await redis.set(lock_key, "1", nx=True, ex=5)  # 锁 5 秒过期

    if not lock_acquired:
        # 没抢到锁，等一小段时间后重试读缓存（其他请求可能已写好）
        await asyncio.sleep(0.05)
        retry_data = await redis.get(cache_key)
        if retry_data:
            data = json.loads(retry_data)
            if data.get("_empty"):
                raise NotFoundError(f"商品不存在 (id={goods_id})")
            return data
        # 重试仍未命中，继续查 DB（降级处理）
    else:
        # 抢到锁，查询数据库
        try:
            result = await db.execute(select(Goods).where(Goods.id == goods_id))
            goods = result.scalar_one_or_none()

            if not goods:
                # 【修复缓存穿透】：缓存空值，短 TTL
                await redis.setex(cache_key, 60, json.dumps({"_empty": True}))
                raise NotFoundError(f"商品不存在 (id={goods_id})")

            # 【修复缓存雪崩】：TTL 加随机抖动 (300~360秒)
            ttl = 300 + random.randint(0, 60)
            goods_dict = {"id": goods.id, "name": goods.name, "price": goods.price, "stock": goods.stock}
            await redis.setex(cache_key, ttl, json.dumps(goods_dict))
            return goods
        finally:
            # 释放分布式锁
            await redis.delete(lock_key)


@app.put("/goods/stock/{goods_id}")
async def deduct_stock(goods_id: int, num: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goods).where(Goods.id == goods_id))
    goods = result.scalar_one_or_none()
    if not goods:
        raise NotFoundError(f"商品不存在 (id={goods_id})")
    if goods.stock < num:
        raise ValidationError(f"库存不足 (当前库存=%d，需要=%d)", goods.stock, num)

    goods.stock -= num
    await db.commit()
    # Cache-Aside 写路径：写 DB 后删除缓存（延迟双删策略）
    cache_key = f"goods:{goods_id}"
    await redis.delete(cache_key)
    logger.info("[扣减库存] goods_id=%s num=%d 剩余库存=%d", goods_id, num, goods.stock)
    return {"code": 200, "msg": "扣库存成功"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=GOODS_SERVICE_PORT)
