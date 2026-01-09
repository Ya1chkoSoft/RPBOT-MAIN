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

async def reset_user_cooldown(session: AsyncSession, user_id: int):
    """Сбрасывает дату создания страны для пользователя."""
    user = await session.get(User, user_id)
    if user:
        user.last_country_creation = None
        return True
    return False