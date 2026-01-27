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
import app.keyboard as kb
import logging

# Устанавливаем КД в секундах (например, 7 дней)
COUNTRY_CREATE_COOLDOWN = 7 * 24 * 60 * 60 # 604800 секунд
from app.keyboard import country_edit_menu, country_edit_confirm, cancel_inline_keyboard, back_to_menu_inline_keyboard
from app.database.requests import (
    get_or_create_user, 
    get_full_user_profile, 
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
    edit_country_url,
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
    choose_field = State()
    edit_name = State()
    edit_ideology = State()
    edit_description = State()
    edit_map = State()
    edit_flag = State()
    edit_country_url = State() 


# ==========================================
# A. ХЕНДЛЕР: НАЧАЛО /createcountry
# ==========================================
@country_create_router.message(Command("createcountry"))
async def cmd_create_country(
    message: types.Message, 
    state: FSMContext, 
    session: AsyncSession, 
    bot: Bot,
    user: User
):
    chat_id = message.chat.id
    
    # 1. Проверка владельца чата через Telegram API
    chat_member = await bot.get_chat_member(chat_id, user.user_id)
    is_owner = chat_member.status == "creator"

    # 2. Проверка бана (по твоей модели punishments)
    # Предполагаем, что мидлварь подгрузила punishments (lazy="selectin")
    is_banned = any(p.is_active and p.action_type == "ban" for p in user.punishments)

    # 3. Match-case: Четкая логика без костылей
    # (Тип чата, Состоит в стране, Последнее создание, Забанен, Владелец)
    match (message.chat.type, user.country_id is not None, user.last_country_creation, is_banned, is_owner):
        
        # Только для групп
        case (chat_type, _, _, _, _) if chat_type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer("🚫 Команда работает только в групповых чатах.")
            return

        # Только для владельца
        case (_, _, _, _, False):
            await message.answer("🚫 Основать страну может только <b>Владелец чата</b>.", parse_mode="HTML")
            return
            
        # Если уже есть страна
        case (_, True, _, _, _):
            # Т.к. lazy="selectin" в модели, user.country уже доступен без await
            c_name = html.escape(user.country.name if user.country else "неизвестной стране")
            await message.answer(f"🚫 Ты уже в стране <b>{c_name}</b>. Выйди через /leave.", parse_mode="HTML")
            return
            
        # Если бан
        case (_, _, _, True, _):
            await message.reply("❌ У тебя активный бан на создание стран.")
            return
            
        # Кулдаун
        case (_, _, last, _, _) if last and (datetime.utcnow() - last).total_seconds() < COUNTRY_CREATE_COOLDOWN:
            rem = int(COUNTRY_CREATE_COOLDOWN - (datetime.utcnow() - last).total_seconds())
            await message.answer(f"⏳ Кулдаун! Жди <b>{str(timedelta(seconds=rem))}</b>", parse_mode="HTML")
            return
            
        # Если всё ок — запускаем FSM
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
    
    # ПЕРЕХОД К СЛЕДУЮЩЕМУ СОСТОЯНИЮ (ideology)
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

#========================================================================================================================
#ИЗМЕНЕНИЕ ПАРАМЕТРОВ СТРАНЫ
#========================================================================================================================
@country_create_router.message(Command("recreate"))
async def cmd_recreate_country(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    country = await get_country_by_ruler_id(session, user_id)
    
    if not country:
        await message.answer("🚫 Вы не правитель страны!")
        return
    
    sent_message = await message.answer(
        f"🔧 <b>Редактирование: {country.name}</b>\n\nВыберите поле:",
        parse_mode="HTML",
        reply_markup=country_edit_menu()
    )
    
    await state.set_state(CountryEditStates.choose_field)
    await state.update_data(country_id=country.country_id, menu_msg_id=sent_message.message_id)

@country_create_router.callback_query(F.data.startswith("edit_"))
async def handle_edit_callback(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_id = callback.from_user.id
    action = callback.data
    data = await state.get_data()
    country_id = data.get('country_id')
    
    if not country_id:
        await callback.answer("❌ Сессия устарела", show_alert=True)
        await state.clear()
        return
    
    country = await get_country_by_ruler_id(session, user_id)
    if not country or country.country_id != country_id:
        await callback.answer("🚫 Отказано в доступе", show_alert=True)
        return
    
    match action:
        case "edit_name":
            await state.set_state(CountryEditStates.edit_name)
            await callback.message.edit_text(
                f"📝 <b>Название: {country.name}</b>\nВведите новое:",
                parse_mode="HTML", reply_markup=cancel_inline_keyboard()
            )
        case "edit_ideology":
            await state.set_state(CountryEditStates.edit_ideology)
            await callback.message.edit_text(
                f"🎭 <b>Идеология: {country.ideology}</b>\nВведите новую:",
                parse_mode="HTML", reply_markup=cancel_inline_keyboard()
            )
        case "edit_map":
            await state.set_state(CountryEditStates.edit_map)
            await callback.message.edit_text(
                f"🗺 <b>Карта: {country.map_url or '-'}</b>\nВведите URL:",
                parse_mode="HTML", reply_markup=cancel_inline_keyboard()
            )
        case "edit_description":
            await state.set_state(CountryEditStates.edit_description)
            await callback.message.edit_text(
                f"📜 <b>Описание</b>\nВведите новое:",
                parse_mode="HTML", reply_markup=cancel_inline_keyboard()
            )
        case "edit_flag":
            await state.set_state(CountryEditStates.edit_flag)
            await callback.message.edit_text(
                "🖼 <b>Флаг</b>\nОтправьте изображение:",
                parse_mode="HTML", reply_markup=cancel_inline_keyboard()
            )
        case "edit_country_url":
            await state.set_state(CountryEditStates.edit_country_url)
            await callback.message.edit_text(
                f"🔗 <b>Ссылка: {country.country_url or '-'}</b>\nВведите новую ссылку:",
                parse_mode="HTML", reply_markup=cancel_inline_keyboard()
            )
        case "edit_back_to_menu":
            await state.set_state(CountryEditStates.choose_field)
            await callback.message.edit_text(
                    f"🔧 <b>Редактирование: {country.name}</b>\n\nВыберите поле:",
                    parse_mode="HTML", 
                    reply_markup=country_edit_menu()
                )

        case "edit_cancel_inline":
            await state.clear()
            await callback.message.edit_text(
                "❌ Редактирование завершено.",
                reply_markup=None
            )
    
    await callback.answer()

@country_create_router.message(CountryEditStates.edit_name, F.text)
async def edit_name_handler(message: types.Message, state: FSMContext, session: AsyncSession):
    new_name = message.text.strip()
    
    if not (2 <= len(new_name) <= 100):
        await message.answer("⚠️ Длина названия: 2-100 символов!")
        return

    data = await state.get_data()
    menu_msg_id = data.get('menu_msg_id')
    
    try:
        success, msg = await edit_country_name(session, message.from_user.id, new_name)
        
        # Удаляем сообщение юзера, чтобы не мусорить в РП-чате
        await message.delete() 

        if success:
            # ПЕРЕВОДИМ стейт обратно в выбор поля
            await state.set_state(CountryEditStates.choose_field)
            
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_msg_id,
                text=f"✅ Название изменено на: <b>{new_name}</b>\n\nВыберите следующее поле для правки:",
                parse_mode="HTML",
                reply_markup=country_edit_menu() # Сразу возвращаем ГЛАВНОЕ меню
            )
        else:
            await message.answer(f"❌ {msg}")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@country_create_router.message(CountryEditStates.edit_country_url, F.text)
async def edit_country_url_handler(message: types.Message, state: FSMContext, session: AsyncSession):
    new_url = message.text.strip()

    if not new_url:
        await message.answer("⚠️ Ссылка не может быть пустой!")
        return

    data = await state.get_data()
    menu_msg_id = data.get('menu_msg_id')

    try:
        success, msg = await edit_country_url(session, message.from_user.id, new_url)

        if success:
            await state.set_state(CountryEditStates.choose_field)
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_msg_id,
                text=f"✅ {msg}\n\nВыберите следующее поле для правки:",
                parse_mode="HTML",
                reply_markup=country_edit_menu()
            )
        else:
            await message.answer(f"❌ {msg}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@country_create_router.message(CountryEditStates.edit_ideology, F.text)
async def edit_ideology_handler(message: types.Message, state: FSMContext, session: AsyncSession):
    new_ideology = message.text.strip()
    
    if not (3 <= len(new_ideology) <= 50):
        await message.answer("⚠️ Идеология должна быть длиной от 3 до 50 символов!")
        return

    data = await state.get_data()
    menu_msg_id = data.get('menu_msg_id')
    
    try:
        success, msg = await edit_country_ideology(session, message.from_user.id, new_ideology)
        
        if success:
            await state.set_state(CountryEditStates.choose_field)
            
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_msg_id,
                text=f"✅ Идеология изменена на: <b>{new_ideology}</b>\n\nВыберите следующее поле для правки:",
                parse_mode="HTML",
                reply_markup=country_edit_menu()
            )
        else:
            await message.answer(f"❌ {msg}")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@country_create_router.message(CountryEditStates.edit_description, F.text)
async def edit_description_handler(message: types.Message, state: FSMContext, session: AsyncSession):
    new_description = message.text.strip()
    
    if not (1 <= len(new_description) <= 1000):
        await message.answer("⚠️ Описание должно быть длиной от 1 до 1000 символов!")
        return

    data = await state.get_data()
    menu_msg_id = data.get('menu_msg_id')
    
    try:
        success, msg = await edit_country_description(session, message.from_user.id, new_description)
        
        if success:
            await state.set_state(CountryEditStates.choose_field)
            
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_msg_id,
                text=f"✅ Описание изменено на: <b>{new_description}</b>\n\nВыберите следующее поле для правки:",
                parse_mode="HTML",
                reply_markup=country_edit_menu()
            )
        else:
            await message.answer(f"❌ {msg}")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@country_create_router.message(CountryEditStates.edit_map, F.text)
async def edit_map_handler(message: types.Message, state: FSMContext, session: AsyncSession):
    new_map_url = message.text.strip()
    
    data = await state.get_data()
    menu_msg_id = data.get('menu_msg_id')
    
    try:
        success, msg = await edit_country_map_url(session, message.from_user.id, new_map_url)
        
        if success:
            await state.set_state(CountryEditStates.choose_field)
            
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_msg_id,
                text=f"✅ Ссылка на карту изменена на: <b>{new_map_url}</b>\n\nВыберите следующее поле для правки:",
                parse_mode="HTML",
                reply_markup=country_edit_menu()
            )
        else:
            await message.answer(f"❌ {msg}")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@country_create_router.message(CountryEditStates.edit_flag, F.photo)
async def edit_flag_handler(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    photo = message.photo[-1]
    file_id = photo.file_id
    
    data = await state.get_data()
    menu_msg_id = data.get('menu_msg_id')
    
    try:
        success, msg = await edit_country_flag(session, message.from_user.id, file_id, bot)
        
        if success:
            await state.set_state(CountryEditStates.choose_field)
            
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_msg_id,
                text=f"✅ Флаг изменен!\n{msg}\n\nВыберите следующее поле для правки:",
                parse_mode="HTML",
                reply_markup=country_edit_menu()
            )
        else:
            await message.answer(f"❌ {msg}")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# ==========================================
# 2. ХЕНДЛЕР: ВСТУПЛЕНИЕ В СТРАНУ (/join)
# ==========================================
@country_create_router.message(Command("join")) 
async def cmd_join_country_explicit(
    message: types.Message,
    session: AsyncSession,
    command: CommandObject,
    user: User  # ✅ User из middleware
):
    if not command.args:
        await message.answer(
            "🚫 <b>Укажите ID или название страны.</b>\n"
            "Примеры:\n"
            "  - <code>/join 3</code> (по ID)\n"
            "  - <code>/join Аторния</code> (по названию)", 
            parse_mode=ParseMode.HTML
        )
        return
        
    user_input = command.args.strip()
    
    # Определяем тип поиска
    if user_input.isdigit():
        country_id = int(user_input)
        query_name = None
    else:
        country_id = None
        query_name = user_input

    try:
        success, response_text = await join_country(
            session=session,
            user=user,           # ✅ Объект User, не user_id
            country_id=country_id,
            query_name=query_name
        )

        await message.answer(response_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logging.exception(f"Ошибка в /join: {e}")
        await message.answer(
            "❌ <b>Произошла критическая ошибка.</b>\nПопробуйте позже.",
            parse_mode=ParseMode.HTML
        )

# ==========================================
# 3. ХЕНДЛЕР: ВЫХОД ИЗ СТРАНЫ (/leave)
# ==========================================
@country_create_router.message(Command("leave"))
async def cmd_leave_country(
    message: types.Message,
    session: AsyncSession,
    user: User  # ✅ User из middleware
):
    """Позволяет пользователю покинуть текущую мемную страну."""
    try:
        success, msg, country_name = await leave_country(
            session=session,
            user_id=user.user_id  # ✅ user_id из объекта User
        )
        
        if success:
            await message.answer(
                f"👋 Вы успешно покинули страну <b>{country_name}</b>.", 
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
# 10. УСТАНОВКА Должности (/setposition)
# ==========================================
@country_create_router.message(Command("setposition"))
async def cmd_set_position(message: Message, session: AsyncSession, command: CommandObject, user: User):
    """
    Установка должности с использованием Match-Case.
    """
    # 1. Проверка прав (используем уже подгруженного user из Middleware)
    if not user.ruled_country_list:
        return await message.answer("❗ Вы не являетесь правителем страны.")

    # 2. Подготовка аргументов
    args = command.args.split() if command.args else []
    target_id = None
    pos_name = None

    # 3. Магия Match-Case
    match args:
        # Случай: /setposition (пусто)
        case []:
            return await message.answer("❗ Формат: <code>/setposition [должность] [id|@username|reply]</code>")

        # Случай: /setposition [название] (через REPLY)
        case [*name_parts] if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            pos_name = " ".join(name_parts)

        # Случай: /setposition [название] @username
        case [*name_parts, target] if target.startswith("@"):
            # Ищем ID по юзернейму
            stmt = select(User.user_id).where(User.username == target[1:])
            target_id = await session.scalar(stmt)
            pos_name = " ".join(name_parts)

        # Случай: /setposition [название] ID
        case [*name_parts, target] if target.isdigit():
            target_id = int(target)
            pos_name = " ".join(name_parts)

        # Если ничего не подошло
        case _:
            return await message.answer("❗ Не удалось распознать цель. Укажите @username, ID или ответьте на сообщение.")

    # 4. Финальные проверки перед записью
    if not target_id or not pos_name:
        return await message.answer("❗ Ошибка: не указана должность или пользователь.")

    if target_id == user.user_id:
        return await message.answer("❗ Вы не можете назначить должность самому себе.")

    # 5. Выполнение логики
    # Передаем ID страны правителя для проверки принадлежности цели к стране
    country_id = user.ruled_country_list[0].country_id
    res_msg = await set_position(session, country_id, target_id, pos_name)
    
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