"""
Функции для работы с мемными странами.
"""
import os
import aiofiles
import logging
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func, and_, delete, cast, Integer
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple
from thefuzz import fuzz

from ..models import User, History, Admins, MemeCountry, CountryReview, CountryBlacklist, Punishment
from config import FUZZY_MATCH_THRESHOLD, OWNER_ID
from app.utils.html_helpers import escape_html, hbold

logger = logging.getLogger(__name__)
from .utils import (
    has_active_country_ban,
    check_creation_allowed,
    get_creation_status
)
async def create_meme_country(
    session: AsyncSession, 
    ruler_id: int,                      # ID создателя (будущего правителя)
    chat_id: int,                       # ID чата, в котором была создана
    name: str, 
    ideology: str,                      # Теперь обязательное поле
    description: str = "Описание не предоставлено.", 
    avatar_url: Optional[str] = None,   # File ID флага/аватара
    map_url: Optional[str] = None,       # Ссылка на карту
    memename: str = "Мем не задан"    # Мем страны
) -> MemeCountry:
    """Создает новую страну с основными параметрами."""
    new_country = MemeCountry(
        ruler_id=ruler_id,
        chat_id=chat_id,
        name=name, 
        ideology=ideology,
        description=description,
        avatar_url=avatar_url,
        map_url=map_url,
        memename=memename
        
        # Остальные поля (influence_points, avg_rating) должны иметь значения по умолчанию в модели
    )
    
    session.add(new_country)
    return new_country


async def assign_ruler(session: AsyncSession, user_id: int, country_id: int) -> tuple[bool, str]:
    """
    Коронация: Делает юзера правителем страны и обновляет его статус.
    """
    # 1. Получаем страну и юзера
    # 💡 Используем get() для чистой загрузки
    country = await session.get(MemeCountry, country_id)
    user = await session.get(User, user_id)

    if not country or not user:
        return False, "Страна или Пользователь не найдены."

    # 2. Логика смены власти
    if country.ruler:
        # Снимаем полномочия с предыдущего правителя (если есть)
        if hasattr(country.ruler, 'is_ruler'):
            country.ruler.is_ruler = False
        country.ruler.position = "Бывший правитель"
    user.country_id = country_id    # ✅ Используем ID, а не объектную связь user.country = country
    
    if hasattr(user, 'is_ruler'):
        user.is_ruler = True
        
    user.position = "Правитель"       # Должность в стране
    user.points += 10  # Бонусные очки за коронацию
    # 4. Установка кулдауна
    # Это было пропущено в вашей функции, но должно быть сделано здесь.
    user.last_country_creation = datetime.now() 

    return True, f"Да здравствует новый правитель {country.name} — {user.userfullname}!"


async def get_country_by_name(session: AsyncSession, name: str) -> MemeCountry | None:
    """Находит страну по названию с подгруженным правителем."""
    stmt = select(MemeCountry).options(selectinload(MemeCountry.ruler)).where(
        func.lower(MemeCountry.name) == func.lower(name)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_my_country_stats(session: AsyncSession, user_id: int) -> dict | None:
    """
    Возвращает полную статистику страны, в которой состоит пользователь.
    Включает: объект страны, имя правителя, кол-во граждан, сумму очков граждан.
    """
    # 1. Получаем пользователя, чтобы узнать ID страны
    user = await session.get(User, user_id)
    
    if not user or not user.country_id:
        return None

    country_id = user.country_id

    # 2. Получаем объект страны с подгрузкой Правителя
    stmt_country = (
        select(MemeCountry)
        .options(selectinload(MemeCountry.ruler))
        .where(MemeCountry.country_id == country_id)
    )
    result_country = await session.execute(stmt_country)
    country = result_country.scalar_one_or_none()

    if not country:
        return None

    # 3. Считаем статистику по гражданам (Количество и Сумма очков)
    stmt_stats = (
        select(
            func.count(User.user_id),      # Количество граждан
            func.sum(User.points)          # Сумма их очков
        )
        .where(User.country_id == country_id)
    )
    result_stats = await session.execute(stmt_stats)
    count, total_points = result_stats.one()

    # Если очков нет (None), ставим 0
    total_points = total_points if total_points else 0

    return {
        "country": country,
        "citizens_count": count,
        "citizens_total_points": total_points
    }



async def has_active_country_ban(session: AsyncSession, user_id: int) -> bool:
    """Проверяет наличие активного бана на создание стран."""
    stmt = select(Punishment).where(
        Punishment.user_id == user_id,
        Punishment.action_type == "COUNTRY_CREATION_BAN",
        Punishment.is_active == True
    )
    result = await session.scalar(stmt)
    
    if result:
        # Используем современный UTC для твоего свежего Arch
        if result.expires_at is None or result.expires_at > datetime.now(timezone.utc):
            return True
        
        # Если срок истёк, деактивируем бан прямо здесь
        result.is_active = False 
    return False

async def check_creation_allowed(session: AsyncSession, user_id: int, cooldown_seconds: int) -> tuple[bool, Optional[str]]:
    """
    Комплексная проверка перед началом FSM.
    Возвращает (разрешено, текст_ошибки)
    """
    user = await session.get(User, user_id)
    if not user:
        return False, "Профиль не найден."

    # 1. Проверка на членство
    if user.country_id:
        return False, "🚫 Ты уже состоишь в стране. Выйди через /leave."

    # 2. Проверка бана
    if await has_active_country_ban(session, user_id):
        return False, "❌ У тебя активный бан на создание стран."

    # 3. Проверка кулдауна
    if user.last_country_creation:
        now = datetime.now()
        passed = (now - user.last_country_creation).total_seconds()
        if passed < cooldown_seconds:
            remaining = int(cooldown_seconds - passed)
            return False, f"⏳ Кулдаун! Жди <b>{str(timedelta(seconds=remaining))}</b>"

    return True, None

async def get_creation_status(session: AsyncSession, user_id: int):
    """
    Загружает профиль пользователя вместе с данными его страны 
    и проверяет наличие активного бана.
    """
    # Используем selectinload для страны, чтобы profile.country.name был доступен
    stmt = (
        select(User)
        .options(selectinload(User.country))
        .where(User.user_id == user_id)
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        return None, False
    
    # Проверяем бан через уже существующую у тебя функцию
    is_banned = await has_active_country_ban(session, user_id)
    
    return profile, is_banned

#ДОНАТЫ В СТРАНУ - - - - - - - - - - - - - - - - - - - - - - - - 
async def donate_to_country_treasury(session: AsyncSession, user_id: int, amount: int) -> tuple[bool, str]:
    """
    Переводит очки пользователя в казну его страны.
    Возвращает (успех, сообщение).
    """
    # Загружаем юзера вместе со страной
    result = await session.execute(
        select(User).options(selectinload(User.country)).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        return False, "Пользователь не найден."
    
    if not user.country:
        return False, "Вы не состоите ни в одной стране."

    if user.points < amount:
        return False, f"Недостаточно очков. Ваш баланс: {user.points}"

    # Проводим транзакцию
    try:
        user.points -= amount
        user.country.treasury = (user.country.treasury or 0) + amount
        # commit сделает миддлварь или хендлер
        return True, f"Успешно! Казна {user.country.name} пополнена на {amount} очков."
    except Exception as e:
        logger.error(f"Ошибка транзакции пожертвования: {e}")
        return False, "Ошибка при обработке транзакции."
# ==========================================
# 2.1 ВСТУПЛЕНИЕ В СТРАНУ (JOIN COUNTRY)
# ==========================================
async def join_country(
    session: AsyncSession,
    user: User,              # Получаем уже готовый объект User
    country_id: int | None = None,
    query_name: str | None = None
) -> tuple[bool, str]:
    # 1. Блокировка для правителей (уже подгружено в user)
    if user.ruled_country_list:
        return False, "🚫 Ты правитель. Сначала передай власть (/transferpower)."

    # 2. Определение целевой страны
    target_country = None
    if country_id:
        target_country = await session.get(MemeCountry, country_id)
    elif query_name:
        target_country = await find_country_by_fuzzy_name(session, query_name)

    if not target_country:
        return False, f"❌ Страна не найдена."

    # 3. Проверка: уже в этой стране?
    if user.country_id == target_country.country_id:
        return False, f"ℹ️ Вы уже гражданин <b>{target_country.name}</b>."

    # 4. Логика смены/вступления
    old_country_name = None
    if user.country_id:
        old_country = await session.get(MemeCountry, user.country_id)
        if old_country:
            old_country_name = old_country.name

    if old_country_name:
        event_type = "CHANGE_COUNTRY"
        reason = f"Смена страны: {old_country_name} → {target_country.name}"
        welcome_text = f"✅ Вы сменили гражданство на <b>{target_country.name}</b>!"
    else:
        event_type = "JOIN_COUNTRY"
        reason = f"Вступление в страну: {target_country.name}"
        welcome_text = f"✅ Добро пожаловать в <b>{target_country.name}</b>!"

    # 5. Обновляем пользователя
    user.country_id = target_country.country_id
    user.position = "Гражданин"

    # 6. Записываем в историю
    session.add(History(
        target_id=user.user_id,
        event_type=event_type,
        reason=reason
    ))
    await session.flush()

    return True, welcome_text

async def find_country_by_fuzzy_name(session: AsyncSession, query: str) -> Optional[MemeCountry]:
    """Находит страну по названию или мем-имени."""
    query = query.strip().lower()
    if len(query) < 2:
        return None

    # Быстрый селект только нужных полей
    result = await session.execute(
        select(MemeCountry.country_id, MemeCountry.name, MemeCountry.memename)
    )
    countries = result.all()

    if not countries:
        return None

    best_match = None
    best_score = 75  # Твой порог из конфига

    for country_id, name, memename in countries:
        score1 = fuzz.token_sort_ratio(query, name.lower())
        score2 = fuzz.token_sort_ratio(query, (memename or "").lower())
        score = max(score1, score2)

        if score > best_score:
            best_score = score
            best_match = await session.get(MemeCountry, country_id)
            
    return best_match
# ==========================================
#ВЫХОД ИЗ СТРАНЫ (LEAVE COUNTRY / LEAVE)
# ==========================================
async def leave_country(session: AsyncSession, user_id: int) -> tuple[bool, str, str | None]:
    """
    Удаляет пользователя из страны, обнуляя country_id.
    """
    from sqlalchemy.orm import selectinload # Импорт необходим для корректной подгрузки страны
    
    # Получаем пользователя СРАЗУ с его текущей страной
    stmt = select(User).options(
        selectinload(User.country)
    ).where(User.user_id == user_id)
    
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
         return False, "Пользователь не найден в базе.", None

    if user.country_id is None:
        return False, "Вы ни в какой стране не состоите.", None
    
    # Правитель не может просто "выйти", он должен отречься через /transferpower
    if user.is_ruler:
        return False, "Вы правитель! Используйте команду передачи власти(/transferpower).", None


    country_name = user.country.name if user.country else "Неизвестная страна"

    # Обнуление полей
    user.country_id = None
    user.position = "Путешественник"

    await session.flush()
    
    return True, "Успешно", country_name


# ==========================================
#ПЕРЕДАЧА ВЛАСТИ И УДАЛЕНИЕ СТРАНЫ
# ==========================================
async def transfer_ruler(session: AsyncSession, old_ruler_id: int, new_ruler_id: int, country_id: int) -> tuple[bool, str]:
    """
    Передает власть правителя страны другому гражданину.
    """
    # Получить страну и пользователей
    country = await session.get(MemeCountry, country_id)
    old_ruler = await session.get(User, old_ruler_id)
    new_ruler = await session.get(User, new_ruler_id)

    if not country or country.ruler_id != old_ruler_id:
        return False, "Вы не правитель этой страны или страна не найдена."

    if not new_ruler:
        return False, "Новый правитель не найден в базе."

    # Запрет бота как правителя
    if new_ruler_id < 0:  # BOTS have negative ID
        return False, "🚫 Нельзя назначать бота правителем."

    if new_ruler.country_id != country_id:
        new_ruler.country_id = country_id  # Авто-вступление
        new_ruler.position = "Гражданин"

    # Сменить правителя
    country.ruler_id = new_ruler_id

    # Обновить статусы
    old_ruler.is_ruler = False
    old_ruler.position = "Бывший правитель"

    new_ruler.is_ruler = True
    new_ruler.position = "Правитель"
    new_ruler.points += 10

    return True, f"Власть успешно передана! Новый правитель: {new_ruler.userfullname or 'Без имени'}."

async def delete_country(session: AsyncSession, ruler_id: int, country_id: int) -> tuple[bool, str]:
    """
    Удаляет страну (только правитель может).
    """
    country = await session.get(MemeCountry, country_id)

    if not country or country.ruler_id != ruler_id:
        return False, "Вы не правитель этой страны."

    # Получить количество граждан (без правителя)
    citizens_count = await session.scalar(
        select(func.count(User.user_id)).where(User.country_id == country_id).where(User.user_id != ruler_id)
    )

    if citizens_count > 0:
        return False, f"Нельзя удалить страну с населением. Сначала выгоните всех: {citizens_count} граждан."

    # Обнуляем правителя
    old_ruler = await session.get(User, ruler_id)
    old_ruler.country_id = None
    old_ruler.position = "Бывший правитель империи"
    old_ruler.is_ruler = False

    await session.execute(delete(CountryReview).where(CountryReview.country_id == country_id))# Удалить отзывы
    await session.execute(delete(CountryBlacklist).where(CountryBlacklist.country_id == country_id))# Удалить blacklist
    await session.delete(country)                                                                   # Удалить страну

    await session.flush()
    return True, f"Страна '{country.name}' успешно удалена. Империя пала!"

async def set_position(session: AsyncSession, ruler_id: int, target_id: int, position: str) -> tuple[bool, str]:
    """
    Назначает должность гражданину (правитель).
    """
    if not position.strip():
        return False, "Укажите должность."
    
    if target_id < 0:
        return False, "🚫 Нельзя взаимодействовать с ботами."
    
    country = await session.scalar(
        select(MemeCountry.country_id).where(MemeCountry.ruler_id == ruler_id)
    )
    if not country:
        return False, "Вы не правитель."
    
    target = await session.get(User, target_id)
    if not target or target.country_id != country:
        return False, "Целевой пользователь не в вашей стране."
    
    target.position = position.strip()
    return True, f"Должность '{position}' назначена {target.userfullname or 'Пользователю'}."

async def kick_user(session: AsyncSession, ruler_id: int, target_id: int) -> tuple[bool, str]:
    """
    Выгоняет гражданина (правитель).
    """
    if target_id < 0:
        return False, "🚫 Нельзя взаимодействовать с ботами."
    
    country_id = await session.scalar(
        select(MemeCountry.country_id).where(MemeCountry.ruler_id == ruler_id)
    )
    if not country_id:
        return False, "Вы не правитель."
    
    target = await session.get(User, target_id)
    if not target or target.country_id != country_id or target_id == ruler_id:
        return False, "Нельзя выгнать."
    
    target.country_id = None
    target.position = "Путешественник"
    target.is_ruler = False  # На всякий
    
    return True, f"Пользователь {target.userfullname or 'Без имени'} выгнан."

async def collect_taxes(session: AsyncSession, country_id: int) -> tuple[bool, str]:
    country = await session.get(MemeCountry, country_id)
    if not country or not country.tax_rate:
        return False, "Налог не установлен."
    
    # Считаем сумму налогов прямо в БД, чтобы не тащить всех юзеров в Python
    tax_sum = await session.scalar(
        select(func.sum(cast(User.points * country.tax_rate, Integer)))
        .where(User.country_id == country_id, User.user_id != country.ruler_id)
    ) or 0

    if tax_sum > 0:
        # Массовое списание у граждан
        await session.execute(
            update(User)
            .where(User.country_id == country_id, User.user_id != country.ruler_id)
            .values(points=User.points - cast(User.points * country.tax_rate, Integer))
        )
        # Начисление стране
        country.influence_points += tax_sum
        return True, f"Налоги собраны: +{tax_sum} влияния."
    
    return False, "Нечего собирать."

# Исправленный set_tax_rate
async def set_tax_rate(session: AsyncSession, ruler_id: int, rate: float) -> tuple[bool, str]:
    if not 0 <= rate <= 0.5:
        return False, f"Налог должен быть от 0% до 50%."

    # Берем объект целиком, чтобы сработал автокоммит миддлвари
    result = await session.execute(select(MemeCountry).where(MemeCountry.ruler_id == ruler_id))
    country = result.scalar_one_or_none()
    
    if not country:
        return False, "Вы не правитель."

    country.tax_rate = rate
    return True, f"Налог установлен на {rate*100:.0f}%."

async def get_all_countries(session: AsyncSession, page: int = 1, limit: int = 5) -> str:
    """Возвращает список стран с пагинацией и именами правителей."""
    offset = (page - 1) * limit
    countries = await session.scalars(
        select(MemeCountry)
        .options(selectinload(MemeCountry.ruler))  # Подгружаем правителей сразу
        .order_by(desc(MemeCountry.influence_points))
        .offset(offset)
        .limit(limit)
    )
    result = [f"📖 <b>СПИСОК СТРАН (стр. {page})</b>:"]
    for idx, c in enumerate(countries, start=offset+1):
        ruler_name = c.ruler.userfullname if c.ruler else "Нет правителя"
        result.append(f"{idx}. {escape_html(c.name)} — Влияние: {c.influence_points} (Правитель: {escape_html(ruler_name)})")
    return "\n".join(result)

async def get_global_stats(session: AsyncSession, limit: int = 10) -> str:
    """Топ стран по влиянию с именами правителей."""
    countries = await session.scalars(
        select(MemeCountry)
        .options(selectinload(MemeCountry.ruler))
        .order_by(desc(MemeCountry.influence_points))
        .limit(limit)
    )
    result = ["🏆 <b>ТОП СТРАН ПО ВЛИЯНИЮ</b>:"]
    for idx, c in enumerate(countries, 1):
        ruler_name = c.ruler.userfullname if c.ruler else "Нет правителя"
        result.append(f"{idx}. {escape_html(c.name)} — {c.influence_points} (Правитель: {escape_html(ruler_name)})")
    return "\n".join(result)

async def get_country_by_ruler_id(session: AsyncSession, ruler_id: int) -> MemeCountry | None:
    """Получает страну по ID правителя"""
    result = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )
    return result
#изменение параметров страны ------------------------------------------------
async def edit_country_flag_local(session: AsyncSession, ruler_id: int, file_id: str) -> tuple[bool, str]:
    """Сохраняет file_id флага локально"""
    country = await get_country_by_ruler_id(session, ruler_id)
    
    if not country:
        return False, "Вы не правитель."
    
    country.flag_file_id = file_id
    return True, "Флаг обновлён!"

async def get_country_flag(session: AsyncSession, country_id: int) -> Optional[str]:
    """Получает file_id флага"""
    country = await session.get(MemeCountry, country_id)
    return country.flag_file_id if country else None


async def edit_country_name(session: AsyncSession, ruler_id: int, new_name: str) -> tuple[bool, str]:
    """Изменяет название страны"""
    if len(new_name) > 100:
        return False, "Название слишком длинное (максимум 100 символов)."
    
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )
    
    if not country:
        return False, "Вы не правитель."
    
    # Проверка на уникальность названия
    existing = await session.scalar(
        select(MemeCountry).where(
            func.lower(MemeCountry.name) == func.lower(new_name),
            MemeCountry.country_id != country.country_id
        )
    )
    
    if existing:
        return False, f"Страна с названием '{new_name}' уже существует."
    
    country.name = new_name
    return True, f"Название страны успешно изменено на '{new_name}'."

async def edit_country_ideology(session: AsyncSession, ruler_id: int, new_ideology: str) -> tuple[bool, str]:
    """Изменяет идеологию страны"""
    if not (3 <= len(new_ideology) <= 50):
        return False, "Идеология должна быть длиной от 3 до 50 символов."
    
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )
    
    if not country:
        return False, "Вы не правитель."
    
    country.ideology = new_ideology
    return True, f"Идеология страны успешно изменена на '{new_ideology}'."

async def edit_country_description(session: AsyncSession, ruler_id: int, new_description: str) -> tuple[bool, str]:
    """Изменяет описание страны"""
    if len(new_description) > 1000:
        return False, "Описание слишком длинное (максимум 1000 символов)."
    
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )
    
    if not country:
        return False, "Вы не правитель."
    
    country.description = new_description
    return True, "Описание страны успешно изменено."

async def edit_country_map_url(session: AsyncSession, ruler_id: int, new_map_url: str) -> tuple[bool, str]:
    """Изменяет ссылку на карту страны"""
    final_map_url = None if new_map_url == '-' else new_map_url
    
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )
    
    if not country:
        return False, "Вы не правитель."
    
    country.map_url = final_map_url
    return True, "Ссылка на карту успешно изменена."

async def edit_country_memename(session: AsyncSession, ruler_id: int, new_memename: str) -> tuple[bool, str]:
    """Изменяет мемное имя страны"""
    if len(new_memename) > 100:
        return False, "Мемное имя слишком длинное (максимум 100 символов)."
    
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )
    
    if not country:
        return False, "Вы не правитель."
    
    # Проверка на уникальность мемного имени
    existing = await session.scalar(
        select(MemeCountry).where(
            func.lower(MemeCountry.memename) == func.lower(new_memename),
            MemeCountry.country_id != country.country_id
        )
    )
    
    if existing:
        return False, f"Мемное имя '{new_memename}' уже используется другой страной."
    
    country.memename = new_memename
    return True, f"Мемное имя страны успешно изменено на '{new_memename}'."


async def edit_country_url(session: AsyncSession, ruler_id: int, new_url: str) -> tuple[bool, str]:
    """Изменяет ссылку на страну."""
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )

    if not country:
        return False, "Вы не правитель."

    country.country_url = new_url
    return True, f"Ссылка страны успешно изменена на '{new_url}'."



#======================================================================
#Сохранение файлов
#======================================================================
async def download_telegram_file(bot: Bot, file_id: str, save_path: str) -> bool:
    """Скачивает файл из Telegram"""
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, save_path)
        return True
    except Exception as e:
        print(f"Ошибка скачивания файла: {e}")
        return False

async def edit_country_flag(session: AsyncSession, ruler_id: int, file_id: str, bot: Bot) -> tuple[bool, str]:
    """Изменяет флаг страны - скачивает и сохраняет локально"""
    country = await session.scalar(
        select(MemeCountry).where(MemeCountry.ruler_id == ruler_id)
    )
    
    if not country:
        return False, "Вы не правитель."
    
    # Создаем папку для флагов если её нет
    flags_dir = Path("assets/flags")
    flags_dir.mkdir(parents=True, exist_ok=True)
    
    # Генерируем имя файла
    file_extension = "jpg"  # можно определить по mime_type
    filename = f"flag_{country.country_id}.{file_extension}"
    save_path = flags_dir / filename
    
    # Скачиваем файл
    if await download_telegram_file(bot, file_id, save_path):
        # Сохраняем file_id для будущих скачиваний
        country.flag_file_id = file_id
        # Сохраняем путь к локальному файлу
        country.avatar_url = f"assets/flags/{filename}"
        return True, f"Флаг успешно сохранен: {filename}"
    else:
        return False, "Не удалось скачать флаг из Telegram"