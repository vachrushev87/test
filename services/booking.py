from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Booking, Slot, User, BookingStatus


class BookingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_booking_by_id(self, booking_id: int) -> Optional[Booking]:
        """Получить бронирование по ID."""
        stmt = select(Booking).where(Booking.id == booking_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_booking(self, barista_id: int, slot_id: int) -> Optional[Booking]:
        """Создать бронирование слота для бариста."""
        # Проверим, не забронировал ли уже этот бариста этот слот
        existing_booking = await self.get_booking_by_barista_and_slot(barista_id, slot_id)
        if existing_booking:
            return None # Уже существует

        booking = Booking(
            barista_id=barista_id,
            slot_id=slot_id,
            status=BookingStatus.BOOKED
        )
        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def get_booking_by_barista_and_slot(self, barista_id: int, slot_id: int) -> Optional[Booking]:
        """Получить бронирование по бариста и слоту."""
        stmt = select(Booking).where(
            and_(Booking.barista_id == barista_id, Booking.slot_id == slot_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_barista_bookings(self, barista_id: int) -> List[Booking]:
        """Получить все бронирования конкретного бариста."""
        stmt = select(Booking).where(Booking.barista_id == barista_id).order_by(Booking.slot_id) # Order for consistency
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_booking_status(self, booking: Booking, new_status: BookingStatus) -> Booking:
        """Обновить статус бронирования."""
        booking.status = new_status
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def cancel_booking(self, booking: Booking) -> Booking:
        """Отменить бронирование."""
        return await self.update_booking_status(booking, BookingStatus.CANCELED)

    async def get_upcoming_bookings_for_user(self, user_id: int) -> List[Booking]:
        """Получить предстоящие (в будущем) бронирования для пользователя."""
        stmt = select(Booking).join(Slot).where(
            and_(
                Booking.barista_id == user_id,
                Slot.start_time >= datetime.utcnow(),
                Booking.status.in_([BookingStatus.BOOKED, BookingStatus.CONFIRMED_WORK]) # Активные бронирования
            )
        ).order_by(Slot.start_time)
        result = await self.session.execute(stmt)
        return result.scalars().all()
