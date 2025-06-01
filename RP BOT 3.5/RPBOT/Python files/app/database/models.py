
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base, relationship
from .session import engine  # асинхронный движок

# 1) Объявляем базовый класс для моделей
Base = declarative_base()

# 2) Модель User (таблица users)
class User(Base):
    __tablename__ = "users"
    user_id  = Column(Integer, primary_key=True)
    username = Column(String, nullable=True)
    points   = Column(Integer, default=0)

# 3) Модель History (таблица history)
class History(Base):
    __tablename__ = "history"
    id        = Column(Integer, primary_key=True)
    admin_id  = Column(Integer, nullable=False)
    target_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    points    = Column(Integer, nullable=False)
    reason    = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now())
    # связь: History.user будет показывать объект User
    user      = relationship("User", backref="histories")

# 4) Функция для создания всех таблиц (если их нет)
async def async_main():
    async with engine.begin() as conn:
        # run_sync оборачивает синхронный create_all в асинхронный контекст
        await conn.run_sync(Base.metadata.create_all)