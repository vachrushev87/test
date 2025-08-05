from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import asynccontextmanager

from src.core.config import settings


DATABASE_URL = str(settings.DATABASE_URL)

# Асинхронный движок
async_engine = create_async_engine(DATABASE_URL, echo=True)

# Асинхронная фабрика сессий
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# Асинхронный контекстный менеджер для получения сессии
@asynccontextmanager
async def get_async_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback() # Откатываем транзакцию при ошибке
            raise
        finally:
            await session.close() # Закрываем сессию

# Для создания таблиц при первом запуске
async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)