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
from .models import User, History, Admins, MemeCountry, CountryReview # + CountryReview

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
# 2. МЕМНЫЕ СТРАНЫ (MEME COUNTRIES)
# ==========================================

from typing import Optional # Добавьте импорт, если его нет
from .models import MemeCountry, User # Убедитесь, что User импортирован

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

    # session.commit() должен вызываться в тележке вызова, а не здесь.
    return True, f"Да здравствует новый правитель {country.name} — {user.userfullname}!"
async def get_country_by_name(session: AsyncSession, name: str) -> MemeCountry | None:
    """
    Находит страну по ее названию, не учитывая регистр.
    """
    # Используем func.lower() для поиска без учета регистра
    stmt = select(MemeCountry).where(
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


async def find_country_by_fuzzy_name(session: AsyncSession, query: str) -> Optional[MemeCountry]:
    """Находит страну по названию или мем-имени. 75 — идеальный порог для 50–70 стран."""
    query = query.strip().lower()
    if len(query) < 2:
        return None

    # Берём только нужные поля — быстро и без тормозов
    result = await session.execute(
        select(MemeCountry.country_id, MemeCountry.name, MemeCountry.memename)
    )
    countries = result.all()

    if not countries:
        return None

    best_match = None
    best_score = FUZZY_MATCH_THRESHOLD  # у тебя 75 в конфиге — идеально!

    for country_id, name, memename in countries:
        # Ищем по названию И по мем-имени
        score1 = fuzz.token_sort_ratio(query, name.lower())
        score2 = fuzz.token_sort_ratio(query, (memename or "").lower())
        score = max(score1, score2)

        if score > best_score:
            best_score = score
            best_match = await session.get(MemeCountry, country_id)

    return best_match

# ==========================================
# 2.1 ВСТУПЛЕНИЕ В СТРАНУ (JOIN COUNTRY)
# ==========================================
async def join_country(
    session: AsyncSession,
    user_id: int,
    search_method: str,
    search_value: str
) -> tuple[bool, str]:
    """
    Полная логика вступления в страну.
    Авторегистрация новичков, защита от правителей, рофлы и история.
    """
    # 1. Гарантированно получаем профиль (создаёт, если нет)
    profile, was_created = await db_ensure_full_user_profile(
        session=session,
        user_id=user_id,
        username="",  # Можно передать из message, если хочешь точные данные
        userfullname=""
    )

    if profile is None:
        return False, "❌ Внутренняя ошибка при загрузке профиля. Попробуйте позже."

    user = profile  # Теперь user — полностью загруженный объект

    # Приветствие новичку
    extra_msg = ""
    if was_created:
        extra_msg = "👋 Вы автоматически зарегистрированы в системе!\nДобро пожаловать в мир мемных стран 🎉\n\n"

    # 2. Блокировка для правителей
    # ruled_country_list уже загружен через joinedload в get_full_user_profile
    if user.ruled_country_list:
        return False, (
            "🚫 Вы — правитель одной или нескольких стран.\n"
            "Пока у вас есть власть, вступить в другую страну нельзя.\n"
            "Удалите или передайте свою страну сначала."
        )

    # 3. Поиск страны
    target_country = None
    if search_method == "id":
        try:
            target_id = int(search_value)
            target_country = await session.get(MemeCountry, target_id)
        except ValueError:
            return False, "🚫 ID страны должен быть числом."

    elif search_method == "name":
        target_country = await find_country_by_fuzzy_name(session, search_value)
    else:
        return False, "🚫 Неизвестный метод. Используйте <code>id</code> или <code>name</code>."

    if not target_country:
        return False, f"❌ Страна не найдена по запросу: <b>{search_value}</b>"

    # 4. Уже в этой стране?
    if user.country_id == target_country.country_id:
        return False, f"ℹ️ Вы уже гражданин <b>{hbold(target_country.name)}</b>."

    # 5. Определяем тип события и текст
    old_country_name = None
    if user.country_id:
        old_country = await session.get(MemeCountry, user.country_id)
        if old_country:
            old_country_name = old_country.name

    if old_country_name:
        event_type = "CHANGE_COUNTRY"
        reason = f"Смена страны: {old_country_name} → {target_country.name}"
        welcome_text = (
            f"✅ Вы сменили гражданство!\n"
            f"Теперь вы гражданин <b>{target_country.name}</b>.\n"
            f"Предательство? Или поиск лучшей жизни? 🤔"
        )
    else:
        event_type = "JOIN_COUNTRY"
        reason = f"Вступление в страну: {target_country.name}"
        welcome_text = (
            f"✅ Добро пожаловать в <b>{target_country.name}</b>!\n"
            f"Теперь вы официальный гражданин 🎉"
        )

    # 6. Обновляем пользователя
    user.country_id = target_country.country_id
    user.position = "Гражданин"

    # 7. Записываем в историю
    session.add(History(
        admin_id=None,
        target_id=user_id,
        event_type=event_type,
        points=0,
        reason=reason
    ))

    await session.flush()

    # 8. Финальный текст с приветствием новичку
    final_text = extra_msg + welcome_text
    return True, final_text
# ==========================================
# 2.2 ВЫХОД ИЗ СТРАНЫ (LEAVE COUNTRY / LEAVE)
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
    
    # Эта проверка должна выполняться, потому что мы не используем get_or_create_user здесь
    if not user:
         return False, "Пользователь не найден в базе.", None

    if user.country_id is None:
        return False, "Вы ни в какой стране не состоите.", None
    
    # Правитель не может просто "выйти", он должен отречься через /transferpower
    if user.is_ruler:
        return False, "Вы правитель! Используйте команду передачи власти.", None


    country_name = user.country.name if user.country else "Неизвестная страна"

    # Обнуление полей
    user.country_id = None
    user.position = "Путешественник"

    await session.flush()
    
    return True, "Успешно", country_name


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
    session.add(History(
        admin_id=admin_id,
        target_id=target_id,
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