# src/services/user.py
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from enum import Enum
from src.models import User, UserRole, Cafe


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        telegram_id: int,
        first_name: str,
        phone_number: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        last_name: Optional[str] = None,
        role: UserRole = UserRole.PENDING, # <--- Здесь приходит Enum объект UserRole.PENDING
        cafe_id: Optional[int] = None,
    ) -> User:
        """Создать нового пользователя."""
        print(f"DEBUG (UserService): Received role type: {type(role)}")
        print(f"DEBUG (UserService): Received role value: {role}")
        if isinstance(role, Enum):
            print(f"DEBUG (UserService): Received role .name: {role.name}")
            print(f"DEBUG (UserService): Received role .value: {role.value}") # Выводит 'pending'
        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            username=username,
            email=email,
            password=password,
            # ВЕРНУТЬ: Передаем целый Enum объект!
            role=role, # <--- ИЗМЕНЕНИЕ ЗДЕСЬ (возвращаем как было)
            cafe_id=cafe_id,
        )
        # Эти принты теперь должны вам сказать, что user.role - это UserRole.<член>, а не строка
        print(f"DEBUG (UserService): User object role type: {type(user.role)}")
        print(f"DEBUG (UserService): User object role value: {user.role}")
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_user_role(self, user: User, new_role: UserRole) -> User:
        """Обновить роль пользователя."""
        user.role = new_role
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_pending_users(self, manager_cafe_id: Optional[int] = None) -> list[User]:
        """Получить список пользователей в статусе PENDING, опционально по кофейне."""
        stmt = select(User).where(User.role == UserRole.PENDING)
        if manager_cafe_id:
            stmt = stmt.where(User.cafe_id == manager_cafe_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def assign_user_to_cafe(self, user: User, cafe: Cafe) -> User:
        """Привязать пользователя к кофейне."""
        user.cafe = cafe
        await self.session.commit()
        await self.session.refresh(user)
        return user
