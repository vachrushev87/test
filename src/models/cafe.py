from typing import List, Optional

from sqlalchemy import String, Time, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Cafe(Base):
    """Модель кофейни."""
    __tablename__ = "cafes"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Время работы: начало и конец дня
    opening_time: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    closing_time: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)

    # Управляющий кофейней (связь с таблицей users)
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    manager: Mapped["User"] = relationship(
        back_populates="managed_cafes",
        foreign_keys=[manager_id]
    )

    # Баристы, назначенные этой кофейне
    users: Mapped[List["User"]] = relationship(
        back_populates="cafe",
        foreign_keys="[User.cafe_id]"
    )
    slots: Mapped[List["Slot"]] = relationship(back_populates="cafe")

    def __repr__(self):
        return f"<Cafe(name={self.name}, address={self.address})>"
