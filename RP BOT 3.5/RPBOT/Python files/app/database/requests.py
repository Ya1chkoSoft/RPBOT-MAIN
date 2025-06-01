from sqlalchemy.future import select
from .session import async_session
from .models import User, History

# 1) get_or_create_user: возвращает объект User, создавая нового, если не найден
async def get_or_create_user(user_id: int, username: str) -> User:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(User).where(User.user_id == user_id)
            )
            user = result.scalars().first()
            if user:
                # если есть, обновляем username
                user.username = username
            else:
                # если нет, создаём нового
                user = User(user_id=user_id, username=username)
                session.add(user)
        # при выходе из session.begin() происходит commit
    return user

# 2) get_balance: возвращает points или 0, если нет записи
async def get_balance(user_id: int) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(User.points).where(User.user_id == user_id)
        )
        points = result.scalar_one_or_none()
    return points or 0

# 3) add_points: меняет баллы пользователя и пишет запись в историю
async def add_points(admin_id: int, target_id: int, amount: int, reason: str) -> None:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(User).where(User.user_id == target_id)
            )
            user = result.scalars().first()
            if not user:
                raise ValueError(f"Пользователь {target_id} не найден")
            user.points += amount
            history_entry = History(
                admin_id=admin_id,
                target_id=target_id,
                points=amount,
                reason=reason
            )
            session.add(history_entry)

# 4) get_top: возвращает топ-N пользователей по убыванию points
async def get_top(limit: int = 10) -> list[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.points.desc()).limit(limit)
        )
        top_users = result.scalars().all()
    return top_users

# 5) get_history: возвращает последние записи из history для данного user
async def get_history(target_id: int, limit: int = 20) -> list[History]:
    async with async_session() as session:
        result = await session.execute(
            select(History)
            .where(History.target_id == target_id)
            .order_by(History.timestamp.desc())
            .limit(limit)
        )
        entries = result.scalars().all()
    return entries