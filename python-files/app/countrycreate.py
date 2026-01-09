import html
from aiogram import Router, types, F, Bot 
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandObject
from datetime import datetime, timedelta 
from aiogram.enums import ParseMode, ChatType
from aiogram.enums import ContentType 
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Tuple
from sqlalchemy import func

from config import REVIEW_COOLDOWN_DAYS
from .database.models import User, MemeCountry, CountryReview

from .review_service import ReviewService
import app.keyboard as kb
import logging

# Устанавливаем КД в секундах (например, 7 дней)
COUNTRY_CREATE_COOLDOWN = 7 * 24 * 60 * 60 # 604800 секунд

from .database.requests import (
    get_or_create_user, 
    get_full_user_profile, 
    db_ensure_full_user_profile,
    create_meme_country, 
    assign_ruler, 
    get_country_by_name, 
    join_country, 
    leave_country,
    get_my_country_stats,
    transfer_ruler,
    delete_country,
    set_position,
    kick_user,
    set_tax_rate,
    collect_taxes,
    get_all_countries,
    get_global_stats,
    has_active_country_ban,
    check_creation_allowed,
    get_creation_status,
    edit_country_name,
    edit_country_ideology,
    edit_country_description,
    edit_country_map_url,
    edit_country_flag,
    edit_country_memename,
    get_country_by_ruler_id
)
logger = logging.getLogger(__name__)

# ==========================================
# ПРОВЕРКА ПРАВИТЕЛЯ
# ==========================================
async def check_ruler_permissions(message: types.Message, session: AsyncSession) -> tuple[bool, MemeCountry | None, User | None]:
    """
    Проверяет, является ли пользователь правителем страны.
    Возвращает (успех, страна, пользователь).
    """
    user = await session.get(User, message.from_user.id)
    
    if not user or not user.country_id:
        await message.answer("❌ Вы не состоите в стране.")
        return False, None, None
    
    country = await session.get(MemeCountry, user.country_id)
    if not country or country.ruler_id != user.user_id:
        await message.answer("🚫 Вы не правитель этой страны.")
        return False, None, None
    
    return True, country, user

# Создаем роутер для этого функционала
country_create_router = Router()

# ==========================================
# 1. КОНЕЧНЫЕ АВТОМАТЫ СОСТОЯНИЙ (FSM)
# ==========================================

class CountryCreateStates(StatesGroup):
    """Определяет шаги для создания мемной страны."""
    memename = State()
    ideology = State() 
    map_url = State()
    transfer_target_id = State() 
    waiting_for_flag = State()

class CountryEditStates(StatesGroup):
    """Шаги для изменения страны"""
    choose_field = State()
    edit_memename = State()
    edit_ideology = State()
    edit_map_url = State()
    edit_description = State()


# ==========================================
# A. ХЕНДЛЕР: НАЧАЛО /createcountry
# ==========================================
@country_create_router.message(Command("createcountry"))
async def cmd_create_country(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # 1. Сразу проверяем статус в чате (API Telegram)
    # Владелец — "creator". Админы — "administrator".
    chat_member = await bot.get_chat_member(chat_id, user_id)
    is_owner = chat_member.status == "creator"

    # 2. Получаем данные из БД (через твой requests.py)
    profile, is_banned = await get_creation_status(session, user_id)
    
    if profile is None:
        profile, _ = await db_ensure_full_user_profile(
            session, user_id, 
            message.from_user.username or "Unknown", 
            message.from_user.full_name or "Unknown"
        )

    # 3. Расширенный match-case (добавили 5-й параметр: is_owner)
    # Структура: (Тип чата, Есть страна, Кулдаун, Бан, Владелец чата)
    match (message.chat.type, profile.country_id is not None, profile.last_country_creation, is_banned, is_owner):
        
        # Проверка на тип чата
        case (chat_type, _, _, _, _) if chat_type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer("🚫 Команда работает только в групповых чатах.")
            return

        # Проверка на владение чатом (Новое!)
        case (_, _, _, _, False):
            await message.answer("🚫 Основать страну может только <b>Владелец чата</b>.", parse_mode="HTML")
            return
            
        # Уже состоит в стране
        case (_, True, _, _, _):
            # Убедись, что в get_creation_status есть selectinload(User.country)
            safe_name = html.escape(profile.country.name if profile.country else "Неизвестно")
            await message.answer(f"🚫 Ты уже в стране <b>{safe_name}</b>. Выйди через /leave.", parse_mode="HTML")
            return
            
        # Активный бан
        case (_, _, _, True, _):
            await message.reply("❌ У тебя активный бан на создание стран.")
            return
            
        # Кулдаун (проверка времени)
        case (_, _, last_creation, _, _) if last_creation and (datetime.now() - last_creation).total_seconds() < COUNTRY_CREATE_COOLDOWN:
            remaining = int(COUNTRY_CREATE_COOLDOWN - (datetime.now() - last_creation).total_seconds())
            await message.answer(f"⏳ Кулдаун! Жди <b>{str(timedelta(seconds=remaining))}</b>", parse_mode="HTML")
            return
            
        # Успешный запуск FSM
        case _:
            chat_info = await bot.get_chat(chat_id)
            await state.update_data(
                chat_id=chat_id,
                name=chat_info.title or "Без названия",
                flag_url=chat_info.photo.big_file_id if chat_info.photo else None,
            )
            await state.set_state(CountryCreateStates.memename)
            await message.answer(
                f"📝 <b>Основание державы: {html.escape(chat_info.title or '')}</b>\n"
                "Шаг 1/3: Введите <b>МЕМ</b> вашей страны (основу).",
                parse_mode="HTML"
            )
# ==========================================
# B. ХЕНДЛЕР FSM: 1/3 Ввод Мема Страны
# ==========================================
@country_create_router.message(CountryCreateStates.memename, F.text)
async def process_memename(message: types.Message, state: FSMContext, session: AsyncSession):
    memename = message.text.strip()
    
    if len(memename) > 100:
        await message.answer("⚠️ Мемное название слишком длинное (Максимум 100 символов).")
        return
    
    await state.update_data(memename=memename)
    
    # 🔥 ПЕРЕХОД К СЛЕДУЮЩЕМУ СОСТОЯНИЮ (ideology)
    await state.set_state(CountryCreateStates.ideology)
    
    await message.answer(
        "⚙️ Записано! Шаг 2 из 3: Введите **ИДЕОЛОГИЮ** вашей страны (3-50 символов)."
    )

@country_create_router.message(CountryCreateStates.memename)
async def process_memename_invalid(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите <b>текст</b>.", parse_mode=ParseMode.HTML)

# ==========================================
# C. ХЕНДЛЕР FSM: 2/3 Ввод Идеологии
# ==========================================

@country_create_router.message(CountryCreateStates.ideology, F.text)
async def process_ideology_save(message: types.Message, state: FSMContext):
    ideology_text = message.text.strip()
    
    # Валидация
    if not (3 <= len(ideology_text) <= 50):
        await message.answer(
            "⚠️ Идеология должна быть длиной от <b>3 до 50 символов</b>.\n"
            "Попробуйте ввести другую идеологию:",
            parse_mode=ParseMode.HTML
        )
        return

    await state.update_data(ideology=ideology_text)
    await state.set_state(CountryCreateStates.map_url) 

    # Исправлена нумерация шага (Шаг 3 из 3)
    await message.answer(
        "✅ Идеология принята.\n"
        "Шаг <b>3 из 3</b>: Введите <b>ссылку на Карту</b> (URL) вашей страны.\n" 
        "*(Если карты нет, введите прочерк '-')*",
        parse_mode=ParseMode.HTML
    )

@country_create_router.message(CountryCreateStates.ideology)
async def process_ideology_invalid(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите <b>текст</b>.", parse_mode=ParseMode.HTML)

# ==========================================
# D. ХЕНДЛЕР FSM: 3/3 Ввод URL и ФИНАЛЬНАЯ ТРАНЗАКЦИЯ
# ==========================================
@country_create_router.message(CountryCreateStates.map_url, F.text)
async def process_map_url_and_finish(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    map_url_text = message.text.strip()
    user_id = message.from_user.id
    chat_id = message.chat.id
    final_map_url = None if map_url_text == '-' else map_url_text

    fsm_data = await state.get_data()

    try:
        # 1. Создаём страну
        new_country = await create_meme_country(
            session=session,
            ruler_id=user_id,
            chat_id=fsm_data['chat_id'],
            name=fsm_data['name'],
            description=fsm_data.get('description', "Описание не предоставлено."),
            ideology=fsm_data['ideology'],
            avatar_url=fsm_data.get('flag_url'),
            memename=fsm_data['memename'],
            map_url=fsm_data.get('map_url', None)
        )

        await session.flush()

        # 2. Назначаем правителя
        await assign_ruler(
            session=session,
            user_id=user_id,
            country_id=new_country.country_id
        )

        # 3. Коммит и очистка
        await state.clear()

        # 4. Успешное сообщение
        country_name_safe = html.escape(new_country.name)
        memename_info = f" (Мем: {html.escape(new_country.memename)})" if new_country.memename else ""

        final_message = (
            f"🎉 <b>ПОЗДРАВЛЯЕМ!</b> 🎉\n"
            f"Страна <b>{country_name_safe}</b>{memename_info} успешно создана!\n"
            f"Идеология: <i>{html.escape(new_country.ideology)}</i>\n"
            f"👑 Вы — первый и единственный Правитель!\n\n"
            f"✨ +10 очков влияния за основание государства!\n"
            f"Теперь приглашайте граждан и развивайте свою мемную империю! 🏰"
        )

        # Явно указываем parse_mode — чтобы не было конфликта
        await message.answer(final_message, parse_mode=ParseMode.HTML)

    except Exception as e:
        await state.clear()
        logger.error("Ошибка при создании страны: %s", e)

        error_msg = "❌ Произошла непредвиденная ошибка. Попробуйте позже."

        if "unique constraint" in str(e).lower():
            if "chat_id" in str(e):
                error_msg = "❌ В этом чате уже есть страна!"
            elif "name" in str(e):
                error_msg = "❌ Страна с таким названием уже существует!"
            elif "memename" in str(e):
                error_msg = "❌ Мемное имя уже занято другой страной!"

        # Используем message.answer — он точно работает с дефолтным parse_mode
        await message.answer(error_msg) 

@country_create_router.message(CountryCreateStates.map_url)
async def process_map_url_invalid(message: types.Message):
    await message.answer("⚠️ Введите <b>текст</b> ссылки или прочерк '-'.", parse_mode=ParseMode.HTML)


@country_create_router.message(Command("editcountry"))
async def cmd_edit_country(message: types.Message, state: FSMContext, session: AsyncSession):
    success, country, user = await check_ruler_permissions(message, session)
    if not success:
        return
    
    await state.set_state(CountryEditStates.choose_field)
    await message.answer(
        f"🔧 <b>Редактирование страны: {country.name}</b>\n\n"
        "Выберите что хотите изменить:",
        parse_mode="HTML",
        reply_markup=kb.country_edit_keyboard()
    )
    await state.set_state(CountryEditStates.choose_field)


# ==========================================
# E. УСТАНОВКА ФЛАГА (/setflag)
# ==========================================

@country_create_router.message(Command("setflag"))
async def cmd_set_flag(message: types.Message, state: FSMContext, **kwargs):
    """Начало процесса установки флага"""
    await state.set_state(CountryCreateStates.waiting_for_flag)
    await message.answer(
        "🖼 <b>Отправьте изображение</b>, которое станет флагом вашей страны.\n\n"
        "<i>Совет: лучше использовать квадратные изображения.</i>",
        parse_mode="HTML"
    )

@country_create_router.message(CountryCreateStates.waiting_for_flag, F.photo)
async def process_flag_image(
    message: types.Message, 
    state: FSMContext, 
    session: AsyncSession
):
    """Принимаем фото и сохраняем его file_id в базу"""
    user_id = message.from_user.id
    
    # Проверяем, что пользователь является правителем через requests.py
    country = await get_country_by_ruler_id(session, user_id)
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    # Берем последний (самый большой) file_id из списка PhotoSize
    new_flag_id = message.photo[-1].file_id
    
    success, msg = await edit_country_flag(session, user_id, new_flag_id)
    await message.answer(msg)
    await state.clear()

@country_create_router.message(CountryCreateStates.waiting_for_flag)
async def process_flag_invalid(message: types.Message):
    """Если юзер прислал не фото"""
    await message.answer("⚠️ Пожалуйста, отправьте именно <b>фотографию</b>.")


# ==========================================
# F. РЕДАКТИРОВАНИЕ СТРАНЫ (/editcountry)
# ==========================================

# Клавиатура для выбора поля редактирования
def country_edit_keyboard():
    """Создаем клавиатуру для выбора поля редактирования"""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="📝 Название", callback_data="edit:name"),
                types.InlineKeyboardButton(text="🎭 Идеология", callback_data="edit:ideology")
            ],
            [
                types.InlineKeyboardButton(text="🗺 Карта", callback_data="edit:map"),
                types.InlineKeyboardButton(text="📜 Описание", callback_data="edit:description")
            ],
            [
                types.InlineKeyboardButton(text="🖼 Флаг", callback_data="edit:flag"),
                types.InlineKeyboardButton(text="❌ Отмена", callback_data="edit:cancel")
            ]
        ]
    )

# Обработчик выбора поля
@country_create_router.callback_query(CountryEditStates.choose_field)
async def process_edit_choice(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_id = callback.from_user.id
    
    # Проверяем, что пользователь является правителем через requests.py
    country = await get_country_by_ruler_id(session, user_id)
    
    if not country:
        await callback.answer("🚫 Вы не правитель этой страны!", show_alert=True)
        return
    
    action = callback.data.split(":")[1]
    
    match action:
        case "name":
            await state.set_state(CountryEditStates.edit_memename)
            await callback.message.edit_text(
                f"📝 <b>Изменение названия страны</b>\n\n"
                f"Текущее название: {country.name}\n"
                f"Введите новое название (максимум 100 символов):",
                parse_mode="HTML"
            )
        
        case "ideology":
            await state.set_state(CountryEditStates.edit_ideology)
            await callback.message.edit_text(
                f"🎭 <b>Изменение идеологии страны</b>\n\n"
                f"Текущая идеология: {country.ideology}\n"
                f"Введите новую идеологию (3-50 символов):",
                parse_mode="HTML"
            )
        
        case "map":
            await state.set_state(CountryEditStates.edit_map_url)
            await callback.message.edit_text(
                f"🗺 <b>Изменение карты страны</b>\n\n"
                f"Текущая карта: {country.map_url or 'Не указана'}\n"
                f"Введите новую ссылку на карту или '-' если нет карты:",
                parse_mode="HTML"
            )
        
        case "description":
            await state.set_state(CountryEditStates.edit_description)
            await callback.message.edit_text(
                f"📜 <b>Изменение описания страны</b>\n\n"
                f"Текущее описание: {country.description}\n"
                f"Введите новое описание (максимум 1000 символов):",
                parse_mode="HTML"
            )
        
        case "flag":
            await state.set_state(CountryCreateStates.waiting_for_flag)
            await callback.message.edit_text(
                f"🖼 <b>Изменение флага страны</b>\n\n"
                "Отправьте новое изображение для флага:",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        case "cancel":
            await state.clear()
            await callback.message.edit_text("❌ Редактирование отменено.")
            await callback.answer()
            return
    
    await callback.answer()


# Редактирование названия
@country_create_router.message(CountryEditStates.edit_memename, F.text)
async def process_edit_name(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    new_name = message.text.strip()
    
    if len(new_name) > 100:
        await message.answer("⚠️ Название слишком длинное (максимум 100 символов).")
        return
    
    # Проверяем, что пользователь является правителем через requests.py
    country = await get_country_by_ruler_id(session, user_id)
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    success, msg = await edit_country_name(session, user_id, new_name)
    await message.answer(msg)
    await state.clear()

@country_create_router.message(CountryEditStates.edit_memename)
async def process_edit_name_invalid(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите <b>текст</b>.")

# Редактирование идеологии
@country_create_router.message(CountryEditStates.edit_ideology, F.text)
async def process_edit_ideology(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    new_ideology = message.text.strip()
    
    if not (3 <= len(new_ideology) <= 50):
        await message.answer("⚠️ Идеология должна быть длиной от 3 до 50 символов.")
        return
    
    # Проверяем, что пользователь является правителем через requests.py
    country = await get_country_by_ruler_id(session, user_id)
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    success, msg = await edit_country_ideology(session, user_id, new_ideology)
    await message.answer(msg)
    await state.clear()

@country_create_router.message(CountryEditStates.edit_ideology)
async def process_edit_ideology_invalid(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите <b>текст</b>.")

# Редактирование карты
@country_create_router.message(CountryEditStates.edit_map_url, F.text)
async def process_edit_map_url(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    new_map_url = message.text.strip()
    final_map_url = None if new_map_url == '-' else new_map_url
    
    # Проверяем, что пользователь является правителем через requests.py
    country = await get_country_by_ruler_id(session, user_id)
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    success, msg = await edit_country_map_url(session, user_id, new_map_url)
    await message.answer(msg)
    await state.clear()

@country_create_router.message(CountryEditStates.edit_map_url)
async def process_edit_map_url_invalid(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите <b>текст</b> или '-'.")


# Редактирование описания
@country_create_router.message(CountryEditStates.edit_description, F.text)
async def process_edit_description(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    new_description = message.text.strip()
    
    if len(new_description) > 1000:
        await message.answer("⚠️ Описание слишком длинное (максимум 1000 символов).")
        return
    
    # Проверяем, что пользователь является правителем через requests.py
    country = await get_country_by_ruler_id(session, user_id)
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    success, msg = await edit_country_description(session, user_id, new_description)
    await message.answer(msg)
    await state.clear()

@country_create_router.message(CountryEditStates.edit_description)
async def process_edit_description_invalid(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите <b>текст</b>.")

# Обработка отмены редактирования
@country_create_router.message(Command("cancel"))
async def cmd_cancel_edit(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    
    await state.clear()
    await message.answer("❌ Редактирование отменено.")


# ==========================================
# G. БЫСТРОЕ РЕДАКТИРОВАНИЕ ЧЕРЕЗ АРГУМЕНТЫ
# ==========================================

@country_create_router.message(Command("setname"))
async def cmd_set_name(message: types.Message, session: AsyncSession, command: CommandObject):
    user_id = message.from_user.id
    
    if not command.args:
        await message.answer("❗ Введите новое название: /setname Новое Название")
        return
    
    new_name = command.args.strip()
    
    # Проверяем, что пользователь является правителем
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == user_id)
    )
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    if len(new_name) > 100:
        await message.answer("⚠️ Название слишком длинное (максимум 100 символов).")
        return
    
    old_name = country.name
    country.name = new_name
    
    await message.answer(
        f"✅ Название успешно изменено!\n"
        f"Было: {old_name}\n"
        f"Стало: {new_name}"
    )

@country_create_router.message(Command("setideology"))
async def cmd_set_ideology(message: types.Message, session: AsyncSession, command: CommandObject):
    user_id = message.from_user.id
    
    if not command.args:
        await message.answer("❗ Введите новую идеологию: /setideology Новая Идеология")
        return
    
    new_ideology = command.args.strip()
    
    # Проверяем, что пользователь является правителем
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == user_id)
    )
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    if not (3 <= len(new_ideology) <= 50):
        await message.answer("⚠️ Идеология должна быть длиной от 3 до 50 символов.")
        return
    
    old_ideology = country.ideology
    country.ideology = new_ideology
    
    await message.answer(
        f"✅ Идеология успешно изменена!\n"
        f"Было: {old_ideology}\n"
        f"Стало: {new_ideology}"
    )

@country_create_router.message(Command("setdescription"))
async def cmd_set_description(message: types.Message, session: AsyncSession, command: CommandObject):
    user_id = message.from_user.id
    
    if not command.args:
        await message.answer("❗ Введите новое описание: /setdescription Новое Описание")
        return
    
    new_description = command.args.strip()
    
    # Проверяем, что пользователь является правителем
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == user_id)
    )
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    if len(new_description) > 1000:
        await message.answer("⚠️ Описание слишком длинное (максимум 1000 символов).")
        return
    
    old_description = country.description
    country.description = new_description
    
    await message.answer(
        f"✅ Описание успешно изменено!\n"
        f"Было: {old_description}\n"
        f"Стало: {new_description}"
    )

@country_create_router.message(Command("setmap"))
async def cmd_set_map(message: types.Message, session: AsyncSession, command: CommandObject):
    user_id = message.from_user.id
    
    if not command.args:
        await message.answer("❗ Введите ссылку на карту: /setmap https://example.com/map")
        return
    
    new_map_url = command.args.strip()
    final_map_url = None if new_map_url == '-' else new_map_url
    
    # Проверяем, что пользователь является правителем
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == user_id)
    )
    
    if not country:
        await message.answer("🚫 Вы не правитель этой страны!")
        return
    
    old_map_url = country.map_url
    
    country.map_url = final_map_url
    
    old_display = old_map_url or "Не указана"
    new_display = final_map_url or "Не указана"
    
    await message.answer(
        f"✅ Карта успешно изменена!\n"
        f"Было: {old_display}\n"
        f"Стало: {new_display}"
    )

@country_create_router.message(Command("setflag"))
async def cmd_set_flag_fsm(message: types.Message, state: FSMContext, **kwargs):
    """Начало процесса установки флага через FSM"""
    await state.set_state(CountryCreateStates.waiting_for_flag)
    await message.answer(
        "🖼 <b>Отправьте изображение</b>, которое станет флагом вашей страны.\n\n"
        "<i>Совет: лучше использовать квадратные изображения.</i>",
        parse_mode="HTML"
    )


# ==========================================
# 2. ХЕНДЛЕР: ВСТУПЛЕНИЕ В СТРАНУ (/join)
# ==========================================
@country_create_router.message(Command("join")) 
async def cmd_join_country_explicit(
    message: types.Message,
    session: AsyncSession,
    command: CommandObject
):
    user_id = message.from_user.id
    
    if not command.args:
        await message.answer(
            "🚫 <b>Укажите ID или название страны.</b>\n"
            "Примеры:\n"
            "  - <code>/join 3</code> (по ID)\n"
            "  - <code>/join Аторния</code> (по названию)", 
            parse_mode=ParseMode.HTML
        )
        return
        
    # Просто берем всё, что ввел пользователь после команды
    user_input = command.args.strip()
    
    # Автоматически определяем метод поиска
    if user_input.isdigit():
        search_method = "id"
        search_value = user_input
    else:
        search_method = "name"
        search_value = user_input

    try:
        # Вызываем твою логику вступления
        success, response_text = await join_country(
            session=session, 
            user_id=user_id, 
            search_method=search_method,
            search_value=search_value
        )

        await message.answer(response_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logging.exception(f"Ошибка в /join: {e}")
        await message.answer(
            "❌ <b>Произошла критическая ошибка.</b>\nПопробуйте позже.",
            parse_mode=ParseMode.HTML
        )
    
        # лог — обязательно
    logging.exception("Ошибка в /join")
# ==========================================
# 3. ХЕНДЛЕР: ВЫХОД ИЗ СТРАНЫ (/leave)
# ==========================================

@country_create_router.message(Command("leave"))
async def cmd_leave_country(message: types.Message, session: AsyncSession):
    """Позволяет пользователю покинуть текущую мемную страну."""
    user_id = message.from_user.id
    
    try:
        success, msg, country_name = await leave_country(
            session=session,
            user_id=user_id
        )
        
        if success:
            await message.answer(
                f"👋 Вы успешно покинули страну **{country_name}**.", 
                parse_mode='HTML'
            )
        else:
            await message.answer(f"❌ Не удалось покинуть страну: {msg}")
            
    except Exception as e:
        logger.error("Ошибка при выполнении команды /leave: %s", e)
        await message.answer("⛔️ Произошла системная ошибка при выходе. Попробуйте позже.")


# ==========================================
# 4. ХЕНДЛЕР: МОЯ СТРАНА (/mycountry)
# ==========================================
@country_create_router.message(Command("mycountry"))
@country_create_router.message(Command("country"))
async def cmd_my_country(message: types.Message, session: AsyncSession, **kwargs): # Добавили **kwargs
    user_id = message.from_user.id
    
    # Получаем данные через твой requests.py
    stats = await get_my_country_stats(session, user_id)
    
    if not stats:
        await message.answer(
            "🏚 <b>Вы бездомный странник.</b>\n"
            "Вы не состоите ни в одной стране.\n\n"
            "Используйте <code>/createcountry</code> чтобы создать свою,\n"
            "или <code>/join [ID]</code> чтобы вступить в чужую.",
            parse_mode=ParseMode.HTML
        )
        return

    country = stats["country"]
    citizens_count = stats["citizens_count"]
    total_citizen_points = stats["citizens_total_points"]
    
    # Форматирование (используем html.escape для безопасности)
    name_safe = html.escape(country.name)
    meme_safe = html.escape(country.memename or "Не указан")
    ideology_safe = html.escape(country.ideology or "Не определена")
    desc_safe = html.escape(country.description or "Описание отсутствует")
    ruler_name = html.escape(country.ruler.userfullname if country.ruler else "Отсутствует")
    
    map_link = ""
    if country.map_url and country.map_url != '-':
        map_link = f"\n🗺 <a href='{country.map_url}'>Карта территории</a>"

    text = (
        f"🚩 <b>ГОСУДАРСТВО: {name_safe}</b>\n"
        f"<i>{desc_safe}</i>\n\n"
        f"👑 <b>Правитель:</b> {ruler_name}\n"
        f"🧠 <b>Идеология:</b> {ideology_safe}\n"
        f"🤣 <b>Мем-основа:</b> {meme_safe}\n"
        f"🆔 <b>ID страны:</b> <code>{country.country_id}</code>\n"
        f"{map_link}\n"
        f"──────────────────\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"👥 <b>Население:</b> {citizens_count} чел.\n"
        f"✨ <b>Очки Влияния (Страна):</b> {country.influence_points}\n"
        f"💎 <b>Богатство граждан:</b> {total_citizen_points}\n"
        f"⭐ <b>Рейтинг:</b> {country.avg_rating:.1f}"
    )
    
    # Пытаемся отправить фото, если оно есть
    if country.avatar_url:
        try:
            await message.answer_photo(
                photo=country.avatar_url,
                caption=text,
                parse_mode=ParseMode.HTML
            )
            return # Если отправили фото, выходим из функции
        except Exception as e:
            # Если file_id битый или тип ChatPhoto — логируем и шлем текстом
            logger.error(f"Ошибка отправки фото страны {country.country_id}: {e}")
            # Не делаем return, код пойдет дальше и отправит текст ниже

    # Отправляем текстом (если фото нет или оно выдало ошибку)
    await message.answer(
        text=text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

# ===============================================================
# ХЕЛПЕР ФУНКЦИЯ ДЛЯ ПОИСКА ЦЕЛИ (ПО REPLY ИЛИ ARGS)
# ===============================================================
async def get_target_user(
    message: Message,
    session: AsyncSession,
) -> User | None:
    """
    Возвращает User по reply или аргументу (/cmd <id|@username>)
    """

    # reply
    if message.reply_to_message:
        tg_user = message.reply_to_message.from_user
        if not tg_user or tg_user.is_bot:
            return None

        return await session.get(User, tg_user.id)

    # args
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return None

    target = parts[1]

    if target.isdigit():
        return await session.get(User, int(target))

    username = target.lstrip("@")
    return await session.scalar(
        select(User).where(func.lower(User.username) == username.lower())
    )

# ===============================================================
# КОМАНДЫ С ДЕКОРАТОРАМИ
# ===============================================================

# ==========================================
# 6. ПЕРЕДАЧА ВЛАСТИ (/transferruler)
# ==========================================
@country_create_router.message(Command("transferruler"))
async def cmd_transfer_ruler(message: types.Message, session: AsyncSession, **kwargs):
    success, country, user = await check_ruler_permissions(message, session)
    if not success:
        return
        
    # Используем твой хелпер для поиска цели
    target_user = await get_target_user(message, session)
    
    if not target_user or target_user.user_id == message.from_user.id:
        await message.answer("❗ Формат: /transferruler <id|@username> (или ответом)")
        return
    
    success, msg = await transfer_ruler(session, message.from_user.id, target_user.user_id, user.country_id)
    await message.answer(f"👑 {msg}")

# ==========================================
# 7. УДАЛЕНИЕ СТРАНЫ (/deletecountry)
# ==========================================
@country_create_router.message(Command("deletecountry"))
async def cmd_delete_country(message: types.Message, session: AsyncSession, **kwargs):
    success, country, user = await check_ruler_permissions(message, session)
    if not success:
        return
        
    success, msg = await delete_country(session, user.user_id, country.country_id)
    await message.answer(f"💥 {msg}")

# ==========================================
# 8. НАЗНАЧЕНИЕ ДОЛЖНОСТИ (/settax)
# ==========================================
@country_create_router.message(Command("settax"))
async def cmd_set_tax_rate(message: types.Message, session: AsyncSession, **kwargs):
    success, country, user = await check_ruler_permissions(message, session)
    if not success:
        return
        
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❗ Укажите процент: /settax 10")
        return
    
    try:
        rate = float(args[1]) / 100.0
        if not 0 <= rate <= 0.5:
            return await message.answer("❗ Налог от 0% до 50%.")
            
        success, msg = await set_tax_rate(session, user.user_id, rate)
        await message.answer(f"💰 {msg}")
    except ValueError:
        await message.answer("❗ Введите число.")

# ==========================================
# 9. ВЫГОН ГРАЖДАНИНА (/kick)
# ==========================================
@country_create_router.message(Command("kick"))
async def cmd_kick_user(message: types.Message, session: AsyncSession, **kwargs):
    success, country, user = await check_ruler_permissions(message, session)
    if not success:
        return
        
    target_user = await get_target_user(message, session)
    if not target_user:
        await message.answer("❗ Укажите кого кикнуть (id|@username|reply)")
        return
    
    success, msg = await kick_user(session, user.user_id, target_user.user_id)
    await message.answer(f"🦶 {msg}")
# ==========================================
# 10. УСТАНОВКА НАЛОГА (/setposition)
# ==========================================
@country_create_router.message(Command("setposition"))
async def cmd_set_position(message: Message, session: AsyncSession, command: CommandObject, **kwargs):
    success, country, user = await check_ruler_permissions(message, session)
    if not success:
        return
        
    if not command.args:
        await message.answer("❗ Формат: /setposition <должность> [id|@username|reply]")
        return

    # Разбираем аргументы
    args = command.args.strip().split()
    
    if len(args) < 1:
        await message.answer("❗ Введите название должности.")
        return
    
    pos_name = args[0]
    target_id = None
    
    # Ищем цель: сначала в аргументах, потом в реплае
    if len(args) > 1:
        target_arg = args[1]
        
        # Если это ID
        if target_arg.isdigit():
            target_id = int(target_arg)
        # Если это username
        elif target_arg.startswith('@'):
            username = target_arg[1:]
            target_user = await session.execute(
                select(User).where(User.username == username)
            )
            target_user = target_user.scalar_one_or_none()
            if target_user:
                target_id = target_user.user_id
    # Если не нашли в аргументах, ищем в реплае
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    
    if not target_id:
        await message.answer("❗ Укажите цель: /setposition <должность> [id|@username|reply]")
        return
    
    if target_id == user.user_id:
        await message.answer("❗ Нельзя назначить должность самому себе.")
        return

    # Вызываем запрос. Автокоммит в миддлвари всё сохранит.
    res_msg = await set_position(session, user.user_id, target_id, pos_name)
    await message.answer(f"✅ {res_msg}")
# ==========================================
# 11. ТОП СТРАН (/globalstats)
# ==========================================
@country_create_router.message(Command("globalstats"))
async def cmd_global_stats(message: types.Message, session: AsyncSession):
    stats = await get_global_stats(session)
    await message.answer(stats, parse_mode="HTML")

# ==========================================
# 12. СПИСОК СТРАН (/countrylist)
# ==========================================
@country_create_router.message(Command("countrylist"))
async def cmd_country_list(message: types.Message, session: AsyncSession):
    args = message.text.split()
    page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    
    countries_list = await get_all_countries(session, page)
    await message.answer(countries_list, parse_mode="HTML")

# ==========================================
# 13. СПИСОК СТРАН (/donate)
# ==========================================
@country_create_router.message(Command("donate"))
async def cmd_donate_to_country(
    message: types.Message, 
    session: AsyncSession, 
    command: CommandObject
):
    if not command.args or not command.args.isdigit():
        await message.answer("❗ Формат: <code>/donate [сумма]</code>")
        return

    amount = int(command.args)
    if amount <= 0:
        await message.answer("❗ Сумма должна быть больше нуля.")
        return

    # Вызываем функцию из requests.py
    success, result_msg = await donate_to_country_treasury(
        session=session, 
        user_id=message.from_user.id, 
        amount=amount
    )

# ==========================================
# 14. СБОР НАЛОГОВ (/collect)
# ==========================================
@country_create_router.message(Command("collect"))
async def cmd_collect_taxes(message: Message, session: AsyncSession, **kwargs):
    success_check, country, user = await check_ruler_permissions(message, session)
    if not success_check:
        return
    
    # Вызываем твою функцию из requests.py
    # Она уже делает всё: считает и списывает у граждан
    success, msg = await collect_taxes(session, country.country_id)
    
    if success:
        # Благодаря твоей миддлвари с автокоммитом всё сохранится сразу
        await message.answer(f"✅ <b>Казна пополнена!</b>\n{msg}", parse_mode="HTML")
    else:
        await message.answer(f"⚠️ {msg}")