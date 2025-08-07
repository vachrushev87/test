from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.config import get_settings

settings = get_settings()

DATABASE_URL = str(settings.DATABASE_URL) # Приводим DSN к строке

engine = create_async_engine(DATABASE_URL, echo=True, future=True, pool_size=10, max_overflow=20)
# echo=True делает логирование всех SQL-запросов, полезно для отладки

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # Важно для работы с объектами, полученными из сессии после ее закрытия
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения асинхронной сессии базы данных.
    Используется как контекстный менеджер.
    """
    async with AsyncSessionLocal() as session:
        yield session
