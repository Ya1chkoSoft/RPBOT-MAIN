"""
Функции для работы с администраторами и наказаниями.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func, and_, delete
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta
from typing import Optional

from ..models import User, History, Admins, MemeCountry, CountryReview, CountryBlacklist, Punishment
from config import OWNER_ID
from app.utils.html_helpers import escape_html

logger = logging.getLogger(__name__)

# ==========================================
# АДМИНИСТРАТОРЫ И БАЛЛЫ
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

# ==========================================
# НАКАЗАНИЯ (PUNISHMENTS)
# ==========================================

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