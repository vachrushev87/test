import logging
import datetime
import re
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters, Application
)
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

from src.core.database import get_async_session, init_db # init_db можно вызвать только при старте
from src.core.models import User, Cafe, Slot, Role, RegistrationStatus, Base
from src.telegа.keyboards import (cancel_keyboard, confirm_keyboard, main_admin_manager_keyboard,
    admin_cafe_management_keyboard, admin_user_management_keyboard,
    cafe_edit_options_keyboard, user_edit_options_keyboard, select_role_keyboard,
    generate_entity_list_keyboard
)
from src.telegа.messages import (send_common_message, get_admin_main_menu_text,
                                 notify_user)

from src.core.database import get_async_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.models import User, Role
import logging

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


# Функция для проверки прав администратора
async def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором, используя базу данных.
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(User)
            .where(User.telegram_id == str(user_id))
        )
        user = result.scalars().first()

        if user:
            return user.role == Role.ADMIN # Сравниваем с Enum Role.ADMIN
        return False # Пользователь не найден или не является администратором

logger = logging.getLogger(__name__)

SELECT_ENTITY_FOR_ACTION = range(1) # Например, для выбора кофейни/пользователя из списка

# Café States
(CREATE_CAFE_NAME, CREATE_CAFE_ADDRESS, CREATE_CAFE_HOURS, CREATE_CAFE_CONTACTS, CREATE_CAFE_DESCRIPTION, CREATE_CAFE_MANAGER,
 EDIT_CAFE_FIELD_VALUE, EDIT_CAFE_SELECT_MANAGER, EDIT_CAFE_HOURS_OPEN, EDIT_CAFE_HOURS_CLOSE) = range(10, 20)

# User States
(CREATE_USER_TG_ID, CREATE_USER_NAME, CREATE_USER_PHONE, CREATE_USER_ROLE, CREATE_USER_CAFE,
 EDIT_USER_FIELD_VALUE, EDIT_USER_SELECT_ROLE, EDIT_USER_SELECT_CAFE) = range(20, 28)


# --- Хелперы для проверки доступа ---
async def check_admin_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_telegram_id = update.effective_user.id
    if str(user_telegram_id) not in context.bot_data.get('ADMIN_IDS', []):
        logger.warning(f'Попытка несанкционированного доступа пользователя {user_telegram_id}')
        await send_common_message(update, context, "У вас нет прав для выполнения этой команды.", reply_markup=main_admin_manager_keyboard())
        return False
    return True

async def check_admin_or_manager_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_telegram_id = update.effective_user.id
    async with get_async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == user_telegram_id)).scalar_one_or_none()
        if user and (user.role == Role.ADMIN or user.role == Role.MANAGER):
            return True
    logger.warning(f'Попытка несанкционированного доступа пользователя {user_telegram_id} (not admin/manager)')
    await send_common_message(update, "У вас нет прав для выполнения этой команды.", reply_markup=main_admin_manager_keyboard())
    return False

# --- Вспомогательные функции для ConversationHandler ---
async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает отмену операции в ConversationHandler через inline-кнопку или команду."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text('Операция отменена. Чем еще могу помочь?', reply_markup=main_admin_manager_keyboard())
    else:
        await update.message.reply_text('Операция отменена. Чем еще могу помочь?', reply_markup=main_admin_manager_keyboard())

    context.user_data.pop('current_edit_entity_id', None)
    context.user_data.pop('current_edit_field', None)
    context.user_data.pop('pending_cafe_data', None)
    context.user_data.pop('pending_user_data', None)
    context.user_data.pop('temp_cafe_object', None)
    context.user_data.pop('temp_user_object', None)

    return ConversationHandler.END

# --- Главное меню для администратора ---
async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_admin_role(update, context):
        return
    await send_common_message(update, get_admin_main_menu_text(), reply_markup=main_admin_manager_keyboard())

# --- Управление кофейнями ---
async def cafe_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_admin_role(update, context):
        return
    await send_common_message(update, 'Выберите действие для управления кофейнями:', reply_markup=admin_cafe_management_keyboard())


async def create_cafe_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f'create_cafe_button called by user {update.effective_user.id}')  # Лог
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await update.callback_query.answer('У вас нет прав для выполнения этой команды.', show_alert=True)
        logger.info(f'Пользователь {user_id} е является администратором, доступ запрещен')  # Лог
        return ConversationHandler.END # Завершаем, так как прав нет

    await update.callback_query.answer() # Убираем иконку загрузки с кнопки
    await update.callback_query.message.reply_text('Пожалуйста, введите название кофейни:')
    logger.info(f'Admin {user_id} прошел проверку, спросив название кафе')  # Лог
    return CREATE_CAFE_NAME

# --- Создание кофейни ConversationHandler ---
async def create_cafe_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f'create_cafe_start вызываемый пользователем {update.effective_user.id}')  # Лог
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        logger.info(f'Пользователь {user_id} не является администратором, доступ запрещен')  # Лог
        if update.message:
            await update.message.reply_text('У вас нет прав для выполнения этой команды.')
        elif update.callback_query:
            await update.callback_query.answer('У вас нет прав для выполнения этой команды.', show_alert=True)
        return ConversationHandler.END

    if update.message:
        await update.message.reply_text('Пожалуйста, введите название кофейни:')
    elif update.callback_query:
        await update.callback_query.message.reply_text('Пожалуйста, введите название кофейни:')
    logger.info(f'Admin {user_id} прошел проверку, спросив название кафе')  # Лог
    return CREATE_CAFE_NAME

    if not await check_admin_role(update, context):
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()

    await send_common_message(update, 'Начинаем создание новой кофейни.\nПожалуйста, введите *название* кофейни:', reply_markup=cancel_keyboard())
    context.user_data['pending_cafe_data'] = {} # Для временного хранения данных
    return CREATE_CAFE_NAME

async def create_cafe_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cafe_name = update.message.text.strip()
    if not (3 <= len(cafe_name) <= 100):
        await update.message.reply_text('Название должно быть от 3 до 100 символов. Попробуйте еще раз.', reply_markup=cancel_keyboard())
        return CREATE_CAFE_NAME

    async with get_async_session() as session:
        result = await session.execute(select(Cafe).where(func.lower(Cafe.name) == func.lower(cafe_name)))
        existing_cafe = result.scalar_one_or_none()

        if existing_cafe:
            await update.message.reply_text('Кофейня с таким названием уже существует. Пожалуйста, введите другое название.', reply_markup=cancel_keyboard())
            return CREATE_CAFE_NAME

    context.user_data['pending_cafe_data']['name'] = cafe_name
    await update.message.reply_text('Введите *адрес* кофейни:', reply_markup=cancel_keyboard())
    return CREATE_CAFE_ADDRESS

async def create_cafe_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['pending_cafe_data']['address'] = update.message.text.strip()
    await update.message.reply_text('Введите *часы работы* кофейни (например, `09:00-22:00` или `Круглосуточно`):', reply_markup=cancel_keyboard())
    return CREATE_CAFE_HOURS

async def create_cafe_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    hours_str = update.message.text.strip()
    open_time_obj, close_time_obj = None, None

    if hours_str.lower() != 'круглосуточно':
        match = re.match(r"(\d{2}:\d{2})-(\d{2}:\d{2})", hours_str)
        if not match:
            await update.message.reply_text('Неверный формат часов работы. Используйте `ЧЧ:ММ-ЧЧ:ММ` или `Круглосуточно`.', reply_markup=cancel_keyboard())
            return CREATE_CAFE_HOURS

        try:
            open_time_str, close_time_str = match.groups()
            open_time_obj = datetime.datetime.strptime(open_time_str, "%H:%M").time()
            close_time_obj = datetime.datetime.strptime(close_time_str, "%H:%M").time()

            if open_time_obj >= close_time_obj:
                await update.message.reply_text('Время открытия должно быть раньше времени закрытия. Попробуйте еще раз.', reply_markup=cancel_keyboard())
                return CREATE_CAFE_HOURS

        except ValueError:
            await update.message.reply_text('Неверный формат времени в часах работы. Попробуйте еще раз.\nПример: `09:00-22:00`', reply_markup=cancel_keyboard())
            return CREATE_CAFE_HOURS

    context.user_data['pending_cafe_data']['open_time'] = open_time_obj
    context.user_data['pending_cafe_data']['close_time'] = close_time_obj
    await update.message.reply_text('Введите *контактную информацию* (телефон, email) кофейни:', reply_markup=cancel_keyboard())
    return CREATE_CAFE_CONTACTS

async def create_cafe_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['pending_cafe_data']['contact_info'] = update.message.text.strip()
    await update.message.reply_text('Введите *описание* кофейни (необязательно, можно ввести `-`):', reply_markup=cancel_keyboard())
    return CREATE_CAFE_DESCRIPTION

async def create_cafe_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text.strip()
    context.user_data['pending_cafe_data']['description'] = description if description != '-' else None # Если введен "-", то устанавливаем None

    await update.message.reply_text('Теперь выберите *управляющего* для этой кофейни. Если менеджера нет, введите `нет`.', reply_markup=cancel_keyboard())

    # Предлагаем список текущих менеджеров или выбираем из всех пользователей
    async with get_async_session() as session:
        managers_result = await session.execute(
            select(User).where(User.role == Role.MANAGER, User.is_active == True, User.cafe_id == None) # Свободные менеджеры
        )
        managers = managers_result.scalars().all()

        active_users_result = await session.execute(
            select(User.id, User.name, User.surname, User.role) # Получение активных пользователей для выбора менеджера
            .where(User.is_active == True)
            .order_by(User.name)
        )
        all_users = [{"id": u[0], "name": f"{u[1]} {u[2] or ''} ({u[3].value.capitalize()})"} for u in active_users_result.all()]

        if all_users:
            keyboard = generate_entity_list_keyboard(all_users, 'select_manager_for_cafe')
            await update.message.reply_text('Выберите пользователя из списка, который будет управляющим, или введите его *Telegram ID*:', reply_markup=keyboard)
        else:
            await update.message.reply_text('На данный момент нет зарегистрированных пользователей. Введите *Telegram ID* будущего управляющего:', reply_markup=cancel_keyboard())

    return CREATE_CAFE_MANAGER

async def create_cafe_manager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    manager_id = None
    query = update.callback_query

    if query:
        await query.answer()
        manager_id = int(query.data.split(":")[1])
        context.user_data['pending_cafe_data']['manager_id'] = manager_id
    elif update.message:
        text_input = update.message.text.strip()
        if text_input.lower() == 'нет':
            context.user_data['pending_cafe_data']['manager_id'] = None
            manager_id = -1 # Для обозначения, что менеджера нет
        else:
            try:
                manager_tg_id = int(text_input)
                async with get_async_session() as session:
                    manager_user = await session.execute(
                        select(User)
                        .where(User.telegram_id == manager_tg_id)
                        .options(selectinload(User.cafe)) # Загружаем текущую кофейню менеджера, если есть
                    ).scalar_one_or_none()

                    if not manager_user:
                        await send_common_message(update, 'Пользователь с таким Telegram ID не найден. Попробуйте еще раз или выберите из списка.', reply_markup=cancel_keyboard())
                        return CREATE_CAFE_MANAGER

                    if manager_user.role != Role.MANAGER:
                         await send_common_message(update, f'Пользователь {manager_user.name} *не является управляющим*. Ему будет автоматически присвоена роль Управляющего. Продолжить?', 
                                                   reply_markup=confirm_keyboard(f'assign_new_manager:{manager_user.id}'))
                         context.user_data['temp_manager_candidate_id'] = manager_user.id
                         # Остаемся в этом же состоянии, ожидая подтверждения.
                         return CREATE_CAFE_MANAGER

                    if manager_user.cafe_id is not None:
                        await send_common_message(update, f"Пользователь {manager_user.name} *уже является управляющим* кофейни {manager_user.cafe.name}. "
                                                   "Вы хотите переназначить его на эту новую кофейню? В таком случае он перестанет быть управляющим старой кофейни.", 
                                                   reply_markup=confirm_keyboard(f"reassign_manager:{manager_user.id}"))
                        context.user_data['manager_to_reassign'] = manager_user.id
                        return CREATE_CAFE_MANAGER # Ждем подтверждения переназначения

                    manager_id = manager_user.id
                    context.user_data['pending_cafe_data']['manager_id'] = manager_id
            except ValueError:
                await send_common_message(update, 'Некорректный Telegram ID. Пожалуйста, введите числовой ID или выберите из списка.', reply_markup=cancel_keyboard())
                return CREATE_CAFE_MANAGER
    else:
        return CREATE_CAFE_MANAGER # Если не было ни callback, ни message

    # Если мы дошли до сюда, значит manager_id определен или "нет"
    if manager_id != -1:
        cafe_data = context.user_data["pending_cafe_data"]

        async with get_async_session() as session:
            try:
                # Создаем новую кофейню
                new_cafe = Cafe(
                    name=cafe_data["name"],
                    address=cafe_data["address"],
                    open_time=cafe_data["open_time"],
                    close_time=cafe_data["close_time"],
                    contact_info=cafe_data["contact_info"],
                    description=cafe_data["description"]
                )
                session.add(new_cafe)
                await session.flush() # Получаем ID новой кофейни

                if manager_id:
                    manager_user = await session.execute(
                        select(User).where(User.id == manager_id)
                    ).scalar_one_or_none()
                    if manager_user:
                        # Если управляющий был привязан к другой кофейне, освобождаем ее
                        if manager_user.cafe_id:
                            old_cafe = await session.execute(
                                select(Cafe).where(Cafe.id == manager_user.cafe_id)
                            ).scalar_one_or_none()
                            if old_cafe:
                                old_cafe.manager_id = None
                                session.add(old_cafe) # Обновляем старую кофейню

                        manager_user.role = Role.MANAGER # Убедимся, что роль MANAGER
                        manager_user.cafe_id = new_cafe.id
                        new_cafe.manager_id = manager_user.id # Привязываем менеджера к новой кофейне
                        session.add(manager_user)

                        await notify_user(context.bot, manager_user.telegram_id, 
                                          f'🎉 Вы назначены управляющим новой кофейни: *{new_cafe.name}*!')

                await session.commit()
                await session.refresh(new_cafe)

                manager_name_display = (await session.execute(select(User.name).where(User.id == manager_id))).scalar_one_or_none() if manager_id else 'не назначен'

                await send_common_message(update, (
                    f"✅ Кофейня *{new_cafe.name}* успешно создана!\n"
                    f"Адрес: _{new_cafe.address}_\n"
                    f"Часы: {cafe_data['open_time'].strftime('%H:%M')}-{cafe_data['close_time'].strftime('%H:%M')}" if cafe_data['open_time'] else "Круглосуточно" + "\n"
                    f"Контакты: _{cafe_data['contact_info']}_\n"
                    f"Описание: _{cafe_data['description'] or 'Нет'}_\n"
                    f"Управляющий: _{manager_name_display}_"
                ), reply_markup=main_admin_manager_keyboard())
                logger.info(f"Cafe '{new_cafe.name}' created by admin {update.effective_user.id}.")

            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating cafe: {e}")
                await send_common_message(update, 'Произошла ошибка при сохранении кофейни. Пожалуйста, попробуйте еще раз.', reply_markup=main_admin_manager_keyboard())
    else: # manager_id == -1 (нет управляющего)
        cafe_data = context.user_data["pending_cafe_data"]
        async with get_async_session() as session:
            try:
                new_cafe = Cafe(
                    name=cafe_data["name"],
                    address=cafe_data["address"],
                    open_time=cafe_data["open_time"],
                    close_time=cafe_data["close_time"],
                    contact_info=cafe_data["contact_info"],
                    description=cafe_data["description"]
                )
                session.add(new_cafe)
                await session.commit()
                await session.refresh(new_cafe)

                await send_common_message(update, (
                    f"✅ Кофейня *{new_cafe.name}* успешно создана!\n"
                    f"Адрес: _{new_cafe.address}_\n"
                    f"Часы: {cafe_data['open_time'].strftime('%H:%M')}-{cafe_data['close_time'].strftime('%H:%M')}" if cafe_data['open_time'] else "Круглосуточно" + "\n"
                    f"Контакты: _{cafe_data['contact_info']}_\n"
                    f"Описание: _{cafe_data['description'] or 'Нет'}_\n"
                    f"Управляющий: _не назначен_"
                ), reply_markup=main_admin_manager_keyboard())
                logger.info(f"Cafe '{new_cafe.name}' created by admin {update.effective_user.id} without manager.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating cafe (no manager): {e}")
                await send_common_message(update, "Произошла ошибка при сохранении кофейни. Пожалуйста, попробуйте еще раз.", reply_markup=main_admin_manager_keyboard())

    context.user_data.pop("pending_cafe_data", None)
    context.user_data.pop("temp_manager_candidate_id", None)
    context.user_data.pop("manager_to_reassign", None)
    return ConversationHandler.END

async def handle_create_cafe_manager_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split(":")[1:]
    user_id = int(user_id)

    async with get_async_session() as session:
        manager_user = await session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not manager_user:
            await send_common_message(update, "Выбранный пользователь не найден. Пожалуйста, попробуйте еще раз.", reply_markup=cancel_keyboard())
            return CREATE_CAFE_MANAGER

        if action == "assign_new_manager":
            manager_user.role = Role.MANAGER # Присваиваем роль Менеджера
            session.add(manager_user)
            await session.commit()
            context.user_data['pending_cafe_data']['manager_id'] = manager_user.id
            await send_common_message(update, f"Пользователю {manager_user.name} *успешно присвоена роль управляющего*. Продолжите создание кофейни.", reply_markup=cancel_keyboard())
            return await create_cafe_manager(update, context) # Продолжаем процесс создания кофейни
        elif action == "reassign_manager":
            old_cafe = await session.execute(select(Cafe).where(Cafe.id == manager_user.cafe_id)).scalar_one_or_none()
            if old_cafe:
                old_cafe.manager_id = None
                session.add(old_cafe)

            manager_user.cafe_id = None # На время отвязки, чтобы затем привязать к новой кофейне
            session.add(manager_user)
            await session.flush() # Сохраняем изменения

            context.user_data['pending_cafe_data']['manager_id'] = manager_user.id
            await send_common_message(update, f"Пользователь {manager_user.name} *отвязан от предыдущей кофейни*. Продолжите создание кофейни.", reply_markup=cancel_keyboard())
            return await create_cafe_manager(update, context) # Продолжаем процесс создания кофейни

    await send_common_message(update, "Действие отменено. Пожалуйста, выберите другого управляющего или введите 'нет'.", reply_markup=cancel_keyboard())
    context.user_data.pop("temp_manager_candidate_id", None)
    context.user_data.pop("manager_to_reassign", None)
    return CREATE_CAFE_MANAGER # Остаемся в этом состоянии

# --- Редактирование кофейни ConversationHandler ---
async def edit_cafe_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_admin_role(update, context):
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()

    async with get_async_session() as session:
        cafes = await session.execute(select(Cafe).order_by(Cafe.name)).scalars().all()
        if not cafes:
            await send_common_message(update, "Кофеен для редактирования не найдено.", reply_markup=admin_cafe_management_keyboard())
            return ConversationHandler.END

        keyboard = generate_entity_list_keyboard(cafes, "select_edit_cafe")
        await send_common_message(update, "Выберите кофейню для редактирования:", reply_markup=keyboard)
        return SELECT_ENTITY_FOR_ACTION

async def edit_cafe_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    cafe_id = int(query.data.split(":")[1])
    context.user_data["current_edit_entity_id"] = cafe_id

    async with get_async_session() as session:
        cafe = await session.execute(
            select(Cafe)
            .where(Cafe.id == cafe_id)
            .options(selectinload(Cafe.manager))
        ).scalar_one_or_none()

        if not cafe:
            await send_common_message(update, "Кофейня не найдена.", reply_markup=admin_cafe_management_keyboard())
            return ConversationHandler.END

        context.user_data['temp_cafe_object'] = {
            'name': cafe.name,
            'address': cafe.address,
            'contact_info': cafe.contact_info,
            'description': cafe.description,
            'open_time': cafe.open_time,
            'close_time': cafe.close_time,
            'manager_id': cafe.manager_id,
        }

        manager_info = f"Управляющий: *{cafe.manager.name} {cafe.manager.surname or ''}*" if cafe.manager else "Управляющий: _не назначен_"
        hours_info = f"Часы работы: `{cafe.open_time.strftime('%H:%M')}-{cafe.close_time.strftime('%H:%M')}`" if cafe.open_time and cafe.close_time else "Часы работы: _Круглосуточно_"

        await send_common_message(update, (
            f"Выбрана кофейня: *{cafe.name}*\n"
            f"Адрес: _{cafe.address}_\n"
            f"Контакты: _{cafe.contact_info or 'Нет'}_\n"
            f"Описание: _{cafe.description or 'Нет'}_\n"
            f"{hours_info}\n"
            f"{manager_info}\n\n"
            "Что хотите изменить?"
        ), reply_markup=cafe_edit_options_keyboard(cafe_id))
        return EDIT_CAFE_FIELD_VALUE # Переходим в состояние выбора поля для редактирования.

async def edit_cafe_prompt_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    field_name = query.data.split(":")[0].replace("edit_cafe_", "") # e.g., 'name', 'address'
    cafe_id = context.user_data["current_edit_entity_id"]

    context.user_data["current_edit_field"] = field_name

    message = ""
    if field_name == "name":
        message = "Введите новое *название* кофейни:"
    elif field_name == "address":
        message = "Введите новый *адрес* кофейни:"
    elif field_name == "contacts":
        message = "Введите новую *контактную информацию* кофейни:"
    elif field_name == "description":
        message = "Введите новое *описание* кофейни (можно `-` для удаления):"
    elif field_name == "hours":
        await send_common_message(update, "Введите новое *время открытия* кофейни в формате *ЧЧ:ММ* (например, `09:00` или `00:00` для круглосуточно):", reply_markup=cancel_keyboard())
        return EDIT_CAFE_HOURS_OPEN
    elif field_name == "manager":
        await send_common_message(update, "Выберите нового *управляющего* или введите его *Telegram ID*. Введите `нет`, если управляющий не нужен.", reply_markup=cancel_keyboard())
        async with get_async_session() as session:
            active_users = await session.execute(
                select(User.id, User.name, User.surname, User.telegram_id, User.role) # Получение активных пользователей для выбора менеджера
                .where(User.is_active == True)
                .order_by(User.name)
            )
            all_users = [{"id": u.id, "name": f"{u.name} {u.surname or ''} ({u.role.value.capitalize()})"} for u in active_users.all()]
            if all_users:
                keyboard = generate_entity_list_keyboard(all_users, "select_manager_for_edit_cafe")
                await send_common_message(update, "Выберите пользователя:", reply_markup=keyboard)
            else:
                await send_common_message(update, "На данный момент нет зарегистрированных пользователей.", reply_markup=cancel_keyboard())
        return EDIT_CAFE_SELECT_MANAGER
    elif field_name == "save_exit":
        return await edit_cafe_save_exit(update, context)

    await send_common_message(update, message, reply_markup=cancel_keyboard())
    return EDIT_CAFE_FIELD_VALUE # Остаемся в этом состоянии для ввода значения.

async def edit_cafe_hours_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    open_time_str = update.message.text.strip()
    if open_time_str.lower() == "круглосуточно":
        context.user_data['temp_cafe_object']['open_time'] = None
        context.user_data['temp_cafe_object']['close_time'] = None
        await send_common_message(update, "Часы работы установлены как *Круглосуточно*.Выберите следующее действие.", reply_markup=cafe_edit_options_keyboard(context.user_data["current_edit_entity_id"]))
        return EDIT_CAFE_FIELD_VALUE # Возвращаемся к выбору опций редактирования

    try:
        open_time = datetime.datetime.strptime(open_time_str, "%H:%M").time()
        context.user_data['temp_cafe_object']['open_time'] = open_time
        await update.message.reply_text("Введите новое *время закрытия* кофейни в формате *ЧЧ:ММ* (например, `22:00`):", reply_markup=cancel_keyboard())
        return EDIT_CAFE_HOURS_CLOSE
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Используйте *ЧЧ:ММ*. Попробуйте еще раз.", reply_markup=cancel_keyboard())
        return EDIT_CAFE_HOURS_OPEN

async def edit_cafe_hours_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    close_time_str = update.message.text.strip()
    try:
        close_time = datetime.datetime.strptime(close_time_str, "%H:%M").time()

        open_time = context.user_data['temp_cafe_object']['open_time']
        if open_time and open_time >= close_time:
            await update.message.reply_text("Время открытия должно быть раньше времени закрытия. Попробуйте еще раз время закрытия.", reply_markup=cancel_keyboard())
            return EDIT_CAFE_HOURS_CLOSE

        context.user_data['temp_cafe_object']['close_time'] = close_time
        await send_common_message(update, "Часы работы обновлены. Выберите следующее действие.", reply_markup=cafe_edit_options_keyboard(context.user_data["current_edit_entity_id"]))
        # Предупреждение о слотах
        cafe_id = context.user_data['current_edit_entity_id']
        async with get_async_session() as session:
            conflicting_slots = await session.execute(
                select(Slot)
                .where(Slot.cafe_id == cafe_id, Slot.is_active == True, Slot.start_time >= datetime.datetime.now())
                .filter(
                    (func.cast(Slot.start_time, Time) < open_time) | 
                    (func.cast(Slot.end_time, Time) > close_time)
                )
            ).scalars().all()
            if conflicting_slots:
                await send_common_message(update, 
                                          "⚠️ *ВНИМАНИЕ:* Изменение часов работы может повлиять на существующие забронированные слоты. "
                                          "Пожалуйста, проверьте и скорректируйте слоты вручную, если это необходимо.", parse_mode='Markdown')

        return EDIT_CAFE_FIELD_VALUE
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Используйте *ЧЧ:ММ*. Попробуйте еще раз.", reply_markup=cancel_keyboard())
        return EDIT_CAFE_HOURS_CLOSE

async def edit_cafe_process_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_value = update.message.text.strip()
    field_name = context.user_data.get("current_edit_field")

    if field_name == "description" and new_value == '-':
        new_value = None # Для удаления описания

    if field_name == "name": # Проверка уникальности имени
        async with get_async_session() as session:
            existing_cafe = await session.execute(
                select(Cafe).where(
                    func.lower(Cafe.name) == func.lower(new_value),
                    Cafe.id != context.user_data['current_edit_entity_id']
                )
            ).scalar_one_or_none()
            if existing_cafe:
                await update.message.reply_text("Кофейня с таким названием уже существует. Введите другое название.", reply_markup=cancel_keyboard())
                return EDIT_CAFE_FIELD_VALUE

    context.user_data['temp_cafe_object'][field_name] = new_value
    await update.message.reply_text(f"Поле *{field_name.capitalize()}* обновлено во временных данных. "
                                   "Выберите следующее действие.", 
                                   reply_markup=cafe_edit_options_keyboard(context.user_data["current_edit_entity_id"]))
    return EDIT_CAFE_FIELD_VALUE

async def edit_cafe_select_manager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    manager_id = None

    if query:
        await query.answer()
        manager_id = int(query.data.split(":")[1])
    elif update.message:
        text_input = update.message.text.strip()
        if text_input.lower() == 'нет':
            manager_id = None # Нет управляющего
        else:
            try:
                manager_tg_id = int(text_input)
                async with get_async_session() as session:
                    manager_user = await session.execute(
                        select(User).where(User.telegram_id == manager_tg_id)
                    ).scalar_one_or_none()

                    if not manager_user:
                        await send_common_message(update, "Пользователь с таким Telegram ID не найден. Попробуйте еще раз или выберите из списка.", reply_markup=cancel_keyboard())
                        return EDIT_CAFE_SELECT_MANAGER

                    if manager_user.role != Role.MANAGER:
                         await send_common_message(update, f"Пользователь {manager_user.name} *не является управляющим*. Ему будет автоматически присвоена роль Управляющего. Продолжить?", 
                                                   reply_markup=confirm_keyboard(f"edit_assign_manager:{manager_user.id}"))
                         context.user_data['temp_manager_candidate_id_edit'] = manager_user.id
                         return EDIT_CAFE_SELECT_MANAGER

                    if manager_user.cafe_id is not None and manager_user.cafe_id != context.user_data["current_edit_entity_id"]:
                        await send_common_message(update, f"Пользователь {manager_user.name} *уже является управляющим* кофейни {manager_user.cafe.name}. "
                                                   "Вы хотите переназначить его на эту кофейню? В таком случае он перестанет быть управляющим старой кофейни.", 
                                                   reply_markup=confirm_keyboard(f"edit_reassign_manager:{manager_user.id}"))
                        context.user_data['temp_manager_to_reassign_edit'] = manager_user.id
                        return EDIT_CAFE_SELECT_MANAGER

                    manager_id = manager_user.id
            except ValueError:
                await send_common_message(update, "Некорректный Telegram ID. Пожалуйста, введите числовой ID или выберите из списка.", reply_markup=cancel_keyboard())
                return EDIT_CAFE_SELECT_MANAGER

    context.user_data['temp_cafe_object']['manager_id'] = manager_id
    await send_common_message(update, "Управляющий обновлен во временных данных. Выберите следующее действие.", 
                              reply_markup=cafe_edit_options_keyboard(context.user_data["current_edit_entity_id"]))

    return EDIT_CAFE_FIELD_VALUE # Возвращаемся к выбору опций редактирования

async def handle_edit_cafe_manager_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split(":")[1:]
    user_id = int(user_id)

    async with get_async_session() as session:
        manager_user = await session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not manager_user:
            await send_common_message(update, "Выбранный пользователь не найден. Пожалуйста, попробуйте еще раз.", reply_markup=cancel_keyboard())
            return EDIT_CAFE_SELECT_MANAGER

        if action == "edit_assign_manager":
            manager_user.role = Role.MANAGER
            session.add(manager_user)
            await session.commit() # Сохраняем изменение роли
            context.user_data['temp_cafe_object']['manager_id'] = manager_user.id
            await send_common_message(update, f"Пользователю {manager_user.name} *успешно присвоена роль управляющего*. Выберите следующее действие.", reply_markup=cafe_edit_options_keyboard(context.user_data["current_edit_entity_id"]))
            context.user_data.pop("temp_manager_candidate_id_edit", None)
            return EDIT_CAFE_FIELD_VALUE # Возвращаемся к выбору опций
        elif action == "edit_reassign_manager":
            old_cafe = await session.execute(select(Cafe).where(Cafe.id == manager_user.cafe_id)).scalar_one_or_none()
            if old_cafe:
                old_cafe.manager_id = None
                session.add(old_cafe)
            manager_user.cafe_id = None # Отвязываем от старой кофейни
            session.add(manager_user)
            await session.flush() # Сохраняем изменения

            context.user_data['temp_cafe_object']['manager_id'] = manager_user.id
            await send_common_message(update, f"Пользователь {manager_user.name} *отвязан от предыдущей кофейни*. Выберите следующее действие.", reply_markup=cafe_edit_options_keyboard(context.user_data["current_edit_entity_id"]))
            context.user_data.pop("temp_manager_to_reassign_edit", None)
            return EDIT_CAFE_FIELD_VALUE # Возвращаемся к выбору опций

    await send_common_message(update, "Действие отменено. Пожалуйста, выберите другого управляющего или введите 'нет'.", reply_markup=cancel_keyboard())
    context.user_data.pop("temp_manager_candidate_id_edit", None)
    context.user_data.pop("temp_manager_to_reassign_edit", None)
    return EDIT_CAFE_SELECT_MANAGER # Остаемся в этом состоянии

async def edit_cafe_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    page = int(query.data.split(":")[1])
    async with get_async_session() as session:
        cafes = await session.execute(select(Cafe).order_by(Cafe.name)).scalars().all()
        keyboard = generate_entity_list_keyboard(cafes, "select_edit_cafe", page)
        await query.edit_message_reply_markup(reply_markup=keyboard) # Обновляем только клавиатуру
        return SELECT_ENTITY_FOR_ACTION # Остаемся в том же состоянии

async def edit_cafe_save_exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    cafe_id = context.user_data["current_edit_entity_id"]
    temp_data = context.user_data['temp_cafe_object']

    async with get_async_session() as session:
        cafe_to_update = await session.execute(
            select(Cafe).where(Cafe.id == cafe_id).options(selectinload(Cafe.manager))
        ).scalar_one()

        # Сохраняем старого менеджера, если он есть, для уведомления
        old_manager_id = cafe_to_update.manager_id
        old_manager_tg_id = cafe_to_update.manager.telegram_id if cafe_to_update.manager else None

        # Обновляем данные кофейни
        cafe_to_update.name = temp_data['name']
        cafe_to_update.address = temp_data['address']
        cafe_to_update.contact_info = temp_data['contact_info']
        cafe_to_update.description = temp_data['description']
        cafe_to_update.open_time = temp_data['open_time']
        cafe_to_update.close_time = temp_data['close_time']

        # Обновление управляющего
        if temp_data['manager_id'] != old_manager_id:
            # Отвязываем старого управляющего от этой кофейни
            if old_manager_id:
                old_manager = await session.execute(select(User).where(User.id == old_manager_id)).scalar_one_or_none()
                if old_manager:
                    old_manager.cafe_id = None
                    session.add(old_manager)
                    if old_manager_tg_id:
                        await notify_user(context.bot, old_manager_tg_id, 
                                          f"⚠️ Вы больше не управляющий кофейни *{cafe_to_update.name}*.")

            # Привязываем нового управляющего
            if temp_data['manager_id']:
                new_manager = await session.execute(select(User).where(User.id == temp_data['manager_id'])).scalar_one_or_none()
                if new_manager:
                    # Если новый менеджер был привязан к другой кофейне, освобождаем ее
                    if new_manager.cafe_id and new_manager.cafe_id != cafe_id:
                        another_old_cafe = await session.execute(select(Cafe).where(Cafe.id == new_manager.cafe_id)).scalar_one_or_none()
                        if another_old_cafe:
                            another_old_cafe.manager_id = None
                            session.add(another_old_cafe)
                            await notify_user(context.bot, new_manager.telegram_id, 
                                        f"⚠️ Вы больше не управляющий кофейни *{another_old_cafe.name}*.")

                    new_manager.role = Role.MANAGER # Убедимся, что роль MANAGER
                    new_manager.cafe_id = cafe_to_update.id
                    cafe_to_update.manager_id = new_manager.id
                    session.add(new_manager)
                    await notify_user(context.bot, new_manager.telegram_id, 
                                      f"🎉 Вы теперь управляющий кофейни *{cafe_to_update.name}*!")
            else: # Если менеджер_id стал None
                cafe_to_update.manager_id = None

        session.add(cafe_to_update)
        await session.commit()
        await session.refresh(cafe_to_update)

    await send_common_message(update, f"✅ Информация о кофейне *{cafe_to_update.name}* успешно обновлена.", reply_markup=main_admin_manager_keyboard())
    logger.info(f"Cafe {cafe_to_update.name} ({cafe_id}) updated by admin {update.effective_user.id}.")

    # Очистка user_data
    context.user_data.pop('current_edit_entity_id', None)
    context.user_data.pop('current_edit_field', None)
    context.user_data.pop('temp_cafe_object', None)
    context.user_data.pop("temp_manager_candidate_id_edit", None)
    context.user_data.pop("temp_manager_to_reassign_edit", None)
    return ConversationHandler.END

# --- Переключение статуса кофейни ---
async def toggle_cafe_status_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_admin_role(update, context):
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()

    async with get_async_session() as session:
        cafes = await session.execute(select(Cafe).order_by(Cafe.name)).scalars().all()
        if not cafes:
            await send_common_message(update, "Кофеен для изменения статуса не найдено.", reply_markup=admin_cafe_management_keyboard())
            return ConversationHandler.END

        keyboard = generate_entity_list_keyboard(cafes, "select_toggle_cafe_status")
        await send_common_message(update, "Выберите кофейню для изменения статуса:", reply_markup=keyboard)
        context.user_data['action_type_for_select'] = 'toggle_cafe_status' # Для обработки в entity_selected
        return SELECT_ENTITY_FOR_ACTION

async def toggle_cafe_status_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    cafe_id = int(query.data.split(":")[1])

    async with get_async_session() as session:
        cafe = await session.execute(select(Cafe).where(Cafe.id == cafe_id)).scalar_one_or_none()
        if not cafe:
            await send_common_message(update, "Кофейня не найдена.", reply_markup=admin_cafe_management_keyboard())
            return await cancel_operation(update, context)

        new_status = not cafe.is_active
        status_word = "деактивировать" if new_status == False else "активировать"
        confirm_data = f"confirm_toggle_cafe_status:{cafe.id}:{new_status}"

        await send_common_message(update, f"Вы действительно хотите *{status_word}* кофейню *{cafe.name}*?", 
                                   reply_markup=confirm_keyboard(confirm_data))
        return SELECT_ENTITY_FOR_ACTION # Остаемся в состоянии ожидания подтверждения

async def toggle_cafe_status_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    cafe_id = int(parts[1])
    new_status = parts[2] == 'True' # Преобразуем строку в булево значение

    async with get_async_session() as session:
        cafe = await session.execute(select(Cafe).where(Cafe.id == cafe_id)).scalar_one_or_none()
        if not cafe:
            await send_common_message(update, "Кофейня не найдена.", reply_markup=admin_cafe_management_keyboard())
            return await cancel_operation(update, context)

        cafe.is_active = new_status
        await session.commit()

        status_msg = "активирована" if new_status else "деактивирована"
        await send_common_message(update, f"✅ Кофейня *{cafe.name}* успешно *{status_msg}*.", reply_markup=main_admin_manager_keyboard())
        logger.info(f"Cafe {cafe.name}({cafe_id}) status toggled to {new_status} by admin {update.effective_user.id}.")

    context.user_data.pop('current_edit_entity_id', None)
    context.user_data.pop('action_type_for_select', None)
    return ConversationHandler.END


# --- Управление пользователями ---
async def user_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_admin_role(update, context):
        return
    await send_common_message(update, "Выберите действие для управления пользователями:", reply_markup=admin_user_management_keyboard())

# --- Создание пользователя ConversationHandler ---
async def create_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_admin_role(update, context):
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()

    context.user_data['pending_user_data'] = {}
    await send_common_message(update, "Начинаем создание нового пользователя.\nПожалуйста, введите *Telegram ID* пользователя:", reply_markup=cancel_keyboard())
    return CREATE_USER_TG_ID

async def create_user_tg_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        tg_id = int(update.message.text.strip())
        async with get_async_session() as session:
            existing_user = await session.execute(select(User).where(User.telegram_id == tg_id)).scalar_one_or_none()
            if existing_user:
                await update.message.reply_text("Пользователь с таким Telegram ID уже существует. Введите другой ID.", reply_markup=cancel_keyboard())
                return CREATE_USER_TG_ID

        context.user_data['pending_user_data']['telegram_id'] = tg_id
        await update.message.reply_text("Введите *Имя* пользователя (и Фамилию, если есть, через пробел):", reply_markup=cancel_keyboard())
        return CREATE_USER_NAME
    except ValueError:
        await update.message.reply_text("Неверный формат Telegram ID. Введите целое число.", reply_markup=cancel_keyboard())
        return CREATE_USER_TG_ID

async def create_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip().split(maxsplit=1)
    context.user_data['pending_user_data']['name'] = full_name[0]
    context.user_data['pending_user_data']['surname'] = full_name[1] if len(full_name) > 1 else None

    await update.message.reply_text("Введите *номер телефона* пользователя (необязательно, можно `-`):", reply_markup=cancel_keyboard())
    return CREATE_USER_PHONE

async def create_user_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    context.user_data['pending_user_data']['phone_number'] = phone if phone != '-' else None

    await send_common_message(update, "Теперь выберите *роль* пользователя:", reply_markup=select_role_keyboard())
    return CREATE_USER_ROLE

async def create_user_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    role_str = query.data.split(":")[1]
    selected_role = Role(role_str)

    context.user_data['pending_user_data']['role'] = selected_role

    if selected_role in [Role.MANAGER, Role.BARISTA]:
        await send_common_message(update, f"Выбрана роль: *{selected_role.value.capitalize()}*.\nТеперь выберите *кофейню*, к которой привязать пользователя (или `нет`, если не привязывать):", reply_markup=cancel_keyboard())
        async with get_async_session() as session:
            cafes = await session.execute(select(Cafe).order_by(Cafe.name)).scalars().all()
            if cafes:
                keyboard = generate_entity_list_keyboard(cafes, "select_cafe_for_user")
                await query.edit_message_reply_markup(reply_markup=keyboard) # Обновляем клавиатуру текущего сообщения
            else:
                await send_common_message(update, "Кофеен пока нет. Пользователь будет создан без привязки к кофейне.", reply_markup=cancel_keyboard())
        return CREATE_USER_CAFE
    else: # ADMIN
        context.user_data['pending_user_data']['cafe_id'] = None # Админ не привязан к кофейне
        return await create_user_end_save(update, context)

async def create_user_cafe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cafe_id = None
    query = update.callback_query

    if query:
        await query.answer()
        cafe_id = int(query.data.split(":")[1])
        context.user_data['pending_user_data']['cafe_id'] = cafe_id
    elif update.message and update.message.text.strip().lower() == 'нет':
        context.user_data['pending_user_data']['cafe_id'] = None
    else:
        await send_common_message(update, "Некорректный ввод. Выберите кофейню из списка или введите `нет`.", reply_markup=cancel_keyboard())
        return CREATE_USER_CAFE

    return await create_user_end_save(update, context)

async def create_user_end_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data['pending_user_data']

    async with get_async_session() as session:
        try:
            new_user = User(
                telegram_id=user_data['telegram_id'],
                name=user_data['name'],
                surname=user_data['surname'],
                phone_number=user_data['phone_number'],
                role=user_data['role'],
                cafe_id=user_data['cafe_id'],
                registration_status= RegistrationStatus.APPROVED if user_data['role'] != Role.BARISTA else RegistrationStatus.UNDEFINED # Для бариста статус Pending (или Undefined, если админ сразу добавляет)
            )

            # Если создаем бариста напрямую, минуя регистрацию, то статус сразу APPRVOED.
            # Если это обычная регистрация, то PENDING. Здесь админ создает - APPRVOED
            if new_user.role == Role.BARISTA:
                new_user.registration_status = RegistrationStatus.APPROVED

            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

            cafe_name_display = "не привязана"
            if new_user.cafe_id:
                cafe = await session.execute(select(Cafe.name).where(Cafe.id == new_user.cafe_id)).scalar_one_or_none()
                if cafe:
                    cafe_name_display = cafe

            await send_common_message(update, (
                f"✅ Пользователь *{new_user.name} {new_user.surname or ''}* успешно создан!\n"
                f"Telegram ID: `{new_user.telegram_id}`\n"
                f"Телефон: _{new_user.phone_number or 'Нет'}_\n"
                f"Роль: *{new_user.role.value.capitalize()}*\n"
                f"Кофейня: _{cafe_name_display}_"
            ), reply_markup=main_admin_manager_keyboard())
            logger.info(f"User {new_user.name} ({new_user.telegram_id}) created by admin {update.effective_user.id} with role {new_user.role.value}.")

            # Уведомление созданному пользователю
            await notify_user(context.bot, new_user.telegram_id, 
                              f"🎉 Администратор добавил вас в систему NiceBot!\n"
                              f"Ваша роль: *{new_user.role.value.capitalize()}*.")


        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating user: {e}")
            await send_common_message(update, "Произошла ошибка при сохранении пользователя. Пожалуйста, попробуйте еще раз.", reply_markup=main_admin_manager_keyboard())

    context.user_data.pop('pending_user_data', None)
    return ConversationHandler.END


# --- Редактирование пользователя ConversationHandler ---
async def edit_user_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_admin_role(update, context):
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()

    async with get_async_session() as session:
        users = await session.execute(
            select(User)
            .order_by(User.name)
        ).scalars().all()
        if not users:
            await send_common_message(update, "Пользователей для редактирования не найдено.", reply_markup=admin_user_management_keyboard())
            return ConversationHandler.END

        # Для отображения пользователя в списке
        users_for_display = [{"id": u.id, "name": f"{u.name} {u.surname or ''} ({u.role.value.capitalize()})"} for u in users]

        keyboard = generate_entity_list_keyboard(users_for_display, "select_edit_user")
        await send_common_message(update, "Выберите пользователя для редактирования:", reply_markup=keyboard)
        return SELECT_ENTITY_FOR_ACTION

async def edit_user_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split(":")[1])
    context.user_data["current_edit_entity_id"] = user_id

    async with get_async_session() as session:
        user = await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.cafe))
        ).scalar_one_or_none()

        if not user:
            await send_common_message(update, "Пользователь не найден.", reply_markup=admin_user_management_keyboard())
            return ConversationHandler.END

        context.user_data['temp_user_object'] = {
            'name': user.name,
            'surname': user.surname,
            'phone_number': user.phone_number,
            'role': user.role,
            'cafe_id': user.cafe_id,
        }

        cafe_info = f"Кофейня: *{user.cafe.name}*" if user.cafe else "Кофейня: _не привязана_"

        await send_common_message(update, (
            f"Выбран пользователь: *{user.name} {user.surname or ''}*\n"
            f"Telegram ID: `{user.telegram_id}`\n"
            f"Телефон: _{user.phone_number or 'Нет'}_\n"
            f"Роль: *{user.role.value.capitalize()}*\n"
            f"{cafe_info}\n\n"
            "Что хотите изменить?"
        ), reply_markup=user_edit_options_keyboard(user_id))
        return EDIT_USER_FIELD_VALUE # Переходим в состояние выбора поля для редактирования.

async def edit_user_prompt_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    field_name = query.data.split(":")[0].replace("edit_user_", "") # e.g., 'name', 'phone'
    user_id = context.user_data["current_edit_entity_id"]

    context.user_data["current_edit_field"] = field_name

    message = ""
    if field_name == "name":
        message = "Введите новое *Имя* пользователя (и Фамилию, если есть, через пробел):"
    elif field_name == "phone":
        message = "Введите новый *номер телефона* пользователя (можно `-` для удаления):"
    elif field_name == "role":
        current_role = context.user_data['temp_user_object']['role']
        await send_common_message(update, f"Выберите новую *роль* пользователя. Текущая: *{current_role.value.capitalize()}*.", reply_markup=select_role_keyboard(current_role))
        return EDIT_USER_SELECT_ROLE
    elif field_name == "cafe":
        await send_common_message(update, "Выберите новую *кофейню* для пользователя (или `нет`, если не привязывать):", reply_markup=cancel_keyboard())
        async with get_async_session() as session:
            cafes = await session.execute(select(Cafe).order_by(Cafe.name)).scalars().all()
            if cafes:
                keyboard = generate_entity_list_keyboard(cafes, "select_cafe_for_edit_user")
                await send_common_message(update, "Выберите кофейню:", reply_markup=keyboard)
            else:
                await send_common_message(update, "Кофеен не найдено.", reply_markup=cancel_keyboard())
        return EDIT_USER_SELECT_CAFE
    elif field_name == "save_exit":
        return await edit_user_save_exit(update, context)

    await send_common_message(update, message, reply_markup=cancel_keyboard())
    return EDIT_USER_FIELD_VALUE # Остаемся в этом состоянии для ввода значения.

async def edit_user_process_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_value = update.message.text.strip()
    field_name = context.user_data.get("current_edit_field")

    if field_name == "name":
        full_name = new_value.split(maxsplit=1)
        context.user_data['temp_user_object']['name'] = full_name[0]
        context.user_data['temp_user_object']['surname'] = full_name[1] if len(full_name) > 1 else None
    elif field_name == "phone":
        context.user_data['temp_user_object']['phone_number'] = new_value if new_value != '-' else None

    await update.message.reply_text(f"Поле *{field_name.capitalize()}* обновлено во временных данных. "
                                   "Выберите следующее действие.", 
                                   reply_markup=user_edit_options_keyboard(context.user_data["current_edit_entity_id"]))
    return EDIT_USER_FIELD_VALUE

async def edit_user_select_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    new_role_str = query.data.split(":")[1]
    new_role = Role(new_role_str)

    old_role = context.user_data['temp_user_object']['role']
    user_id = context.user_data['current_edit_entity_id']

    # Проверка забронированных смен при смене роли
    if new_role != old_role:
        async with get_async_session() as session:
            user_obj = await session.execute(
                select(User).where(User.id == user_id).options(selectinload(User.booked_slots))
            ).scalar_one_or_none() # Загружаем пользователя с его слотами

            if user_obj and user_obj.booked_slots:
                # Отфильтровываем только будущие слоты
                future_booked_slots = [s for s in user_obj.booked_slots if s.start_time > datetime.datetime.now()]
                if future_booked_slots:
                    await send_common_message(update, f"⚠️ У пользователя есть *забронированные слоты* ({len(future_booked_slots)} шт.) в будущем. "
                                                   "При изменении роли на не-бариста (или бариста на другую) эти слоты будут *отменены*. Вы уверены?",
                                                   reply_markup=confirm_keyboard(f"confirm_change_role:{user_id}:{new_role_str}"))
                    context.user_data['pending_role_change_new_role'] = new_role # Сохраняем новую роль для подтверждения
                    return EDIT_USER_SELECT_ROLE # Ждем подтверждения

    context.user_data['temp_user_object']['role'] = new_role
    await send_common_message(update, f"Роль обновлена на *{new_role.value.capitalize()}* во временных данных. Выберите следующее действие.", 
                              reply_markup=user_edit_options_keyboard(user_id))
    return EDIT_USER_FIELD_VALUE

async def handle_change_role_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action, user_id_str, new_role_str = query.data.split(":")[1:]
    user_id = int(user_id_str)
    new_role = Role(new_role_str)

    if action == "confirm_change_role":
        async with get_async_session() as session:
            user_obj = await session.execute(
                select(User).where(User.id == user_id).options(selectinload(User.booked_slots))
            ).scalar_one_or_none()

            if user_obj and user_obj.booked_slots:
                for slot in user_obj.booked_slots:
                    if slot.start_time > datetime.datetime.now(): # Отменяем только будущие слоты
                        slot.barista_id = None # Освобождаем слот
                        session.add(slot)
                await session.commit()
                await notify_user(context.bot, user_obj.telegram_id, 
                                  "⚠️ Ваши забронированные слоты были отменены в связи с изменением вашей роли.")

        context.user_data['temp_user_object']['role'] = new_role
        await send_common_message(update, f"Роль обновлена на *{new_role.value.capitalize()}* (слоты отменены). Выберите следующее действие.", 
                                  reply_markup=user_edit_options_keyboard(user_id))
        context.user_data.pop('pending_role_change_new_role', None)
        return EDIT_USER_FIELD_VALUE
    else:
        await send_common_message(update, "Изменение роли отменено. Выберите другое действие.", reply_markup=user_edit_options_keyboard(user_id))
        context.user_data.pop('pending_role_change_new_role', None)
        return EDIT_USER_FIELD_VALUE

async def edit_user_select_cafe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    cafe_id = None

    if query:
        await query.answer()
        cafe_id = int(query.data.split(":")[1])
    elif update.message and update.message.text.strip().lower() == 'нет':
        cafe_id = None
    else:
        await send_common_message(update, "Некорректный ввод. Выберите кофейню из списка или введите `нет`.", reply_markup=cancel_keyboard())
        return EDIT_USER_SELECT_CAFE

    old_cafe_id = context.user_data['temp_user_object']['cafe_id']
    user_id = context.user_data['current_edit_entity_id']
    current_role = context.user_data['temp_user_object']['role']

    # Проверка забронированных смен при смене кофейни для бариста
    if current_role == Role.BARISTA and cafe_id != old_cafe_id:
        async with get_async_session() as session:
            user_obj = await session.execute(
                select(User).where(User.id == user_id).options(selectinload(User.booked_slots))
            ).scalar_one_or_none()

            if user_obj and user_obj.booked_slots:
                future_booked_slots_old_cafe = [s for s in user_obj.booked_slots if s.start_time > datetime.datetime.now() and s.cafe_id == old_cafe_id]
                if future_booked_slots_old_cafe:
                    await send_common_message(update, f"⚠️ У пользователя есть *забронированные слоты* ({len(future_booked_slots_old_cafe)} шт.) в текущей кофейне. "
                                                   "При изменении кофейни эти слоты будут *отменены*. Вы уверены?",
                                                   reply_markup=confirm_keyboard(f"confirm_change_cafe_for_barista:{user_id}:{cafe_id}"))
                    context.user_data['pending_cafe_change_new_cafe_id'] = cafe_id
                    return EDIT_USER_SELECT_CAFE # Ждем подтверждения

    context.user_data['temp_user_object']['cafe_id'] = cafe_id
    await send_common_message(update, f"Кофейня обновлена во временных данных. Выберите следующее действие.", 
                              reply_markup=user_edit_options_keyboard(user_id))
    return EDIT_USER_FIELD_VALUE

async def handle_change_cafe_for_barista_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action, user_id_str, new_cafe_id_str = query.data.split(":")[1:]
    user_id = int(user_id_str)
    new_cafe_id = int(new_cafe_id_str) if new_cafe_id_str != 'None' else None

    if action == "confirm_change_cafe_for_barista":
        async with get_async_session() as session:
            user_obj = await session.execute(
                select(User).where(User.id == user_id).options(selectinload(User.booked_slots))
            ).scalar_one_or_none()

            if user_obj and user_obj.booked_slots:
                old_cafe_id = context.user_data['temp_user_object']['cafe_id'] # Это еще старая привязанная кофейня
                for slot in user_obj.booked_slots:
                    if slot.start_time > datetime.datetime.now() and slot.cafe_id == old_cafe_id:
                        slot.barista_id = None # Освобождаем слот
                        session.add(slot)
                await session.commit()
                await notify_user(context.bot, user_obj.telegram_id, 
                                  "⚠️ Ваши забронированные слоты в старой кофейне были отменены в связи с изменением вашей привязки к кофейне.")

        context.user_data['temp_user_object']['cafe_id'] = new_cafe_id
        await send_common_message(update, f"Кофейня обновлена (слоты отменены). Выберите следующее действие.", 
                                  reply_markup=user_edit_options_keyboard(user_id))
        context.user_data.pop('pending_cafe_change_new_cafe_id', None)
        return EDIT_USER_FIELD_VALUE
    else:
        await send_common_message(update, "Изменение кофейни отменено. Выберите другое действие.", reply_markup=user_edit_options_keyboard(user_id))
        context.user_data.pop('pending_cafe_change_new_cafe_id', None)
        return EDIT_USER_FIELD_VALUE

async def edit_user_save_exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    user_id = context.user_data["current_edit_entity_id"]
    temp_data = context.user_data['temp_user_object']

    async with get_async_session() as session:
        user_to_update = await session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.cafe))
        ).scalar_one()

        old_role = user_to_update.role
        old_cafe_id = user_to_update.cafe_id
        old_cafe_name = user_to_update.cafe.name if user_to_update.cafe else "не привязана"

        user_to_update.name = temp_data['name']
        user_to_update.surname = temp_data['surname']
        user_to_update.phone_number = temp_data['phone_number']
        user_to_update.role = temp_data['role']
        user_to_update.cafe_id = temp_data['cafe_id']

        # Обновляем статус регистрации, если роль изменилась
        if user_to_update.role == Role.BARISTA and user_to_update.registration_status == RegistrationStatus.UNDEFINED:
            user_to_update.registration_status = RegistrationStatus.APPROVED # Если админ сам задал роль бариста, то она одобрена

        session.add(user_to_update)
        await session.commit()
        await session.refresh(user_to_update)

        # Уведомления
        notifications = []
        if old_role != user_to_update.role:
            notifications.append(f"Ваша роль изменена на: *{user_to_update.role.value.capitalize()}*.")

        if old_cafe_id != user_to_update.cafe_id:
            new_cafe_name = (await session.execute(select(Cafe.name).where(Cafe.id == user_to_update.cafe_id))).scalar_one_or_none() if user_to_update.cafe_id else "нет"
            notifications.append(f"Ваша привязка к кофейне изменена с *{old_cafe_name}* на *{new_cafe_name}*.")

            # Уведомление старым управляющим
            if old_cafe_id:
                old_manager = await session.execute(
                    select(User).where(User.cafe_id == old_cafe_id, User.role == Role.MANAGER)
                ).scalar_one_or_none()
                if old_manager:
                    await notify_user(context.bot, old_manager.telegram_id, 
                                      f"⚠️ Бариста *{user_to_update.name} {user_to_update.surname or ''}* отвязан от вашей кофейни *{old_cafe_name}*.")

            # Уведомление новым управляющим
            if user_to_update.cafe_id:
                new_manager = await session.execute(
                    select(User).where(User.cafe_id == user_to_update.cafe_id, User.role == Role.MANAGER)
                ).scalar_one_or_none()
                if new_manager and new_manager.telegram_id != user_to_update.telegram_id: # Не уведомлять самого пользователя, если он стал менеджером своей новой кафе
                    await notify_user(context.bot, new_manager.telegram_id, 
                                      f"🎉 Бариста *{user_to_update.name} {user_to_update.surname or ''}* теперь привязан к вашей кофейне *{new_cafe_name}*.")


        if notifications:
            await notify_user(context.bot, user_to_update.telegram_id, "\n".join(notifications))

    await send_common_message(update, f"✅ Информация о пользователе *{user_to_update.name} {user_to_update.surname or ''}* успешно обновлена.", reply_markup=main_admin_manager_keyboard())
    logger.info(f"User {user_to_update.name} ({user_id}) updated by admin {update.effective_user.id}.")

    # Очистка user_data
    context.user_data.pop('current_edit_entity_id', None)
    context.user_data.pop('current_edit_field', None)
    context.user_data.pop('temp_user_object', None)
    context.user_data.pop('pending_role_change_new_role', None)
    context.user_data.pop('pending_cafe_change_new_cafe_id', None)
    return ConversationHandler.END

# --- Переключение статуса пользователя ---
async def toggle_user_status_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_admin_role(update, context):
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()

    async with get_async_session() as session:
        users = await session.execute(select(User).order_by(User.name)).scalars().all()
        if not users:
            await send_common_message(update, "Пользователей для изменения статуса не найдено.", reply_markup=admin_user_management_keyboard())
            return ConversationHandler.END

        users_for_display = [{"id": u.id, "name": f"{u.name} {u.surname or ''} ({u.role.value.capitalize()})"} for u in users]

        keyboard = generate_entity_list_keyboard(users_for_display, "select_toggle_user_status")
        await send_common_message(update, "Выберите пользователя для изменения статуса:", reply_markup=keyboard)
        context.user_data['action_type_for_select'] = 'toggle_user_status'
        return SELECT_ENTITY_FOR_ACTION

async def toggle_user_status_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split(":")[1])

    async with get_async_session() as session:
        user = await session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            await send_common_message(update, "Пользователь не найден.", reply_markup=admin_user_management_keyboard())
            return await cancel_operation(update, context)

        new_status = not user.is_active
        status_word = "деактивировать" if new_status == False else "активировать"
        confirm_data = f"confirm_toggle_user_status:{user.id}:{new_status}"

        await send_common_message(update, f"Вы действительно хотите *{status_word}* пользователя *{user.name} {user.surname or ''}*?", 
                                   reply_markup=confirm_keyboard(confirm_data))
        return SELECT_ENTITY_FOR_ACTION

async def toggle_user_status_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    user_id = int(parts[1])
    new_status = parts[2] == 'True'

    async with get_async_session() as session:
        user = await session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.booked_slots))
        ).scalar_one_or_none()
        if not user:
            await send_common_message(update, "Пользователь не найден.", reply_markup=admin_user_management_keyboard())
            return await cancel_operation(update, context)

        # Если деактивируем пользователя (особенно баристу), отменяем будущие слоты
        if not new_status and user.role == Role.BARISTA:
            for slot in user.booked_slots:
                if slot.start_time > datetime.datetime.now():
                    slot.barista_id = None
                    session.add(slot)
            await session.flush() # Сохраняем изменения слотов перед обновлением пользователя
            await notify_user(context.bot, user.telegram_id, 
                              "⚠️ Ваши забронированные слоты были отменены, так как ваш аккаунт деактивирован.")


        user.is_active = new_status
        await session.commit()

        status_msg = "активирован" if new_status else "деактивирован"
        await send_common_message(update, f"✅ Пользователь *{user.name} {user.surname or ''}* успешно *{status_msg}*.", reply_markup=main_admin_manager_keyboard())
        logger.info(f"User {user.name} ({user_id}) status toggled to {new_status} by admin {update.effective_user.id}.")

        # Уведомление пользователю
        message_to_user = f"Ваш аккаунт в NiceBot был *{'активирован' if new_status else 'деактивирован'}* администратором."
        await notify_user(context.bot, user.telegram_id, message_to_user)

    context.user_data.pop('current_edit_entity_id', None)
    context.user_data.pop('action_type_for_select', None)
    return ConversationHandler.END


# --- Универсальная функция для обработки выбора сущности из списка ---
async def select_entity_for_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action_type = context.user_data.get('action_type_for_select')

    if action_type == 'toggle_cafe_status':
        return await toggle_cafe_status_confirm(update, context)
    elif action_type == 'toggle_user_status':
        return await toggle_user_status_confirm(update, context)
    elif action_type == 'select_edit_cafe': # Для редактирования кафе
        return await edit_cafe_selected(update, context)
    elif action_type == 'select_edit_user': # Для редактирования юзера
        return await edit_user_selected(update, context)

    # Если callback_query попадает сюда без определенного action_type, это ошибка или пропущенный случай
    await send_common_message(update, "Произошла ошибка при обработке выбора. Пожалуйста, попробуйте еще раз.", reply_markup=main_admin_manager_keyboard())
    return ConversationHandler.END

# --- Регистрация хендлеров ---
def register_admin_handlers(application):
    # Command Handlers
    application.add_handler(CommandHandler("start_admin", start_admin))
    # --- ДОБАВЬТЕ ЭТИ MessageHandler-ы для кнопок ReplyKeyboardMarkup ---
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🏢 Кофейни$"), handle_admin_cafe_button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^👨‍💻 Пользователи$"), handle_admin_user_button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📈 Мониторинг смен$"), handle_admin_monitoring_button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^⚙️ Управление слотами$"), handle_admin_slots_button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^❓ Помощь$"), handle_admin_help_button))
    # --- Конец добавленных MessageHandler-ов ---
    application.add_handler(CallbackQueryHandler(cafe_management_menu, pattern="^back_to_admin_main$")) # Кнопка "Назад"
    application.add_handler(CallbackQueryHandler(user_management_menu, pattern="^back_to_admin_main$")) # Кнопка "Назад"

    # Create Cafe Conversation
    create_cafe_conv = ConversationHandler(
        entry_points=[CommandHandler("create_cafe", create_cafe_start), CallbackQueryHandler(create_cafe_start, pattern="^admin_create_cafe$")],
        states={
            CREATE_CAFE_NAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_cafe_name)],
            CREATE_CAFE_ADDRESS: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_cafe_address)],
            CREATE_CAFE_HOURS: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_cafe_hours)],
            CREATE_CAFE_CONTACTS: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_cafe_contacts)],
            CREATE_CAFE_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_cafe_description)],
            CREATE_CAFE_MANAGER: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), create_cafe_manager),
                CallbackQueryHandler(create_cafe_manager, pattern="^select_manager_for_cafe:"),
                CallbackQueryHandler(handle_create_cafe_manager_confirmation, pattern="^(assign_new_manager|reassign_manager):") # Подтверждение роли/переназначения
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_operation), CallbackQueryHandler(cancel_operation, pattern="^cancel_operation$")],
        allow_reentry=True # Позволяет прерывать и заново начинать другие conv
    )
    application.add_handler(create_cafe_conv)

    # Edit Cafe Conversation
    edit_cafe_conv = ConversationHandler(
        entry_points=[CommandHandler("edit_cafe", edit_cafe_select), CallbackQueryHandler(edit_cafe_select, pattern="^admin_edit_cafe$")],
        states={
            SELECT_ENTITY_FOR_ACTION: [
                CallbackQueryHandler(edit_cafe_selected, pattern="^select_edit_cafe:"),
                CallbackQueryHandler(edit_cafe_page, pattern="^select_edit_cafe_page:"),
            ],
            EDIT_CAFE_FIELD_VALUE: [
                CallbackQueryHandler(edit_cafe_prompt_field, pattern="^edit_cafe_"),
                MessageHandler(filters.TEXT & (~filters.COMMAND), edit_cafe_process_value),
            ],
            EDIT_CAFE_HOURS_OPEN: [MessageHandler(filters.TEXT & (~filters.COMMAND), edit_cafe_hours_open)],
            EDIT_CAFE_HOURS_CLOSE: [MessageHandler(filters.TEXT & (~filters.COMMAND), edit_cafe_hours_close)],
            EDIT_CAFE_SELECT_MANAGER: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), edit_cafe_select_manager),
                CallbackQueryHandler(edit_cafe_select_manager, pattern="^select_manager_for_edit_cafe:"),
                CallbackQueryHandler(handle_edit_cafe_manager_confirmation, pattern="^(edit_assign_manager|edit_reassign_manager):")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_operation), CallbackQueryHandler(cancel_operation, pattern="^cancel_operation$")],
        allow_reentry=True
    )
    application.add_handler(edit_cafe_conv)

    # Toggle Cafe Status Conversation
    toggle_cafe_status_conv = ConversationHandler(
        entry_points=[CommandHandler("toggle_cafe_status", toggle_cafe_status_select), CallbackQueryHandler(toggle_cafe_status_select, pattern="^admin_toggle_cafe_status$")],
        states={
            SELECT_ENTITY_FOR_ACTION: [
                CallbackQueryHandler(toggle_cafe_status_confirm, pattern="^select_toggle_cafe_status:"),
                CallbackQueryHandler(toggle_cafe_status_execute, pattern="^confirm_toggle_cafe_status:"),
                CallbackQueryHandler(edit_cafe_page, pattern="^select_toggle_cafe_status_page:"), # Пагинация
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_operation), CallbackQueryHandler(cancel_operation, pattern="^cancel_operation$")],
        allow_reentry=True
    )
    application.add_handler(toggle_cafe_status_conv)

    # Create User Conversation
    create_user_conv = ConversationHandler(
        entry_points=[CommandHandler("create_user", create_user_start), CallbackQueryHandler(create_user_start, pattern="^admin_create_user$")],
        states={
            CREATE_USER_TG_ID: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_user_tg_id)],
            CREATE_USER_NAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_user_name)],
            CREATE_USER_PHONE: [MessageHandler(filters.TEXT & (~filters.COMMAND), create_user_phone)],
            CREATE_USER_ROLE: [CallbackQueryHandler(create_user_role, pattern="^select_user_role:")],
            CREATE_USER_CAFE: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), create_user_cafe),
                CallbackQueryHandler(create_user_cafe, pattern="^select_cafe_for_user:")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_operation), CallbackQueryHandler(cancel_operation, pattern="^cancel_operation$")],
        allow_reentry=True
    )
    application.add_handler(create_user_conv)

    # Edit User Conversation
    edit_user_conv = ConversationHandler(
        entry_points=[CommandHandler("edit_user", edit_user_select), CallbackQueryHandler(edit_user_select, pattern="^admin_edit_user$")],
        states={
            SELECT_ENTITY_FOR_ACTION: [
                CallbackQueryHandler(edit_user_selected, pattern="^select_edit_user:"),
                CallbackQueryHandler(edit_cafe_page, pattern="^select_edit_user_page:"), # Переименовать бы, но пока что так
            ],
            EDIT_USER_FIELD_VALUE: [
                CallbackQueryHandler(edit_user_prompt_field, pattern="^edit_user_"),
                MessageHandler(filters.TEXT & (~filters.COMMAND), edit_user_process_value),
            ],
            EDIT_USER_SELECT_ROLE: [
                CallbackQueryHandler(edit_user_select_role, pattern="^select_user_role:"),
                CallbackQueryHandler(handle_change_role_confirmation, pattern="^confirm_change_role:") # Отмена слотов при смене роли
            ],
            EDIT_USER_SELECT_CAFE: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), edit_user_select_cafe),
                CallbackQueryHandler(edit_user_select_cafe, pattern="^select_cafe_for_edit_user:"),
                CallbackQueryHandler(handle_change_cafe_for_barista_confirmation, pattern="^confirm_change_cafe_for_barista:") # Отмена слотов при смене кафе
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_operation), CallbackQueryHandler(cancel_operation, pattern="^cancel_operation$")],
        allow_reentry=True
    )
    application.add_handler(edit_user_conv)

    # Toggle User Status Conversation
    toggle_user_status_conv = ConversationHandler(
        entry_points=[CommandHandler("toggle_user_status", toggle_user_status_select), CallbackQueryHandler(toggle_user_status_select, pattern="^admin_toggle_user_status$")],
        states={
            SELECT_ENTITY_FOR_ACTION: [
                CallbackQueryHandler(toggle_user_status_confirm, pattern="^select_toggle_user_status:"),
                CallbackQueryHandler(toggle_user_status_execute, pattern="^confirm_toggle_user_status:"),
                CallbackQueryHandler(edit_cafe_page, pattern="^select_toggle_user_status_page:"), # Пагинация
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_operation), CallbackQueryHandler(cancel_operation, pattern="^cancel_operation$")],
        allow_reentry=True
    )
    application.add_handler(toggle_user_status_conv)

    # Inline Keyboard Callbacks (menu navigation)
    application.add_handler(CallbackQueryHandler(cafe_management_menu, pattern="^admin_cafe_management$"))
    application.add_handler(CallbackQueryHandler(user_management_menu, pattern="^admin_user_management$"))


async def handle_admin_cafe_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку '🏢 Кофейни' из ReplyKeyboardMarkup."""
    # update.message всегда будет существовать для MessageHandler
    await update.message.reply_text(
        "Вы управляете кофейнями. Выберите действие:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Создать кофейню", callback_data="admin_create_cafe")],
            [InlineKeyboardButton("Редактировать кофейню", callback_data="admin_edit_cafe")],
            [InlineKeyboardButton("Изменить статус кофейни", callback_data="admin_toggle_cafe_status")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin_main")] # Кнопка назад на inline клавиатуре
        ])
    )

async def handle_admin_user_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку '👨‍💻 Пользователи' из ReplyKeyboardMarkup."""
    await update.message.reply_text(
        "Вы управляете пользователями. Выберите действие:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Создать пользователя", callback_data="admin_create_user")],
            [InlineKeyboardButton("Редактировать пользователя", callback_data="admin_edit_user")],
            [InlineKeyboardButton("Изменить статус пользователя", callback_data="admin_toggle_user_status")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin_main")]
        ])
    )

async def handle_admin_monitoring_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку '📈 Мониторинг смен'."""
    # Здесь может быть InlineKeyboardMarkup с вариантами мониторинга
    await update.message.reply_text("Функционал мониторинга смен будет добавлен позже.") # Или сразу выводите данные

async def handle_admin_slots_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку '⚙️ Управление слотами'."""
    await update.message.reply_text("Функционал управления слотами будет добавлен позже.")

async def handle_admin_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку '❓ Помощь'."""
    await update.message.reply_text("Для получения помощи обратитесь к администратору.")


async def back_to_admin_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает CallbackQuery от инлайн-кнопки '⬅️ Назад' на админских InLine Клавиатурах
    и возвращает пользователя в главное меню администратора (ReplyKeyboardMarkup).
    """
    query = update.callback_query
    await query.answer() # Всегда отвечайте на CallbackQuery

    # Удаляем предыдущее сообщение с Inline клавиатурой
    if query.message: # Проверяем, существует ли сообщение
        try:
            await query.delete_message()
        except Exception as e:
            # Handle the case where the message might have already been deleted or is too old
            print(f"Failed to delete message: {e}")

    # Отправляем новое сообщение с ReplyKeyboardMarkup
    await context.bot.send_message(
        chat_id=query.from_user.id, # Используем chat_id пользователя
        text="Вы вернулись в главное меню администратора.",
        reply_markup=main_admin_manager_keyboard()
    )


#async def create_cafe_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#    """Start the cafe creation process."""
#    user_id = update.effective_user.id