# src/utils/notifications.py
import logging

logger = logging.getLogger(__name__)

async def send_notification_to_manager(telegram_id: str, message: str, bot) -> None:
    """Отправляет менеджеру уведомление в Telegram."""
    try:
        # Проверяем, что telegram_id не None и является строкой
        if not telegram_id or not isinstance(telegram_id, str):
            logger.warning(f"Неверный идентификатор менеджера telegram для уведомления: {telegram_id}. Сообщение: {message}")
            return
        await bot.send_message(chat_id=telegram_id, text=f"УВЕДОМЛЕНИЕ ДЛЯ УПРАВЛЯЮЩЕГО:\n{message}", parse_mode='HTML')
        logger.info(f"Уведомление отправлено менеджеру {telegram_id}.")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление менеджеру{telegram_id}: {e}")

async def send_notification_to_user(telegram_id: str, message: str, bot) -> None:
    """Отправляет уведомление в Telegram обычному пользователю."""
    try:
        if not telegram_id or not isinstance(telegram_id, str):
            logger.warning(f"Неверный идентификатор пользователя telegram для уведомления: {telegram_id}. Сообщение:  {message}")
            return
        await bot.send_message(chat_id=telegram_id, text=f"УВЕДОМЛЕНИЕ:\n{message}", parse_mode='HTML')
        logger.info(f"Уведомление, отправленное пользователю {telegram_id}.")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {telegram_id}: {e}")
