from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from typing import Optional, List
from src.core.models import Role

def confirm_keyboard() -> InlineKeyboardButton:
    keyboard = [[
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm:{action_data}"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_operation")
        ]]
    return InlineKeyboardMarkup(keyboard)


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Генерирует клавиатуру с одной кнопкой 'Отмена'."""
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data="cancel_operation")]]
    return InlineKeyboardMarkup(keyboard)



def main_admin_manager_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура для администратора и управляющего."""
    keyboard = [
        ["📈 Мониторинг смен", "⚙️ Управление слотами"],
        ["🏢 Кофейни", "👨‍💻 Пользователи"],
        ["❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def admin_cafe_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления кофейнями со стороны администратора."""
    keyboard = [
        [InlineKeyboardButton("➕ Создать", callback_data="admin_create_cafe")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_edit_cafe")],
        [InlineKeyboardButton("❗️ Деактивировать/Активировать", callback_data="admin_toggle_cafe_status")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_user_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления пользователями со стороны администратора."""
    keyboard = [
        [InlineKeyboardButton("➕ Создать", callback_data="admin_create_user")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_edit_user")],
        [InlineKeyboardButton("❗️ Деактивировать/Активировать", callback_data="admin_toggle_user_status")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def cafe_edit_options_keyboard(cafe_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора опций редактирования кофейни."""
    keyboard = [
        [InlineKeyboardButton("📝 Название", callback_data=f"edit_cafe_name:{cafe_id}")],
        [InlineKeyboardButton("📍 Адрес", callback_data=f"edit_cafe_address:{cafe_id}")],
        [InlineKeyboardButton("📞 Контакты", callback_data=f"edit_cafe_contacts:{cafe_id}")],
        [InlineKeyboardButton("📜 Описание", callback_data=f"edit_cafe_description:{cafe_id}")],
        [InlineKeyboardButton("⏰ Часы работы", callback_data=f"edit_cafe_hours:{cafe_id}")],
        [InlineKeyboardButton("🤴 Управляющий", callback_data=f"edit_cafe_manager:{cafe_id}")],
        [InlineKeyboardButton("✅ Сохранить и выйти", callback_data=f"edit_cafe_save_exit:{cafe_id}")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="cancel_operation")],
    ]
    return InlineKeyboardMarkup(keyboard)

def user_edit_options_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора опций редактирования пользователя."""
    keyboard = [
        [InlineKeyboardButton("📝 Имя/Фамилия", callback_data=f"edit_user_name:{user_id}")],
        [InlineKeyboardButton("📞 Телефон", callback_data=f"edit_user_phone:{user_id}")],
        [InlineKeyboardButton("🎭 Роль", callback_data=f"edit_user_role:{user_id}")],
        [InlineKeyboardButton("🏢 Кофейня", callback_data=f"edit_user_cafe:{user_id}")],
        [InlineKeyboardButton("✅ Сохранить и выйти", callback_data=f"edit_user_save_exit:{user_id}")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="cancel_operation")],
    ]
    return InlineKeyboardMarkup(keyboard)

def select_role_keyboard(current_role: Optional[Role] = None) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для выбора роли пользователя."""
    buttons = []
    for role in Role:
        if current_role is None or role != current_role:
            buttons.append(InlineKeyboardButton(role.value.capitalize(), callback_data=f"select_user_role:{role.name}"))

    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("🚫 Отмена", callback_data="cancel_operation")])
    return InlineKeyboardMarkup(rows)

def generate_entity_list_keyboard(entities: List, prefix: str, page: int = 0, page_size: int = 5) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру со списком сущностей (кофеен/пользователей) для выбора с пагинацией.

    Args:
        entities (List): Список объектов сущностей (Cafe, User).
        prefix (str): Префикс для callback_data, например, "select_cafe" или "select_user".
        page (int): Текущая страница.
        page_size (int): Количество сущностей на странице.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками сущностей и пагинацией.
    """
    keyboard = []
    total_pages = (len(entities) + page_size - 1) // page_size

    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(entities))

    for i in range(start_idx, end_idx):
        entity = entities[i]
        label = ""
        # Порядок проверки важен: сначала 'full_name' для пользователей, затем 'name' для кофеен, и т.д.
        if hasattr(entity, 'full_name'): 
            label = entity.full_name
        elif hasattr(entity, 'name'):
            label = entity.name
        elif hasattr(entity, 'title'):
            label = entity.title
        elif hasattr(entity, 'id'):
            label = f"ID: {entity.id}"

        if hasattr(entity, 'is_active'):
            label += " (Активен)" if entity.is_active else " (Неактивен)"

        keyboard.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{entity.id}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{prefix}_page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"{prefix}_page:{page + 1}"))

    if nav_buttons:
        if len(nav_buttons) == 2:
            nav_buttons.insert(1, InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="ignore_page_num_btn"))
        elif total_pages > 1:
            nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="ignore_page_num_btn"))

        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🚫 Отмена", callback_data="cancel_operation")])
    return InlineKeyboardMarkup(keyboard)

def main_barista_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура для бариста."""
    keyboard = [
        ["🗓 Мои смены", "✨ Свободные слоты"],
        ["❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
