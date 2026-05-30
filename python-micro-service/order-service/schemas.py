from pydantic import BaseModel


class OrderCreate(BaseModel):
    user_id: int
    goods_id: int
    buy_num: int


class OrderInfo(BaseModel):
    id: int
    order_no: str
    user_id: int
    goods_id: int
    buy_num: int
    total_price: float
    status: str

    class Config:
        from_attributes = True
