from pydantic import BaseModel


class GoodsCreate(BaseModel):
    name: str
    price: float
    stock: int


class GoodsInfo(BaseModel):
    id: int
    name: str
    price: float
    stock: int

    class Config:
        from_attributes = True
