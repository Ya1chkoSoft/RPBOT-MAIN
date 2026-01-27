import logging
from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем только то, что нужно. 
# Мы импортируем функцию получения юзера, которая НЕ вызывает циклов.
from app.database.requests.users import get_or_create_user

logger = logging.getLogger(__name__)

class UserMiddleware(BaseMiddleware):
    """
    Чистый Middleware для работы с пользователем.
    Работает в едином цикле транзакции, без принудительных коммитов.
    """
    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        
        # 1. Сессия должна быть проброшена из SessionMiddleware выше
        session: AsyncSession = data.get("session")
        if not session:
            logger.error("UserMiddleware: Сессия не найдена в data!")
            return await handler(event, data)

        # 2. Игнорируем апдейты без юзера (например, посты в каналах)
        tg_user = event.from_user
        if not tg_user or tg_user.is_bot:
            return await handler(event, data)

        try:
            user = await get_or_create_user(
                session=session,
                user_id=tg_user.id,
                username=tg_user.username or "",
                userfullname=tg_user.full_name or ""
            )

            # 4. Кладем объект в data под коротким именем 'user'
            # Теперь в любом хендлере можно просто добавить аргумент 'user: User'
            data["user"] = user

        except Exception as e:
            logger.error(f"Ошибка в UserMiddleware для юзера {tg_user.id}: {e}")
            # В случае ошибки БД лучше не ломать бота, а пропустить запрос дальше,
            # хендлеры сами разберутся, если 'user' будет None.
            data["user"] = None

        return await handler(event, data)