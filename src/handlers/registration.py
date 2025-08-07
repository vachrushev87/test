from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.fsm.states import RegistrationStates
from src.models import User, UserRole, Cafe
from src.services.user import UserService
from src.services.cafe import CafeService
from src.keyboards.reply import get_phone_request_keyboard
from src.keyboards.inline import InlineKeyboardBuilder # Re-use builder for cafe selection

router = Router()

@router.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    """Обработка введенного имени пользователя."""
    if not message.text or len(message.text) < 3:
        await message.answer("Пожалуйста, введите корректное полное имя.")
        return

    # Обновляем имя user'а в БД. Phone number будет обновлен позже.
    user_service = UserService(session)
    current_user.first_name = message.text.strip()
    await user_service.session.commit() # Сохраняем изменения имени
    await user_service.session.refresh(current_user)

    await state.update_data(first_name=message.text.strip())
    await message.answer(
        "Спасибо! Теперь, пожалуйста, поделитесь вашим номером телефона.",
        reply_markup=get_phone_request_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_phone)

@router.message(RegistrationStates.waiting_for_phone, F.contact)
async def process_phone(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    """Обработка номера телефона, полученного через кнопку."""
    phone_number = message.contact.phone_number
    await state.update_data(phone_number=phone_number)

    user_service = UserService(session)
    # Обновляем номер телефона пользователя
    # Если user был создан с заглушкой temp_*, то мы теперь ее заменяем.
    current_user.phone_number = phone_number
    await user_service.session.commit()
    await user_service.session.refresh(current_user)

    cafe_service = CafeService(session)
    all_cafes = await cafe_service.get_all_cafes()

    if not all_cafes:
        await message.answer("В настоящее время нет доступных кофеен для выбора. Пожалуйста, ожидайте подтверждения администратором.", reply_markup=None)
        await state.clear()
        # Возможно, здесь нужно уведомить админа, что новый юзер не смог выбрать кофейню
        return

    builder = InlineKeyboardBuilder()
    for cafe in all_cafes:
        builder.button(text=cafe.name, callback_data=f"select_cafe_{cafe.id}")
    builder.adjust(1)
    await message.answer("Отлично! Теперь выберите кофейню, в которой вы работаете (базовая):", reply_markup=builder.as_markup())
    await state.set_state(RegistrationStates.waiting_for_cafe_selection)


@router.message(RegistrationStates.waiting_for_phone)
async def process_phone_invalid(message: Message, state: FSMContext) -> None:
    """Обработка невалидного ввода номера телефона."""
    await message.answer(
        "Пожалуйста, используйте кнопку 'Поделиться номером телефона' для отправки вашего номера."
    )

@router.callback_query(RegistrationStates.waiting_for_cafe_selection, F.data.startswith("select_cafe_"))
async def process_cafe_selection(
    callback_query: CallbackQuery,
    state: FSMContext,
    current_user: User,
    session: AsyncSession
) -> None:
    """Обработка выбора кофейни."""
    cafe_id = int(callback_query.data.split("_")[2])

    cafe_service = CafeService(session)
    selected_cafe = await cafe_service.get_cafe_by_id(cafe_id)

    if not selected_cafe:
        await callback_query.message.answer("Выбранная кофейня не найдена. Попробуйте еще раз.")
        await callback_query.answer()
        return

    user_service = UserService(session)
    await user_service.assign_user_to_cafe(current_user, selected_cafe)

    await callback_query.message.answer(
        f"Ваша регистрация почти завершена! Вы выбрали кофейню: {selected_cafe.name}.\n"
        "Ваша заявка ожидает подтверждения управляющего этой кофейни.\n"
        f"Контакты кофейни: {selected_cafe.phone_number}" # Можно добавить контакты управляющего
    )
    await callback_query.answer("Кофейня выбрана!")
    await state.clear() # Завершаем FSM сценарий
    # TODO: Отправить уведомление управляющемуSelectedCafe, что новый пользователь ожидает подтверждения
