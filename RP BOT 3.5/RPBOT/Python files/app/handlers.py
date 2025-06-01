from email import message
import random
import pickle
import re


from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

# Импортируем только функции-обёртки для работы с БД
from app.database.requests import get_or_create_user, get_balance

import app.database.requests as rq
import app.keyboard as kb


player: list = []
router = Router()

test: str = "ТЕСТ ПРОЙДЕН"

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Используем get_or_create_user вместо несуществующего set_user
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or ""
    )
    await message.answer(
        """<b>ПРИВЕТСТВУЮ В НАШЕМ РП БОТЕ</b>
<i>версия бота 3.1</i>
данный бот будет помогать вам в рп и тд:3
ниже будет распологаться меню, желаем вам удачи""",
        parse_mode='HTML',
        reply_markup=kb.main
    )

async def randomizers(rand):
    await message.reply(f'{rand}')

# ниже слова для хендлеров
keywords = [
    "женщина",
    "мужчина",
    # ... добавь сколько угодно слов
]
pattern = re.compile(
    r"\b(" + "|".join(map(re.escape, keywords)) + r")\b",
    flags=re.IGNORECASE
)

@router.message(Command("ping"))
async def test_ping(message: Message):
    await message.reply("pong")

@router.message(F.text)
async def randomizer1(message: Message):
    global rand, rand1_100
    text = message.text.strip().lower()
    rand = random.randint(1, 10)
    rand1_100 = random.randint(1, 100)

    match text:
        case 'фарма':
            await message.reply('Иди на поле, раб')
        case '1' | 'ранд' | 'рандом' | 'rand' | 'random':
            await message.reply(f'{rand}')
        case 'тест':
            await message.reply(test)
        case 'урон':
            await message.reply(f'{rand1_100}')
        case 'кубик':
            await message.reply_dice()
        case 'лс':
            await message.reply('<b>ЛС</b>', parse_mode='HTML')
        case 'ахуеть':
            await message.reply('<b>Звуки бравл старса</b>', parse_mode='HTML')
        case 'рп профиль':
            # 1) Гарантируем, что пользователь в базе и получаем объект
            user = await get_or_create_user(
                user_id=message.from_user.id,
                username=message.from_user.username or ""
            )
            # 2) Берём текущее количество очков
            points = await get_balance(message.from_user.id)
            # 3) Отвечаем пользователю с его данными
            await message.reply(
                f"Ваш профиль:\n"
                f"• ID: {user.user_id}\n"
                f"• Username: @{user.username}\n"
                f"• Очки: {points}"
            )
            return
        case 'рп регистрация':
            # Меняем на get_or_create_user, так как set_user нет в requests.py
            user = await get_or_create_user(
                user_id=message.from_user.id,
                username=message.from_user.username or ""
            )
            # Проверяем, создался ли новый пользователь: если points == 0 и только что создан
            if user.points == 0 and user.username == message.from_user.username:
                await message.reply('успешно пройдена регистрация')
            else:
                await message.reply('ВЫ УЖЕ ЗАРЕГЕСТРИРОВАНЫ!!!')
    # Обработка ключевых слов через pattern
    if match := pattern.search(text):
        key = match.group(1).lower()
        reply = random.choice(responses.get(key, [f"Нашёл: {key}"]))
        await message.reply(reply)
        return

@router.callback_query(F.data == 'menubutton')
async def menu(callback: CallbackQuery):
    await callback.answer('успешно')
    await callback.message.edit_text(
        'Вы перешли в меню, ниже кнопки с пояснениями',
        reply_markup=kb.menubuttons
    )

@router.callback_query(F.data == 'whatsrpbt')
async def defwhatsrpbutton(callback: CallbackQuery):
    await callback.answer('')
    await callback.message.edit_text(
        '''<b>РП происходит от RolePlay</b>, 
<i>на рп вы отыгрываете за персонажа, он может быть любым, 
но ограничения устанавливает администрация</i>''',
        parse_mode='HTML',
        reply_markup=kb.main
    )

@router.callback_query(F.data == 'rpcommandbuttom')
async def defrpcommandsbutton(callback: CallbackQuery):
    await callback.answer('успешно')
    await callback.message.edit_text(
        '''рп комманды: 
<b>*действие*</b>(или жирным текстом)
<i>шёпот</i>
(мысли)
//вне рп''',
        parse_mode='HTML',
        reply_markup=kb.main
    )

@router.callback_query(F.data == 'botcommandbt')
async def defrpcommandsbutton(callback: CallbackQuery):
    await callback.answer('успешно')
    await callback.message.edit_text(
        '''ранд(рандом,rand,random) - кидает рандомное значение от 1 до 10
урон - кидает прокид на урон(1-100)
кубик - кидает кубик
женщина,мужчина - угар комманды''',
        parse_mode='HTML',
        reply_markup=kb.main
    )


# Для каждого ключевого слова определяем список возможных ответов
responses = {
    "женщина": [
        'Я ЖЕНЩИНА',
        'АААААА ЖЕНЩИНЫ БЛЯТЬ',
        'НЕЕЕЕЕЕТ УБЕРИ ЭТО',
        'ЭТО ПРОСТО НЕВОЗМОЖНО!!!',
        'СПАСАЙСЯ КТО МОЖЕТ',
        'Ох Ахъ женщины топчег  \n  *Застрелил черта*  туда егооооо',
        'ЖЕНЩИНА В ЧАТЕ!!! \nСРОЧНО ТРАХАТЬ',
        'Ну бывает',
    ],
    "мужчина": [
        'Я МУЖЧИНА',
        'АААААА МУЖИКИ, СВЕЖЕЕ МЯСО!!!',
        'а вы знали что в корее все мужики поголовно КПОП и не натуралы',
        'ЭТО ПРОСТО НЕВОЗМОЖНО!!!',
        'Пошли в хоечку и отжарь меня по самое нихачу',
        'Он любит смачно в попачку?',
        'МУЖИК В ЧАТЕ!!! \nСРОЧНО ТРАХАТЬ И ПОШЛИ В ХОЙКУ',
        'Надо повысить',
        'БЫСТРО ЗОВИ ЕГО В ТЕРКУ!\n мы будем на пенсиле прыгать',
    ],
    # ... словарь для всех keywords
}
