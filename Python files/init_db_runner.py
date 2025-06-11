import asyncio
from app.database.models import async_main

if __name__ == "__main__":
    # запускаем асинхронное создание таблиц
    asyncio.run(async_main())
    print(" Таблицы созданы.")