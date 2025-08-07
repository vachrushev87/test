# models/user.py
from enum import Enum
from typing import List, Optional
from datetime import datetime

from sqlalchemy import Column, BigInteger, String, ForeignKey, UniqueConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from src.db.base import Base
from sqlalchemy import DateTime, Boolean 


class UserRole(str, Enum):
    """Роли пользователя."""
    ADMIN = "admin"
    MANAGER = "manager"
    BARISTA = "barista"
    PENDING = "pending" # Ожидающий подтверждения регистрации


class User(Base):
    """Модель пользователя."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True) 
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)

    # ИЗМЕНЕНИЯ ЗДЕСЬ: nullable=True
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False) # Добавьте это, если его нет
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Возможно, тоже отсутствует
    username: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True) # Может быть None
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)   # Может быть None
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)              # Может быть None

    first_name: Mapped[str] = mapped_column(String(50), nullable=True) # Рекомендую сделать nullable=True, т.к. может быть отсутствовать
    last_name: Mapped[str] = mapped_column(String(50), nullable=True) # Рекомендую сделать nullable=True

    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True)
    role: Mapped[UserRole] = mapped_column(
        PG_ENUM(UserRole, name="user_role", create_type=False), # <-- ИЗМЕНЕНО
        nullable=False,
        default=UserRole.PENDING # Можно установить дефолтное значение
    )

    cafe_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cafes.id"), index=True, nullable=True)
    cafe: Mapped["Cafe"] = relationship(back_populates="users", foreign_keys=[cafe_id])

    bookings: Mapped[List["Booking"]] = relationship(back_populates="barista")

    managed_cafes: Mapped[List["Cafe"]] = relationship(
        back_populates="manager",
        foreign_keys="[Cafe.manager_id]"
    )

    def __repr__(self):
        return f"<User(username={self.username or 'N/A'}, email={self.email or 'N/A'})>"