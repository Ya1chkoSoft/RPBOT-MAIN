import logging
from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем ваши функции и модели
# (точка означает, что мы ищем в той же папке app/database)
from .requests import db_ensure_full_user_profile
from .models import User

logger = logging.getLogger(__name__)

class UserMiddleware(BaseMiddleware):
    """
    Middleware, который выполняется ПОСЛЕ SessionMiddleware.
    1. Берет session из data.
    2. Находит/Создает юзера в БД.
    3. Кладет объект User в data['current_user'].
    """
    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        
        # 1. Проверяем наличие сессии (она должна быть создана SessionMiddleware)
        session: AsyncSession = data.get("session")
        if not session:
            logger.error("UserMiddleware: Session not found! Check SessionMiddleware registration.")
            return await handler(event, data)

        # 2. Получаем данные о пользователе Telegram
        tg_user = event.from_user
        if not tg_user:
            # Если это служебное обновление без пользователя, пропускаем логику БД, но вызываем хендлер
            return await handler(event, data)

        # 3. Загружаем или создаем профиль через вашу функцию
        # db_ensure_full_user_profile делает commit и expire_all, возвращая свежий профиль
        user, was_created = await db_ensure_full_user_profile(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            userfullname=tg_user.full_name
        )

        if user is None:
            logger.critical(f"UserMiddleware: Failed to get/create user {tg_user.id}")
            # Можно прервать выполнение, чтобы не вызывать хендлер с ошибкой
            return 

        # 4. 🔥 САМОЕ ГЛАВНОЕ: Кладем юзера в data
        # Именно отсюда хендлер review_country_handler_new берет аргумент current_user
        data["current_user"] = user

        # 5. Передаем управление хендлеру
        return await handler(event, data)