import logging
from datetime import datetime # Импортируем явно datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.filters import Command

from src.models import User
from src.services import slot as slots_service


logger = logging.getLogger(__name__) # Лучше использовать __name__ вместо name


router = Router()
router.message.filter(F.text) # Это фильтр для всех сообщений, идущих в этот роутер,
                             # что может быть не совсем то, что вы хотите.
                             # Возможно, вам нужен более специфичный фильтр
                             # или вообще его здесь не нужно, если команды обрабатываются.
                             # Если этот роутер только для текстовых команд и сообщений, то ок.


class BaristaSlotFSM(StatesGroup):
    waiting_for_date = State()
    waiting_for_slot_choice = State()


@router.message(Command("my_slots"))
async def command_my_slots(message: types.Message, state: FSMContext, session: AsyncSession, user: User):
    """
    Показать бариста его забронированные слоты.
    """
    try:
        slots = await slots_service.get_user_slots(session, user.id)
        if not slots:
             await message.answer("У вас нет забробированных слотов.")
        else:
            response = "Ваши забробированные слоты:\n"
            for slot in slots:
                # Убедитесь, что slot.cafe действительно объект и у него есть name
                # и что start_time/end_time в удобном формате (например, datetime.time)
                slot_info = f"- {slot.start_time} - {slot.end_time}, Кофейня: {slot.cafe.name}\n"
                response += slot_info
            await message.answer(response)

    except Exception as e: # Этот except должен быть внутри функции
        logger.exception("Error fetching user slots: %s", e)
        await message.answer("Произошла ошибка при получении ваших слотов.")
    finally: # Этот finally тоже должен быть внутри функции
        await state.clear()


@router.message(Command("available_slots"))
async def command_available_slots(message: types.Message, state: FSMContext):
    """
    Запуск процесса просмотра доступных слотов для бронирования.
    """
    await state.set_state(BaristaSlotFSM.waiting_for_date)
    await message.answer("Пожалуйста, введите дату, для которой вы хотите посмотреть доступные слоты (YYYY-MM-DD):")


@router.message(BaristaSlotFSM.waiting_for_date)
async def process_date(message: types.Message, state: FSMContext, session: AsyncSession, user: User):
    """
    Обработка введенной даты и отображение доступных слотов.
    """
    date_str = message.text
    try:
        # Валидация формата даты
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Здесь был неверный отступ. available_slots и все последующее должно быть внутри try
        available_slots = await slots_service.get_available_slots_by_date(session, selected_date)
        if not available_slots:
            await message.answer("Нет доступных слотов на выбранную дату.")
            await state.clear()
            return

        # Сохраняем доступные слоты в состоянии для следующего шага
        await state.update_data(available_slots=available_slots)

        keyboard = []
        for i, slot in enumerate(available_slots):
            # Убедитесь, что slot.cafe действительно объект и у него есть name
            # и что start_time/end_time в удобном формате
            slot_info = f"{slot.start_time} - {slot.end_time}, Кофейня: {slot.cafe.name}"
            keyboard.append([types.InlineKeyboardButton(text=slot_info, callback_data=f"slot_{i}")])
        keyboard.append([types.InlineKeyboardButton(text="Отмена", callback_data="cancel")])

        reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer("Доступные слоты. Выберите слот для бронирования:", reply_markup=reply_markup)
        await state.set_state(BaristaSlotFSM.waiting_for_slot_choice)

    except ValueError: # Этот except должен соответствовать try выше
        await message.answer("Неверный формат даты. Пожалуйста, используйте YYYY-MM-DD.")
        # Не сбрасываем состояние, чтобы пользователь мог повторить ввод даты
        # await state.set_state(BaristaSlotFSM.waiting_for_date) # УЖЕ в этом состоянии, повторно не нужно
    except Exception as e: # Этот except должен соответствовать try выше
         logger.exception("Error during slot selection: %s", e)
         await message.answer("Произошла ошибка при получении доступных слотов.")
         await state.clear()


@router.callback_query(BaristaSlotFSM.waiting_for_slot_choice)
async def process_slot_choice(query: types.CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """
    Обработка выбора слота для бронирования.
    """
    if query.data == "cancel":
        await query.message.edit_text("Бронирование слота отменено.")
        await state.clear()
        return

    # Этот if (if query.data.startswith("slot_")) должен быть на том же уровне отступа, что и предыдущий if
    if query.data.startswith("slot_"):
        slot_index = int(query.data.split("_")[1])
        state_data = await state.get_data()
        available_slots = state_data.get("available_slots")
        if not available_slots or slot_index >= len(available_slots):
            await query.answer("Ошибка: Слот больше не доступен.")
            await state.clear()
            return

        selected_slot = available_slots[slot_index]

        try:
            # Убедитесь, что slots_service.book_slot принимает user_id и slot_id
            await slots_service.book_slot(session, user.id, selected_slot.id)
            await session.commit()
            await query.message.edit_text(f"Вы забронировали слот: {selected_slot.start_time} - {selected_slot.end_time}, Кофейня: {selected_slot.cafe.name}")
        except Exception as e:
            logger.exception("Error booking slot: %s", e)
            await query.message.answer("Произошла ошибка при бронировании слота. Возможно, он уже занят.")
        finally: # Убедитесь, что finally находится на правильном уровне отступа (внутри try)
            await state.clear()

    # await query.answer() должен быть в конце функции, но убедитесь, что он на правильном уровне отступа
    await query.answer()
