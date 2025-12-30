from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

class IsRPAdmin(BaseFilter):
    async def __call__(self, message: Message, session: AsyncSession) -> bool:
        from app.database.requests import get_current_user_admin_level  # или твоя функция
        level = await get_current_user_admin_level(session, message.from_user.id)
        return level > 0

class IsCountryRuler(BaseFilter):
    async def __call__(self, message: Message, session: AsyncSession) -> bool:
        from app.database.requests import get_user_country
        country = await get_user_country(session, message.from_user.id)
        return country and country.ruler_id == message.from_user.id