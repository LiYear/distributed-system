from pydantic import BaseModel, Field


class GoodsCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["iPhone 16 Pro"])
    price: float = Field(ge=0, le=999999.99, examples=[8999.00])
    stock: int = Field(ge=0, le=99999, examples=[100])


class GoodsInfo(BaseModel):
    id: int
    name: str
    price: float
    stock: int

    class Config:
        from_attributes = True
