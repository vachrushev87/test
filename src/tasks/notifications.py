from src.core.celery_app import celery_app
from src.core.utils import send_telegram_message
from src.core.config import settings


@celery_app.task
def notify_manager_about_new_cafe(cafe_id: int, cafe_name: str, cafe_address: str) -> None:
    """Отправляет менеджеру уведомление о появлении нового кафе."""
    for manager_id in settings.MANAGER_IDS:
        message = f'Создано новое кафе!\nID: {cafe_id}\nНазвание: {cafe_name}\nАдрес: {cafe_address}'
        asyncio.run(send_telegram_message(chat_id=str(manager_id), text=message)) # Оборачиваем асинхронный вызов


@celery_app.task
def notify_barista_about_registration_status(barista_telegram_id: str, barista_name: str) -> None:
    """Отправляет бариста уведомление об их статусе регистрации."""
    message = f"Друг {barista_name}, ваша регистрация подтверждена!!"
    asyncio.run(send_telegram_message(chat_id=barista_telegram_id, text=message)) # Оборачиваем асинхронный вызов
