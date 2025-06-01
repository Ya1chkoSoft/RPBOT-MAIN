
from .session import engine
from .models import Base

async def init_db():
    """
    Создаёт все таблицы, описанные в models.Base,
    если их ещё нет.
    """
    async with engine.begin() as conn:
        # run_sync позволяет вызывать синхронный create_all в асинхронном контексте
        await conn.run_sync(Base.metadata.create_all)