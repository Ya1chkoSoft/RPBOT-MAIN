"""
Функции для работы с пользователями.
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

async def get_or_create_user(
    session: AsyncSession, 
    user_id: int, 
    username: str = "", 
    userfullname: str = ""
) -> User:
    """
    Получает пользователя со всеми связями. Если нет — создает.
    """
    # Используем selectinload, чтобы связи были доступны сразу в памяти
    stmt = (
        select(User)
        .where(User.user_id == user_id)
        .options(
            selectinload(User.ruled_country_list), # Чтобы проверка if user.ruled_country_list не падала
            selectinload(User.country),            # Чтобы сразу видеть название страны
            selectinload(User.punishments)         # Чтобы проверка на бан работала мгновенно
        )
    )
    
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Обновление данных (если изменились в телеге)
        if user.username != username:
            user.username = username
        if user.userfullname != userfullname:
            user.userfullname = userfullname
    else:
        # Создание нового профиля
        user = User(
            user_id=user_id, 
            username=username, 
            userfullname=userfullname,
            position="Путешественник",
            points=0,
            adminlevel=0
        )
        session.add(user)
    
    # flush поднимет ID и зафиксирует изменения в текущей транзакции
    await session.flush()
    
    return user

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

async def reset_user_cooldown(session: AsyncSession, user_id: int):
    """Сбрасывает дату создания страны для пользователя."""
    user = await session.get(User, user_id)
    if user:
        user.last_country_creation = None
        return True
    return False

# ==========================================
# 🎰 ТОП ЛУДОМАНОВ (Проёбанные баблишки в казике)
# ==========================================
async def get_top_ludomans(session: AsyncSession) -> list[User]:
    """
    Получает топ 10 пользователей, которые больше всего проебали в казино
    """
    try:
        stmt = (
            select(User)
            .where(User.lost_in_casino > 0)  # Только те, кто что-то проебал
            .order_by(User.lost_in_casino.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        top_users = result.scalars().all()
        return list(top_users)
    except Exception as e:
        logger.error(f"Error in get_top_ludomans: {e}")
        return []