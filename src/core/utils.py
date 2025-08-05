import telegram
from src.core.config import settings


async def send_telegram_message(chat_id: str, text: str) -> None:
    """
    Отправьте сообщение пользователю Telegram.

    Аргументы:
        chat_id: Идентификатор чата пользователя.
        текст: текст сообщения.
    """
    bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        print(f'Сообщение, отправленное н {chat_id}: {text}')
    except Exception as e:
        print(f'Не удалось отправить сообщение на {chat_id}: {e}')
