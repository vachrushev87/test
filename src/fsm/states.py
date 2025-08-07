from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния для сценария регистрации баристы."""
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_cafe_selection = State()

class BaristaSlotStates(StatesGroup):
    """Состояния для сценариев выбора слота бариста."""
    waiting_for_slot_selection = State()
    waiting_for_booking_confirmation = State()

class AdminCafeStates(StatesGroup):
    """Состояния для сценариев управления кофейнями администратором."""
    waiting_for_cafe_name = State()
    waiting_for_cafe_address = State()
    waiting_for_cafe_phone = State()
    waiting_for_cafe_description = State()
    waiting_for_cafe_manager = State()

class ManagerShiftCreationStates(StatesGroup):
    """Состояния для сценария создания смен управляющим."""
    waiting_for_shift_date = State()
    waiting_for_shift_start_time = State()
    waiting_for_shift_end_time = State()
    waiting_for_required_baristas = State()
    confirm_add_more_shifts = State()

class ManagerUserConfirmationStates(StatesGroup):
    """Состояния для управляющего для подтверждения регистрации бариста."""
    waiting_for_user_selection = State()
    waiting_for_confirmation_action = State()
