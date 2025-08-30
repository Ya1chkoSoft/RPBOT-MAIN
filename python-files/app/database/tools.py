from sqlalchemy import text
from .session import async_session

async def add_column(table: str, column: str, col_type: str = "TEXT"):
    async with async_session() as session:
        await session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        await session.commit()