"""
Функции для работы с отзывами и рейтингами.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, select, update, desc, func, and_, delete
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

from ..models import User, History, MemeCountry, CountryReview
# Убедись, что импорты соответствуют твоей структуре

logger = logging.getLogger(__name__)

# Константы
REVIEW_COOLDOWN_DAYS = 7 

# ==========================================
# ОТЗЫВЫ (REVIEWS)
# ==========================================

async def check_review_cooldown(session: AsyncSession, user_id: int, country_id: int) -> tuple[bool, str]:
    stmt = select(CountryReview.created_at).where(
        and_(
            CountryReview.user_id == user_id,
            CountryReview.country_id == country_id
        )
    ).order_by(desc(CountryReview.created_at)) # Берем самый свежий
    
    last_review_date = await session.scalar(stmt)
    
    if last_review_date:
        time_passed = datetime.now() - last_review_date
        cooldown = timedelta(days=REVIEW_COOLDOWN_DAYS)
        
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            rem_str = str(remaining).split('.')[0] 
            return False, rem_str
            
    return True, ""

async def save_review(session: AsyncSession, user_id: int, country_id: int, rating: int) -> tuple[bool, str]:
    """
    Сохраняет отзыв и обновляет рейтинг страны.
    """
    try:
        # 1. Удаляем старый
        await session.execute(
            delete(CountryReview).where(
                and_(CountryReview.user_id == user_id, CountryReview.country_id == country_id)
            )
        )
        
        # 2. Вставляем новый
        session.add(CountryReview(
            user_id=user_id, 
            country_id=country_id, 
            rating=rating,
            created_at=datetime.utcnow() # Используй utcnow для стабильности
        ))
        
        await session.flush()
        
        # 3. Пересчитываем среднее
        stats = await session.execute(
            select(func.avg(CountryReview.rating), func.count(CountryReview.review_id))
            .where(CountryReview.country_id == country_id)
        )
        avg, count = stats.one()
        
        # 4. Обновляем страну
        await session.execute(
            update(MemeCountry)
            .where(MemeCountry.country_id == country_id)
            .values(
                avg_rating=float(avg) if avg else 0.0, 
                total_reviews=int(count)
            )
        )

        # ВОТ ЭТОГО НЕ ХВАТАЛО:
        return True, "✅ Ваш отзыв успешно сохранен!"

    except Exception as e:
        logger.error(f"Error in save_review: {e}")
        return False, "❌ Ошибка при сохранении отзыва."

async def get_countries_for_list(
    session: AsyncSession,
    page: int,
    limit: int = 5,
    sort_by: str = "influence"
) -> Tuple[List[MemeCountry], int]:
    """
    Получает список стран с безопасной пагинацией и валидацией.
    """
    # 1. Защита от кривых входных данных (Security/Validation)
    page = max(1, page)
    limit = min(100, max(1, limit)) # Ограничиваем сверху, чтобы не положить базу
    offset = (page - 1) * limit

    # 2. Маппинг сортировки
    # Используем dict.get() — это правильно, защищает от SQL-инъекций через sort_by
    sort_options = {
        "influence": desc(MemeCountry.influence_points),
        "rating": desc(MemeCountry.avg_rating),
        "newest": desc(MemeCountry.created_at),
        "members": desc(MemeCountry.total_reviews)
    }
    
    order_criterion = sort_options.get(sort_by, sort_options["influence"])

    # 3. Основной запрос
    stmt = (
        select(MemeCountry)
        .order_by(order_criterion, asc(MemeCountry.name))
        .offset(offset)
        .limit(limit)
    )

    # 4. Выполнение (используем scalars() для чистого списка объектов)
    res = await session.execute(stmt)
    countries = res.scalars().all()

    # 5. Подсчет общего количества (лучше делать это через Scalar)
    total_stmt = select(func.count()).select_from(MemeCountry)
    total = await session.scalar(total_stmt) or 0

    return list(countries), total
# ==========================================
# СТАТИСТИКА И ИСТОРИЯ (Заглушки для импорта)
# ==========================================

async def get_top_users(session: AsyncSession, limit: int = 10):
    """
    Топ пользователей по очкам.
    """
    stmt = (
        select(User)
        .order_by(desc(User.points))
        .limit(limit)
        .options(joinedload(User.country))
    )
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_history(session: AsyncSession, target_id: int, limit: int = 20):
    """
    История действий/наказаний.
    """
    from ..models import History
    from sqlalchemy import desc
    
    stmt = (
        select(History)
        .where(History.target_id == target_id)
        .order_by(desc(History.timestamp))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
