import logging


from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.client.bot import Bot 
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from src.services import slot as slots_service
from src.services import user as user_service
from src.config import get_settings
from src.models import User
from aiogram.filters import Command


logger = logging.getLogger(__name__)
settings = get_settings()


router = Router()
router.message.filter(F.text)


class SlotCreationFSM(StatesGroup):
    waiting_for_cafe = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_date = State()
    confirm_creation = State()


class EmploymentConfirmationFSM(StatesGroup):
    waiting_for_barista = State()
    confirm_or_decline = State()


class MonitoringFSM(StatesGroup):
    waiting_for_date = State()


@router.message(Command("create_slot"))
async def command_create_slot(message: types.Message, state: FSMContext, session: AsyncSession, user:User):
    """
    Начало процесса создания слота.
    """
    # TODO: Get the cafes which current manager is in charge to.
    cafes = user.managed_coffees  # Assuming you have a relation set up in the User model
    if not cafes:
        await message.answer("Вы не управляете ни одной кофейней. Невозможно создать слот.")
        await state.clear()
        return

    # !!! ВНИМАНИЕ: Эти строки были с неправильным отступом.
    # Они должны быть частью функции command_create_slot.
    keyboard = []
    for cafe in cafes:
        keyboard.append([types.InlineKeyboardButton(text=cafe.name, callback_data=f"cafe_{cafe.id}")])
    keyboard.append([types.InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("Выберите кофейню для создания слота:", reply_markup=reply_markup)
    await state.set_state(SlotCreationFSM.waiting_for_cafe)

@router.callback_query(SlotCreationFSM.waiting_for_cafe)
async def process_cafe_selection(query: types.CallbackQuery, state: FSMContext):
    """
    Обработка выбора кофейни для создания слота.
    """
    if query.data == "cancel":
        await query.message.edit("Создание слота отменено.")
        await state.clear()
        return


    cafe_id = int(query.data.split("_")[1])
    await state.update_data(cafe_id=cafe_id)
    await query.message.edit_text("Введите дату для слота (YYYY-MM-DD):")
    await state.set_state(SlotCreationFSM.waiting_for_date)
    await query.answer()

@router.message(SlotCreationFSM.waiting_for_date)
async def process_date(message: types.Message, state: FSMContext):
    date_str = message.text
    try:
        from datetime import datetime
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
         # Save information to state.
        await state.update_data(selected_date=selected_date)
        await message.answer("Введите время начала слота в формате HH:MM:")
        await state.set_state(SlotCreationFSM.waiting_for_start_time)
    except ValueError:
        await message.answer("Неверный формат даты. Пожалуйста, используйте YYYY-MM-DD.")
        await state.set_state(SlotCreationFSM.waiting_for_date)


@router.message(SlotCreationFSM.waiting_for_start_time)
async def process_start_time(message: types.Message, state: FSMContext):
    """
    Обработка времени начала слота.
    """
    start_time_str = message.text
    try:
        from datetime import datetime
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        await state.update_data(start_time=start_time)
        await message.answer("Введите время окончания слота в формате HH:MM:")
        await state.set_state(SlotCreationFSM.waiting_for_end_time)
    except ValueError:
        await message.answer("Неверный формат времени. Пожалуйста, используйте HH:MM.")
        await state.set_state(SlotCreationFSM.waiting_for_start_time)


@router.message(SlotCreationFSM.waiting_for_end_time)
async def process_end_time(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка времени окончания слота и подтверждение создания.
    """
    end_time_str = message.text
    try:
        from datetime import datetime
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        await state.update_data(end_time=end_time)

        # ВСЕ ЭТИ СТРОКИ НУЖНО СДЕЛАТЬ ЧАСТЬЮ БЛОКА TRY
        # Get data from state
        data = await state.get_data()
        cafe_id = data.get("cafe_id")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        selected_date = data.get("selected_date")

        # Ask manager to confirm.
        keyboard = [
            [types.InlineKeyboardButton(text="Подтвердить", callback_data="confirm")],
            [types.InlineKeyboardButton(text="Отмена", callback_data="cancel")]
        ]
        reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

        # Show information to confirm
        await message.answer(f"Подтвердите создание слота:\n"
                            f"Дата: {selected_date}\nКофейня: {cafe_id}\n"
                            f"Начало: {start_time}\nОкончание: {end_time}",
                            reply_markup=reply_markup)
        await state.set_state(SlotCreationFSM.confirm_creation)

    except ValueError: # <-- Этот except должен быть связан с try
        await message.answer("Неверный формат времени. Пожалуйста, используйте HH:MM.")
        await state.set_state(SlotCreationFSM.waiting_for_end_time)

@router.callback_query(SlotCreationFSM.confirm_creation)
async def process_confirmation(query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Подтверждение или отмена создания слота.
    """
    if query.data == "confirm":
        data = await state.get_data()
        cafe_id = data.get("cafe_id")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        selected_date = data.get("selected_date")


    try:
        await slots_service.create_slot(session, cafe_id,selected_date, start_time, end_time)
        await session.commit()
        await query.message.edit_text("Слот успешно создан!")
    except Exception as e:
        logger.exception("Error creating slot: %s", e)
        await query.message.edit_text("Произошла ошибка при создании слота.")
    else:
        await query.message.edit_text("Создание слота отменено.")

    await state.clear()

    await query.answer()

@router.message(Command("employment_conf"))
async def command_employment_conf(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Запуск процесса подтверждения выхода бариста на смену.
    """
    # Получаем список бариста, ожидающих подтверждения
    try:
        baristas = await user_service.get_unconfirmed_baristas(session) # TODO write the the logic
        if not baristas:
            await message.answer("Нет бариста, ожидающих подтверждения.")
            await state.clear()
            return

        # ВСЕ ЭТИ СТРОКИ НУЖНО СДЕЛАТЬ ЧАСТЬЮ БЛОКА TRY
        # Формируем клавиатуру с бариста
        keyboard = []
        for barista in baristas:
            keyboard.append([types.InlineKeyboardButton(text=barista.first_name, callback_data=f"barista_{barista.id}")])
        keyboard.append([types.InlineKeyboardButton(text="Отмена", callback_data="cancel")])

        reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer("Выберите бариста для подтверждения выхода на смену:", reply_markup=reply_markup)
        await state.set_state(EmploymentConfirmationFSM.waiting_for_barista)

    except Exception as e: # <-- Теперь этот except находится на правильном уровне отступа
        logger.exception("Error fetching baristas: %s", e)
        await message.answer("Произошла ошибка при получении списка бариста.")
        await state.clear()

@router.callback_query(EmploymentConfirmationFSM.waiting_for_barista)
async def process_barista_selection(query: types.CallbackQuery, state: FSMContext):
    """
    Обработка выбора бариста и запрос подтверждения или отклонения.
    """
    # Этот блок if имеет правильный отступ относительно функции
    if query.data == "cancel":
        await query.message.edit_text("Подтверждение отменено.")
        await state.clear()
        await query.answer() # Обязательно отвечать на callback_query, даже если отменено
        return

    # Все эти строки должны быть на том же уровне отступа, что и 'if',
    # то есть они являются частью основной логики функции, если условие 'if' не сработало.
    barista_id = int(query.data.split("_")[1])
    await state.update_data(barista_id=barista_id)

    # Формируем клавиатуру для подтверждения или отклонения
    keyboard = [
        [types.InlineKeyboardButton(text="Подтвердить", callback_data="confirm")],
        [types.InlineKeyboardButton(text="Отклонить", callback_data="decline")],
        [types.InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await query.message.edit_text("Подтвердить или отклонить выход бариста на смену?", reply_markup=reply_markup)
    await state.set_state(EmploymentConfirmationFSM.confirm_or_decline)  # Corrected state

    await query.answer()  # Ensure answer is awaited

@router.callback_query(EmploymentConfirmationFSM.confirm_or_decline)
async def process_confirmation_or_decline(query: types.CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """
    Обработка подтверждения или отклонения выхода бариста на смену.
    """
    if query.data == "confirm":
        data = await state.get_data()
        barista_id = data.get("barista_id")
        try:
            # Update barista.
            await user_service.confirm_barista_employment(session, barista_id)
            await session.commit()

            await bot.send_message(chat_id=settings.get_admin_ids()[0], text=f"Бариста (id={barista_id}) подтвердил выход на смену.")

            # Send confirmation message to manager
            await query.message.edit_text("Вы подтвердили выход бариста на смену.")

            # Send notification to barista (assuming you have their Telegram ID stored)
            user = await user_service.get_user(session, barista_id) # Предполагается, что get_user_by_id не было переименовано
            if user and user.telegram_id:
                await bot.send_message(chat_id=user.telegram_id, text="Ваш выход на смену подтвержден менеджером.")
        except Exception as e:
            await session.rollback() # Откатываем транзакцию в случае ошибки
            logger.exception("Error confirming barista: %s", e)
            await query.message.edit_text("Произошла ошибка при подтверждении выхода бариста.")
        finally:
            await state.clear()
            await query.answer() # Ответ на callback_query после обработки

    elif query.data == "decline": # <--- Весь этот блок должен быть правильно выровнен
        data = await state.get_data()
        barista_id = data.get("barista_id") # Эта строка теперь с правильным отступом
        try:
            #Update barista.
            await user_service.decline_barista_employment(session, barista_id)
            await session.commit()

            #Send notification to manager
            await query.message.edit_text("Вы отклонили выход бариста на смену.")

            # Send notification to barista (assuming you have their Telegram ID stored)
            user = await user_service.get_user(session, barista_id) # Предполагается, что get_user_by_id не было переименовано
            if user and user.telegram_id:
                await bot.send_message(chat_id=user.telegram_id, text="Ваш выход на смену отклонен менеджером.")
        except Exception as e:
            await session.rollback() # Откатываем транзакцию в случае ошибки
            logger.exception("Error declining barista: %s", e)
            await query.message.edit_text("Произошла ошибка при отклонении выхода бариста.")
        finally:
            await state.clear()
            await query.answer() # Ответ на callback_query после обработки

    else: # <--- Этот else теперь правильно выровнен по отношению к if/elif
        await query.message.edit_text("Действие отменено.")
        await state.clear()
        await query.answer() # Ответ на callback_query после обработки

    # Убедитесь, что await query.answer() вызывается только один раз и в каждом возможном пути исполнения.
    # Я переместил его в body каждого if/elif/else блока. Поэтому эту строчку можно удалить:
    # await query.answer() # Эту строку можно удалить, если она уже в каждом блоке.


@router.message(Command("monitoring"))
async def command_monitoring(message: types.Message, state: FSMContext):
        """
        Запуск процесса мониторинга загруженности смен.
        """
        await message.answer("Введите дату для мониторинга загруженности (YYYY-MM-DD):")
        await state.set_state(MonitoringFSM.waiting_for_date)


@router.message(MonitoringFSM.waiting_for_date)
async def process_monitoring_date(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработка введенной даты и отображение информации о загруженности смен.
    """
    date_str = message.text
    try:
        from datetime import datetime
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()


        # call service `get_slots_status_by_date``
        slots_status = await slots_service.get_slots_status_by_date(session, selected_date)

        # Format answer.
        response = f"Статус слотов на {selected_date}:\n"
        for slot_info in slots_status:
            response += f"{slot_info.start_time} - {slot_info.end_time}: {slot_info.status}\n"

        await message.answer(response)

    except ValueError:
        await message.answer("Неверный формат даты. Пожалуйста, используйте YYYY-MM-DD.")
        await state.set_state(MonitoringFSM.waiting_for_date)
    except Exception as e:
        logger.exception("Error during monitoring: %s", e)
        await message.answer("Произошла ошибка при получении информации о загруженности смен.")
    finally:
        await state.clear()