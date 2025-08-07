from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User, UserRole
from src.keyboards.reply import get_admin_menu_keyboard, get_manager_menu_keyboard, get_barista_menu_keyboard, get_phone_request_keyboard
from src.fsm.states import RegistrationStates


router = Router()

@router.message(Command("start"))
async def cmd_start(
    message: Message,
    state: FSMContext,
    current_user: User, # Внедряется из UserRegisterMiddleware
    is_new_pending_user: bool = False # Флаг из UserRegisterMiddleware
) -> None:
    """
    Обработчик команды /start.
    Регистрирует нового пользователя или приветствует существующего.
    """
    if is_new_pending_user:
        # Пользователь новый и имеет статус PENDING, запускаем регистрационный флоу
        await message.answer(
            f"Привет, {message.from_user.full_name}! 👋\n"
            "Добро пожаловать в систему управления сменами.\n"
            "Для продолжения, пожалуйста, пройдите быструю регистрацию.\n\n"
            "Пожалуйста, введите ваше полное имя (например, 'Иван Иванов'):"
        )
        await state.set_state(RegistrationStates.waiting_for_name)
    else:
        # Пользователь уже зарегистрирован
        if current_user.role == UserRole.ADMIN:
            reply_keyboard = get_admin_menu_keyboard()
            await message.answer(f"С возвращением, Администратор {current_user.first_name}! Чем могу помочь?", reply_markup=reply_keyboard)
        elif current_user.role == UserRole.MANAGER:
            reply_keyboard = get_manager_menu_keyboard()
            await message.answer(f"С возвращением, Управляющий {current_user.first_name}! Чем могу помочь?", reply_markup=reply_keyboard)
        elif current_user.role == UserRole.BARISTA:
            reply_keyboard = get_barista_menu_keyboard()
            await message.answer(f"С возвращением, Бариста {current_user.first_name}! Чем могу помочь?", reply_markup=reply_keyboard)
        elif current_user.role == UserRole.PENDING:
            await message.answer(
                f"Мы вас приветствуем, {current_user.first_name}! Ваша заявка на регистрацию ожидает подтверждения управляющего.\n"
                "Мы сообщим вам, как только статус изменится."
            )
        else:
            await message.answer(f"Привет, {current_user.first_name}! Ваша роль не определена. Пожалуйста, дождитесь назначения.")
