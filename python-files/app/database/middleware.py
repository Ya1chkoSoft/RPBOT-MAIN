import logging
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

# Импортируем твой настроенный maker сессий
from .session import async_session

logger = logging.getLogger(__name__)

class SessionMiddleware(BaseMiddleware):
    """
    Middleware, которое создает асинхронную сессию на каждый запрос 
    и передает ее в хендлеры через аргумент 'session: AsyncSession'.
    """
    # session_pool по умолчанию берется из .session.py
    def __init__(self, session_pool: async_sessionmaker = async_session):
        self.session_pool = session_pool
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        # 1. Открываем новую сессию для обработки запроса
        async with self.session_pool() as session:
            # 2. Добавляем сессию в словарь 'data'. 
            # Теперь она доступна в хендлере!
            data["session"] = session
            
            try:
                # 3. Вызываем сам хендлер (где происходит вся логика)
                result = await handler(event, data)
                await session.commit()  # Явно коммитим, если все прошло успешно
            except Exception as e:
                # В случае ошибки в хендлере - откатываем все изменения в базе
                logger.error("🚫 Ошибка в хендлере, откат транзакции: %s", e)
                await session.rollback()
                raise e # Передаем исключение выше, чтобы бот знал об ошибке
            
            
            return result