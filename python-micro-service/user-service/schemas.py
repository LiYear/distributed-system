from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    phone: str | None = None


class UserInfo(BaseModel):
    id: int
    username: str
    phone: str | None

    class Config:
        from_attributes = True
