import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_db_url, DB_NAME_GOODS, validate_config
validate_config("Goods-Service", ["DB_PASSWORD"])

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = get_db_url(DB_NAME_GOODS)

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
