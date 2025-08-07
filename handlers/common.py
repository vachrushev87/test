from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

router = Router()

@router.message(F.text == "/cancel")
@router.callback_query(F.data == "cancel_action")
async def cmd_cancel(event: Message | CallbackQuery, state: FSMContext) -> None:
    """
    Позволяет пользователю отменить любое текущее действие FSM.
    """
    current_state = await state.get_state()
    if current_state is None:
        if isinstance(event, Message):
            await event.answer("Нет активного действия для отмены.")
        elif isinstance(event, CallbackQuery):
            await event.message.answer("Нет активного действия для отмены.")
        return

    await state.clear()
    if isinstance(event, Message):
        await event.answer(
            "Действие отменено.",
            reply_markup=None
        )
    elif isinstance(event, CallbackQuery):
        await event.message.answer(
            "Действие отменено.",
            reply_markup=None
        )
        await event.answer() # Закрыть уведомление о кнопке
