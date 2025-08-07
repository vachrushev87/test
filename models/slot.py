from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Slot(Base):
    """Модель временного слота для смены."""
    __tablename__ = "slots"

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    required_baristas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    cafe_id: Mapped[int] = mapped_column(ForeignKey("cafes.id"), index=True, nullable=False)
    cafe: Mapped["Cafe"] = relationship(back_populates="slots")

    bookings: Mapped[List["Booking"]] = relationship(back_populates="slot")

    def __repr__(self):
        return f"<Slot(cafe_id={self.cafe_id}, start={self.start_time.strftime('%Y-%m-%d %H:%M')}, end={self.end_time.strftime('%H:%M')})>"
