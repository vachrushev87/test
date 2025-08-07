import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable, Union

from aiogram import Bot, Dispatcher, BaseMiddleware, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
# from redis.asyncio import Redis

from handlers import manager_handlers
from src.config import get_settings
from src.db.session import AsyncSessionLocal
from src.redis_del.client import get_redis_client
from aiogram.types import Message, TelegramObject 

# Импортируем все наши роутеры
# from src.handlers import start, registration, barista_slots, admin_handlers, manager_handlers, common
from src.handlers import start, registration, common, barista_slots, admin_handlers
from src.middlewares.role_check import UserRegisterMiddleware, RoleMiddleware
from src.models import UserRole

logger = logging.getLogger(__name__)
# redis_client = Redis(host='localhost', port=6379, db=0)

# --- ИСПРАВЛЕННЫЙ Middleware для инъекции сессии ---
class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: Callable[[], AsyncSession]):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session: # Открываем сессию
            data["session"] = session

            try:
                # Теперь вызываем следующий handler в цепочке, передавая ему event и data
                result = await handler(event, data)
                await session.commit()
            except Exception as e:
                print(f"Ошибка в обработчике: {e}")
                await session.rollback()
                raise
            return result

async def main() -> None:
    settings = get_settings()

    # Инициализация бота
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    # Инициализация Redis для FSM
    redis_client = await get_redis_client()
    # storage = MemoryStorage(redis=redis_client)
    storage = RedisStorage(redis=redis_client)

    # Инициализация диспетчера
    dp = Dispatcher(storage=storage)

    # Регистрация Middlewares (ОБЩИЕ для ВСЕХ сообщений и коллбэков)
    # Middleware для управления сессиями БД
    dp.message.outer_middleware(DBSessionMiddleware(AsyncSessionLocal))
    dp.callback_query.outer_middleware(DBSessionMiddleware(AsyncSessionLocal))

    # Middleware для регистрации пользователей и внедрения объекта User в data
    dp.message.middleware(UserRegisterMiddleware(
        admin_ids=settings.get_admin_ids(),
        manager_ids=settings.get_manager_ids()
    ))
    dp.callback_query.middleware(UserRegisterMiddleware(
        admin_ids=settings.get_admin_ids(),
        manager_ids=settings.get_manager_ids()
    ))

    # Регистрация роутеров. Порядок важен!
    # Общие хендлеры, которые должны быть доступны всем без проверки роли до регистрации
    dp.include_router(common.router)

    # Хендлеры для регистрации и старта (без проверки ролей)
    dp.include_router(registration.router)
    dp.include_router(start.router)

    # BARISTA handlers
    barista_base_router = Router()
    barista_base_router.message.middleware(RoleMiddleware(required_roles=[UserRole.BARISTA]))
    barista_base_router.callback_query.middleware(RoleMiddleware(required_roles=[UserRole.BARISTA]))
    barista_base_router.include_router(barista_slots.router)
    dp.include_router(barista_base_router)

    # MANAGER handlers
    manager_base_router = Router()
    manager_base_router.message.middleware(RoleMiddleware(required_roles=[UserRole.MANAGER, UserRole.ADMIN]))
    manager_base_router.callback_query.middleware(RoleMiddleware(required_roles=[UserRole.MANAGER, UserRole.ADMIN]))
    manager_base_router.include_router(manager_handlers.router)
    dp.include_router(manager_base_router)

    # ADMIN handlers
    admin_base_router = Router()
    admin_base_router.message.middleware(RoleMiddleware(required_roles=[UserRole.ADMIN]))
    admin_base_router.callback_query.middleware(RoleMiddleware(required_roles=[UserRole.ADMIN]))
    admin_base_router.include_router(admin_handlers.router)
    dp.include_router(admin_base_router)

    # Запуск бота
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    asyncio.run(main())
