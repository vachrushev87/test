import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

from dotenv import load_dotenv


load_dotenv()


class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN')
    DATABASE_URL: str = os.getenv('DATABASE_URL')
    REDIS_URL: str = os.getenv('REDIS_URL')
    ADMIN_IDS: List[int] = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]
    MANAGER_IDS: List[int] = [int(id) for id in os.getenv('MANAGER_IDS', '').split(',') if id]


settings = Settings()
