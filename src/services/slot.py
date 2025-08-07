from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Slot, Cafe, Booking, BookingStatus


class SlotService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_slot_by_id(self, slot_id: int) -> Optional[Slot]:
        """Получить слот по ID."""
        stmt = select(Slot).where(Slot.id == slot_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_available_slots_for_cafe(
        self, cafe_id: int, start_date: date, end_date: date
    ) -> List[Slot]:
        """Получить доступные слоты для кофейни в заданном диапазоне дат."""
        stmt = select(Slot).where(
            and_(
                Slot.cafe_id == cafe_id,
                Slot.start_time >= start_date,
                Slot.start_time < end_date.replace(hour=23, minute=59, second=59, microsecond=999999) # До конца дня
            )
        ).order_by(Slot.start_time)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_slot(
        self,
        cafe_id: int,
        start_time: datetime,
        end_time: datetime,
        required_baristas: int = 1
    ) -> Slot:
        """Создать новый слот."""
        slot = Slot(
            cafe_id=cafe_id,
            start_time=start_time,
            end_time=end_time,
            required_baristas=required_baristas,
        )
        self.session.add(slot)
        await self.session.commit()
        await self.session.refresh(slot)
        return slot

    async def get_booked_baristas_count(self, slot_id: int) -> int:
        """Получить количество бариста, забронировавших слот."""
        stmt = select(Booking).where(
            and_(
                Booking.slot_id == slot_id,
                Booking.status.in_([BookingStatus.BOOKED, BookingStatus.CONFIRMED_WORK]) # Только активные брони
            )
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def is_slot_available_for_booking(self, slot_id: int) -> bool:
        """Проверить, есть ли свободные места в слоте."""
        slot = await self.get_slot_by_id(slot_id)
        if not slot:
            return False
        booked_count = await self.get_booked_baristas_count(slot_id)
        return booked_count < slot.required_baristas
