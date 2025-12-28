
import logging
import math 
import asyncio
from datetime import datetime, time, timedelta
from aiogram import Bot # Для рассылки сообщений в чаты стран
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.database.models import User, MemeCountry, History 
from config import DAILY_BONUS_RATIO # Импортируем константу из config.py

logger = logging.getLogger(__name__)

# ==========================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ РАСЧЕТА ЗАДЕРЖКИ
# ==========================================

def get_delay_until_next_run(hour: int, minute: int) -> int:
    """
    Рассчитывает количество секунд до следующего заданного времени (hour:minute).
    """
    now = datetime.now()
    
    # 1. Определяем целевое время сегодня
    target_time_today = datetime.combine(now.date(), time(hour, minute))
    
    # 2. Определяем, когда будет следующий запуск
    if now < target_time_today:
        # Если текущее время меньше целевого, запускаемся сегодня
        next_run = target_time_today
    else:
        # Если целевое время уже прошло, запускаемся завтра
        next_run = target_time_today + timedelta(days=1)
        
    # 3. Рассчитываем задержку в секундах
    delay = (next_run - now).total_seconds()
    return int(delay)


# ==========================================
# ОБНОВЛЕННЫЙ ПЛАНИРОВЩИК ЗАДАЧ
# ==========================================

async def smart_daily_scheduler(bot: Bot, session_factory: async_sessionmaker):
    """
    Запускает распределение бонусов ежедневно в заданное время (например, в 00:00).
    """
    # Задаем целевое время (например, полночь)
    TARGET_HOUR = 0 
    TARGET_MINUTE = 0

    while True:
        # 1. Рассчитываем, сколько секунд осталось до 00:00
        delay_seconds = get_delay_until_next_run(TARGET_HOUR, TARGET_MINUTE)
        
        logger.info(f"Планировщик: Следующий запуск бонусов в {TARGET_HOUR:02d}:{TARGET_MINUTE:02d} через {delay_seconds} секунд.")
        
        # 2. Ждем ровно до целевого времени
        await asyncio.sleep(delay_seconds)
        
        # 3. Выполняем задачу
        await distribute_daily_influence_bonus(bot, session_factory)


# ==========================================
# ЛОГИКА НАЧИСЛЕНИЯ БОНУСОВ
# ==========================================

async def distribute_daily_influence_bonus(bot: Bot, session_factory: async_sessionmaker):
    """
    Ежедневная задача: Начисление пассивных очков гражданам страны 
    на основе Влияния страны, с оповещением в чаты стран.
    """
    
    # Сообщение о начале
    start_message = "⏳ **ВНИМАНИЕ!** Начался подсчёт ежедневных РП-бонусов за Влияние страны. В течение минуты возможны задержки в начислении очков."
    
    # Получаем все страны для рассылки (нужно выполнить до создания сессии для логики)
    async with session_factory() as temp_session:
        country_result = await temp_session.execute(select(MemeCountry))
        countries = country_result.scalars().all()
    
    # 1.1 Рассылка предупреждения
    for country in countries:
        if country.chat_id:
            try:
                await bot.send_message(country.chat_id, start_message, parse_mode='Markdown')
            except Exception as e:
                logger.warning(f"Не удалось отправить предупреждение в чат страны {country.name} ({country.chat_id}): {e}")
    
    # --- ОСНОВНАЯ ЛОГИКА НАЧИСЛЕНИЯ ---
    async with session_factory() as session:
        try:
            updates = [] 
            
            # Повторно получаем страны, но уже для работы с транзакцией
            # Это гарантирует, что мы работаем с актуальными данными в этой сессии
            country_result_tx = await session.execute(select(MemeCountry))
            countries_tx = country_result_tx.scalars().all()
            
            for country in countries_tx:
                influence = country.influence_points
                
                # 2. 🧠 Рассчитываем целое число бонуса, используя импортированную константу
                daily_bonus = influence // DAILY_BONUS_RATIO 
                
                if daily_bonus <= 0:
                    continue

                # 3. Начисление, запись истории и обновление
                users_result = await session.execute(
                    select(User)
                    .where(User.country_id == country.id)
                )
                citizens = users_result.scalars().all()
                
                description = (
                    f"Пассивный бонус страны '{country.name}' "
                    f"(Влияние: {influence}, Начислено: {daily_bonus} RP)."
                )
                
                for user in citizens:
                    user.points += daily_bonus
                    
                    history_record = History(
                        target_id=user.user_id,
                        event_type="daily_influence_bonus",
                        description=description,
                        timestamp=datetime.utcnow()
                    )
                    session.add(history_record)
                    updates.append(1)
                    
                logger.info(f"Страна '{country.name}' начислила {daily_bonus} RP {len(citizens)} гражданам.")

            # 4. Сохранение изменений
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.critical(f"❌ Критическая ошибка при распределении бонусов: {e}")
            
        finally:
            # 5. Оповещаем об успешном начислении
            total_users_updated = len(updates)
            
            if total_users_updated > 0:
                final_message = f"🎉 **Ежедневное начисление завершено!** Обновлено {total_users_updated} пользователей. Проверьте свои РП-очки!"
            else:
                final_message = "✅ Ежедневное начисление завершено. Активных стран для начисления не найдено."
            
            # 5.1 Рассылка оповещения о завершении
            for country in countries: # Используем список, полученный до транзакции
                if country.chat_id:
                    try:
                        await bot.send_message(country.chat_id, final_message, parse_mode='Markdown')
                    except Exception as e:
                        logger.warning(f"Не удалось отправить оповещение о завершении в чат страны {country.name} ({country.chat_id}): {e}")
            
            logger.warning(">>> Процесс ежедневного начисления завершен.")