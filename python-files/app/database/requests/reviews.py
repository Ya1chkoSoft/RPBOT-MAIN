"""
Функции для работы с отзывами и рейтингами.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func, and_, delete
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta
from typing import Optional

from ..models import User, History, Admins, MemeCountry, CountryReview, CountryBlacklist
from config import OWNER_ID
from app.utils.html_helpers import escape_html

logger = logging.getLogger(__name__)

# Константы
REVIEW_COOLDOWN_DAYS = 7 # Раз в неделю можно менять оценку

# ==========================================
# ОТЗЫВЫ (REVIEWS)
# ==========================================

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
    """
    Сохраняет отзыв (удаляя старый) и обновляет рейтинг страны.
    """
    
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
# СТАТИСТИКА (STATS)
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