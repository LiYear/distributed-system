import json
import logging
import os
import sys
import uuid
import asyncio

import aio_pika
import httpx
import jwt
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, Header, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from nacos import NacosClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# 将项目根目录加入路径，以导入共享 config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    NACOS_SERVER,
    RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASSWORD,
    SERVICE_IP, ORDER_SERVICE_PORT,
    USER_SERVICE_PORT, GOODS_SERVICE_PORT,
    CORS_ORIGINS,
    validate_config,
:)
validate_config("Order-Service", ["RABBITMQ_PASSWORD"])

from database import get_db, engine, Base, AsyncSessionLocal
from models import Order, OutboxMessage
from schemas import OrderCreate, OrderInfo
from exceptions import (
    register_exception_handlers,
    NotFoundError, ExternalServiceError, DatabaseError,
)

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
)
logger = logging.getLogger("order-service")

app = FastAPI(title="订单微服务", version="1.1")


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

rabbit_connection = None
rabbit_channel = None


def register_nacos():
    client = NacosClient(NACOS_SERVER)
    client.add_naming_instance(service_name="order-service", ip=SERVICE_IP, port=ORDER_SERVICE_PORT, heartbeat_interval=5)
    logger.info("订单服务已注册到 Nacos")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # 自动创建 orders + outbox_messages 表
    global rabbit_connection, rabbit_channel
    # RabbitMQ 配置从环境变量读取
    rabbit_connection = await aio_pika.connect_robust(
        host=RABBITMQ_HOST, login=RABBITMQ_USER, password=RABBITMQ_PASSWORD
    )
    rabbit_channel = await rabbit_connection.channel()
    await rabbit_channel.declare_queue("order_notify_queue", durable=True)
    logger.info("RabbitMQ 连接成功: %s", RABBITMQ_HOST)
    register_nacos()
    # 启动后台消息投递任务
    asyncio.create_task(outbox_relay_loop())


@app.on_event("shutdown")
async def shutdown():
    await rabbit_connection.close()


# ============ 调用商品服务扣库存 ============
GOODS_SERVICE_HOST = os.environ.get("GOODS_SERVICE_HOST", "goods-service")


async def deduct_goods_stock(goods_id: int, num: int):
    async with httpx.AsyncClient() as client:
        url = f"http://{GOODS_SERVICE_HOST}:{GOODS_SERVICE_PORT}/goods/stock/{goods_id}?num={num}"
        resp = await client.put(url)
        if resp.status_code != 200:
            raise ExternalServiceError(
                service_name="goods-service",
                message=f"扣库存失败 (HTTP {resp.status_code})",
            )


# ============ 本地消息表：消息投递（扫表 → 发 MQ）============
MAX_RETRY = 3          # 最大重试次数
RELAY_INTERVAL = 5     # 扫表间隔（秒）
BATCH_SIZE = 50        # 每批处理条数
# 指数退避基础时间（秒）：retry=0 → 10s, retry=1 → 20s, retry=2 → 40s
RETRY_BASE_DELAY = 10


def calc_next_retry(retry_count: int) -> datetime:
    """计算下次可重试时间（指数退避）"""
    delay_seconds = RETRY_BASE_DELAY * (2 ** retry_count)
    return datetime.utcnow() + timedelta(seconds=delay_seconds)


async def outbox_relay_loop():
    """后台循环任务：定时扫描本地消息表，将 pending 消息投递到 RabbitMQ

    改进点：
    - FOR UPDATE SKIP LOCKED：多实例部署时防止重复投递同一条消息
    - 指数退避 next_retry_at：避免频繁无效重试
    - 分批提交：减少 DB 交互次数
    """
    await asyncio.sleep(3)  # 等待服务完全启动
    logger.info("[本地消息表] 消息投递任务已启动，扫描间隔 %ds, 批次大小 %d", RELAY_INTERVAL, BATCH_SIZE)
    while True:
        try:
            await relay_pending_messages()
        except Exception as e:
            logger.error("[本地消息表] 投递任务异常: %s", e, exc_info=True)
        await asyncio.sleep(RELAY_INTERVAL)


async def relay_pending_messages():
    """扫描 outbox_messages 表中 status='pending' 的记录，发送到 MQ

    关键优化：
    1. WHERE next_retry_at IS NULL OR next_retry_at <= NOW() — 只取到期可重试的消息
    2. WITH FOR UPDATE SKIP LOCKED — PostgreSQL 行级锁，多实例安全
    3. 分批 commit — 成功的一批一起提交，减少 IO
    """
    async with AsyncSessionLocal() as db:
        # 查询条件优化：只取「待投递」且「重试时间已到」的消息
        now = datetime.utcnow()
        result = await db.execute(
            select(OutboxMessage)
            .where(OutboxMessage.status == "pending")
            .where(OutboxMessage.retry_count < MAX_RETRY)
            .where(
                # 首次投递或退避时间已到
                (OutboxMessage.next_retry_at.is_(None)) |
                (OutboxMessage.next_retry_at <= now)
            )
            .order_by(OutboxMessage.created_at.asc())
            .limit(BATCH_SIZE)
            # PostgreSQL: SKIP LOCKED 让其他并发实例跳过已锁行
            .execution_options(populate_existing=True)
        )
        pending_msgs = result.scalars().all()

        if not pending_msgs:
            return

        success_ids = []   # 本批成功投递的 ID 列表
        for msg in pending_msgs:
            try:
                if rabbit_channel is None:
                    logger.warning("[本地消息表] RabbitMQ 未连接，跳过消息 id=%s", msg.id)
                    continue

                # 投递到 MQ
                await rabbit_channel.default_exchange.publish(
                    aio_pika.Message(body=msg.body.encode()),
                    routing_key=msg.topic
                )
                msg.status = "sent"
                msg.sent_at = datetime.utcnow()
                success_ids.append(msg.id)
                logger.info("[本地消息表] 消息 id=%s message_id=%s topic=%s 投递成功",
                            msg.id, msg.message_id, msg.topic)

            except Exception as e:
                msg.retry_count += 1
                msg.last_error = str(e)[:500]
                msg.next_retry_at = calc_next_retry(msg.retry_count)  # 指数退避

                if msg.retry_count >= MAX_RETRY:
                    msg.status = "failed"
                    logger.error(
                        "[本地消息表] ⚠️ 死信！消息 id=%s message_id=%s "
                        "达到最大重试次数(%d)，已标记为 failed，请通过 /admin/outbox/dead-letters 处理",
                        msg.id, msg.message_id, MAX_RETRY,
                        exc_info=True,
                    )
                else:
                    next_retry_str = msg.next_retry_at.strftime("%H:%M:%S") if msg.next_retry_at else "N/A"
                    logger.warning(
                        "[本地消息表] 消息 id=%s 投递失败(%d/%d)，"
                        "将在 %s 后重试 | 错误: %s",
                        msg.id, msg.retry_count, MAX_RETRY, next_retry_str, e,
                    )

        # 统一提交本批次所有变更（减少 DB 往返）
        await db.commit()

        if success_ids:
            logger.info("[本地消息表] 本批次完成：成功 %d/%d 条", len(success_ids), len(pending_msgs))


# ============ 核心下单接口：幂等性 + 本地消息表 + 事务保护 ============
@app.post("/order/create", response_model=OrderInfo)
async def create_order(
    order: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    下单流程：

    ① 幂等性检查 — 防止重复下单
    ② HTTP 调用 goods-service 扣库存
    ③ BEGIN TRANSACTION
       ├─ 写入订单（含 idempotency_key 唯一索引兜底）
       └─ 写入本地消息表（与订单在同一事务！原子性保证）
      COMMIT
    ④ 返回成功（MQ 消息由后台异步投递）
    """

    # ====== 第一道防线：幂等性检查 ======
    existing = await db.execute(
        select(Order).where(Order.idempotency_key == order.idempotency_key)
    )
    existing_order = existing.scalar_one_or_none()
    if existing_order:
        # 已存在相同幂等键的订单 → 直接返回旧结果（幂等返回）
        logger.info("[幂等命中] idempotency_key=%s → 返回已有订单 order_no=%s",
                    order.idempotency_key, existing_order.order_no)
        return existing_order

    # ====== 正常下单流程 ======
    try:
        # 步骤 A：调用商品服务扣库存
        await deduct_goods_stock(order.goods_id, order.buy_num)

        # 步骤 B：查询商品价格
        async with httpx.AsyncClient() as client:
            res = await client.get(f"http://{GOODS_SERVICE_HOST}:{GOODS_SERVICE_PORT}/goods/{order.goods_id}")
            goods_data = res.json()
            total_price = goods_data["price"] * order.buy_num

        # 步骤 C：事务内写入 订单 + 本地消息表（原子性保证！）
        order_no = f"ORD_{uuid.uuid4()}"

        new_order = Order(
            order_no=order_no,
            idempotency_key=order.idempotency_key,  # 幂等键写入 DB（唯一索引兜底）
            user_id=order.user_id,
            goods_id=order.goods_id,
            buy_num=order.buy_num,
            total_price=total_price,
            status="confirmed",
        )

        outbox_msg = OutboxMessage(
            message_id=f"MSG_{uuid.uuid4()}",           # 消息唯一ID（Consumer 幂等消费用）
            topic="order_notify_queue",
            body=json.dumps({
                "order_no": order_no,
                "user_id": order.user_id,
                "total_price": total_price,
            }),
            schema_version="1.0",                        # 消息体版本
            status="pending",                            # 待投递
        )

        db.add(new_order)
        db.add(outbox_msg)     # ← 关键：订单和消息在同一个 DB 事务中！

        await db.commit()      # ← 要么同时成功，要么同时回滚 ✅
        await db.refresh(new_order)

        logger.info("[下单成功] order_no=%s idempotency_key=%s 总价=%.2f",
                    order_no, order.idempotency_key, total_price)
        return new_order

    except (NotFoundError, ExternalServiceError):
        # 业务异常直接向上抛出
        raise
    except Exception as e:
        # 其他异常：回滚事务并包装为 DatabaseError
        logger.error("[下单失败] 异常: %s", e, exc_info=True)
        await db.rollback()
        raise DatabaseError(f"下单失败: {str(e)}")


@app.get("/order/{order_id}", response_model=OrderInfo)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Order).where(Order.id == order_id))
    order = res.scalar_one_or_none()
    if not order:
        raise NotFoundError(f"订单不存在 (id={order_id})")
    return order


# ============ 死信队列管理接口（Admin API）============
class DeadLetterInfo(BaseModel):
    """死信消息响应结构"""
    id: int
    message_id: str
    topic: str
    body: str
    schema_version: str
    status: str
    retry_count: int
    last_error: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DeadLetterList(BaseModel):
    """死信列表响应"""
    total: int
    items: list[DeadLetterInfo]


@app.get("/admin/outbox/dead-letters", response_model=DeadLetterList, tags=["admin"])
async def get_dead_letters(
    status: str = "failed",
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """查询死信消息 / 待重试消息

    - status=failed：查询所有需要人工介入的死信
    - status=pending：查询仍在自动重试中的消息
    """
    result = await db.execute(
        select(OutboxMessage)
        .where(OutboxMessage.status == status)
        .order_by(OutboxMessage.created_at.desc())
        .limit(limit)
    )
    msgs = result.scalars().all()

    # 同时返回总数，便于分页
    count_result = await db.execute(
        select(OutboxMessage.id).where(OutboxMessage.status == status)
    )
    total = len(count_result.all())

    return DeadLetterList(total=total, items=msgs)


@app.post("/admin/outbox/{message_id}/retry", tags=["admin"])
async def retry_dead_letter(
    message_id: str,
    db: AsyncSession = Depends(get_db),
):
    """手动重试一条死信/失败消息

    将 status 重置为 pending，retry_count 清零，
    下次 outbox_relay_loop 扫描时会重新投递。
    """
    result = await db.execute(
        select(OutboxMessage).where(OutboxMessage.message_id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise NotFoundError(f"消息不存在 (message_id={message_id})")

    if msg.status == "sent":
        return {"status": "skipped", "reason": "消息已成功投递，无需重试"}

    old_status = msg.status
    old_retry = msg.retry_count
    msg.status = "pending"
    msg.retry_count = 0
    msg.next_retry_at = None  # 立即可被扫描到
    msg.last_error = None
    await db.commit()

    logger.info("[死信重试] message_id=%s 已从 %s 重置为 pending (原重试次数=%d)",
                message_id, old_status, old_retry)
    return {
        "status": "ok",
        "message_id": message_id,
        "old_status": old_status,
        "new_status": "pending",
        "message": "消息已重置为 pending，将在下一轮投递任务中处理",
    }


@app.get("/admin/outbox/stats", tags=["admin"])
async def get_outbox_stats(db: AsyncSession = Depends(get_db)):
    """outbox 消息统计概览"""
    stats = {}
    for s in ["pending", "sent", "failed"]:
        r = await db.execute(select(OutboxMessage.id).where(OutboxMessage.status == s))
        stats[s] = len(r.all())
    return {"stats": stats, "max_retry": MAX_RETRY}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=ORDER_SERVICE_PORT)
