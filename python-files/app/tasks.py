import logging
import asyncio
from datetime import datetime, time, timedelta, timezone
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database.models import User, MemeCountry, History 
from config import DAILY_BONUS_RATIO
from app.utils.html_helpers import escape_html 

logger = logging.getLogger(__name__)

async def distribute_daily_influence_bonus(bot: Bot, session_factory: async_sessionmaker):
    # Используем одну сессию на весь процесс
    async with session_factory() as session:
        try:
            # 1. Загружаем страны СРАЗУ вместе с их гражданами (Eager Loading)
            # Это ОДИН запрос к БД вместо десятков. Твой i5 скажет спасибо.
            result = await session.execute(
                select(MemeCountry).options(selectinload(MemeCountry.citizens))
            )
            countries = result.scalars().all()
            
            if not countries:
                logger.info("Стран для начисления бонусов не найдено.")
                return

            total_updated = 0
            
            for country in countries:
                influence = country.influence_points
                daily_bonus = influence // DAILY_BONUS_RATIO
                
                if daily_bonus <= 0 or not country.citizens:
                    continue

                # Подготовка сообщения
                c_name = escape_html(country.name)
                description = f"Пассивный бонус страны '{c_name}' (Влияние: {influence}, Бонус: {daily_bonus} RP)."
                
                # Массовое обновление объектов в памяти
                for user in country.citizens:
                    user.points += daily_bonus
                    
                    # Создаем запись истории
                    history = History(
                        target_id=user.user_id,
                        event_type="daily_bonus",
                        description=description,
                        timestamp=datetime.now(timezone.utc)
                    )
                    session.add(history)
                    total_updated += 1

                # Оповещаем чат страны (если есть ID)
                if country.chat_id:
                    try:
                        msg = (f"🎉 <b>Ежедневное начисление!</b>\n"
                               f"Страна <b>{c_name}</b> принесла гражданам по <b>{daily_bonus}</b> RP.")
                        await bot.send_message(country.chat_id, msg, parse_mode='HTML')
                    except Exception as e:
                        logger.warning(f"Ошибка рассылки в чат {country.chat_id}: {e}")

            # Фиксируем всё одним махом
            if total_updated > 0:
                logger.info(f"Успешно начислено бонусов {total_updated} пользователям.")
            
        except Exception as e:
            logger.error(f"Критическая ошибка планировщика: {e}", exc_info=True)

# Функция задержки (оставляем как была, она норм)
def get_delay_until_next_run(hour: int, minute: int) -> int:
    now = datetime.now()
    target = datetime.combine(now.date(), time(hour, minute))
    if now >= target:
        target += timedelta(days=1)
    return int((target - now).total_seconds())

async def smart_daily_scheduler(bot: Bot, session_factory: async_sessionmaker):
    TARGET_HOUR, TARGET_MINUTE = 0, 0
    while True:
        delay = get_delay_until_next_run(TARGET_HOUR, TARGET_MINUTE)
        logger.info(f"Бонусы через {delay} сек. ({TARGET_HOUR:02d}:{TARGET_MINUTE:02d})")
        await asyncio.sleep(delay)
        await distribute_daily_influence_bonus(bot, session_factory)