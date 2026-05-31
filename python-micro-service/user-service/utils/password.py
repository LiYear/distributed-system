"""
密码工具模块：bcrypt 哈希 + 校验
"""

import hashlib
from passlib.context import CryptContext

# bcrypt 上下文（自动加盐，安全哈希）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """明文密码 → 哈希存储"""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码是否与哈希值匹配"""
    return pwd_context.verify(plain_password, hashed_password)
