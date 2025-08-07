import logging


from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from src.services import cafe as cafe_service
from src.services import user as user_service
from src.config import get_settings
from src.models import User, UserRole
from aiogram.filters import Command

logger = logging.getLogger(__name__)
settings = get_settings()


router = Router()
# router.message.filter(F.text) # Этот фильтр будет применяться ко всем сообщениям.
                                # Возможно, вам нужно применять его к более специфичным обработчикам.
                                # Пока оставлю как есть, но это может быть нежелательным поведением.


class CafeCreationFSM(StatesGroup):
    waiting_for_name = State()
    waiting_for_address = State()
    waiting_for_work_hours = State()
    waiting_for_phone = State()
    waiting_for_manager = State()
    waiting_for_description = State()


class CafeEditionFSM(StatesGroup):
    waiting_for_cafe_selection = State()
    waiting_for_field_to_edit = State()
    waiting_for_new_value = State()


class UserCreationFSM(StatesGroup):
    waiting_for_telegram_id = State()
    waiting_for_first_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()
    waiting_for_cafe = State()
    waiting_for_password = State()


class UserEditionFSM(StatesGroup):
    waiting_for_user_selection = State()
    waiting_for_field_to_edit = State()
    waiting_for_new_value = State()


@router.message(Command("create_cafe")) # Использование Command фильтра
async def command_create_cafe(message: types.Message, state: FSMContext):
    """
    Запуск процесса создания кофейни.
    """
    await message.answer("Введите название кофейни:")
    await state.set_state(CafeCreationFSM.waiting_for_name)


@router.message(CafeCreationFSM.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    """
    Обработка названия кофейни.
    """
    await state.update_data(name=message.text)
    await message.answer("Введите адрес кофейни:")
    await state.set_state(CafeCreationFSM.waiting_for_address)


@router.message(CafeCreationFSM.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    """
    Обработка адреса кофейни.
    """
    await state.update_data(address=message.text)
    await message.answer("Введите часы работы кофейни:")
    await state.set_state(CafeCreationFSM.waiting_for_work_hours)


@router.message(CafeCreationFSM.waiting_for_work_hours)
async def process_work_hours(message: types.Message, state: FSMContext):
    """
    Обработка часов работы кофейни.
    """
    await state.update_data(work_hours=message.text)
    await message.answer("Введите телефон кофейни:")
    await state.set_state(CafeCreationFSM.waiting_for_phone)


@router.message(CafeCreationFSM.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка телефона кофейни.
    """
    await state.update_data(phone=message.text)

    # Get All available managers.
    managers = await user_service.get_users_by_role(session, UserRole.MANAGER)

    if not managers:
        await message.answer("Нет доступных менеджеров для выбора.")
        await state.clear()
        return

    keyboard = []
    for manager in managers:
        keyboard.append([types.InlineKeyboardButton(text=manager.first_name, callback_data=f"manager_{manager.id}")])
    keyboard.append([types.InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("Выберите управляющего кофейни:", reply_markup=reply_markup)
    await state.set_state(CafeCreationFSM.waiting_for_manager)  # Corrected

@router.callback_query(CafeCreationFSM.waiting_for_manager)
async def process_manager(query: types.CallbackQuery, state: FSMContext):
    """
    Обработка выбора управляющего кофейни.
    """
    if query.data == "cancel":
        await query.message.edit_text("Создание кофейни отменено.")
        await state.clear()
        return

    # ЭТИ СТРОКИ ДОЛЖНЫ БЫТЬ ВНУТРИ ФУНКЦИИ (ИСПРАВЛЕН ОТСТУП)
    manager_id = int(query.data.split("_")[1])
    await state.update_data(manager_id=manager_id)
    await query.message.edit_text("Введите описание кофейни:")
    await state.set_state(CafeCreationFSM.waiting_for_description)

    await query.answer()  # Ensure you answer the callback query

@router.message(CafeCreationFSM.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка описания кофейни и создание кофейни.
    """
    await state.update_data(description=message.text)
    data = await state.get_data()
    try:
        # ЭТИ СТРОКИ ДОЛЖНЫ БЫТЬ ВНУТРИ БЛОКА TRY (ИСПРАВЛЕН ОТСТУП)
        await cafe_service.create_cafe(session, data["name"], data["address"], data["work_hours"], data["phone"], data["manager_id"], data["description"])  # Corrected
        await session.commit()
        await message.answer("Кофейня успешно создана!")
    except Exception as e :
        logger.exception("Error creating cafe: %s", e)
        await message.answer("Произошла ошибка при создании кофейни.")
    finally:
        await state.clear()

@router.message(Command("edit_cafe")) # Использование Command фильтра
async def command_edit_cafe(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Запуск процесса редактирования кофейни.
    """
    cafes = await cafe_service.get_all_cafes(session)
    if not cafes:
        await message.answer("Нет доступных кофеен для редактирования.")
        await state.clear()
        return

    keyboard = []
    for cafe in cafes:
        keyboard.append([types.InlineKeyboardButton(text=cafe.name, callback_data=f"cafe_{cafe.id}")])
    keyboard.append([types.InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("Выберите кофейню для редактирования:", reply_markup=reply_markup)
    await state.set_state(CafeEditionFSM.waiting_for_cafe_selection)

@router.callback_query(CafeEditionFSM.waiting_for_cafe_selection)
async def process_cafe_selection_for_edit(query: types.CallbackQuery, state: FSMContext):
    """
    Обработка выбора кофейни для редактирования.
    """
    if query.data == "cancel":
        await query.message.edit_text("Редактирование кофейни отменено.")
        await state.clear()
        return

    cafe_id = int(query.data.split("_")[1])
    await state.update_data(cafe_id=cafe_id)

    keyboard = [
        [types.InlineKeyboardButton(text="Название", callback_data="name")],
        [types.InlineKeyboardButton(text="Адрес", callback_data="address")],
        [types.InlineKeyboardButton(text="Часы работы", callback_data="work_hours")],
        [types.InlineKeyboardButton(text="Телефон", callback_data="phone")],
        [types.InlineKeyboardButton(text="Управляющий", callback_data="manager")], # TODO: Возможно тут нужна обработка имени, а не ID
        [types.InlineKeyboardButton(text="Описание", callback_data="description")],
        [types.InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await query.message.edit_text("Выберите поле для редактирования:", reply_markup=reply_markup)
    await state.set_state(CafeEditionFSM.waiting_for_field_to_edit)

    await query.answer()  # Ensure you answer the callback query

@router.callback_query(CafeEditionFSM.waiting_for_field_to_edit)
async def process_field_selection(query: types.CallbackQuery, state: FSMContext):
    """
    Обработка выбора поля для редактирования.
    """
    if query.data == "cancel":
        await query.message.edit_text("Редактирование кофейни отменено.")
        await state.clear()
        return

    await state.update_data(field_to_edit=query.data)
    await query.message.edit_text(f"Введите новое значение для поля '{query.data}':")
    await state.set_state(CafeEditionFSM.waiting_for_new_value)

    await query.answer()  # Ensure you answer the callback query

@router.message(CafeEditionFSM.waiting_for_new_value)
async def process_new_value(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """
    Обработка нового значения для поля и сохранение изменений.
    """
    data = await state.get_data()
    cafe_id = data.get("cafe_id")
    field_to_edit = data.get("field_to_edit")
    new_value = message.text

    try:
        # Checking if the field being edited is manager
        if field_to_edit == 'manager':
            # Need to get the current cafe to find the old manager_id
            current_cafe = await cafe_service.get_cafe_by_id(session, cafe_id) # Предполагается, что есть get_cafe_by_id

            if not current_cafe:
                await message.answer("Кофейня не найдена. Обновление невозможно.")
                await state.clear()
                return

            old_manager_id = current_cafe.manager_id # Предполагается, что у cafe есть manager_id
            old_manager = await user_service.get_user(session, old_manager_id)

            new_manager_id = int(new_value)  # Assuming new_value is the manager ID
            new_manager = await user_service.get_user(session, new_manager_id)

            if old_manager and old_manager.telegram_id and old_manager.telegram_id != new_manager_id: # Отправляем только если менеджер был и он другой
                 try:
                    await bot.send_message(chat_id=old_manager.telegram_id, text=f"Вы больше не являетесь управляющим кофейни {current_cafe.name}.")
                 except Exception as err:
                    logger.warning(f"Could not send message to old manager {old_manager.telegram_id}: {err}")


            if new_manager and new_manager.telegram_id:
                try:
                    await bot.send_message(chat_id=new_manager.telegram_id, text=f"Вы назначены управляющим кофейни {current_cafe.name}.")
                except Exception as err:
                    logger.warning(f"Could not send message to new manager {new_manager.telegram_id}: {err}")


            await cafe_service.update_cafe(session, cafe_id, field_to_edit, new_manager_id) # Сохраняем ID, не новый_value
        else:
            await cafe_service.update_cafe(session, cafe_id, field_to_edit, new_value) # update other fields normally

        await session.commit()
        await message.answer("Информация о кофейне успешно обновлена!")
    except ValueError:
        await message.answer("Неверный формат для менеджера. Пожалуйста, введите числовой ID.")
    except Exception as e:
        logger.exception("Error updating cafe: %s", e)
        await message.answer("Произошла ошибка при обновлении информации о кофейне.")
    finally:
        await state.clear()

@router.message(Command("create_user")) # Использование Command фильтра
async def command_create_user(message: types.Message, state: FSMContext):
    """
    Запуск процесса создания пользователя.
    """
    await message.answer("Введите Telegram ID пользователя:")
    await state.set_state(UserCreationFSM.waiting_for_telegram_id)


@router.message(UserCreationFSM.waiting_for_telegram_id)
async def process_telegram_id(message: types.Message, state: FSMContext):
    """
    Обработка Telegram ID пользователя.
    """
    telegram_id = message.text
    try:
        telegram_id = int(telegram_id)
        await state.update_data(telegram_id=telegram_id)
        await message.answer("Введите имя пользователя:")
        await state.set_state(UserCreationFSM.waiting_for_first_name)
    except ValueError:
        await message.answer("Неверный формат Telegram ID. Пожалуйста, введите число.")


@router.message(UserCreationFSM.waiting_for_first_name)
async def process_first_name(message: types.Message, state: FSMContext):
    """
    Обработка имени пользователя.
    """
    await state.update_data(first_name=message.text)
    await message.answer("Введите телефон пользователя:")
    await state.set_state(UserCreationFSM.waiting_for_phone)


@router.message(UserCreationFSM.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка телефона пользователя.
    """
    await state.update_data(phone=message.text)
    # Here get information about user role to the Keyboard`


    keyboard = []
    keyboard.append([types.InlineKeyboardButton(text="Barista", callback_data="barista")])
    keyboard.append([types.InlineKeyboardButton(text="Manager", callback_data="manager")])
    keyboard.append([types.InlineKeyboardButton(text="Admin", callback_data="admin")])

    keyboard.append([types.InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("Выберите роль пользователя:", reply_markup=reply_markup)
    await state.set_state(UserCreationFSM.waiting_for_role)

@router.callback_query(UserCreationFSM.waiting_for_role)
async def process_role(query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработка выбора роли пользователя.
    """
    if query.data == "cancel":
        await query.message.edit_text("Создание пользователя отменено.")
        await state.clear()
        return

