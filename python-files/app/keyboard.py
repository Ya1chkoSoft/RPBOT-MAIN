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

def country_edit_keyboard():
    """Кнопки для редактирования страны"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Название", callback_data="edit:name"),
            InlineKeyboardButton(text="🎭 Идеология", callback_data="edit:ideology")
        ],
        [
            InlineKeyboardButton(text="🗺 Карта", callback_data="edit:map"),
            InlineKeyboardButton(text="📜 Описание", callback_data="edit:description")
        ],
        [
            InlineKeyboardButton(text="🖼 Флаг", callback_data="edit:flag"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="edit:cancel")
        ]
    ])
# Команда для начала создания мемной страны