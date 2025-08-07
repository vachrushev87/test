# src/redis_del/client.py
import redis.asyncio as aioredis # ИМЕННО ТАК!
# Или from redis.asyncio import Redis as AsyncRedisClient

from src.config import get_settings

settings = get_settings()

# async def get_redis_client() -> redis.Redis: # Эта аннотация типа может быть неточной
async def get_redis_client() -> aioredis.Redis:  # Изменил аннотацию для ясности
    """
    Возвращает асинхронный клиент Redis.
    """
    return aioredis.from_url(str(settings.REDIS_URL))
