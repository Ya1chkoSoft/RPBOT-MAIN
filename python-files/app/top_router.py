# app/top_router.py

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
import math

# Импортируем нашу функцию
from .database.requests import get_top_countries_page, RESULTS_PER_PAGE 

top_router = Router()
CALLBACK_PREFIX = "country_list" # Префикс для Callback Data

def generate_country_list_message(countries, total_count, current_page):
    """Формирует текст сообщения и клавиатуру пагинации."""
    
    if not countries:
        return "ℹ️ Пока нет созданных стран.", None
    
    # Формируем список стран
    rank_start = ((current_page - 1) * RESULTS_PER_PAGE) + 1
    text_lines = [
        f"👑 **ЛЕНТА СТРАН** (Страница {current_page}/{math.ceil(total_count / RESULTS_PER_PAGE)})"
    ]
    
    for i, country in enumerate(countries):
        rank = rank_start + i
        text_lines.append(
            f"\n{rank}\\. **{country.name}**\n"
            f"   Идеология: _{country.ideology}_\n"
            f"   Влияние: `{country.influence_points}` pts"
        )

    # 2. Формируем клавиатуру пагинации
    builder = InlineKeyboardBuilder()
    
    total_pages = math.ceil(total_count / RESULTS_PER_PAGE)
    
    # Кнопка "Назад"
    if current_page > 1:
        builder.button(text="⬅️", callback_data=f"{CALLBACK_PREFIX}:{current_page - 1}")
    else:
        builder.button(text=" ", callback_data="ignore") # Пустая кнопка для центрирования
        
    # Страница
    builder.button(text=f"Стр. {current_page}/{total_pages}", callback_data="ignore")
    
    # Кнопка "Вперед"
    if current_page < total_pages:
        builder.button(text="➡️", callback_data=f"{CALLBACK_PREFIX}:{current_page + 1}")
    else:
        builder.button(text=" ", callback_data="ignore") # Пустая кнопка
        
    return "\n".join(text_lines), builder.as_markup()


@top_router.message(Command("top"))
async def cmd_show_top_countries(message: types.Message, session: AsyncSession):
    # Показываем первую страницу
    countries, total_count = await get_top_countries_page(session, page=1)
    
    text, keyboard = generate_country_list_message(countries, total_count, 1)
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@top_router.callback_query(lambda c: c.data and c.data.startswith(CALLBACK_PREFIX))
async def process_pagination_callback(callback: types.CallbackQuery, session: AsyncSession):
    # Разбираем Callback Data: "country_list:2" -> page=2
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка в данных пагинации.")
        return
        
    countries, total_count = await get_top_countries_page(session, page)
    
    # Проверяем, что страница существует
    if page <= 0 or page > math.ceil(total_count / RESULTS_PER_PAGE):
        await callback.answer("Эта страница не существует.")
        return

    text, keyboard = generate_country_list_message(countries, total_count, page)
    
    # Обновляем сообщение вместо отправки нового
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer() # Закрываем уведомление "Загрузка"