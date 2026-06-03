from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.core.config import config

engine = create_async_engine(
    config.database_url,
    echo=False)

async_session = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session