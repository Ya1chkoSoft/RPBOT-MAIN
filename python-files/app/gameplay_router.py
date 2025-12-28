import math
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession

from .database.requests import (
    get_full_user_profile, 
    get_countries_for_list, 
    join_country, 
    check_review_cooldown, 
    save_review
)
from .database.models import MemeCountry

gameplay_router = Router()

# --- 1. СПИСОК СТРАН И ВСТУПЛЕНИЕ (/top) ---

@gameplay_router.message(Command("top"))
async def cmd_top_countries(message: types.Message, session: AsyncSession):
    await show_countries_page(message, session, page=1)

async def show_countries_page(message_or_call, session, page):
    limit = 5
    countries, total_count = await get_countries_for_list(session, page, limit)
    
    if not countries:
        text = "🌍 Стран пока нет. Создайте свою через /createcountry!"
        if isinstance(message_or_call, types.CallbackQuery):
            await message_or_call.answer(text)
        else:
            await message_or_call.answer(text)
        return

    # Формируем текст
    total_pages = math.ceil(total_count / limit)
    text = f"🏆 **РЕЙТИНГ МЕМНЫХ СТРАН** (Стр. {page}/{total_pages})\n\n"
    
    builder = InlineKeyboardBuilder()
    
    for i, c in enumerate(countries, start=(page-1)*limit + 1):
        # Звезды в тексте
        stars = "⭐" * round(c.avg_rating) if c.avg_rating else "нет оценок"
        text += f"{i}. **{c.name}**\n"
        text += f"   📊 Влияние: `{c.influence_points}` | Рейтинг: {c.avg_rating:.1f} ({stars})\n"
        
        # Кнопка вступления для каждой страны
        builder.button(text=f"✈️ Вступить в {c.name}", callback_data=f"join:{c.country_id}")
    
    # Кнопки навигации
    row_nav = []
    if page > 1:
        row_nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"top_page:{page-1}"))
    if page < total_pages:
        row_nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"top_page:{page+1}"))
    
    builder.row(*row_nav)
    
    if isinstance(message_or_call, types.CallbackQuery):
        await message_or_call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.MARKDOWN)
    else:
        await message_or_call.answer(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.MARKDOWN)

# Обработка листания страниц
@gameplay_router.callback_query(F.data.startswith("top_page:"))
async def on_top_page(call: types.CallbackQuery, session: AsyncSession):
    page = int(call.data.split(":")[1])
    await show_countries_page(call, session, page)
    await call.answer()

# Обработка вступления
@gameplay_router.callback_query(F.data.startswith("join:"))
async def on_join_click(call: types.CallbackQuery, session: AsyncSession):
    country_id = int(call.data.split(":")[1])
    user_id = call.from_user.id
    
    success, msg = await join_country(session, user_id, country_id)
    
    if success:
        await session.commit()
        await call.message.answer(f"✅ **Успешно!** {msg}", parse_mode=ParseMode.MARKDOWN)
    else:
        await call.answer(f"🚫 {msg}", show_alert=True)

# --- 2. ОЦЕНКА СТРАНЫ (/rate) ---

@gameplay_router.message(Command("rate"))
async def cmd_rate_country(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    profile = await get_full_user_profile(session, user_id)
    
    # 1. Проверяем, в стране ли юзер
    if not profile or not profile.country:
        await message.answer("🚫 Вы бомж! Вступите в страну через /top, чтобы оценивать её.")
        return
        
    country = profile.country
    
    # 2. Проверяем КД
    can_vote, wait_time = await check_review_cooldown(session, user_id, country.country_id)
    if not can_vote:
        await message.answer(f"⏳ **Рано!** Вы уже голосовали. Следующая попытка через: **{wait_time}**.", parse_mode=ParseMode.MARKDOWN)
        return

    # 3. Рисуем кнопки 1-5
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="⭐" * i, callback_data=f"vote:{country.country_id}:{i}")
    builder.adjust(1) # Кнопки в столбик
    
    await message.answer(
        f"🗳 **Оцените страну: {country.name}**\n"
        f"Ваш голос влияет на рейтинг! (Можно менять раз в 7 дней)",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )

# Обработка нажатия на звезду
@gameplay_router.callback_query(F.data.startswith("vote:"))
async def on_vote_click(call: types.CallbackQuery, session: AsyncSession):
    # data format: vote:country_id:rating
    parts = call.data.split(":")
    country_id = int(parts[1])
    rating = int(parts[2])
    user_id = call.from_user.id
    
    # Повторная проверка КД (на всякий случай)
    can_vote, _ = await check_review_cooldown(session, user_id, country_id)
    if not can_vote:
        await call.answer("⏳ Кулдаун активен!", show_alert=True)
        return

    try:
        await save_review(session, user_id, country_id, rating)
        await session.commit()
        
        await call.message.edit_text(f"✅ Вы поставили **{rating} ⭐**!\nСпасибо за гражданскую позицию.")
        await call.answer("Голос принят!")
    except Exception as e:
        await session.rollback()
        await call.answer("Ошибка при голосовании :(", show_alert=True)