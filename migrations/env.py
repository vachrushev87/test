import os
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context
from dotenv import load_dotenv

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
# Обязательно загружаем .env файл, чтобы Alembic мог получить DATABASE_URL
load_dotenv()

# --- ИМПОРТ ВАШИХ МОДЕЛЕЙ И НАСТРОЕК ---
# !!! ВАЖНО: Адаптируйте эти импорты под СВОЮ СТРУКТУРУ ПРОЕКТА !!!
try:
    # Пример: если Base определен в src.db.base
    from src.db.base import Base  # Убедитесь, что это правильный путь к вашему Base

    # Пример: если get_settings определена в src.config
    from src.config import get_settings # Убедитесь, что это правильный путь к вашей функции настроек

    # Метаданные ваших моделей, необходимые для autogenerate
    target_metadata = Base.metadata
    print("DEBUG: target_metadata set from src.db.base")

except ImportError as e:
    print(f"ERROR: Could not import necessary modules for Alembic: {e}")
    print("Please ensure 'src.db.base' (for Base) and 'src.config' (for get_settings) are correctly defined and accessible.")
    print("Autogenerate will not work without target_metadata. Exiting.")
    exit(1) # Выходим, так как без метаданных autogenerate не имеет смысла

# --- КОНФИГУРАЦИЯ ALEMBIC ---
config = context.config

# Интерпретация файла конфигурации для логирования Python.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_offline() -> None:
    """
    Выполняет миграции в 'оффлайн' режиме.

    В этом режиме Alembic не подключается к базе данных.
    Он просто генерирует SQL-скрипты на основе URL,
    указанного в alembic.ini, или переданного напрямую.
    Используется для генерации SQL-файлов для ручного применения.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    """
    Вспомогательная функция для выполнения миграций в синхронном контексте.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True, # Важно для autogenerate, чтобы Alembic корректно сравнивал типы колонок
        # Если вы используете psycopg2/asyncpg вместе с SQLAlchemy 2.0+ и async,
        # убедитесь, что ваш асинхронный адаптер правильно настроен.
        # Для asyncpg с SQLAlchemy 2.0+ обычно достаточно 'create_async_engine'.
        # dialect_opts={"asyncpg": True} # <--- Эта опция не всегда нужна здесь, если create_async_engine используется
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """
    Выполняет миграции в 'онлайн' режиме, используя асинхронный движок.
    """
    print("DEBUG: Entering run_migrations_online()")

    # Получаем URL базы данных из настроек вашего проекта
    # Pydantic BaseSettings обычно возвращает URL в виде pydantic.networks.PostgresDsn
    # или str. Преобразуем его в str, если он не является строкой.
    # ВАЖНО: Убедитесь, что ваш DATABASE_URL в .env или других источниках НЕ ДВАЖДЫ КОДИРОВАН!
    # Pydantic обычно сам кодирует пароли.
    try:
        settings = get_settings()
        db_url = str(settings.DATABASE_URL)
        print(f"DEBUG: Using DATABASE_URL from settings: {db_url}")
    except Exception as e:
        print(f"ERROR: Could not retrieve DATABASE_URL from settings: {e}")
        print("Please ensure get_settings() and .DATABASE_URL are correctly configured.")
        exit(1)


    # Создаем асинхронный движок SQLAlchemy
    # Используем create_async_engine для явного указания асинхронности
    connectable = create_async_engine(
        db_url,
        poolclass=pool.NullPool, # Для миграций обычно не нужен пул соединений
        future=True, # Рекомендуется для SQLAlchemy 2.0+
    )

    async with connectable.connect() as connection:
        # Выполняем синхронную часть миграций в асинхронном контексте
        await connection.run_sync(do_run_migrations)

    # Убедитесь, что движок корректно закрывается после миграции
    await connectable.dispose()
    print("DEBUG: Disposed of connectable.")


# --- ГЛАВНАЯ ЛОГИКА ALEMBIC: ВЫБИРАЕМ РЕЖИМ РАБОТЫ ---
if context.is_offline_mode():
    print("DEBUG: Running migrations in offline mode.")
    run_migrations_offline()
else:
    print("DEBUG: Running migrations in online mode.")
    # Запускаем асинхронные миграции в синхронном окружении Alembic
    asyncio.run(run_migrations_online())
