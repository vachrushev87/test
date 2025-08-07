import os
from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс для управления конфигурацией приложения.
    Загружает переменные окружения из .env файла и валидирует их.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )

    TELEGRAM_BOT_TOKEN: str
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn

    ADMIN_IDS: list[int]
    MANAGER_IDS: list[int]

    @classmethod
    def get_admin_ids(cls) -> list[int]:
        """Парсит строку ADMIN_IDS в список целых чисел."""
        admin_ids_str = os.getenv("ADMIN_IDS")
        if admin_ids_str:
            return [int(uid.strip()) for uid in admin_ids_str.split(',') if uid.strip().isdigit()]
        return []

    @classmethod
    def get_manager_ids(cls) -> list[int]:
        """Парсит строку MANAGER_IDS в список целых чисел."""
        manager_ids_str = os.getenv("MANAGER_IDS")
        if manager_ids_str:
            return [int(uid.strip()) for uid in manager_ids_str.split(',') if uid.strip().isdigit()]
        return []

@lru_cache()
def get_settings() -> Settings:
    """
    Возвращает экземпляр настроек, кэшируя его для предотвращения повторной загрузки.
    """
    return Settings()
