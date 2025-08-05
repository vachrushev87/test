from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup
from telegram.ext import ContextTypes # Добавляем импорт ContextTypes
from telegram.constants import ParseMode
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def send_common_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode: ParseMode = ParseMode.HTML) -> None:
    """
    Универсальная функция для отправки сообщений.
    Автоматически определяет, нужно ли редактировать существующее сообщение (для Inline-клавиатур)
    или отправлять новое (для Reply-клавиатур или при отсутствии CallbackQuery).
    Добавляет обработку ошибок и очистку чата при смене типа клавиатуры.
    """

    bot_instance = context.bot

    if not bot_instance:
        logger.error(f"send_common_message: Не удалось получить экземпляр бота из context.bot. Это ОЧЕНЬ странно. Для User ID: {update.effective_user.id if update.effective_user else 'N/A'}")
        return # Выходим, так как не можем отправлять сообщения

    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if isinstance(reply_markup, InlineKeyboardMarkup):
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception as e:
                logger.warning(f"send_common_message: Failed to edit_message_text with InlineKeyboardMarkup (from user {query.from_user.id}). Error: {e}. Attempting to send new message.")
                try:
                    await bot_instance.send_message(
                        chat_id=query.from_user.id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
                except Exception as send_e:
                    logger.error(f"send_common_message: CRITICAL FAILED to send new message after edit failure to user {query.from_user.id}. Error: {send_e}")
        else:
            if query.message:
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.info(f"send_common_message: Could not delete old message (id: {query.message.message_id}) from user {query.from_user.id}. Error: {e}")

            try:
                await bot_instance.send_message(
                    chat_id=query.from_user.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            except Exception as e:
                logger.error(f"send_common_message: FAILED to send new message with Reply/No markup to user {query.from_user.id}. Error: {e}")

    elif update.message:
        try:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"send_common_message: FAILED to reply to message from user {update.message.from_user.id}. Error: {e}")
    else:
        logger.warning(f"send_common_message: Unhandled Update type in send_common_message: {type(update).__name__}. Content: {update}")


async def notify_user(bot, user_id: int, message: str):
    """Отправляет уведомление конкретному пользователю."""
    try:
        await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Failed to send message to user {user_id}: {e}")

# --- Сообщения для Администратора ---
def get_admin_main_menu_text():
    return "<b>Главное меню администратора</b>\n\n"\
           "Здесь вы можете управлять кофейнями, пользователями и другими аспектами системы."

def get_cafe_management_text():
    return "<b>Управление кофейнями</b>\n\n"\
           "Добавляйте, редактируйте или удаляйте кофейни."
