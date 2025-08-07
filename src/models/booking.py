from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class BookingStatus(str, Enum):
    """Статусы бронирования слота."""
    BOOKED = "booked"                 # Забронирован
    CONFIRMED_WORK = "confirmed_work" # Подтвержден выход на работу (бариста)
    COMPLETED = "completed"           # Смена завершена и подтверждена управляющим
    CANCELED = "canceled"             # Отменена
    NO_SHOW = "no_show"               # Бариста не вышел на смену


class Booking(Base):
    """Модель бронирования слота бариста."""
    __tablename__ = "bookings"

    barista_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    barista: Mapped["User"] = relationship(back_populates="bookings")

    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), index=True, nullable=False)
    slot: Mapped["Slot"] = relationship(back_populates="bookings")

    status: Mapped[BookingStatus] = mapped_column(String(50), default=BookingStatus.BOOKED)

    __table_args__ = (
        UniqueConstraint("barista_id", "slot_id", name="uq_booking_barista_slot"),
    )

    def __repr__(self):
        return f"<Booking(barista_id={self.barista_id}, slot_id={self.slot_id}, status={self.status})>"
