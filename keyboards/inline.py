from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_confirm_registration_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения/отклонения регистрации бариста."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить ✅", callback_data=f"confirm_reg_{user_id}")
    builder.button(text="Отклонить ❌", callback_data=f"decline_reg_{user_id}")
    return builder.as_markup()

def get_slots_keyboard(slots: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора слотов."""
    builder = InlineKeyboardBuilder()
    for slot in slots:
        # Пример: "2023-11-15 10:00 - 12:00 (Кофейня А)"
        text = f"{slot.start_time.strftime('%Y-%m-%d %H:%M')} - {slot.end_time.strftime('%H:%M')} ({slot.cafe.name})"
        builder.button(text=text, callback_data=f"select_slot_{slot.id}")
    builder.adjust(1) # По одной кнопке на строку
    return builder.as_markup()

def get_confirm_booking_keyboard(slot_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения бронирования слота."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить бронирование ✅", callback_data=f"confirm_booking_{slot_id}")
    builder.button(text="Отмена ❌", callback_data="cancel_action")
    return builder.as_markup()

def get_confirm_user_going_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения выхода на смену бариста."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Я вышел на смену ✅", callback_data=f"user_going_{booking_id}")
    builder.button(text="Отмена ❌", callback_data="cancel_action")
    return builder.as_markup()

def get_manager_confirmation_keyboard(booking_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для управляющего для подтверждения выхода бариста на смену."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить выход ✅", callback_data=f"manager_confirm_going_{booking_id}")
    builder.button(text="Отклонить выход ❌", callback_data=f"manager_decline_going_{booking_id}")
    return builder.as_markup()

def get_manager_user_selection_keyboard(users: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора пользователя управляющим для подтверждения регистрации."""
    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(text=f"{user.first_name} ({user.telegram_id})", callback_data=f"select_pending_user_{user.id}")
    builder.adjust(1)
    return builder.as_markup()
