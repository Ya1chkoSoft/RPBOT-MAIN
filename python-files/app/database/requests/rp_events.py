from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.models import RPEvent, RPParticipant, User
from app.database.requests.admins import get_current_user_admin_level
async def create_rp_event(session: AsyncSession, admin_id: int, chat_id: int, title: str, description: str = None, reward_points: int = 10) -> tuple[bool, str, int]:
    """Создает новый РП-ивент"""
    # Проверяем, есть ли активный ивент у этого администратора
    existing_event = await session.scalar(
        select(RPEvent).where(
            RPEvent.admin_id == admin_id,
            RPEvent.status == 'active'
        )
    )
    
    if existing_event:
        return False, "У вас уже есть активный RP-ивент! Завершите его перед созданием нового.", 0
    
    event = RPEvent(
        admin_id=admin_id,
        chat_id=chat_id,
        title=title,
        description=description
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return True, "РП-ивент создан!", event.event_id

async def add_participant(session: AsyncSession, event_id: int, user_id: int) -> tuple[bool, str]:
    """Добавляет участника в РП-ивент"""
    # Проверяем, не участвует ли уже пользователь
    existing = await session.scalar(
        select(RPParticipant).where(
            RPParticipant.event_id == event_id,
            RPParticipant.user_id == user_id
        )
    )
    
    if existing:
        return False, "Вы уже участвуете в этом РП!"
    
    participant = RPParticipant(event_id=event_id, user_id=user_id)
    session.add(participant)
    return True, "Вы добавлены в список участников!"


async def leave_rp_event(session: AsyncSession, event_id: int, user_id: int) -> tuple[bool, str]:
    """Пользователь выходит из РП-ивента сам"""
    # Проверяем, существует ли участник
    participant = await session.scalar(
        select(RPParticipant).where(
            RPParticipant.event_id == event_id,
            RPParticipant.user_id == user_id
        )
    )
    
    if not participant:
        return False, "Вы не участвуете в этом РП-ивенте!"
    
    await session.delete(participant)
    return True, "Вы покинули РП-ивент!"


async def kick_participant(session: AsyncSession, event_id: int, user_id: int, admin_id: int) -> tuple[bool, str]:
    """Администратор удаляет участника из РП-ивента"""
    # Проверяем права администратора
    admin_level = await get_current_user_admin_level(session, admin_id)
    if admin_level < 1:
        return False, "Только администраторы могут удалять участников!"
    
    # Проверяем, существует ли участник
    participant = await session.scalar(
        select(RPParticipant).where(
            RPParticipant.event_id == event_id,
            RPParticipant.user_id == user_id
        )
    )
    
    if not participant:
        return False, "Этот пользователь не участвует в РП-ивенте!"
    
    await session.delete(participant)
    return True, "Участник удален из РП-ивента администратором!"

async def get_event_participants_with_users(session: AsyncSession, event_id: int):
    """Получает участников с их данными за один запрос"""
    result = await session.execute(
        select(RPParticipant, User)
        .join(User, RPParticipant.user_id == User.user_id)
        .where(RPParticipant.event_id == event_id)
        .order_by(RPParticipant.joined_at)
    )
    return result.all()  # Вернет кортежи (participant, user)

async def remove_participant(session: AsyncSession, event_id: int, user_id: int, admin_id: int) -> tuple[bool, str]:
    """Удаляет участника из РП-ивента"""
    # Проверяем, существует ли ивент
    event = await session.get(RPEvent, event_id)
    if not event:
        return False, "РП-ивент не найден!"
    
    # Проверяем, является ли пользователь администратором
    admin_level = await get_current_user_admin_level(session, admin_id)
    if admin_level < 1:
        return False, "Только администраторы могут удалять участников!"
    
    # Проверяем, существует ли участник
    participant = await session.scalar(
        select(RPParticipant).where(
            RPParticipant.event_id == event_id,
            RPParticipant.user_id == user_id
        )
    )
    
    if not participant:
        return False, "Участник не найден в этом ивенте!"
    
    # Удаляем участника
    await session.delete(participant)
    return True, "Участник удален из ивента!"


async def end_rp_event(session: AsyncSession, event_id: int, admin_id: int, reward_points: int = 10) -> tuple[bool, str]:
    """Завершает РП-ивент и начисляет очки"""
    event = await session.get(RPEvent, event_id)
    if not event:
        return False, "РП-ивент не найден!"
    
    if event.admin_id != admin_id:
        return False, "Только создатель может завершить ивент!"
    
    if event.status != 'active':
        return False, "Ивент уже завершен!"
    
    event.status = 'finished'
    event.finished_at = func.now()
    
    participants_with_users = await session.execute(
        select(RPParticipant, User)
        .join(User, RPParticipant.user_id == User.user_id)
        .where(RPParticipant.event_id == event_id)
    )
    participants_list = participants_with_users.all()
    
    # Начисляем очки всем участникам (кроме создателя ивента)
    for participant, user in participants_list:
        if user.user_id != admin_id:  # Не начисляем очки создателю ивента
            user.points += reward_points
            # Логируем начисление очков (опционально)
            print(f"Начислено {reward_points} RP-очков пользователю {user.user_id}")
    
    return True, f"Ивент завершен! {len(participants_list)} участникам начислено {reward_points} очков!"


async def get_chat_rp_events(session: AsyncSession, chat_id: int) -> list[RPEvent]:
    """Получает историю RP-ивентов в чате"""
    result = await session.execute(
        select(RPEvent).where(RPEvent.chat_id == chat_id).order_by(RPEvent.created_at.desc())
    )
    return result.scalars().all()

from sqlalchemy import delete, text

async def clear_rp_events(session: AsyncSession, admin_id: int) -> tuple[bool, str]:
    """Очищает все RP-ивенты и участников (Secure & Optimized)"""
    # 1. Проверка прав (как и была)
    admin_level = await get_current_user_admin_level(session, admin_id)
    if admin_level < 4:
        return False, "🚫 У вас недостаточно прав для этой операции!"
    try:
        # 2. Используем TRUNCATE для PostgreSQL — это быстрее и чище для больших баз
        # CASCADE удалит зависимых участников автоматически, если настроены FK
        # RESTART IDENTITY сбросит счетчики ID до 1
        await session.execute(text("TRUNCATE TABLE rp_events, rp_participants RESTART IDENTITY CASCADE"))
        # 3. Фиксируем изменения
        await session.commit()
        return True, "🗑️ База данных ивентов полностью очищена и обнулена!"
    except Exception as e:
        await session.rollback()  # Откатываемся, если что-то пошло не так
        return False, f"❌ Ошибка при очистке: {str(e)}"

