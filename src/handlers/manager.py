import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters
)
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.core.database import get_async_session
from src.core.models import User, Cafe, Slot, Role, RegistrationStatus
from src.telegа.keyboards import main_admin_manager_keyboard
from src.telegа.messages import send_common_message

logger = logging.getLogger(__name__)

# --- Вспомогательные функции (могут быть переиспользованы админом, но с проверкой роли) ---
async def check_manager_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_telegram_id = update.effective_user.id
    async with get_async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == user_telegram_id)).scalar_one_or_none()
        if user and (user.role == Role.MANAGER or user.role == Role.ADMIN):
            # Если это администратор, но он хочет использовать менеджерскую функцию, ему это разрешено.
            # Если это менеджер, то он работает только со своей кофейней.
            if user.role == Role.MANAGER and not user.cafe_id:
                await send_common_message(update, "Вы назначены менеджером, но у вас нет привязанной кофейни. Обратитесь к администратору.", 
                                          reply_markup=main_admin_manager_keyboard())
                return False

            # Для менеджера сохраняем ID его кофейни в user_data, чтобы не запрашивать каждый раз
            if user.role == Role.MANAGER:
                context.user_data['manager_cafe_id'] = user.cafe_id
            return True

    logger.warning(f"Unauthorized access attempt by user {user_telegram_id} (not manager/admin).")
    await send_common_message(update, "У вас нет прав для выполнения этой команды.", reply_markup=main_admin_manager_keyboard())
    return False

# --- Функции мониторинга смен (доступны как менеджеру, так и админу) ---
async def monitor_shifts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_manager_role(update, context): # Проверяет роль, позволяет админам тоже
        return

    current_user_is_admin = str(update.effective_user.id) in context.bot_data.get('ADMIN_IDS', [])

    async with get_async_session() as session:
        if current_user_is_admin:
            # Администратор видит все кофейни
            cafes_query = select(Cafe).where(Cafe.is_active == True)
        else:
            # Менеджер видит только свою кофейню
            manager_cafe_id = context.user_data.get('manager_cafe_id')
            if not manager_cafe_id:
                await send_common_message(update, "Ваша кофейня не найдена.", reply_markup=main_admin_manager_keyboard())
                return
            cafes_query = select(Cafe).where(Cafe.id == manager_cafe_id)

        cafes = await session.execute(
            cafes_query.options(selectinload(Cafe.slots).selectinload(Slot.barista))
            .order_by(Cafe.name if current_user_is_admin else Cafe.id) # Сортировка только для админа
        )
        cafes = cafes.scalars().all()

        if not cafes:
            await send_common_message(update, "Кофеен для мониторинга не найдено." if current_user_is_admin else "Ваша кофейня не найдена или неактивна.", 
                                      reply_markup=main_admin_manager_keyboard())
            return

        report_messages = []
        for cafe in cafes:
            text = f"**Кофейня: {cafe.name}**\n"
            text += f"_{cafe.address}_\n\n"

            # Получаем слоты на ближайшие X дней (например, 7 дней)
            end_date = datetime.datetime.now() + datetime.timedelta(days=7)
            active_slots = [
                s for s in cafe.slots 
                if s.is_active and s.start_time > datetime.datetime.now() and s.start_time <= end_date
            ]
            active_slots.sort(key=lambda s: s.start_time)

            if not active_slots:
                text += "Нет активных будущих слотов на ближайшую неделю.\n\n"
            else:
                text += "Слоты на ближайшую неделю:\n"
                for slot in active_slots:
                    slot_status = "✅ Занят" if slot.barista else "⏳ Свободен"
                    barista_info = f" ({slot.barista.name})" if slot.barista else ""
                    text += (
                        f"  - `{slot.start_time.strftime('%d.%m %H:%M')}` - `{slot.end_time.strftime('%H:%M')}`: "
                        f"{slot_status}{barista_info}\n"
                    )
                text += "\n"
            report_messages.append(text)

        for msg in report_messages:
            await send_common_message(update, msg, parse_mode='Markdown', reply_markup=main_admin_manager_keyboard())

# --- Регистрация хендлеров для менеджера ---
def register_manager_handlers(application):
    application.add_handler(CommandHandler("monitor_shifts", monitor_shifts_command))
    application.add_handler(CallbackQueryHandler(monitor_shifts_command, pattern="^monitor_shifts_menu$")) # Для кнопок

    # ... Здесь будут другие хендлеры для управляющего (слоты, одобрение регистрации и т.д.)
    # Например:
    # application.add_handler(CommandHandler("slot_management", slot_management_menu))
    # application.add_handler(CallbackQueryHandler(slot_management_menu, pattern="^slot_management_menu$"))
