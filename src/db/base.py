from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.orm import mapped_column, Mapped


@as_declarative()
class Base:
    """
    Базовый класс для всех декларативных моделей SQLAlchemy.
    Добавляет поля id, created_at, updated_at по умолчанию.
    """
    id: Mapped[int] = mapped_column(primary_key=True)

    __name__: str
    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s" # Название таблицы = имя класса в нижнем регистре + "s"

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
