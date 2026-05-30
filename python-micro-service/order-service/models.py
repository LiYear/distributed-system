from sqlalchemy import Column, Integer, String, Float
from database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(64), unique=True, nullable=False)  # 订单号
    user_id = Column(Integer, nullable=False)
    goods_id = Column(Integer, nullable=False)
    buy_num = Column(Integer, default=1)
    total_price = Column(Float)
    status = Column(String(20), default="pending")  # 订单状态
