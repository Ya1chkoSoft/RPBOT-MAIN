import os
import sys
import logging
import tempfile
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from app.handlers import router
from app.database.models import async_main

load_dotenv()
BOT_TOKEN = os.getenv('BOT')

log_handlers = [logging.StreamHandler(stream=sys.stdout)]

# используем системный временный каталог
tmp_dir = tempfile.gettempdir()
log_file_path = os.path.join(tmp_dir, "bot_debug.log")

try:
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    log_handlers.append(file_handler)
except Exception as e:
    # если что-то пойдет не так — оставляем только stdout и выводим warning
    print("WARNING: cannot create file log handler:", e, file=sys.stderr)

logging.basicConfig(
    level=logging.DEBUG,  # DEBUG чтобы ловить logger.debug(...) из хендлеров
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    handlers=log_handlers
)

logging.getLogger('aiogram').setLevel(logging.INFO)
logging.getLogger('app').setLevel(logging.DEBUG)

# выводим путь к лог-файлу для удобства
logging.info("Логи пишутся в: %s", log_file_path)
# ----------------- /ЛОГИРОВАНИЕ -----------------

# ВАЖНО: устанавливаем глобально parse_mode=None, чтобы Telegram не парсил HTML
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
dp = Dispatcher()

dp.include_router(router)

async def on_startup():
    logging.info("Инициализация базы...")
    await async_main()
    logging.info("База готова. Запускаем бота.")

async def on_shutdown():
    logging.info("Останавливаем бота...")
    await bot.session.close()
    logging.info("Бот остановлен.")

if __name__ == "__main__":
    try:
        dp.run_polling(
            bot,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=True
        )
    except KeyboardInterrupt:
        logging.info("Бот завершён вручную.")