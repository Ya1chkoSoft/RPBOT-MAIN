from sqlalchemy.future import select
from sqlalchemy.orm import Session
from .session import async_session
from .models import User, History, Admins
from datetime import datetime

# 1) get_or_create_user: возвращает объект User, создавая нового, если не найден
async def get_or_create_user(user_id: int, username: str, userfullname:str) -> User:
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
                user = User(user_id=user_id, username=username,userfullname=userfullname)
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

async def add_admin(user_id: int, username: str | None = None, userfullname: str | None = None, adminlevel: int = 1) -> Admins:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(Admins).where(Admins.user_id == user_id))
            admin = result.scalars().first()

            if admin:
                updated = False
                if username and admin.username != username:
                    admin.username = username
                    updated = True
                if userfullname and admin.userfullname != userfullname:
                    admin.userfullname = userfullname
                    updated = True
                if admin.adminlevel != adminlevel:
                    admin.adminlevel = adminlevel
                    updated = True
                return admin

            new_admin = Admins(
                user_id=user_id,
                username=username,
                userfullname=userfullname,
                adminlevel=adminlevel
            )
            session.add(new_admin)
            return new_admin
        
async def get_user_by_username(username: str):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        return result.scalars().first()
    
# 4) add_points: меняет баллы пользователя и пишет запись в историю
def give_points(session: Session, admin_id: int, target_id: int, points: int, reason: str) -> str:
    # 1. Получаем админа
    admin = session.query(Admins).filter_by(user_id=admin_id).first()
    if not admin:
        return "Ошибка: Вы не админ."

    # 2. Получаем целевого пользователя
    target_user = session.query(User).filter_by(user_id=target_id).first()
    if not target_user:
        return "Ошибка: Пользователь не найден."

    # 3. Проверка прав админа (может добавить свои условия, например, >= target.level и т.д.)
    if admin.adminlevel == 0:
        return "Ошибка: У вас нет прав начислять очки."

    # 4. Начисляем очки
    target_user.points += points

    # 5. Сохраняем историю
    history = History(
        admin_id=admin_id,
        target_id=target_id,
        points=points,
        reason=reason,
        timestamp=datetime.now()
    )
    session.add(history)

    # 6. Подтверждаем изменения
    session.commit()
    return f"✅ {points} очков начислено пользователю {target_user.userfullname or target_user.username} за: {reason}"

# 5) get_top: возвращает топ-N пользователей по убыванию points
async def get_top(limit: int = 10) -> list[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.points.desc()).limit(limit)
        )
        top_users = result.scalars().all()
    return top_users

# 6) get_history: возвращает последние записи из history для данного user
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
