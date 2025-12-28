# app/countrycreate.py
import html
from aiogram import Router, types, F, Bot # 🔥 Убрали Text, добавили F и Bot
from aiogram.filters import Command # 🔥 Оставили только Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandObject
from datetime import datetime, timedelta 
from aiogram.enums import ParseMode, ChatType
from aiogram.enums import ContentType 
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Tuple

from config import REVIEW_COOLDOWN_DAYS
from .database.models import User, MemeCountry, CountryReview

from .review_service import ReviewService
import logging

# Устанавливаем КД в секундах (например, 7 дней)
COUNTRY_CREATE_COOLDOWN = 7 * 24 * 60 * 60 # 604800 секунд

# Импортируем твои DB-хендлеры (предполагаем, что они в .database.requests)
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
)

logger = logging.getLogger(__name__)

# Создаем роутер для этого функционала
country_create_router = Router()


# ==========================================
# 1. КОНЕЧНЫЙ АВТОМАТ СОСТОЯНИЙ (FSM)
# ==========================================

class CountryCreateStates(StatesGroup):
    """Определяет шаги для создания мемной страны."""
    memename = State()
    ideology = State() 
    map_url = State()
    transfer_target_id = State() 




# ==========================================
# A. ХЕНДЛЕР: НАЧАЛО /createcountry
# ==========================================

@country_create_router.message(Command("createcountry"))
async def cmd_create_country(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # 0. ПРОВЕРКА ЧАТА 
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("🚫 Эту команду можно использовать только в групповом чате.")
        return

    # 1. АВТО-РЕГИСТРАЦИЯ И ЗАГРУЗКА ПРОФИЛЯ
    profile, was_created = await db_ensure_full_user_profile(
        session=session,
        user_id=user_id,
        username=message.from_user.username or "Unknown",
        userfullname=message.from_user.full_name or "Unknown"
    )
    
    if was_created:
        await message.answer("👋 Вы не были зарегистрированы, но я это исправил! Продолжаем создание...")

    if profile is None:
        await message.answer("❌ Внутренняя ошибка: не удалось загрузить профиль. Попробуйте снова.")
        return

    # 2. ПРОВЕРКА КУЛДАУНА
    if profile.last_country_creation:
        time_since_creation = datetime.now() - profile.last_country_creation
        
        # NOTE: COUNTRY_CREATE_COOLDOWN должен быть определен где-то
        if time_since_creation.total_seconds() < COUNTRY_CREATE_COOLDOWN:
            remaining_seconds = COUNTRY_CREATE_COOLDOWN - time_since_creation.total_seconds()
            remaining_time = str(timedelta(seconds=int(remaining_seconds)))
            
            error_text = (
                f"⏳ <b>КУЛДАУН АКТИВЕН!</b>\n"
                f"Новую страну можно создать через <b>{remaining_time}</b> (Д:Ч:М:С)."
            )
            await bot.send_message(chat_id=chat_id, text=error_text, parse_mode=ParseMode.HTML)
            return

    # 3. ПРОВЕРКА ЧЛЕНСТВА
    if profile.country:
        country_safe = html.escape(profile.country.name)
        error_text = (
            f"🚫 Вы уже состоите в стране <b>{country_safe}</b>. "
            "Выйдите командой /leave, чтобы создать новую."
        )
        await bot.send_message(chat_id=chat_id, text=error_text, parse_mode=ParseMode.HTML)
        return

    # 4. СБОР ДАННЫХ ЧАТА (Имя, описание, флаг)
    chat_info = await bot.get_chat(chat_id)
    chat_name = chat_info.title
    chat_desc = chat_info.description or f"Мемная страна, основанная в чате '{chat_name}'."
    chat_name_safe = html.escape(chat_name)
    
    flag_url = None
    try:
        if chat_info.photo:
            flag_url = chat_info.photo.big_file_id
    except Exception as e:
        logger.warning(f"Не удалось получить фото чата {chat_id}: {e}")
    
    # 5. СОХРАНЯЕМ НАЧАЛЬНЫЕ ДАННЫЕ В FSM
    await state.update_data(
        chat_id=chat_id,
        name=chat_name, 
        description=chat_desc,
        flag_url=flag_url,
    )
    
    # 6. НАЧИНАЕМ FSM (переход к первому шагу: memename)
    await state.set_state(CountryCreateStates.memename) 
    
    await message.answer(
        f"📝 <b>Начинаем создание страны: {chat_name_safe}</b>\n"
        "Название, описание и флаг взяты из настроек чата.\n"
    "Шаг 1 из 3: Введите <b>МЕМ ВАШЕЙ СТРАНЫ</b> (основу) страны.\n",
        parse_mode=ParseMode.HTML
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

# NOTE: Был C. ХЕНДЛЕР FSM: Ввод мема страны (2/3) — этот код был ошибочно скопирован, 
# и логика memename была продублирована. Я сохраняю только финальный хендлер.
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
            description=fsm_data['description'],
            ideology=fsm_data['ideology'],
            avatar_url=fsm_data.get('flag_url'),
            memename=fsm_data['memename'],
            map_url=final_map_url
        )

        await session.flush()

        # 2. Назначаем правителя
        await assign_ruler(
            session=session,
            user_id=user_id,
            country_id=new_country.country_id
        )

        # 3. Коммит и очистка
        await session.commit()
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
        await session.rollback()
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
        await message.answer(error_msg)  # Без parse_mode — использует дефолт из Bot

@country_create_router.message(CountryCreateStates.map_url)
async def process_map_url_invalid(message: types.Message):
    await message.answer("⚠️ Введите <b>текст</b> ссылки или прочерк '-'.", parse_mode=ParseMode.HTML)
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
            "🚫 <b>Укажите метод поиска и значение</b>.\n"
            "Примеры:\n"
            "  - По ID: <code>/join id 123</code>\n"
            "  - По названию: <code>/join name Аторния</code>", 
            parse_mode=ParseMode.HTML
        )
        return
        
    # /join <method> <value>
    args = command.args.split(maxsplit=1)
    
    if len(args) != 2:
        await message.answer(
            "🚫 Неверный формат команды.\n"
            "Пример: <code>/join name Крабовия</code>",
            parse_mode=ParseMode.HTML
        )
        return
        
    search_method = args[0].lower()
    search_value = args[1].strip()

    try:
        success, response_text = await join_country(
            session=session, 
            user_id=user_id, 
            search_method=search_method,
            search_value=search_value
        )

        if not success:
            await session.rollback()
            await message.answer(response_text, parse_mode=ParseMode.HTML)
            return

        # 💾 Фиксируем изменения
        await session.commit()

        # ✅ Отвечаем ТОЛЬКО после успешного коммита
        await message.answer(response_text, parse_mode=ParseMode.HTML)
    except IntegrityError:
        await session.rollback()
        return False, "Конфликт в БД (дубликат или ограничение)."
    except NoResultFound:
        return False, "Страна не найдена."
    except Exception as e:
        logging.exception("Ошибка в join_country")
        return False, "Критическая ошибка, админ в курсе."
    except Exception as e:
            await session.rollback()
            await message.answer(
                "❌ <b>Произошла критическая ошибка.</b>\n"
                "Попробуйте позже.",
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
            await session.commit()
            await message.answer(
                f"👋 Вы успешно покинули страну **{country_name}**.", 
                parse_mode='HTML'
            )
        else:
            await message.answer(f"❌ Не удалось покинуть страну: {msg}")
            
    except Exception as e:
        await session.rollback()
        logger.error("Ошибка при выполнении команды /leave: %s", e)
        await message.answer("⛔️ Произошла системная ошибка при выходе. Попробуйте позже.")



# ==========================================
# 4. ХЕНДЛЕР: МОЯ СТРАНА (/mycountry)
# ==========================================
@country_create_router.message(Command("mycountry"))
@country_create_router.message(Command("country")) # Алиас для удобства
async def cmd_my_country(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    
    # Получаем данные
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

    # Распаковываем данные
    country = stats["country"]
    citizens_count = stats["citizens_count"]
    total_citizen_points = stats["citizens_total_points"]
    
    # Форматирование данных
    name_safe = html.escape(country.name)
    meme_safe = html.escape(country.memename) if country.memename else "Не указан"
    ideology_safe = html.escape(country.ideology) if country.ideology else "Не определена"
    desc_safe = html.escape(country.description)
    
    # Имя правителя
    ruler_name = html.escape(country.ruler.userfullname) if country.ruler else "Отсутствует"
    
    # Ссылка на карту (если есть)
    map_link = ""
    if country.map_url and country.map_url != '-':
        map_link = f"\n🗺 <a href='{country.map_url}'>Карта территории</a>"

    # Итоговое сообщение
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
        f"💎 <b>Богатство граждан (Сумма):</b> {total_citizen_points} очков\n"
        f"⭐ <b>Рейтинг:</b> {country.avg_rating:.1f} ({country.total_reviews} отзывов)"
    )
    
    # Если у страны есть флаг (avatar_url - это file_id), отправляем фото
    if country.avatar_url:
        await message.answer_photo(
            photo=country.avatar_url,
            caption=text,
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True # Чтобы карта не раскрывалась огромной картинкой внизу
        )


# ==========================================
# 4. ХЕНДЛЕР: МОЯ СТРАНА (/mycountry)
# ==========================================
@country_create_router.message(Command("mycountry"))
@country_create_router.message(Command("country")) # Алиас для удобства
async def cmd_my_country(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    
    # Получаем данные
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

    # Распаковываем данные
    country = stats["country"]
    citizens_count = stats["citizens_count"]
    total_citizen_points = stats["citizens_total_points"]
    
    # Форматирование данных
    name_safe = html.escape(country.name)
    meme_safe = html.escape(country.memename) if country.memename else "Не указан"
    ideology_safe = html.escape(country.ideology) if country.ideology else "Не определена"
    desc_safe = html.escape(country.description)
    
    # Имя правителя
    ruler_name = html.escape(country.ruler.userfullname) if country.ruler else "Отсутствует"
    
    # Ссылка на карту (если есть)
    map_link = ""
    if country.map_url and country.map_url != '-':
        map_link = f"\n🗺 <a href='{country.map_url}'>Карта территории</a>"

    # Итоговое сообщение
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
        f"💎 <b>Богатство граждан (Сумма):</b> {total_citizen_points} очков\n"
        f"⭐ <b>Рейтинг:</b> {country.avg_rating:.1f} ({country.total_reviews} отзывов)"
    )
    
    # Если у страны есть флаг (avatar_url - это file_id), отправляем фото
    if country.avatar_url:
        await message.answer_photo(
            photo=country.avatar_url,
            caption=text,
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True # Чтобы карта не раскрывалась огромной картинкой внизу
        )

# ==========================================
# 5. ОЦЕНКА ПРАВИТЕЛЬСТВА (/rate) — ЧИСТАЯ ВЕРСИЯ (БЕЗ РЕВЬЮБОМБИНГА)
# ==========================================
@country_create_router.message(Command("rate"))
async def cmd_rate(
    message: types.Message,
    session: AsyncSession,
    current_user: User  # Твой UserMiddleware даёт current_user
):
    # 1. Проверяем, состоит ли юзер в стране
    if current_user.country_id is None:
        await message.answer(
            "🚫 Вы не состоите ни в одной стране.\n"
            "Вступите в страну командой /join, чтобы иметь право голоса на оценку правительства!",
            parse_mode=ParseMode.HTML
        )
        return

    # 2. Проверяем, есть ли аргументы (оценка)
    if not message.text or not command.args:
        await message.answer(
            "🚫 Укажите оценку от 1 до 5.\n\n"
            f"Пример: <code>/rate 4</code>\n\n"
            f"Вы оцениваете правительство своей страны:\n"
            f"<b>{hbold(current_user.country.name)}</b>",
            parse_mode=ParseMode.HTML
        )
        return

    # 3. Парсим оценку (единственный аргумент)
    try:
        rating = int(command.args.strip())
        if not 1 <= rating <= 5:
            raise ValueError
    except ValueError:
        await message.answer("🚫 Оценка должна быть числом от 1 до 5.")
        return

    # 4. Создаём сервис и вызываем обработку
    review_service = ReviewService(cooldown_days=REVIEW_COOLDOWN_DAYS)

    success, response = await review_service.handle_rating(
        session=session,
        user_id=current_user.user_id,
        country_name=current_user.country.name,
        rating=rating,
        user_country_id=current_user.country_id
    )

    # 5. Коммит/роллбэк и ответ
    if success:
        await session.commit()
    else:
        await session.rollback()

    await message.answer(response, parse_mode=ParseMode.HTML)