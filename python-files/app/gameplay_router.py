import math
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

# Импортируем только нужные реквесты
from app.database.requests import (
    get_countries_for_list, 
    join_country, 
    check_review_cooldown, 
    save_review
)
from app.keyboard import countries_top_keyboard, rating_keyboard
gameplay_router = Router()

async def show_countries_page(
    event: types.Message | types.CallbackQuery,
    session: AsyncSession,
    page: int,
    sort_by: str = "influence"
):
    limit = 5
    countries, total_count = await get_countries_for_list(session, page, limit, sort_by)

    if not countries and page == 1:
        msg = "🌍 Стран пока нет."
        if isinstance(event, types.CallbackQuery):
            return await event.answer(msg, show_alert=True)
        return await event.answer(msg)

    total_pages = math.ceil(total_count / limit)

    sort_names = {"influence": "Влиянию", "rating": "Рейтингу", "newest": "Новизне"}
    current_sort_name = sort_names.get(sort_by, "Влиянию")

    text = f"🏆 <b>РЕЙТИНГ СТРАН</b> (по {current_sort_name})\n"
    text += f"📖 Стр. {page}/{total_pages}\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    for i, c in enumerate(countries, start=1):
        rating = c.avg_rating or 0
        stars = "⭐" * round(rating) if rating > 0 else "нет оценок"
        text += f"{i}. <b>{c.name}</b>\n"
        text += f"   📊 Влияние: <code>{c.influence_points}</code> | {rating:.1f} {stars}\n"

        # Добавляем ссылку, если она есть
        if c.country_url:
            text += f"   🔗 <a href='{c.country_url}'>Ссылка</a>\n"

        text += "\n"

    text += "✈️ <i>Выберите номер для вступления или смените фильтр:</i>"

    markup = countries_top_keyboard(countries, page, total_pages, sort_by)

    try:
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            # Показываем сообщение, если стран нет
            if total_count == 0:
                await event.answer("⚠️ Стран пока нет.", show_alert=True)
        else:
            await event.answer(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest:
        if isinstance(event, types.CallbackQuery):
            await event.answer()

@gameplay_router.message(Command("top"))
async def cmd_top(message: types.Message, session: AsyncSession):
    await show_countries_page(message, session, 1, "influence")

@gameplay_router.callback_query(F.data.startswith("top_page:"))
async def on_page(call: types.CallbackQuery, session: AsyncSession):
    # Разбираем новый формат: top_page:PAGE:SORT
    parts = call.data.split(":")
    page = int(parts[1])
    sort_by = parts[2] if len(parts) > 2 else "influence"

    countries, total_count = await get_countries_for_list(session, page, 5, sort_by)
    total_pages = math.ceil(total_count / 5)

    # Проверяем, что страница существует
    if page <= 0 or page > total_pages:
        await call.answer("Эта страница не существует.", show_alert=True)
        return

    await show_countries_page(call, session, page, sort_by)
    await call.answer()

@gameplay_router.callback_query(F.data.startswith("join:"))
async def on_join(call: types.CallbackQuery, session: AsyncSession, user):
    """
    Вступление: теперь максимально чисто.
    user уже подгружен мидлварью.
    """
    country_id = int(call.data.split(":")[1])

    # Передаем сессию и готовый объект пользователя
    success, msg = await join_country(session, user, country_id=country_id)

    if success:
        await call.message.answer(msg, parse_mode="HTML")
        await call.answer()
    else:
        await call.answer(msg, show_alert=True)

@gameplay_router.message(Command("rate"))
async def cmd_rate(message: types.Message, session: AsyncSession, user):
    """
    Оценка: используем данные из объекта user, подгруженного мидлварью.
    """
    if not user.country_id:
        return await message.answer("🚫 Вы не состоите в стране!")

    # Проверка кулдауна
    can_vote, wait = await check_review_cooldown(session, user.user_id, user.country_id)
    if not can_vote:
        return await message.answer(f"⏳ Рано! Ждите: <code>{wait}</code>", parse_mode="HTML")

    # В модели User связь country должна быть подгружена (lazy="joined" или "selectin")
    country_name = user.country.name if user.country else "свою страну"

    await message.answer(
        f"🗳 <b>Оценка страны: {country_name}</b>",
        reply_markup=rating_keyboard(user.country_id),
        parse_mode="HTML"
    )

@gameplay_router.callback_query(F.data.startswith("vote:"))
async def on_vote(call: types.CallbackQuery, session: AsyncSession, user):
    """
    Голосование: user.user_id вместо call.from_user.id для единообразия.
    """
    _, c_id, val = call.data.split(":")

    success, msg = await save_review(session, user.user_id, int(c_id), int(val))

    if success:
        await call.message.edit_text(f"✅ Вы поставили <b>{val} ⭐</b>!")
    else:
        await call.answer(msg, show_alert=True)