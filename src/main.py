import os
import sys
import logging
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler

# Вот данные штиуки у Вас и без них должно работать у меня на ПК потерял путь по этому дописал костыли
# Получаем абсолютный путь к текущему файлу (main.py). 
current_dir = os.path.dirname(os.path.abspath(__file__))
# Поднимаемся на один уровень вверх, чтобы получить путь к корневой директории проекта
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# Добавляем корневую директорию в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.database import init_db, get_async_session
from src.handlers.admin import register_admin_handlers
from src.handlers.manager import register_manager_handlers
from src.core.models import User, Role
from src.telegа.keyboards import main_admin_manager_keyboard
from sqlalchemy import select

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Временная заглушка для клавиатуры бариста, пока не будет реализована
def main_barista_keyboard() -> ReplyKeyboardMarkup:
    """Временная заглушка для основной клавиатуры бариста."""
    keyboard = [
        ["🗓 Мои смены", "✨ Свободные слоты"],
        ["❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


async def start_command(update: Update, context):
    if not update.message:
        return

    user = update.effective_user
    user_telegram_id = str(user.id)

    async with get_async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        db_user = result.scalar_one_or_none()

        if db_user:
            if db_user.is_active:
                if db_user.role == Role.ADMIN:
                    await update.message.reply_text("👋 Приветствую, Администратор! Что вы хотите сделать?", reply_markup=main_admin_manager_keyboard())
                elif db_user.role == Role.MANAGER:
                    await update.message.reply_text("👋 Привет, Управляющий! Как дела в кофейне?", reply_markup=main_admin_manager_keyboard())
                elif db_user.role == Role.BARISTA:
                    await update.message.reply_text("👋 Привет, Бариста! Желаешь забронировать смену?", reply_markup=main_barista_keyboard())
                else:
                    await update.message.reply_text("Ваша роль не определена. Обратитесь к администратору.")
            else:
                await update.message.reply_text("Ваш аккаунт неактивен. Обратитесь к администратору.")
        else:
            await update.message.reply_text(
                "Добро пожаловать в систему Skuratov Coffee! \n"
                "Вы новый пользователь. Пожалуйста, введите ваше имя для регистрации. \n"
                "Пример: `Иванов Иван Иванович`",
                parse_mode='Markdown'
            )
            # Здесь можно начать ConversationHandler для регистрации новых пользователей (для бариста)

async def post_init(application: Application):
    """Выполняется после инициализации бота и **внутри** асинхронного цикла обработки событий."""
    # Инициализация базы данных должна быть здесь
    await init_db()
    logger.info("Database initialized.")

    bot_info = await application.bot.get_me()
    logger.info(f"Bot @{bot_info.username} started successfully!")

    admin_ids_str = os.getenv("ADMIN_IDS", "")
    try:
        application.bot_data['ADMIN_IDS'] = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
    except ValueError:
        logger.error(f"Недопустимые идентификаторы АДМИНИСТРАТОРА, найденные в переменных окружения: {admin_ids_str}. Убедитесь, что это целые числа, разделенные запятыми.")
        application.bot_data['ADMIN_IDS'] = []

    logger.info(f"Admin IDs loaded: {application.bot_data['ADMIN_IDS']}")

def main():
    """Основная функция для запуска бота."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        raise ValueError("TELEGRAM_BOT_TOKEN is required.")

    application = Application.builder().token(token).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start_command))
    register_admin_handlers(application)
    register_manager_handlers(application)
    logger.info("Бот проводит опрос на предмет обновлений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
