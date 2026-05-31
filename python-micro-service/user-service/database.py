import os
import sys

# 将项目根目录加入路径，以导入共享 config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_db_url, DB_NAME_USER, validate_config
validate_config("User-Service", ["DB_PASSWORD"])

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = get_db_url(DB_NAME_USER)

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
