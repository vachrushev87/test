# src/handlers/barista.py
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler, # Добавьте это
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    filters,
    ConversationHandler
)

from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from src.core.database import get_async_session
from src.core.models import User, Role, Cafe, Slot, SlotStatus, RegistrationStatus
from src.core.config import settings

logger = logging.getLogger(__name__)

# STATES for ConversationHandler
# Это можно вынести в отдельный файл со StateMachine, если будет много сценариев
# Но для простоты оставлю пока здесь
ENTER_NAME_SURNAME, ENTER_PHONE, SELECT_CAFE = range(3)

# Короткий временной лаг (в минутах) между сменами в разных кофейнях в одном городе
# Это можно вынести в настройки конфига или БД для каждой кофейни/города
MIN_TIME_LAG_MINUTES = 60 # 1 час

async def start(update: Update, context: CallbackContext) -> int:
    """
    Отправляет приветственное сообщение и инициирует процесс регистрации, если пользователь новый.
    """
    user_telegram_id = str(update.effective_user.id)
    user_name = update.effective_user.full_name

    async with get_async_session() as session:
        db_user = await session.execute(select(User).where(User.telegram_id == user_telegram_id))
        db_user = db_user.scalar_one_or_none()

        if not db_user:
            logger.info(f"New user started the bot: {user_name} ({user_telegram_id})")
            # Новый пользователь, запускаем процесс регистрации
            await update.message.reply_html(
                rf"Привет {user_name}! Я ваш бот в команде Skuratov Coffee. Я здесь, чтобы помочь вам организовать рабочие смены."
                f"\n\nПохоже, вы новичок. Давайте зарегистрируемся."
                f"\n\nПожалуйста, введите ваше имя и фамилию (например, Иван Иванов):"
            )
            # Сохраняем telegram_id нового пользователя во временное хранилище (user_data)
            context.user_data['temp_telegram_id'] = user_telegram_id
            return ENTER_NAME_SURNAME
        else:
            # Пользователь уже существует
            if db_user.role == Role.BARISTA:
                if db_user.registration_status == RegistrationStatus.PENDING:
                    await update.message.reply_text(
                        f"Привет, {db_user.name}! Ваша заявка находится на рассмотрении. "
                        f"Пожалуйста, ожидайте подтверждения от управляющего."
                    )
                elif db_user.registration_status == RegistrationStatus.APPROVED:
                    await update.message.reply_text(
                        f"С возвращением, {db_user.name}! Вы успешно зарегистрированы как бариста. "
                        f"Используйте команды (/slots, /my_slots, /going) для работы со сменами."
                    )
                elif db_user.registration_status == RegistrationStatus.REJECTED:
                    await update.message.reply_text(
                        f"Привет, {db_user.name}. К сожалению, ваша заявка на регистрацию была отклонена. "
                        f"Если это ошибка, пожалуйста, свяжитесь с администрацией."
                    )
            elif db_user.role == Role.MANAGER:
                await update.message.reply_text(f"Привет, управляющий {db_user.name}! Вам доступны команды управляющего.")
            elif db_user.role == Role.ADMIN:
                await update.message.reply_text(f"Привет, администратор {db_user.name}! Вам доступны команды администратора.")

            return ConversationHandler.END # Завершаем ConversationHandler, если пользователь уже зарегистрирован

async def handle_registration_input(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает ввод имени, фамилии и телефона.
    """
    user_input = update.message.text
    current_state = context.user_data.get('state')

    if current_state == ENTER_NAME_SURNAME:
        parts = user_input.split(maxsplit=1)
        if len(parts) < 1:
            await update.message.reply_text("Пожалуйста, введите корректное имя и фамилию (например, Иван Иванов):")
            return ENTER_NAME_SURNAME

        context.user_data['temp_name'] = parts[0]
        context.user_data['temp_surname'] = parts[1] if len(parts) > 1 else "" # Фамилия может быть пустой

        logger.info(f"User {context.user_data.get('temp_telegram_id')} entered name: {context.user_data['temp_name']} {context.user_data['temp_surname']}")

        # Запрашиваем номер телефона с использованием кнопки запроса контактов
        keyboard = [[KeyboardButton("Поделиться номером телефона", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Отлично! Теперь поделитесь, пожалуйста, вашим номером телефона. Это необходимо для связи с вами.",
            reply_markup=reply_markup
        )
        context.user_data['state'] = ENTER_PHONE
        return ENTER_PHONE

    elif current_state == ENTER_PHONE:
        phone_number = None
        if update.message.contact:
            phone_number = update.message.contact.phone_number
            # Telegram иногда добавляет '+' для международных номеров
            if not phone_number.startswith('+'):
                phone_number = '+' + phone_number # Убедимся, что номер имеет формат с плюсом
        elif user_input:
            # Если пользователь ввел номер вручную, можно добавить простую валидацию
            if user_input.replace(' ', '').replace('-', '').isdigit() and len(user_input.replace(' ', '').replace('-', '')) >= 10:
                phone_number = user_input.replace(' ', '').replace('-', '')
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number # Добавим плюс, если его нет
            else:
                await update.message.reply_text("Пожалуйста, введите корректный номер телефона или воспользуйтесь кнопкой 'Поделиться номером телефона'.")
                return ENTER_PHONE

        if not phone_number:
            await update.message.reply_text("Пожалуйста, введите корректный номер телефона или воспользуйтесь кнопкой 'Поделиться номером телефона'.")
            return ENTER_PHONE

        context.user_data['temp_phone'] = phone_number
        logger.info(f"User {context.user_data.get('temp_telegram_id')} entered phone: {phone_number}")

        await update.message.reply_text(
            "Спасибо! Теперь выберите кофейню, к которой вы хотели бы привязаться. "
            "Это поможет управляющему подтвердить вашу регистрацию.",
            reply_markup=ReplyKeyboardRemove() # Убираем кнопку запроса номера
        )

        # Отправляем список кофеен для выбора
        return await send_cafe_selection(update, context)

    return ConversationHandler.END # Неожиданное состояние, завершаем

async def send_cafe_selection(update: Update, context: CallbackContext) -> int:
    """Отправляет клавиатуру с выбором кофеен."""
    async with get_async_session() as session:
        cafes = await session.execute(select(Cafe).order_by(Cafe.name))
        cafes = cafes.scalars().all()

        if not cafes:
            await update.message.reply_text("К сожалению, нет доступных кофеен для выбора. Пожалуйста, попробуйте позже или свяжитесь с администрацией.")
            logger.warning("No cafes found in DB for selection.")
            return ConversationHandler.END

        keyboard = []
        for cafe in cafes:
            keyboard.append([InlineKeyboardButton(f"{cafe.name} ({cafe.address})", callback_data=f"select_cafe:{cafe.id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите кофейню:", reply_markup=reply_markup)
        context.user_data['state'] = SELECT_CAFE
        return SELECT_CAFE

async def select_cafe_callback(update: Update, context: CallbackContext) -> int:
    """Обрабатывает выбор кофейни пользователем."""
    query = update.callback_query
    await query.answer()

    cafe_id = int(query.data.split(':')[1])
    cafe_name = ""
    telegram_id = context.user_data.get('temp_telegram_id', str(query.from_user.id))

    async with get_async_session() as session:
        cafe = await session.execute(select(Cafe).where(Cafe.id == cafe_id))
        cafe = cafe.scalar_one_or_none()

        if not cafe:
            await query.edit_message_text("Выбранная кофейня не найдена.")
            logger.error(f"Cafe with ID {cafe_id} not found during selection callback.")
            return ConversationHandler.END

        cafe_name = cafe.name

        # Создаем нового пользователя со статусом PENDING
        new_user = User(
            telegram_id=telegram_id,
            name=context.user_data.get('temp_name'),
            surname=context.user_data.get('temp_surname'),
            phone=context.user_data.get('temp_phone'),
            role=Role.BARISTA,
            registration_status=RegistrationStatus.PENDING,
            cafe_id=cafe_id,
            is_active=False # Неактивен, пока не одобрен
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user) # Обновляем, чтобы получить id

        await query.edit_message_text(
            f"Вы выбрали кофейню: *{cafe_name}*.\n\n"
            f"Ваша заявка на регистрацию отправлена на рассмотрение управляющему. "
            f"Как только она будет одобрена, вы получите уведомление и сможете начать работу со сменами."
        )
        logger.info(f"User {telegram_id} submitted registration for cafe {cafe_name}. ID: {new_user.id}")

        # Очищаем данные состояния
        context.user_data.clear()

        # Уведомляем менеджеров
        await notify_managers_about_new_registration(context, new_user, cafe) # Асинхронно уведомляем менеджеров

    return ConversationHandler.END

async def notify_managers_about_new_registration(context: CallbackContext, new_user: User, cafe: Cafe):
    """Отправляет уведомление менеджерам об ожидающей регистрации."""
    async with get_async_session() as session:
        # Можно найти менеджеров, привязанных к этой кофейне, или всех менеджеров
        managers = await session.execute(
            select(User)
            .where(User.role == Role.MANAGER, User.registration_status == RegistrationStatus.APPROVED)
        )
        managers = managers.scalars().all()

        if managers:
            message_text = (
                f"🚨 Новая заявка на регистрацию бариста! 🚨\n\n"
                f"Имя: {new_user.name} {new_user.surname}\n"
                f"Телефон: {new_user.phone}\n"
                f"Выбранная кофейня: *{cafe.name}* ({cafe.address})\n\n"
                f"Для просмотра и подтверждения заявки, используйте команду /pending_registrations "
                f"или нажмите 'Одобрить' / 'Отклонить' ниже."
            )
            keyboard = [[
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_reg:{new_user.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_reg:{new_user.id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            for manager in managers:
                try:
                    await context.bot.send_message(
                        chat_id=manager.telegram_id,
                        text=message_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Notified manager {manager.telegram_id} about new registration for user {new_user.id}.")
                except Exception as e:
                    logger.error(f"Failed to notify manager {manager.telegram_id}: {e}")

# Функции для ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ENTER_NAME_SURNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registration_input)],
        ENTER_PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), handle_registration_input)],
        SELECT_CAFE: [CallbackQueryHandler(select_cafe_callback, pattern=r'^select_cafe:(\d+)$')],
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)], # Можно добавить команду для отмены
    map_to_parent={
        ConversationHandler.END: ConversationHandler.END # Важно, если это под-хендлер
    },
    allow_reentry=True # Разрешить перезапуск, если пользователь введет /start снова
)


async def slots_command(update: Update, context: CallbackContext) -> None:
    """Показывает доступные слоты для бариста."""
    user_telegram_id = str(update.effective_user.id)

    async with get_async_session() as session:
        db_user = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
            .options(selectinload(User.cafe)) # Загружаем связанную кофейню
        )
        db_user = db_user.scalar_one_or_none()

        if not db_user or db_user.role != Role.BARISTA or db_user.registration_status != RegistrationStatus.APPROVED:
            await update.message.reply_text("Вы не зарегистрированы как одобренный бариста. Пожалуйста, используйте /start для регистрации или дождитесь одобрения.")
            return

        if not db_user.cafe_id:
            await update.message.reply_text("К вашей учетной записи не привязана кофейня. Пожалуйста, свяжитесь с управляющим.")
            return

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Получаем слоты для этой же кофейни, которые доступны для бронирования
        slots = await session.execute(
            select(Slot)
            .where(
                Slot.cafe_id == db_user.cafe_id,
                Slot.status == SlotStatus.AVAILABLE,
                Slot.start_time >= today # Только будущие слоты
            )
            .order_by(Slot.start_time)
            .options(selectinload(Slot.cafe)) # Загружаем связанные кафе
        )
        slots = slots.scalars().all()

        if not slots:
            await update.message.reply_text(f"На данный момент нет доступных слотов для вашей кофейни ({db_user.cafe.name}).")
            return

        text = f"Доступные слоты в кофейне *{db_user.cafe.name}*:\n\n"
        keyboard = []
        for slot in slots:
            date_str = slot.start_time.strftime("%d.%m")
            time_str = slot.start_time.strftime("%H:%M") + " - " + slot.end_time.strftime("%H:%M")
            text += f"*{date_str}* | {time_str}\n"
            keyboard.append([InlineKeyboardButton(f"{date_str} {time_str}", callback_data=f"select_slot:{slot.id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def select_slot_callback(update: Update, context: CallbackContext) -> None:
    """Обрабатывает выбор слота пользователем."""
    query = update.callback_query
    await query.answer()

    slot_id = int(query.data.split(':')[1])
    user_telegram_id = str(query.from_user.id)

    async with get_async_session() as session:
        # Проверяем пользователя
        db_user = await session.execute(select(User).where(User.telegram_id == user_telegram_id))
        db_user = db_user.scalar_one_or_none()

        if not db_user or db_user.role != Role.BARISTA or db_user.registration_status != RegistrationStatus.APPROVED:
            await query.edit_message_text("У вас нет прав для выполнения этого действия.")
            return

        # Проверяем слот
        slot = await session.execute(
            select(Slot)
            .where(Slot.id == slot_id)
            .options(selectinload(Slot.cafe))
        )
        slot = slot.scalar_one_or_none()

        if not slot:
            await query.edit_message_text("Выбранный слот не найден.")
            return

        if slot.status != SlotStatus.AVAILABLE:
            await query.edit_message_text(f"Этот слот уже {slot.status.value}.")
            return

        if slot.cafe_id != db_user.cafe_id:
            await query.edit_message_text("Вы можете бронировать слоты только в своей привязанной кофейне.")
            return

        # Валидация временного лага
        existing_slots = await session.execute(
            select(Slot)
            .where(
                Slot.barista_id == db_user.id,
                Slot.end_time > datetime.now(), # Только будущие слоты баристы
                Slot.status.in_([SlotStatus.BOOKED, SlotStatus.CONFIRMED])
            )
        )
        existing_slots = existing_slots.scalars().all()

        can_book = True
        for existing_slot in existing_slots:
            time_diff1 = abs((slot.start_time - existing_slot.end_time).total_seconds()) / 60
            time_diff2 = abs((existing_slot.start_time - slot.end_time).total_seconds()) / 60

            # Если слоты на один и тот же день и в разных кофейнях (или даже в одной, если очень близко)
            # Применим лаг, только если слоты в разных кофейнях, но в одном городе,
            # и они находятся близко по времени, пересекаются или почти пересекаются.
            # Для простоты пока проверяю на пересечение или близость в пределах лага

            # Проверяем, пересекаются ли слоты
            if (slot.start_time < existing_slot.end_time and slot.end_time > existing_slot.start_time):
                can_book = False
                await query.edit_message_text(
                    f"Вы не можете забронировать этот слот, так как он пересекается с вашим слотом "
                    f"*{existing_slot.start_time.strftime('%d.%m %H:%M')}-{existing_slot.end_time.strftime('%H:%M')}*."
                )
                return

            # Проверяем временной лаг, если слоты на один день и в разных кофейнях
            if (slot.start_time.date() == existing_slot.start_time.date() and
                slot.cafe_id != existing_slot.cafe_id and 
                (time_diff1 < MIN_TIME_LAG_MINUTES or time_diff2 < MIN_TIME_LAG_MINUTES)):

                can_book = False
                await query.edit_message_text(
                    f"Вы не можете забронировать этот слот. "
                    f"Между сменами в разных кофейнях ({existing_slot.cafe.name}) "
                    f"необходимо минимум {MIN_TIME_LAG_MINUTES} минут "
                    f"({existing_slot.start_time.strftime('%d.%m %H:%M')}-{existing_slot.end_time.strftime('%H:%M')})."
                )
                return

        if not can_book:
            return # Сообщение об ошибке уже отправлено

        # Предлагаем подтвердить бронирование
        date_str = slot.start_time.strftime("%d.%m.%Y")
        time_str = slot.start_time.strftime("%H:%M") + " - " + slot.end_time.strftime("%H:%M")

        keyboard = [[
            InlineKeyboardButton("✅ Подтвердить бронирование", callback_data=f"confirm_booking:{slot.id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_booking")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Вы выбрали слот в *{slot.cafe.name}*:\n"
            f"📅 Дата: *{date_str}*\n"
            f"⏰ Время: *{time_str}*\n\n"
            f"Подтвердите бронирование.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def confirm_slot_booking_callback(update: Update, context: CallbackContext) -> None:
    """Подтверждает бронирование слота."""
    query = update.callback_query
    await query.answer()

    slot_id = int(query.data.split(':')[1])
    user_telegram_id = str(query.from_user.id)

    async with get_async_session() as session:
        db_user = await session.execute(select(User).where(User.telegram_id == user_telegram_id))
        db_user = db_user.scalar_one_or_none()

        if not db_user or db_user.role != Role.BARISTA or db_user.registration_status != RegistrationStatus.APPROVED:
            await query.edit_message_text("У вас нет прав для выполнения этого действия.")
            return

        slot = await session.execute(
            select(Slot)
            .where(Slot.id == slot_id, Slot.status == SlotStatus.AVAILABLE)
            .options(selectinload(Slot.cafe))
        )
        slot = slot.scalar_one_or_none()

        if not slot:
            await query.edit_message_text("Слот не найден или уже забронирован.")
            return

        # Валидация лага повторно, на случай если пользователь долго думал
        existing_slots = await session.execute(
            select(Slot)
            .where(
                Slot.barista_id == db_user.id,
                Slot.end_time > datetime.now(), # Только будущие слоты баристы
                Slot.status.in_([SlotStatus.BOOKED, SlotStatus.CONFIRMED])
            )
        )
        existing_slots = existing_slots.scalars().all()

        can_book = True
        for existing_slot in existing_slots:
            time_diff1 = abs((slot.start_time - existing_slot.end_time).total_seconds()) / 60
            time_diff2 = abs((existing_slot.start_time - slot.end_time).total_seconds()) / 60

            if (slot.start_time < existing_slot.end_time and slot.end_time > existing_slot.start_time):
                can_book = False
                await query.edit_message_text(
                    f"К сожалению, кто-то успел забронировать слот, который пересекается с вашим текущим бронированием. "
                    f"*{existing_slot.start_time.strftime('%d.%m %H:%M')}-{existing_slot.end_time.strftime('%H:%M')}*."
                )
                return

            if (slot.start_time.date() == existing_slot.start_time.date() and
                slot.cafe_id != existing_slot.cafe_id and 
                (time_diff1 < MIN_TIME_LAG_MINUTES or time_diff2 < MIN_TIME_LAG_MINUTES)):

                can_book = False
                await query.edit_message_text(
                    f"К сожалению, кто-то успел забронировать слот, который нарушает временной лаг. "
                    f"Между сменами в разных кофейнях необходимо минимум {MIN_TIME_LAG_MINUTES} минут."
                )
                return

        if not can_book:
            return

        # Бронируем слот
        slot.barista_id = db_user.id
        slot.status = SlotStatus.BOOKED
        await session.commit()
        await session.refresh(slot)

        date_str = slot.start_time.strftime("%d.%m.%Y")
        time_str = slot.start_time.strftime("%H:%M") + " - " + slot.end_time.strftime("%H:%M")

        await query.edit_message_text(
            f"✅ Вы успешно забронировали слот в *{slot.cafe.name}*:\n"
            f"📅 Дата: *{date_str}*\n"
            f"⏰ Время: *{time_str}*\n\n"
            f"Удачной смены!",
            parse_mode='Markdown'
        )
        logger.info(f"User {db_user.id} booked slot {slot.id} in cafe {slot.cafe.id}.")

async def my_slots_command(update: Update, context: CallbackContext) -> None:
    """Показывает забронированные слоты бариста."""
    user_telegram_id = str(update.effective_user.id)

    async with get_async_session() as session:
        db_user = await session.execute(select(User).where(User.telegram_id == user_telegram_id))
        db_user = db_user.scalar_one_or_none()

        if not db_user or db_user.role != Role.BARISTA or db_user.registration_status != RegistrationStatus.APPROVED:
            await update.message.reply_text("Вы не зарегистрированы как одобренный бариста.")
            return

        today = datetime.now()
        # Получаем только будущие и актуальные слоты (BOOKED, CONFIRMED)
        slots = await session.execute(
            select(Slot)
            .where(
                Slot.barista_id == db_user.id,
                Slot.end_time > today, # Только будущие или текущие слоты
                Slot.status.in_([SlotStatus.BOOKED, SlotStatus.CONFIRMED])
            )
            .order_by(Slot.start_time)
            .options(selectinload(Slot.cafe))
        )
        slots = slots.scalars().all()

        if not slots:
            await update.message.reply_text("У вас пока нет забронированных слотов.")
            return

        text = "Ваши забронированные слоты:\n\n"
        for slot in slots:
            date_str = slot.start_time.strftime("%d.%m.%Y")
            time_str = slot.start_time.strftime("%H:%M") + " - " + slot.end_time.strftime("%H:%M")
            status_map = {
                SlotStatus.BOOKED: "Забронирован",
                SlotStatus.CONFIRMED: "Вы подтвердили выход",
            }
            status_text = status_map.get(slot.status, slot.status.value)
            text += f"*{date_str}* | {time_str} | {slot.cafe.name} | _Статус: {status_text}_\n"

        await update.message.reply_text(text, parse_mode='Markdown')

async def going_command(update: Update, context: CallbackContext) -> None:
    """Предлагает подтвердить выход на ближайший слот."""
    user_telegram_id = str(update.effective_user.id)

    async with get_async_session() as session:
        db_user = await session.execute(select(User).where(User.telegram_id == user_telegram_id))
        db_user = db_user.scalar_one_or_none()

        if not db_user or db_user.role != Role.BARISTA or db_user.registration_status != RegistrationStatus.APPROVED:
            await update.message.reply_text("У вас нет прав для выполнения этого действия.")
            return

        now = datetime.now()
        # Ищем ближайший слот, который забронирован, но еще не подтвержден и не начался
        # Слот должен быть не ранее, чем через час (чтобы успеть доехать) и не позднее, чем начинается

        # Находим ближайший слот, который еще не подтвержден и не завершился
        # и до его начала осталось, скажем, не более 24 часов (чтобы не предлагать очень дальние)
        # и не менее 30 минут (чтобы было время, если команда вызвана заранее)

        # Для простоты, найдем ближайший BOOKED слот, который ещё не начался
        closest_slot = await session.execute(
            select(Slot)
            .where(
                Slot.barista_id == db_user.id,
                Slot.status == SlotStatus.BOOKED,
                Slot.start_time >= now # Слот ещё не начался
            )
            .order_by(Slot.start_time)
            .options(selectinload(Slot.cafe))
        )
        closest_slot = closest_slot.scalar_one_or_none()

        if not closest_slot:
            await update.message.reply_text("У вас нет слотов, для которых можно подтвердить выход.")
            return

        # Проверяем, сколько времени осталось до начала слота
        time_until_start = closest_slot.start_time - now

        # Можно добавить логику, что подтверждать можно за N часов до начала и не позднее M минут после начала
        # Например, если слот начинается через 10 минут, или уже начался, но не более часа назад

        if time_until_start > timedelta(hours=24): # Если слот слишком далеко
             await update.message.reply_text(
                f"Ваш ближайший слот {closest_slot.start_time.strftime('%d.%m %H:%M')} в {closest_slot.cafe.name}. "
                "Подтверждение выхода возможно ближе к началу смены."
            )
             return

        if time_until_start < timedelta(minutes=-60): # Если слот начался более часа назад
            await update.message.reply_text(
                f"Ваш ближайший слот {closest_slot.start_time.strftime('%d.%m %H:%M')} в {closest_slot.cafe.name} уже завершился или был пропущен. "
                "Выход на эту смену подтвердить невозможно."
            )
            return


        date_str = closest_slot.start_time.strftime("%d.%m.%Y")
        time_str = closest_slot.start_time.strftime("%H:%M") + " - " + closest_slot.end_time.strftime("%H:%M")

        text = (
            f"Ваш ближайший запланированный слот:\n"
            f"В кофейне: *{closest_slot.cafe.name}* ({closest_slot.cafe.address})\n"
            f"Дата: *{date_str}*\n"
            f"Время: *{time_str}*\n\n"
            f"Подтвердите, что вы выходите на смену."
        )

        keyboard = [[InlineKeyboardButton("✅ Я иду на смену!", callback_data=f"confirm_going:{closest_slot.id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def confirm_going_callback(update: Update, context: CallbackContext) -> None:
    """Подтверждает выход бариста на смену."""
    query = update.callback_query
    await query.answer()

    slot_id = int(query.data.split(':')[1])
    user_telegram_id = str(query.from_user.id)

    async with get_async_session() as session:
        db_user = await session.execute(select(User).where(User.telegram_id == user_telegram_id))
        db_user = db_user.scalar_one_or_none()

        if not db_user or db_user.role != Role.BARISTA or db_user.registration_status != RegistrationStatus.APPROVED:
            await query.edit_message_text("У вас нет прав для выполнения этого действия.")
            return

        slot = await session.execute(
            select(Slot)
            .where(Slot.id == slot_id, Slot.barista_id == db_user.id)
            .options(selectinload(Slot.cafe))
        )
        slot = slot.scalar_one_or_none()

        if not slot:
            await query.edit_message_text("Слот не найден или не принадлежит вам.")
            return

        if slot.status == SlotStatus.CONFIRMED:
            await query.edit_message_text("Выход на эту смену уже подтвержден ранее.")
            return

        if slot.status != SlotStatus.BOOKED:
            await query.edit_message_text(f"Статус слота ({slot.status.value}) не позволяет подтвердить выход.")
            return

        # Обновляем статус слота
        slot.status = SlotStatus.CONFIRMED
        await session.commit()
        await session.refresh(slot)

        date_str = slot.start_time.strftime("%d.%m.%Y")
        time_str = slot.start_time.strftime("%H:%M") + " - " + slot.end_time.strftime("%H:%M")

        await query.edit_message_text(
            f"🎉 Отлично! Вы подтвердили выход на смену в *{slot.cafe.name}*:\n"
            f"📅 Дата: *{date_str}*\n"
            f"⏰ Время: *{time_str}*\n"
            f"Ждем вас!",
            parse_mode='Markdown'
        )
        logger.info(f"User {db_user.id} confirmed going for slot {slot.id}.")
