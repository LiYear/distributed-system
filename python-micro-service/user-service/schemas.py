from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_\u4e00-\u9fa5]+$", examples=["zhangsan"])
    password: str = Field(min_length=6, max_length=64, examples=["Abc123"])
    phone: str | None = Field(default=None, pattern=r"^1[3-9]\d{9}$", examples=["13800138000"])


class UserInfo(BaseModel):
    id: int
    username: str
    phone: str | None

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user_id: int
    username: str
    token: str
