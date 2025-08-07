from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_barista_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="/slots")
    builder.button(text="/my_slots")
    builder.button(text="/going")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

def get_manager_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="/user_conf")
    builder.button(text="/creating_shifts")
    builder.button(text="/edit_shifts")
    builder.button(text="/change_booking")
    builder.button(text="/employment_conf")
    builder.button(text="/monitoring")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="/create_cafe")
    builder.button(text="/edit_cafe")
    builder.button(text="/create_user")
    builder.button(text="/edit_user")
    # Admin also has manager commands
    builder.button(text="/user_conf")
    builder.button(text="/creating_shifts")
    builder.button(text="/edit_shifts")
    builder.button(text="/change_booking")
    builder.button(text="/employment_conf")
    builder.button(text="/monitoring")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_phone_request_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для запроса номера телефона."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="Поделиться номером телефона", request_contact=True)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
