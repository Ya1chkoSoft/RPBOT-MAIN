from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# 1) Определяем абсолютный путь к файлу БД, чтобы он всегда создавался в папке database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "playerstat.db")

# 2) Строка подключения с async-драйвером aiosqlite
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# 3) Создаём асинхронный движок
engine = create_async_engine(DATABASE_URL, echo=True)

# 4) Фабрика асинхронных сессий (AsyncSession)
async_session = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)