from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Cafe


class CafeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cafe_by_id(self, cafe_id: int) -> Optional[Cafe]:
        """Получить кофейню по ID."""
        stmt = select(Cafe).where(Cafe.id == cafe_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_cafes(self) -> List[Cafe]:
        """Получить список всех кофеен."""
        stmt = select(Cafe).order_by(Cafe.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_cafe(
        self,
        name: str,
        address: str,
        phone_number: str,
        description: Optional[str] = None,
        opening_time=None, # datetime.time
        closing_time=None, # datetime.time
        manager_id: Optional[int] = None,
    ) -> Cafe:
        """Создать новую кофейню."""
        cafe = Cafe(
            name=name,
            address=address,
            phone_number=phone_number,
            description=description,
            opening_time=opening_time,
            closing_time=closing_time,
            manager_id=manager_id,
        )
        self.session.add(cafe)
        await self.session.commit()
        await self.session.refresh(cafe)
        return cafe

    async def update_cafe(
        self,
        cafe: Cafe,
        name: Optional[str] = None,
        address: Optional[str] = None,
        phone_number: Optional[str] = None,
        description: Optional[str] = None,
        opening_time = None,
        closing_time = None,
        manager_id: Optional[int] = None,
    ) -> Cafe:
        """Обновить информацию о кофейне."""
        if name:
            cafe.name = name
        if address:
            cafe.address = address
        if phone_number:
            cafe.phone_number = phone_number
        if description:
            cafe.description = description
        if opening_time:
            cafe.opening_time = opening_time
        if closing_time:
            cafe.closing_time = closing_time
        if manager_id:
            cafe.manager_id = manager_id # Привязка к пользователю по ID
        await self.session.commit()
        await self.session.refresh(cafe)
        return cafe
