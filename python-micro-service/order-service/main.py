from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import aiohttp
import aio_pika
import uuid
from nacos import NacosClient
import uvicorn

from database import get_db, engine, Base
from models import Order
from schemas import OrderCreate, OrderInfo

app = FastAPI(title="订单微服务", version="1.0")
rabbit_connection = None
rabbit_channel = None


@app.on_event("startup")
async def startup():
    # 创建订单表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 连接 RabbitMQ
    global rabbit_connection, rabbit_channel
    rabbit_connection = await aio_pika.connect_robust(
        host="localhost", login="admin", password="admin123"
    )
    rabbit_channel = await rabbit_connection.channel()
    await rabbit_channel.declare_queue("order_notify_queue", durable=True)


@app.on_event("shutdown")
async def shutdown():
    await rabbit_connection.close()


# Nacos 注册
def register_nacos():
    client = NacosClient("localhost:8848")
    client.add_naming_instance(service_name="order-service", ip="127.0.0.1", port=8003)
    print("订单服务已注册到 Nacos")


# 调用商品服务扣库存（服务间HTTP调用）
async def deduct_goods_stock(goods_id: int, num: int):
    async with aiohttp.ClientSession() as session:
        url = f"http://127.0.0.1:8002/goods/stock/{goods_id}?num={num}"
        async with session.put(url) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=400, detail="扣库存失败")


# 发送消息到 RabbitMQ
async def send_order_msg(order_info: dict):
    msg_body = str(order_info)
    await rabbit_channel.default_exchange.publish(
        aio_pika.Message(body=msg_body.encode()),
        routing_key="order_notify_queue"
    )


# 下单接口
@app.post("/order/create", response_model=OrderInfo)
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    # 1. 远程调用商品服务扣库存
    await deduct_goods_stock(order.goods_id, order.buy_num)

    # 2. 模拟查询商品价格（简化）
    async with aiohttp.ClientSession() as session:
        res = await session.get(f"http://127.0.0.1:8002/goods/{order.goods_id}")
        goods_data = await res.json()
        total_price = goods_data["price"] * order.buy_num

    # 3. 创建订单
    order_no = f"ORD_{uuid.uuid4()}"
    new_order = Order(
        order_no=order_no,
        user_id=order.user_id,
        goods_id=order.goods_id,
        buy_num=order.buy_num,
        total_price=total_price
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)

    # 4. 发送异步消息
    await send_order_msg({
        "order_no": order_no,
        "user_id": order.user_id,
        "total_price": total_price
    })
    return new_order


# 查询订单
@app.get("/order/{order_id}", response_model=OrderInfo)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Order).where(Order.id == order_id))
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8003)
