from src.core.celery_app import celery_app
from src.core.utils import send_telegram_message
from src.core.config import settings


@celery_app.task
def send_daily_slot_reminders() -> None:
    """Отправляет ежедневные напоминания о предстоящих слотах."""
    message = 'Ежедневные напоминания пока не реализованы.'
    for manager_id in settings.MANAGER_IDS:
        asyncio.run(send_telegram_message(chat_id=str(manager_id), text=message)) # Оборачиваем асинхронный вызов


@celery_app.task
def check_no_show_baristas_and_notify() -> None:
    """Проверяет, нет ли бариста, которые не заняли свои места, и уведомляет об этом менеджера."""
    message = "Проверка на отсутствие бариста еще не реализована."
    for manager_id in settings.MANAGER_IDS:
        asyncio.run(send_telegram_message(chat_id=str(manager_id), text=message)) # Оборачиваем асинхронный вызов