import logging
import os
import sys
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.handlers import router
from app.database.models import async_main
from app.database.session import engine
from app.countrycreate import country_create_router
from app.database.session import async_session as DB_POOL
from app.admin_router import admin_router

# --- МИДЛВАРЕ ---
from app.database.middleware import SessionMiddleware 
from app.database.user_middleware import UserMiddleware
# ----------------------------------------
DATABASE_URL = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/{os.getenv('POSTGRES_DB')}"
logger = logging.getLogger(__name__)

async def main() -> None:
    load_dotenv()
    BOT_TOKEN = os.getenv('BOT')

    if not BOT_TOKEN:
        logger.error("Error: BOT_TOKEN is not set in the environment.")
        sys.exit(1)

    # === Ожидание готовности PostgreSQL ===
    max_attempts = 30  # Максимум 30 попыток (2.5 минуты)
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        try:
            async with engine.connect() as conn:
                pass
            logger.info("✅ Подключение к PostgreSQL успешно.")
            break

        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL не готов (попытка {attempt}/{max_attempts}). Ожидание 5 секунд...")
            logger.debug(f"Подробная ошибка подключения: {e}")  # Детали в debug (если включишь уровень DEBUG)
            await asyncio.sleep(5)
    else:
        logger.error("❌ Не удалось подключиться к PostgreSQL после %s попыток. Завершаю работу.", max_attempts)
        sys.exit(1)


    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    ) 
    dp = Dispatcher()

    # ============================================================
    #MIDDLEWARE (ПОРЯДОК ВАЖЕН)
    # ============================================================
    # 1. Сначала SessionMiddleware.
    dp.update.outer_middleware(SessionMiddleware()) 
    # 2. Затем UserMiddleware.
    # Он работает внутри сессии. Регистрируем на message и callback_query.
    user_middleware = UserMiddleware()
    dp.message.middleware(user_middleware)
    dp.callback_query.middleware(user_middleware)

    # ============================================================
    dp.include_router(admin_router)
    dp.include_router(country_create_router)
    dp.include_router(router)

    async def on_startup() -> None:
        await async_main()
        logger.info("✅ Database initialized and ready.")
    
    dp.startup.register(on_startup)

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error("An error occurred during polling: %s", e)
    finally:
        logger.info("Bot shutting down.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    try:
        asyncio.run(main()) 
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")