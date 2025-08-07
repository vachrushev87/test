from typing import Callable, Dict, Any, Awaitable, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession
from enum import Enum

from src.models import User, UserRole
from src.services.user import UserService


class RoleMiddleware(BaseMiddleware):
    def __init__(self, required_roles: list[UserRole]):
        super().__init__()
        self.required_roles = required_roles

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        # Получение сессии из данных
        session: AsyncSession = data["session"]
        user_service = UserService(session)

        # Попытка получить текущего пользователя из данных
        user: Union[User, None] = data.get("current_user")

        # Если пользователь не найден, пытаемся получить по telegram_id
        if user is None and hasattr(event, 'from_user') and event.from_user:
            user = await user_service.get_user_by_telegram_id(event.from_user.id)
            if user:
                data["current_user"] = user

        # Проверка прав пользователя
        if not user or user.role not in self.required_roles:
            if isinstance(event, Message):
                await event.answer("У вас нет прав для выполнения этого действия.")
            elif isinstance(event, CallbackQuery):
                await event.answer("У вас нет прав для выполнения этого действия.")
            return None  # Прерываем цепочку

        return await handler(event, data)


class UserRegisterMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: list[int], manager_ids: list[int]):
        super().__init__()
        self.admin_ids = admin_ids
        self.manager_ids = manager_ids

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        # Получение сессии из данных
        session: AsyncSession = data["session"]
        user_service = UserService(session)

        # Определение telegram_id
        telegram_id = None
        if event.from_user:
            telegram_id = event.from_user.id
        else:
            # Обработка случаев, когда event.from_user может отсутствовать,
            # но в данном контексте для регистрации пользователя это критично.
            # Возможно, стоит продумать более детальную обработку или ограничить типы событий
            if isinstance(event, Message):
                await event.answer("Не удалось определить ваш Telegram ID. Пожалуйста, убедитесь, что вы отправляете сообщение или нажимаете на кнопку от своего имени.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Не удалось определить ваш Telegram ID. Пожалуйста, убедитесь, что вы отправляете сообщение или нажимаете на кнопку от своего имени.")
            else:
                 # Для других типов событий, где from_user может отсутствовать (например, ChatMemberUpdated для других пользователей)
                 # можно либо пропустить, либо логировать и затем прервать.
                 print(f"Warning: Attempted to register user from event type {type(event).__name__} without from_user.")
                 return await handler(event, data) # Возможно, просто пропустить, если это не критично для регистрации

            return None # Прерываем, если не удалось определить telegram_id и это критично


        user: Union[User, None] = await user_service.get_user_by_telegram_id(telegram_id)

        if not user:
            first_name = event.from_user.first_name or "Неизвестный"
            last_name = event.from_user.last_name or ""
            # Временный номер телефона, так как реальный номер получим позже
            temp_phone_number = f"temp_{telegram_id}"

            initial_role = UserRole.PENDING
            if telegram_id in self.admin_ids:
                initial_role = UserRole.ADMIN
            elif telegram_id in self.manager_ids:
                initial_role = UserRole.MANAGER
            
            print(f"DEBUG (Middleware): initial_role type: {type(initial_role)}")
            print(f"DEBUG (Middleware): initial_role value: {initial_role}")
            if isinstance(initial_role, Enum):
                print(f"DEBUG (Middleware): initial_role .name: {initial_role.name}")
                print(f"DEBUG (Middleware): initial_role .value: {initial_role.value}")

            user = await user_service.create_user(
                telegram_id=telegram_id,
                first_name=first_name,
                last_name=last_name,
                phone_number=temp_phone_number,
                role=initial_role
            )
            # Помечаем в данных, что это новый пользователь с pending-статусом,
            # чтобы хендлеры могли соответствующим образом отреагировать.
            if initial_role == UserRole.PENDING:
                data["is_new_pending_user"] = True

        data["current_user"] = user # Сохраняем найденного или созданного пользователя в данных

        # Передаем управление следующему в цепочке
        return await handler(event, data)
