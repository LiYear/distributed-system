from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum as SAEnum, UniqueConstraint, Index
from datetime import datetime
from database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(64), unique=True, nullable=False, index=True)  # 订单号（唯一索引=天然幂等键）
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)  # 客户端幂等键
    user_id = Column(Integer, nullable=False)
    goods_id = Column(Integer, nullable=False)
    buy_num = Column(Integer, default=1)
    total_price = Column(Float)
    status = Column(String(20), default="pending")  # pending / confirmed / cancelled
    created_at = Column(DateTime, default=datetime.utcnow)


class OutboxMessage(Base):
    """本地消息表——保证 DB 写入与 MQ 发送的原子性（最终一致性）

    改进点：
    1. message_id — 消息唯一标识，MQ Consumer 可做幂等消费
    2. schema_version — 消息体版本，格式变更时兼容处理
    3. next_retry_at — 指数退避重试时间，避免频繁无效重试
    4. 联合唯一索引 — 防止同一条消息重复写入
    5. created_at 索引 — 加速轮询查询
    """
    __tablename__ = "outbox_messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(64), unique=True, nullable=False, index=True)   # 消息唯一ID（UUID），Consumer 幂等消费用
    topic = Column(String(100), nullable=False)          # MQ 路由键/队列名
    body = Column(Text, nullable=False)                   # 消息体 JSON
    schema_version = Column(String(10), default="1.0")   # 消息体 schema 版本
    status = Column(SAEnum("pending", "sent", "failed", name="outbox_status"), default="pending")
    retry_count = Column(Integer, default=0)              # 已重试次数
    next_retry_at = Column(DateTime, nullable=True)       # 下次可重试时间（指数退避）
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # 加索引加速扫表
    sent_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)       # 最后一次失败原因

    __table_args__ = (
        # 联合唯一索引：防止同一业务消息重复写入 outbox（如客户端重试下单时）
        UniqueConstraint("topic", "message_id", name="uq_outbox_topic_message_id"),
        Index("ix_outbox_pending_retry", "status", "next_retry_at"),  # 复合索引：快速查找待重试消息
    )
