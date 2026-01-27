import aiogram
from aiogram.utils.keyboard import KeyboardBuilder, ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

instart = ['меню']
menu = ['что такое рп?','Комманды']

main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='меню',callback_data='menubutton')]
    
])
menubuttons = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Что такое РП?',callback_data='whatsrpbt')],
    [InlineKeyboardButton(text='РП комманды',callback_data='rpcommandbuttom')],
    [InlineKeyboardButton(text='Комманды бота',callback_data='botcommandbt')],
    [InlineKeyboardButton(text='Создание страны',callback_data='countrycommandbt')]
    
])

async def istart():
    keyboard = InlineKeyboardBuilder()
    for buttons in instart:
        keyboard.add(InlineKeyboardButton(text=buttons,callback_data='instart'))
    return keyboard.adjust(1).as_markup()


async def inmenu():
    keyboard = InlineKeyboardBuilder()
    for buttons in menu:
        keyboard.add(InlineKeyboardButton(text=buttons,callback_data='menu'))
    return keyboard.adjust(1).as_markup()

# app/keyboard.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def country_edit_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Название", callback_data="edit_name"),
            InlineKeyboardButton(text="🎭 Идеология", callback_data="edit_ideology")
        ],
        [
            InlineKeyboardButton(text="🗺 Карта", callback_data="edit_map"),
            InlineKeyboardButton(text="📜 Описание", callback_data="edit_description")
        ],
        [
            InlineKeyboardButton(text="🖼 Флаг", callback_data="edit_flag"),
            InlineKeyboardButton(text="🔗 Ссылка", callback_data="edit_country_url")  # Новая кнопка
        ],
        [
            InlineKeyboardButton(text="❌ Закрыть меню", callback_data="edit_cancel_inline")
        ]
    ])


def cancel_inline_keyboard():
    """Универсальная кнопка возврата в меню при вводе данных"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="edit_back_to_menu")]
    ])

def back_to_menu_inline_keyboard():
    # Вот эта функция, которой не хватало Python
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="edit_back_to_menu")]
    ])

def country_edit_confirm():
    """Подтверждение фиксации изменений"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="edit_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel_inline")
        ]
    ])

def countries_top_keyboard(countries, page: int, total_pages: int, sort_by: str = "influence"):
    builder = InlineKeyboardBuilder()

    # 1. РЯД СОРТИРОВКИ
    sort_labels = {
        "influence": "🔥 Топ",
        "rating": "⭐ Рейтинг",
        "newest": "✨ Новые"
    }
    sort_btns = []
    for s_key, s_label in sort_labels.items():
        label = f"[{s_label}]" if s_key == sort_by else s_label
        sort_btns.append(InlineKeyboardButton(
            text=label,
            callback_data=f"top_page:1:{s_key}"
        ))
    builder.row(*sort_btns)

    # 2. КНОПКИ ВСТУПЛЕНИЯ
    join_btns = []
    for i, country in enumerate(countries, start=1):
        join_btns.append(InlineKeyboardButton(
            text=str(i),
            callback_data=f"join:{country.country_id}"
        ))
    builder.row(*join_btns)

    # 3. НАВИГАЦИЯ
    nav_btns = []
    if page > 1:
        nav_btns.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"top_page:{page-1}:{sort_by}"
        ))

    nav_btns.append(InlineKeyboardButton(text=f"• {page} •", callback_data="ignore"))

    if page < total_pages:
        nav_btns.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"top_page:{page+1}:{sort_by}"
        ))

    builder.row(*nav_btns)

    return builder.as_markup()

def rating_keyboard(country_id: int):
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="⭐" * i, callback_data=f"vote:{country_id}:{i}")
    builder.adjust(1)
    return builder.as_markup()


def countries_top_keyboard(countries, page: int, total_pages: int, sort_by: str = "influence"):
    builder = InlineKeyboardBuilder()

    # 1. РЯД СОРТИРОВКИ
    sort_labels = {
        "influence": "🔥 Топ",
        "rating": "⭐ Рейтинг",
        "newest": "✨ Новые"
    }

    sort_btns = []
    for s_key, s_label in sort_labels.items():
        label = f"[{s_label}]" if s_key == sort_by else s_label
        sort_btns.append(InlineKeyboardButton(
            text=label,
            callback_data=f"top_page:1:{s_key}"
        ))
    builder.row(*sort_btns)

    # 2. КНОПКИ ВСТУПЛЕНИЯ
    join_btns = []
    for i, country in enumerate(countries, start=1):
        join_btns.append(InlineKeyboardButton(
            text=str(i),
            callback_data=f"join:{country.country_id}"
        ))
    builder.row(*join_btns)

    # 3. НАВИГАЦИЯ
    nav_btns = []
    if page > 1:
        nav_btns.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"top_page:{page-1}:{sort_by}"
        ))

    nav_btns.append(InlineKeyboardButton(text=f"• {page} •", callback_data="none"))

    if page < total_pages:
        nav_btns.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"top_page:{page+1}:{sort_by}"
        ))

    builder.row(*nav_btns)

    return builder.as_markup()


def event_admin_keyboard(event_id: int):
    """Клавиатура для администратора RP-ивента"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Вступить", callback_data=f"join_rp_{event_id}"),
            InlineKeyboardButton(text="👥 Участники", callback_data=f"list_participants_{event_id}")
        ],
        [
            InlineKeyboardButton(text="🎉 Завершить ивент", callback_data=f"end_rp_{event_id}")
        ]
    ])





def event_participant_keyboard(event_id: int):
    """Клавиатура для участников RP-ивента"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Вступить", callback_data=f"join_rp_{event_id}"),
            InlineKeyboardButton(text="👥 Участники", callback_data=f"list_participants_{event_id}")
        ]
    ])


def event_join_keyboard(event_id: int):
    """Клавиатура для вступления в RP-ивент"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Вступить", callback_data=f"join_rp_{event_id}")
        ]
    ])


def event_participant_keyboard(event_id: int):
    """Клавиатура для участников RP-ивента с кнопкой выхода"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Участники", callback_data=f"list_participants_{event_id}"),
            InlineKeyboardButton(text="🚪 Выйти из ивента", callback_data=f"leave_rp_{event_id}")
        ]
    ])

