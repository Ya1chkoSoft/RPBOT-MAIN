from datetime import datetime, timedelta
from sqlalchemy import select, func, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Tuple, Optional, Any
from aiogram.utils.markdown import hbold # Для безопасного экранирования HTML

from config import REVIEW_COOLDOWN_DAYS

from .database.models import CountryReview, MemeCountry, User
class ReviewService:
    """Сервис для обработки логики, связанной с оценкой правительства/стран."""
    
    def __init__(self, cooldown_days: int):
        self.cooldown = timedelta(days=cooldown_days)

    async def _check_cooldown(self, session: AsyncSession, user_id: int, country_id: int) -> Tuple[bool, str]:
        """Проверяет, прошел ли кулдаун (REVIEW_COOLDOWN_DAYS) для повторной оценки."""
        
        # Находим дату последнего отзыва пользователя о данной стране
        stmt = select(CountryReview.created_at).where(
            and_(CountryReview.user_id == user_id, CountryReview.country_id == country_id)
        ).order_by(CountryReview.created_at.desc()).limit(1)

        last_review_date = await session.scalar(stmt)
        
        if last_review_date:
            time_passed = datetime.now() - last_review_date 
            
            if time_passed < self.cooldown:
                remaining = self.cooldown - time_passed
                
                # Форматирование оставшегося времени (Д:Ч:М:С)
                total_seconds = int(remaining.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                rem_str = f"{remaining.days}д {hours:02}ч {minutes:02}м {seconds:02}с"
                return False, rem_str
                
        return True, ""

    async def _update_country_stats(self, session: AsyncSession, country_id: int) -> MemeCountry:
        """Пересчитывает средний рейтинг и количество отзывов для страны."""
        
        # 1. Пересчитываем среднее для страны
        stats = await session.execute(
            select(func.avg(CountryReview.rating), func.count(CountryReview.review_id))
            .where(CountryReview.country_id == country_id)
        )
        avg, count = stats.one()
        
        # 2. Обновляем страну (используем update, чтобы избежать race conditions)
        update_stmt = (
            update(MemeCountry)
            .where(MemeCountry.country_id == country_id) # Предполагаю, что primary key - country_id
            .values(
                avg_rating=avg if avg is not None else 0.0, 
                total_reviews=count
            )
        )
        
        await session.execute(update_stmt)
        
        # 3. Принудительно загружаем обновленный объект для возврата в хендлер
        updated_country = await session.get(MemeCountry, country_id)
        
        # Если get вернул None, что-то пошло не так
        if updated_country is None:
             raise ValueError(f"Не удалось найти страну с ID {country_id} после обновления.")
             
        return updated_country

    async def handle_rating(
        self, 
        session: AsyncSession, 
        user_id: int, 
        country_name: str, 
        rating: int, 
        user_country_id: Optional[int]
    ) -> Tuple[bool, str]:
        """Обрабатывает полный цикл оценки правительства/страны."""
        
        # 1. Находим целевую страну
        target_country = await session.scalar(
            select(MemeCountry).where(MemeCountry.name == country_name)
        )

        if not target_country:
            return False, f"Страна с названием <b>{hbold(country_name)}</b> не найдена."

        # 2. ПРОВЕРКА: Правитель не может оценивать свое правительство
        # NOTE: Предполагается, что MemeCountry имеет атрибут 'ruler_id'
        if user_id == target_country.ruler_id:
            return False, "👑 Как правитель, Вы не можете оценивать свое собственное правительство."
            
        # 3. ПРОВЕРКА КУЛДАУНА
        can_review, remaining_time_str = await self._check_cooldown(
            session, user_id, target_country.country_id # Используем Country ID
        )
        
        if not can_review:
            message = (
                f"⏳ Вы уже оценивали правительство <b>{hbold(target_country.name)}</b> недавно. "
                f"Можете изменить оценку через: {remaining_time_str}."
            )
            return False, message
            
        # 4. Сохранение отзыва (DELETE + INSERT для сброса created_at)
        # Удаляем старый отзыв (если есть)
        await session.execute(
            delete(CountryReview).where(
                and_(CountryReview.user_id == user_id, CountryReview.country_id == target_country.country_id)
            )
        )
        # Вставляем новый отзыв с текущим временем
        session.add(CountryReview(user_id=user_id, country_id=target_country.country_id, rating=rating, created_at=datetime.now()))
        await session.flush() 
        
        # 5. Обновление статистики (в той же транзакции)
        updated_country = await self._update_country_stats(session, target_country.country_id)
        
        # 6. Успешный ответ
        response = (
            f"✅ Вы успешно поставили оценку <b>{rating}⭐</b> правительству <b>{hbold(updated_country.name)}</b>.\n\n"
            f"Новый средний рейтинг страны: <b>{updated_country.avg_rating:.2f}</b> (Отзывов: {updated_country.total_reviews})"
        )
        
        return True, response