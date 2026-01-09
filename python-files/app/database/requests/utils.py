"""
Утилиты для работы с базой данных.
Специально для особых запросов, которые пока не отнесены к конкретным группам.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from ..models import Punishment, User, MemeCountry
from config import OWNER_ID

logger = logging.getLogger(__name__)

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

async def get_user_country(session: AsyncSession, user_id: int) -> MemeCountry | None:
    """Получает страну пользователя по его ID."""
    user = await session.get(User, user_id)
    if not user or not user.country_id:
        return None
    
    country = await session.get(MemeCountry, user.country_id)
    return country
