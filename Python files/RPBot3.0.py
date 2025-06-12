import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from app.handlers import router
from app.database.models import async_main

# 1) Загружаем .env (должен лежать в корне проекта рядом с папкой app)
load_dotenv()
BOT_TOKEN = os.getenv('BOT')

# 2) Включаем логирование
logging.basicConfig(level=logging.INFO)

# 3) Создаём объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN,default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# 4) Обязательно подключаем роутер ДО старта polling
dp.include_router(router)

async def on_startup():
    logging.info("Инициализация базы...")
    await async_main()  # создаёт все таблицы если их нет
    logging.info("База готова. Запускаем бота.")

async def on_shutdown():
    logging.info("Останавливаем бота...")
    await bot.session.close()
    logging.info("Бот остановлен.")

if __name__ == "__main__":
    # 5) Запускаем polling с колбеками
    try:
        dp.run_polling(
            bot,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=True
        )
    except KeyboardInterrupt:
        logging.info("Бот завершён вручную.")