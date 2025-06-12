from email import message
import random
import pickle
import re
import sys
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup

# Импортируем только функции-обёртки для работы с БД
from app.database.requests import get_or_create_user, get_balance, get_top, add_admin, get_user_by_username
from sqlalchemy.future import select
from app.database.models import User, Admins, History
from app.database.session import async_session
from datetime import datetime

import app.database.requests as rq
import app.keyboard as kb

from config import OWNER_ID

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class GivePointsStates(StatesGroup):
    waiting_for_points = State()

player: list = []
router = Router()

test: str = "ТЕСТ ПРОЙДЕН"

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Используем get_or_create_user вместо несуществующего set_user
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        userfullname=message.from_user.full_name
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


#НАЗНАЧЕНИЕ АДМИНИСТРАЦИИ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.startswith("рп назначить"))
async def handle_set_admin_level(message: Message):
    args = message.text.strip().split()  # убрал maxsplit, чтобы разделить все части
    
    if len(args) < 4:
        await message.reply("❗ Формат: рп назначить <user_id или @username> <уровень>")
        return

    target_str = args[2]  # третий элемент — пользователь или айди
    level_str = args[3]   # четвертый — уровень

    if not level_str.isdigit():
        await message.reply("❗ Уровень должен быть числом.")
        return

    new_level = int(level_str)
    caller_id = message.from_user.id

    async with async_session() as session:
        # Определяем уровень вызывающего
        if caller_id == OWNER_ID:
            caller_adminlevel = 10  # максимально возможный уровень
        else:
            caller_result = await session.execute(select(Admins).where(Admins.user_id == caller_id))
            caller = caller_result.scalar_one_or_none()
            if not caller or caller.adminlevel < 5:
                await message.reply("🚫 У вас нет прав для назначения админов.")
                return
            caller_adminlevel = caller.adminlevel

        # Получаем целевого пользователя
        if target_str.isdigit():
            target_result = await session.execute(select(User).where(User.user_id == int(target_str)))
        else:
            username = target_str.lstrip("@")
            target_result = await session.execute(select(User).where(User.username == username))

        target_user = target_result.scalar_one_or_none()
        if not target_user:
            await message.reply("❌ Пользователь не найден.")
            return

        # Получаем текущий уровень админства целевого
        target_admin_result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        target_admin = target_admin_result.scalar_one_or_none()

        # 🔒 Проверка: нельзя переназначать равного или вышестоящего, если не OWNER
        if target_admin and caller_adminlevel <= target_admin.adminlevel and caller_id != OWNER_ID:
            await message.reply("🚫 Вы не можете переназначить этого администратора. У него уровень выше или равный вашему.")
            return

        # 🔒 Проверка: нельзя назначить уровень выше или равный себе (если не OWNER)
        if new_level >= caller_adminlevel and caller_id != OWNER_ID:
            await message.reply("🚫 Вы не можете назначить админа уровня равного или выше вашего.")
            return

        # ✅ Назначение уровня
        target_user.adminlevel = new_level
        session.add(target_user)

        if not target_admin:
            session.add(Admins(user_id=target_user.user_id, adminlevel=new_level))
        else:
            target_admin.adminlevel = new_level
            session.add(target_admin)

        await session.commit()

        await message.reply(
            f"✅ Пользователь {target_user.userfullname or '@' + (target_user.username or 'без_ника')} "
            f"(ID: {target_user.user_id}) назначен админом уровня {new_level}."
        )
        
@router.message(F.text == "рп я овнер")
async def make_myself_owner(message: Message):
    caller_id = message.from_user.id
    async with async_session() as session:
        session.add(Admins(user_id=caller_id, adminlevel=4))
        await session.commit()
        await message.reply(f"✅ Вы добавлены как OWNER (уровень 4). ID: {caller_id}")


#СНЯТИЕ АДМИНИСТРАЦИИ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.startswith("рп снять"))
async def handle_remove_admin(message: Message):
    args = message.text.strip().split(maxsplit=2)

    if len(args) < 3:
        await message.reply("❗ Формат: рп снять <user_id или @username> <причина>")
        return

    target_str = args[2]
    reason = args[3] if len(args) > 3 else "Без причины"
    remover_id = message.from_user.id
    OWNER_ID

    async with async_session() as session:
        # Получаем админа, который снимает
        remover_result = await session.execute(select(Admins).where(Admins.user_id == remover_id))
        remover = remover_result.scalar_one_or_none()

        if not remover:
            await message.reply("🚫 У вас нет прав для снятия админов.")
            return

        # Получаем снимаемого по ID или username
        if target_str.isdigit():
            target_user_result = await session.execute(select(User).where(User.user_id == int(target_str)))
        else:
            username = target_str.lstrip("@")
            target_user_result = await session.execute(select(User).where(User.username == username))

        target_user = target_user_result.scalar_one_or_none()

        if not target_user:
            await message.reply("❌ Пользователь не найден.")
            return

        # Получаем запись из Admins
        target_admin_result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        target_admin = target_admin_result.scalar_one_or_none()

        if not target_admin:
            await message.reply("❌ Этот пользователь не является админом.")
            return

        # Проверка прав
        if remover.adminlevel <= target_admin.adminlevel and remover.user_id != OWNER_ID:
            await message.reply("🚫 Вы не можете снять этого администратора. У него уровень выше или равный вашему.")
            return

        # Снимаем: удаляем из Admins и сбрасываем adminlevel в Users
        await session.delete(target_admin)
        target_user.adminlevel = 0
        session.add(target_user)

        await session.commit()

        await message.reply(
            f"✅ {target_user.userfullname or '@' + (target_user.username or 'без_ника')} снят с админки.\n"
            f"Причина: {reason}"
        )


#НАЧИСЛЕНИЕ ОЧКОВ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.startswith("рп начислить"))
async def handle_give_points_rp(message: Message):
    args = message.text.strip().split(maxsplit=3)

    # Проверяем, есть ли ответ на сообщение — если есть, целевой пользователь берем оттуда
    if message.reply_to_message:
        target_user_telegram = message.reply_to_message.from_user
        target_str = None  # Будем искать по user_id из reply_to_message
    else:
        if len(args) < 4:
            await message.reply("❗ Формат: рп начислить <user_id или @username> <очки> <причина>")
            return
        target_str = args[2]
    
    # В зависимости от формы, парсим очки и причину
    if message.reply_to_message:
        # В ответе: args будет примерно ["рп", "начислить", "<очки> <причина>"]
        # Тогда очки и причина - берём из args[2], дальше разбираем
        if len(args) < 3:
            await message.reply("❗ Формат: рп начислить <очки> <причина>")
            return
        points_reason = args[2].split(maxsplit=1)
        points_str = points_reason[0]
        reason = points_reason[1] if len(points_reason) > 1 else "Без причины"
    else:
        points_str = args[3].split(maxsplit=1)[0]
        reason = args[3].split(maxsplit=1)[1] if len(args[3].split(maxsplit=1)) > 1 else "Без причины"

    # Проверка очков
    if not points_str.lstrip("-").isdigit():
        await message.reply("❗ Количество очков должно быть целым числом.")
        return

    points = int(points_str)
    admin_id = message.from_user.id

    async with async_session() as session:
        # Проверяем админа
        admin_result = await session.execute(select(Admins).where(Admins.user_id == admin_id))
        admin = admin_result.scalar_one_or_none()
        if not admin or admin.adminlevel == 0:
            await message.reply("🚫 У вас нет прав на начисление очков.")
            return

        # Получаем пользователя для начисления
        if message.reply_to_message:
            # Поиск по user_id из telegram (reply_to_message.from_user.id)
            target_result = await session.execute(select(User).where(User.user_id == target_user_telegram.id))
        else:
            if target_str.isdigit():
                target_result = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                target_result = await session.execute(select(User).where(User.username == username))

        target_user = target_result.scalar_one_or_none()
        if not target_user:
            await message.reply("❌ Пользователь не найден.")
            return

        # Проверка уровня доступа
        if target_user.adminlevel >= admin.adminlevel:
            await message.reply("🚫 Вы не можете начислить очки пользователю с таким же или более высоким уровнем.")
            return

        # Начисление очков
        target_user.points += points
        session.add(target_user)

        # Запись в историю
        session.add(History(
            admin_id=admin.user_id,
            target_id=target_user.user_id,
            points=points,
            reason=reason,
            timestamp=datetime.now()
        ))

        await session.commit()

        await message.reply(
            f"✅ Начислено {points} очков пользователю "
            f"{target_user.userfullname or '@' + (target_user.username or 'без_ника')} за: {reason}"
        )

@router.message(Command("ping"))
async def test_ping(message: Message):
    await message.reply("pong")


#ОСНОВНЫЕ ХЕНДЛЕРЫ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
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
                username=message.from_user.username or "",
                userfullname=message.from_user.full_name
            )
            # 2) Берём текущее количество очков
            points = await get_balance(message.from_user.id)
            # 3) Отвечаем пользователю с его данными
            await message.reply(
                f"Ваш профиль:\n"
                f"• ID: {user.user_id}\n"
                f"• ИМЯ: {user.userfullname}\n"
                f"• РП очки: {points}"
            )
            return
        case 'рп топ':
            top_users = await get_top(10)  # получаем топ 10 пользователей
            if not top_users:
                await message.answer("Топ рпшеров пуст.")

            response_lines = ["🏆 Топ РП игроков:"]
            for i, user in enumerate(top_users, start=1):
                username = user.username or f"ID {user.user_id}"
                response_lines.append(f"{i}. {username} — {user.points} баллов")

            response_text = "\n".join(response_lines)
            await message.answer(response_text)
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
женщина,мужчина - угар комманды
РП профиль - ваш профиль в меном мире:
рп топ - то РП игроков''',
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
