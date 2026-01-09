import logging
import html
from html import escape as escape_html
from datetime import datetime
from sqlalchemy import select, update, desc, func, and_, delete # + and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload # + selectinload
from sqlalchemy.future import select
from datetime import datetime, timedelta # + timedelta
from typing import Optional
# Импортируем модели из твоего файла models.py
from .models import User, History, Admins, MemeCountry, CountryReview, CountryBlacklist

# Импортируем модели из твоего файла models.py
# (Убедись, что путь импорта верный, например from .models import ...)
from .models import User, History, Admins, MemeCountry

#Импортируем FuzzyWuzzy для нечеткого поиска
from thefuzz import fuzz

#ИМПОРТ КОНСТАНТЫ
from config import (
    FUZZY_MATCH_THRESHOLD, 
    RP_TO_INFLUENCE_RATIO
)


# ==========================================
# 1. ПОЛЬЗОВАТЕЛИ (USER MANAGEMENT)
# ==========================================
# Предполагается, что User импортирован из models.py

async def get_or_create_user(
    session: AsyncSession, 
    user_id: int, 
    username: str = "", 
    userfullname: str = ""
) -> User:
    """
    Получает пользователя. Если нет — создает.
    """
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Обновление данных
        if user.username != username:
            user.username = username
        if user.userfullname != userfullname:
            user.userfullname = userfullname
        # flush происходит автоматически при commit, но можно и явно
    else:
        # Создание нового
        user = User(
            user_id=user_id, 
            username=username, 
            userfullname=userfullname,
            position="Путешественник", # Явно задаем должность
            points=0,
            adminlevel=0
        )
        session.add(user)
        # await session.flush() # Не обязательно, commit сделает это
    
    return user

async def db_ensure_full_user_profile(
    session: AsyncSession, 
    user_id: int, 
    username: str, 
    userfullname: str
) -> tuple[Optional[User], bool]:
    """
    Гарантированно возвращает профиль пользователя.
    Если юзера нет -> создает, коммитит, сбрасывает кэш и возвращает профиль.
    """
    
    # 1. Сначала пробуем получить (может вернуть None)
    profile = await get_full_user_profile(session, user_id)
    was_created = False
    
    if profile is None:
        try:
            # 2. Создаем (или обновляем базовую запись)
            await get_or_create_user(
                session=session,
                user_id=user_id,
                username=username,
                userfullname=userfullname
            )
            
            # 3. ФИКСИРУЕМ создание
            await session.commit() 
            
            # 4. ВАЖНО: Сбрасываем кэш сессии, чтобы следующий SELECT увидел изменения
            session.expire_all() 
            
            # 5. Загружаем полный профиль заново (теперь он точно есть)
            profile = await get_full_user_profile(session, user_id)
            
            if profile:
                was_created = True
            else:
                logging.error(f"FATAL: User {user_id} created but not found by select!")
            
        except Exception as e:
            await session.rollback()
            logging.error("Критическая ошибка при регистрации пользователя %s: %s", user_id, e)
            return None, False

    return profile, was_created

async def get_full_user_profile(session: AsyncSession, user_id: int) -> User | None:
    """
    Получает профиль пользователя с предзагруженными отношениями.
    - ruled_country_list: чтобы проверка на правителя не вызывала lazy load ошибку.
    - country и admin: как было раньше (joinedload ок для single, но можно на selectinload).
    """
    stmt = (
        select(User)
        .where(User.user_id == user_id)
        .options(
            selectinload(User.ruled_country_list),
            joinedload(User.country),               #(страна гражданина)
            joinedload(User.admin)                  # Если есть админка
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """
    Находит пользователя по его уникальному username (никнейму) в Telegram.
    """
    # Сначала удаляем символ '@', если он присутствует
    clean_username = username.lstrip('@') 
    
    stmt = (
        select(User)
        .where(User.username == clean_username)
    )
    result = await session.execute(stmt)
    # Возвращаем найденный объект User или None, если он не найден
    return result.scalar_one_or_none()


# ==========================================
# 3. АДМИНИСТРАТОРЫ И БАЛЛЫ (ADMINS & POINTS)
# ==========================================

async def add_admin(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    userfullname: Optional[str] = None,
    adminlevel: int = 1
) -> Admins:
    """
    Добавляет нового админа или обновляет существующего.
    Возвращает объект Admins.
    """
    result = await session.execute(
        select(Admins).where(Admins.user_id == user_id)
    )
    admin = result.scalar_one_or_none()

    if admin:
        # Обновляем только если передали новые значения
        if username is not None:
            admin.username = username
        if userfullname is not None:
            admin.userfullname = userfullname
        admin.adminlevel = adminlevel
    else:
        # Создаём нового админа
        admin = Admins(
            user_id=user_id,
            username=username,
            userfullname=userfullname,
            adminlevel=adminlevel
        )
        session.add(admin)

    return admin


async def give_points(
    session: AsyncSession,
    admin_id: int,
    target_id: int,
    points: int,
    reason: str = "Без причины"
) -> str:
    """
    Начисляет очки пользователю от имени админа.
    Проверяет права админа, обновляет баланс, пишет в историю.
    Возвращает строку с результатом (для ответа в чате).
    """
    # 1. Проверка прав админа
    result = await session.execute(
        select(Admins.adminlevel).where(Admins.user_id == admin_id)
    )
    admin_level = result.scalar()

    if not admin_level or admin_level < 1:
        return "🚫 У вас нет прав на начисление очков."

    # 2. Получаем цель
    target_user = await session.get(User, target_id)
    if not target_user:
        return "❌ Пользователь не найден."

    # 3. Проверка иерархии (владелец может всё)
    if admin_id != OWNER_ID:
        target_admin_level = await session.scalar(
            select(Admins.adminlevel).where(Admins.user_id == target_id)
        ) or 0

        if target_admin_level >= admin_level:
            return "🚫 Вы не можете начислять очки админу равного или выше вашего уровня."

    # 4. Начисление очков
    old_balance = target_user.points or 0
    target_user.points = old_balance + points
    session.add(target_user)

    # 5. Запись в историю
    event_type = "POINTS_CHANGE"  # Определяем тип события
    session.add(History(
        admin_id=admin_id,
        target_id=target_id,
        event_type=event_type,
        points=points,
        reason=reason,
        timestamp=datetime.now()
    ))

    # 6. Формируем ответ
    display_name = target_user.userfullname or f"@{target_user.username or 'без_ника'}"
    icon = "📈" if points > 0 else "📉" if points < 0 else "⚖️"

    return (
        f"{icon} Пользователю {display_name} начислено <b>{points:+}</b> RP-очков.\n"
        f"Баланс: <b>{old_balance}</b> → <b>{target_user.points}</b>\n"
        f"Причина: <i>{escape_html(reason)}</i>"
    )



async def get_current_user_admin_level(session: AsyncSession, user_id: int) -> int:
    """
    Возвращает уровень админа пользователя.
    Если админа нет — возвращает 0.
    """
    result = await session.execute(
        select(Admins.adminlevel).where(Admins.user_id == user_id)
    )
    level = result.scalar()
    return level or 0

async def reset_user_cooldown(session: AsyncSession, user_id: int):
    """Сбрасывает дату создания страны для пользователя."""
    user = await session.get(User, user_id)
    if user:
        user.last_country_creation = None
        return True
    return False
# ==========================================
# 4. СТАТИСТИКА (STATS)
# ==========================================

async def get_top_users(session: AsyncSession, limit: int = 10) -> list[User]:
    """
    Топ пользователей + название их страны (за 1 запрос).
    """
    stmt = (
        select(User)
        .order_by(desc(User.points))
        .limit(limit)
        .options(joinedload(User.country)) # Важно для отображения в топе
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_history(session: AsyncSession, target_id: int, limit: int = 20) -> list[History]:
    """История наказаний/поощрений."""
    stmt = (
        select(History)
        .where(History.target_id == target_id)
        .order_by(desc(History.timestamp))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()

# ==========================================
# 5. ОТЗЫВЫ (REVIEWS)
# ==========================================
# Настройки КД
REVIEW_COOLDOWN_DAYS = 7 # Раз в неделю можно менять оценку

# --- ЛОГИКА ОТЗЫВОВ ---

async def check_review_cooldown(session: AsyncSession, user_id: int, country_id: int) -> tuple[bool, str]:
    """
    Проверяет, прошел ли КД. Возвращает (True, "") если можно голосовать,
    или (False, "время") если рано.
    """
    stmt = select(CountryReview.created_at).where(
        and_(
            CountryReview.user_id == user_id,
            CountryReview.country_id == country_id
        )
    )
    last_review_date = await session.scalar(stmt)
    
    if last_review_date:
        # Считаем, сколько прошло
        time_passed = datetime.now() - last_review_date
        cooldown = timedelta(days=REVIEW_COOLDOWN_DAYS)
        
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            # Форматируем время (дни, часы)
            rem_str = str(remaining).split('.')[0] 
            return False, rem_str
            
    return True, ""

async def save_review(session: AsyncSession, user_id: int, country_id: int, rating: int):
    """Сохраняет отзыв (удаляя старый) и обновляет рейтинг страны."""
    
    # 1. Удаляем старый (если был) - благодаря UniqueConstraint это безопасно
    # Но для чистоты created_at лучше сделать upsert или delete+insert
    await session.execute(
        delete(CountryReview).where(
            and_(CountryReview.user_id == user_id, CountryReview.country_id == country_id)
        )
    )
    
    # 2. Вставляем новый
    session.add(CountryReview(user_id=user_id, country_id=country_id, rating=rating))
    await session.flush()
    
    # 3. Пересчитываем среднее для страны
    stats = await session.execute(
        select(func.avg(CountryReview.rating), func.count(CountryReview.review_id))
        .where(CountryReview.country_id == country_id)
    )
    avg, count = stats.one()
    
    # 4. Обновляем страну
    await session.execute(
        update(MemeCountry)
        .where(MemeCountry.country_id == country_id)
        .values(avg_rating=avg if avg else 0, total_reviews=count)
    )

async def get_countries_for_list(session: AsyncSession, page: int, limit: int = 5):
    """
    Возвращает список стран с пагинацией.
    Сортирует: 1. По очкам влияния (убывание). 2. По названию (возрастание).
    """
    offset = (page - 1) * limit
    
    stmt = (
        select(MemeCountry)
        .order_by(
            desc(MemeCountry.influence_points),
            MemeCountry.name
        )
        .offset(offset)
        .limit(limit)
    )
    
    res = await session.execute(stmt)
    
    # Считаем всего стран
    total = await session.scalar(select(func.count()).select_from(MemeCountry))
    return res.scalars().all(), total

# ==========================================
# 5.5 ПЕРЕДАЧА ВЛАСТИ И УДАЛЕНИЕ СТРАНЫ
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

    # Удалить отзывы
    await session.execute(delete(CountryReview).where(CountryReview.country_id == country_id))

    # Удалить blacklist
    await session.execute(delete(CountryBlacklist).where(CountryBlacklist.country_id == country_id))

    # Удалить страну
    await session.delete(country)

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
    """
    Возвращает список стран с пагинацией.
    """
    offset = (page - 1) * limit
    countries = await session.scalars(
        select(MemeCountry).order_by(desc(MemeCountry.influence_points)).offset(offset).limit(limit)
    )
    result = [f"📖 <b>СПИСОК СТРАН (стр. {page})</b>:"]
    for idx, c in enumerate(countries, start=offset+1):
        result.append(f"{idx}. {escape_html(c.name)} — Влияние: {c.influence_points}")
    return "\n".join(result)

async def get_global_stats(session: AsyncSession, limit: int = 10) -> str:
    """
    Топ стран по влиянию.
    """
    countries = await session.scalars(
        select(MemeCountry).order_by(desc(MemeCountry.influence_points)).limit(limit)
    )
    result = ["🏆 <b>ТОП СТРАН ПО ВЛИЯНИЮ</b>:"]
    for idx, c in enumerate(countries, 1):
        result.append(f"{idx}. {escape_html(c.name)} — {c.influence_points}")
    return "\n".join(result)



# ==========================================
# 6. НАКАЗАНИЯ (PUNISHMENTS)
# ==========================================
from .models import Punishment

async def add_punishment(
    session: AsyncSession,
    user_id: int,
    punishment_type: str,
    reason: str,
    admin_id: int | None = None
) -> Punishment:
    """
    Добавляет наказание пользователю.
    Типы: 'country_creation', 'global', 'chat' и т.д.
    """
    # Сначала деактивируем старые наказания этого типа
    await session.execute(
        update(Punishment)
        .where(
            Punishment.user_id == user_id,
            Punishment.punishment_type == punishment_type,
            Punishment.is_active == True
        )
        .values(is_active=False)
    )
    
    # Создаём новое наказание
    punishment = Punishment(
        user_id=user_id,
        punishment_type=punishment_type,
        reason=reason,
        admin_id=admin_id,
        is_active=True
    )
    session.add(punishment)
    return punishment


async def remove_punishment(
    session: AsyncSession,
    user_id: int,
    punishment_type: str
) -> bool:
    """
    Снимает активное наказание.
    Возвращает True, если что-то сняли, False если не нашли.
    """
    result = await session.execute(
        update(Punishment)
        .where(
            Punishment.user_id == user_id,
            Punishment.punishment_type == punishment_type,
            Punishment.is_active == True
        )
        .values(is_active=False)
    )
    return result.rowcount > 0


async def is_punished(
    session: AsyncSession,
    user_id: int,
    punishment_type: str
) -> bool:
    """
    Проверяет, есть ли активное наказание у юзера.
    """
    stmt = select(Punishment).where(
        Punishment.user_id == user_id,
        Punishment.punishment_type == punishment_type,
        Punishment.is_active == True
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def get_active_punishments(
    session: AsyncSession,
    user_id: int
) -> list[Punishment]:
    """
    Возвращает список всех активных наказаний юзера.
    """
    stmt = select(Punishment).where(
        Punishment.user_id == user_id,
        Punishment.is_active == True
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_all_active_punishments_by_type(
    session: AsyncSession,
    punishment_type: str
) -> list[tuple[User, Punishment]]:
    """
    Возвращает список всех активных наказаний определённого типа.
    Возвращает кортежи (User, Punishment) для удобного вывода.
    """
    stmt = (
        select(User, Punishment)
        .join(Punishment, User.user_id == Punishment.user_id)
        .where(
            Punishment.punishment_type == punishment_type,
            Punishment.is_active == True
        )
        .order_by(Punishment.timestamp.desc())
    )
    result = await session.execute(stmt)
    return result.all()