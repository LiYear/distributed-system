from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    user_id: int = Field(ge=1, examples=[1])
    goods_id: int = Field(ge=1, examples=[10])
    buy_num: int = Field(ge=1, le=999, examples=[2])
    idempotency_key: str = Field(min_length=8, max_length=128,
                                   description="幂等键：客户端生成的唯一标识，防止重复下单",
                                   examples=["order_20260531_u1001_g001"])


class OrderInfo(BaseModel):
    id: int
    order_no: str
    idempotency_key: str
    user_id: int
    goods_id: int
    buy_num: int
    total_price: float
    status: str

    class Config:
        from_attributes = True
