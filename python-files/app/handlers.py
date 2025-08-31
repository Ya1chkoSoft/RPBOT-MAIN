from email import message
import random
import pickle
import re
import sys
import os
import html
import logging
import asyncio
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup

# Импортируем только функции-обёртки для работы с БД
from app.database.requests import get_or_create_user, get_balance, get_top, add_admin, get_user_by_username
from sqlalchemy.future import select
from sqlalchemy import func
from app.database.models import User, Admins, History
from app.database.session import async_session
from datetime import datetime

import app.database.requests as rq
import app.keyboard as kb

from config import OWNER_ID

load_dotenv()  # Загружаем переменные окружения из .env

OWNER_ID = int(os.getenv("OWNER_ID"))
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
<i>версия бота 3.2</i>
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
@router.message(F.text.lower().startswith("рп назначить"))
async def handle_set_admin_level(message: Message):
    try:
        args = message.text.strip().split()
        if len(args) < 4:
            await message.reply("❗ Формат: рп назначить <user_id или @username> <уровень>")
            return

        target_str = args[2]
        level_str = args[3]

        if not level_str.isdigit():
            await message.reply("❗ Уровень должен быть числом.")
            return

        new_level = int(level_str)
        caller_id = message.from_user.id

        async with async_session() as session:
            # Получаем уровень вызывающего
            if caller_id == OWNER_ID:
                caller_adminlevel = 5  # OWNER может всё
            else:
                caller_result = await session.execute(select(Admins).where(Admins.user_id == caller_id))
                caller = caller_result.scalar_one_or_none()
                if not caller or caller.adminlevel < 5:
                    await message.reply("🚫 У вас нет прав для назначения админов.")
                    return
                caller_adminlevel = caller.adminlevel

            # Получаем целевого пользователя
                target_user = None

            if target_str.isdigit():
                # Поиск по ID в базе
                target_result = await session.execute(
                    select(User).where(User.user_id == int(target_str))
                )
                target_user = target_result.scalar_one_or_none()
            else:
                # Сначала пробуем найти по username в базе (регистр игнорируем)
                username = target_str.lstrip("@")
                target_result = await session.execute(
                    select(User).where(func.lower(User.username) == username.lower())
                )
                target_user = target_result.scalar_one_or_none()

                # Если в базе нет — пробуем достать из Telegram по @username
                if not target_user:
                    try:
                        tg_chat = await message.bot.get_chat(username)  # @username -> Chat/User
                        # Проверяем, нет ли уже записи по user_id
                        by_id_result = await session.execute(
                            select(User).where(User.user_id == tg_chat.id)
                        )
                        target_user = by_id_result.scalar_one_or_none()

                        if not target_user:
                                # Создаём запись (сохранится при общем commit ниже)
                            target_user = User(
                                user_id=tg_chat.id,
                                username=tg_chat.username,
                                userfullname=tg_chat.full_name,
                            )
                            session.add(target_user)
                            await session.flush()
                        else:
                            # Обновим ник/имя, если поменялись
                            target_user.username = tg_chat.username
                            target_user.userfullname = tg_chat.full_name
                            session.add(target_user)
                    except Exception:
                        target_user = None
            #проверка, что пользователь уже этого уровня
            target_admin_result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
            target_admin = target_admin_result.scalar_one_or_none()
            if target_admin and target_admin.adminlevel == new_level:
                await message.reply(f"❗ Пользователь уже имеет уровень {new_level}.")
                return

            if not target_user:
                await message.reply("❌ Пользователь не найден.")
                return

            # Получаем текущий уровень админства целевого
            target_admin_result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
            target_admin = target_admin_result.scalar_one_or_none()
            target_adminlevel = target_admin.adminlevel if target_admin else 0

            # Проверка: нельзя назначить уровень выше своего (если не OWNER)
            if new_level >= caller_adminlevel and caller_id != OWNER_ID:
                await message.reply("Вы не можете назначить админа уровня равного или выше вашего.")
                return

            # Проверка: нельзя переназначать равного или вышестоящего (если не OWNER)
            if target_admin and caller_adminlevel <= target_adminlevel and caller_id != OWNER_ID:
                await message.reply("Вы не можете переназначить этого администратора. У него уровень выше или равный вашему.")
                return

            # Проверка: нельзя повысить выше максимального уровня
            if new_level > 5:
                await message.reply("Максимальный уровень администратора — 5.")
                return

            # Назначение уровня в базе
            target_user.adminlevel = new_level
            session.add(target_user)

            if not target_admin:
                session.add(Admins(user_id=target_user.user_id, adminlevel=new_level))
            else:
                target_admin.adminlevel = new_level
                session.add(target_admin)

            await session.commit()

            # --- Собираем ответ телеграм ---
            full_display = target_user.userfullname or f"@{(target_user.username or 'без_ника')}"
            reply_text = (
                f"✅ Пользователь {full_display} "
                f"(ID: {target_user.user_id}) назначен админом уровня {new_level}."
            )

            # Отправляем в Telegram
            await message.reply(reply_text)



#            # --- ЛОГИ для отладки, если что-то пошло не так с кодировкой ---
#            b = reply_text.encode('utf-8')
#            logger.debug("OUTGOING_REPLY_REPR: %r", reply_text)         # Python repr (видно \n, \t и спецсимволы)
#            logger.debug("OUTGOING_REPLY_HEX: %s", b.hex())             # чистые hex-байты
#            logger.debug("OUTGOING_REPLY_UNICODE_POINTS: %s", [hex(ord(c)) for c in reply_text])

    except ValueError as e:
        await message.reply(f"❌ Произошла ошибка: {e}")
    except TypeError as e:
        await message.reply(f"❌ Произошла ошибка: {e}")
    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {e}")


# --- ОВНЕР НАЗНАЧИТЬ АДМИНА --- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп овнер назначить"))
async def owner_assign_admin(message: Message):
    args = message.text.strip().split()
    if len(args) < 4:
        await message.reply("❗ Формат: рп овнер назначить <user_id или @username> <уровень>")
        return

    target_str = args[2]
    level_str = args[3]

    if not level_str.isdigit():
        await message.reply("❗ Уровень должен быть числом.")
        return

    new_level = int(level_str)
    if new_level < 0 or new_level > 5:
        await message.reply("❗ Уровень должен быть от 0 до 5.")
        return

    caller_id = message.from_user.id
    if caller_id != OWNER_ID:
        await message.reply("🚫 Только владелец может использовать эту команду.")
        return

    async with async_session() as session:
        # Получаем пользователя
        if target_str.isdigit():
            target_result = await session.execute(select(User).where(User.user_id == int(target_str)))
        else:
            username = target_str.lstrip("@")
            target_result = await session.execute(select(User).where(User.username == username))

        target_user = target_result.scalar_one_or_none()
        if not target_user:
            await message.reply("❌ Пользователь не найден.")
            return

        # Назначаем уровень
        target_user.adminlevel = new_level
        session.add(target_user)

        admin_result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        admin = admin_result.scalar_one_or_none()
        if not admin:
            session.add(Admins(user_id=target_user.user_id, adminlevel=new_level))
        else:
            admin.adminlevel = new_level
            session.add(admin)

        await session.commit()
        await message.reply(
            f"✅ Пользователь {target_user.userfullname or '@' + (target_user.username or 'без_ника')} "
            f"(ID: {target_user.user_id}) назначен админом уровня {new_level}."
        )

# --- ОВНЕР НАЧИСЛИТЬ ОЧКИ --- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп овнер начислить"))
async def owner_add_points(message: Message):
    args = message.text.strip().split()

    # Формат: рп овнер начислить @username <очки> <причина>
    if len(args) < 5:
        await message.reply("❗ Формат: рп овнер начислить @username <очки> <причина>")
        return

    caller_id = message.from_user.id
    if caller_id != OWNER_ID:
        await message.reply("🚫 Только владелец может использовать эту команду.")
        return

    username = args[3].replace("@", "")  # @username
    points_str = args[4]


    if not points_str.lstrip("-").isdigit():
        await message.reply("❗ Количество очков должно быть целым числом.")
        return

    points = int(points_str)
    if points == 0:
        await message.reply("❗ Количество очков не может быть нулём.")
        return

    reason = " ".join(args[5:]) or "Без причины"

    async with async_session() as session:
        # ищем пользователя в базе
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            await message.reply(f"🚫 Пользователь @{username} не найден в базе.")
            return

        # начисляем очки
        user.points += points
        session.add(user)

        # сохраняем историю
        history = History(
            admin_id=caller_id,
            target_id=user.user_id,
            points=points,
            reason=reason,
            timestamp=datetime.now()
        )
        session.add(history)

        await session.commit()

    await message.reply(
        f"✅ Пользователю @{username} начислено {points} очков.\n"
        f"Причина: {reason}"
    )


# --- ОВНЕР ОТНЯТЬ ОЧКИ --- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
@router.message(F.text.lower().startswith("рп овнер отнять"))
async def owner_remove_points(message: Message):
    args = message.text.strip().split()

    # Формат: рп овнер отнять @username <очки> <причина>
    if len(args) < 5:
        await message.reply("❗ Формат: рп овнер отнять @username <очки> <причина>")
        return

    caller_id = message.from_user.id
    if caller_id != OWNER_ID:
        await message.reply("🚫 Только владелец может использовать эту команду.")
        return

    username = args[3].replace("@", "")  # @username
    points_str = args[4]

    if not points_str.isdigit():
        await message.reply("❗ Количество очков должно быть положительным целым числом.")
        return

    points = int(points_str)
    if points <= 0:
        await message.reply("❗ Количество очков должно быть больше нуля.")
        return

    reason = " ".join(args[5:]) or "Без причины"

    async with async_session() as session:
        # ищем пользователя в базе
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            await message.reply(f"🚫 Пользователь @{username} не найден в базе.")
            return

        # вычитаем очки
        user.points -= points
        if user.points < 0:  # защита от отрицательного баланса
            user.points = 0
        session.add(user)

        # сохраняем историю
        history = History(
            admin_id=caller_id,
            target_id=user.user_id,
            points=-points,  # минусовые очки
            reason=reason,
            timestamp=datetime.now()
        )
        session.add(history)

        await session.commit()

    await message.reply(
        f"❌ У пользователя @{username} отнято {points} очков.\n"
        f"Причина: {reason}"
    )

#СНЯТИЕ АДМИНИСТРАЦИИ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп снять"))
async def handle_remove_admin(message: Message):
    args = message.text.strip().split(maxsplit=2)

    if len(args) < 3:
        await message.reply("❗ Формат: рп снять <user_id или @username> <причина>")
        return

    target_str = args[2]
    reason = (message.text.strip().replace("рп снять " + target_str, "").strip()) or "Без причины"
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


#СПИСОК АДМИНИСТРАТОРОВ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп админы"))
async def list_admins(message: Message):
    async with async_session() as session:
        result = await session.execute(select(Admins))
        admins = result.scalars().all()

    if not admins:
        await message.reply("Список администраторов пуст.")
        return

    admin_text = "Список администраторов:\n"
    for admin in admins:
        user_result = await session.execute(select(User).where(User.user_id == admin.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            admin_text += f"• {user.userfullname or '@' + (user.username or 'без_ника')} (ID: {user.user_id}) — уровень {admin.adminlevel}\n"
        else:
            admin_text += f"• ID: {admin.user_id} — уровень {admin.adminlevel} (пользователь не в базе)\n"

    await message.reply(admin_text)

#НАЧИСЛЕНИЕ ОЧКОВ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп начислить"))
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
#передача очков  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп передать"))
async def transfer_points(message: Message):
    args = message.text.strip().split()
    if len(args) < 3:
        await message.reply("❗ Формат: рп передать <сумма> <@юзер или ID>")
        return

    amount_str = args[2]
    if not amount_str.isdigit():
        await message.reply("❗ Сумма должна быть числом.")
        return

    amount = int(amount_str)
    if amount <= 0:
        await message.reply("❗ Сумма должна быть больше нуля.")
        return

    sender_id = message.from_user.id
    receiver_id = None

    # Получатель из реплая
    if message.reply_to_message:
        receiver_id = message.reply_to_message.from_user.id
    elif len(args) >= 4:
        receiver_arg = args[3]

        # Если @username
        if receiver_arg.startswith("@"):
            username = receiver_arg[1:]
            async with async_session() as session:
                user_result = await session.execute(
                    select(User).where(User.username == username)
                )
                receiver = user_result.scalar_one_or_none()
                if receiver:
                    receiver_id = receiver.user_id
        else:
            # Пытаемся интерпретировать как ID
            if receiver_arg.isdigit():
                receiver_id = int(receiver_arg)

    if not receiver_id:
        await message.reply("❌ Укажите получателя (реплай или @username или ID).")
        return

    async with async_session() as session:
        # ищем отправителя
        sender_result = await session.execute(select(User).where(User.user_id == sender_id))
        sender = sender_result.scalar_one_or_none()

        if not sender:
            await message.reply("❌ Вы не зарегистрированы.")
            return

        if sender.points < amount:
            await message.reply("🚫 Недостаточно очков для перевода.")
            return

        # ищем получателя
        receiver_result = await session.execute(select(User).where(User.user_id == receiver_id))
        receiver = receiver_result.scalar_one_or_none()

        if not receiver:
            await message.reply("❌ Получатель не найден или не зарегистрирован.")
            return

        if receiver.user_id == sender.user_id:
            await message.reply("❌ Нельзя переводить очки самому себе.")
            return

        # перевод
        sender.points -= amount
        receiver.points += amount

        session.add_all([sender, receiver])
        await session.commit()

        await message.reply(
            f"💸 {amount} очков успешно переведено!\n"
            f"👤 Отправитель: {sender.username or sender.user_id}\n"
            f"👤 Получатель: {receiver.username or receiver.user_id}\n"
            f"💰 Ваш баланс: {sender.points}"
        )

#Казино на очках - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
SLOT_SYMBOLS = ["🍒", "🍋", "🦷", "⭐", "👼🏿"]  # можно расширить

@router.message(F.text.lower().startswith("рп казино"))
async def casino(message: Message):
    args = message.text.strip().split()
    if len(args) < 3:
        await message.reply("❗ Формат: рп казино <ставка>")
        return

    bet_str = args[2]
    if not bet_str.isdigit():
        await message.reply("❗ Ставка должна быть положительным числом.")
        return

    bet = int(bet_str)
    if bet <= 0:
        await message.reply("❗ Ставка должна быть больше нуля.")
        return

    user_id = message.from_user.id

    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.user_id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            await message.reply("❌ Вы не зарегистрированы в системе. Используйте /start.")
            return

        if user.points < bet:
            await message.reply("🚫 У вас недостаточно очков для этой ставки.")
            return

        # снимаем ставку
        user.points -= bet

        # крутим слоты
        slot1 = random.choice(SLOT_SYMBOLS)
        slot2 = random.choice(SLOT_SYMBOLS)
        slot3 = random.choice(SLOT_SYMBOLS)

        # анимация "вращения"
        msg = await message.reply("🎰 Крутим барабаны...")
        await asyncio.sleep(1)
        await msg.edit_text(f"🎰 | {slot1} | ❓ | ❓ |")
        await asyncio.sleep(1)
        await msg.edit_text(f"🎰 | {slot1} | {slot2} | ❓ |")
        await asyncio.sleep(1)
        await msg.edit_text(f"🎰 | {slot1} | {slot2} | {slot3} |")

        # случайный множитель (показываем даже при проигрыше)
        multiplier = round(random.uniform(2.0, 5.3), 2)

        # проверка совпадений
        if slot1 == slot2 == slot3:
            # джекпот
            winnings = int(bet * multiplier)
            user.points += winnings
            result_text = (
                f"✨ Джекпот! Три одинаковых символа!\n"
                f"💎 Множитель: {multiplier}x\n"
                f"🏆 Вы выиграли {winnings} очков!"
            )
        # две пары
        elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
            winnings = int(bet * (multiplier / 2.5))
            user.points += winnings
            result_text = (
                f"🎉 Поздравляем! Два одинаковых символа!\n"
                f"💎 Множитель: {multiplier/2}x\n"
                f"🏆 Вы выиграли {winnings} очков!"
            )
        else:
            result_text = (
                f"❌ Увы, вы проиграли.\n"
                f"💰 Ваша ставка: {bet} очков\n"
                f"🔢 Множитель на этот раунд: {multiplier}x"
            )

        session.add(user)
        await session.commit()

        await message.reply(
            f"{result_text}\n\n💰 Ваш баланс: {user.points} очков.\n"
            f"Проверьте через 'рп профиль'."
        )
#Функции слот машины - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def generate_symbols(symbols, base_mult=2, mult_step=1, base_weight=30, weight_step=-5):
    """
    symbols: список символов (["🌚", "🍋", ...])
    base_mult: множитель первого символа
    mult_step: насколько растёт множитель к следующему символу
    base_weight: вес (частота выпадения) первого символа
    weight_step: насколько уменьшается вес к следующему символу
    """
    multipliers = {}
    weights = []

    for i, sym in enumerate(symbols):
        # множитель растёт
        multipliers[sym] = base_mult + mult_step * i
        # вес уменьшается
        weight = max(1, base_weight + weight_step * i)  # чтобы не уйти в 0 или минус
        weights.append(weight)

    return multipliers, weights


#--------------- НАСТРОЙКА ----------------
SLOT_SYMBOLS = ["🌚", "🍋", "⭐", "☢", "🎸", "👼🏿","🚺","🚹"]

# генерим множители и веса автоматически
SYMBOL_MULTIPLIERS, SYMBOL_WEIGHTS = generate_symbols(
    SLOT_SYMBOLS,
    base_mult=2,   # первый множитель
    mult_step=1,   # шаг роста множителя
    base_weight=30, # вес самого частого символа
    weight_step=-5 # шаг уменьшения веса
)
def spin_slots():
    return [[random.choice(SLOT_SYMBOLS) for _ in range(3)] for _ in range(3)]

def format_slots(slots):
    return "\n".join(" | ".join(row) for row in slots)

def get_winning_lines(slots):
    """Возвращает список всех выигрышных линий [(символ, описание, множитель)]."""
    winning_lines = []
    n = 3  # размер поля

    # --- Горизонтали ---
    for i in range(n):
        if slots[i][0] == slots[i][1] == slots[i][2]:
            winning_lines.append((slots[i][0], f"Горизонталь {i+1}", 1.0))

    # --- Вертикали ---
    for j in range(n):
        if slots[0][j] == slots[1][j] == slots[2][j]:
            winning_lines.append((slots[0][j], f"Вертикаль {j+1}", 1.0))

    # --- Диагонали ---
    if slots[0][0] == slots[1][1] == slots[2][2]:
        winning_lines.append((slots[0][0], "Главная диагональ", 1.0))
    if slots[0][2] == slots[1][1] == slots[2][0]:
        winning_lines.append((slots[0][2], "Побочная диагональ", 1.0))

    return winning_lines

#СЛОТ МАШИНА 3 на 3  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп слот"))
async def slot_machine(message: Message):
    args = message.text.strip().split()
    if len(args) < 3:
        await message.reply("❗ Формат: рп казино <ставка>")
        return

    bet_str = args[2]
    if not bet_str.isdigit():
        await message.reply("❗ Ставка должна быть числом.")
        return

    bet = int(bet_str)
    if bet <= 0:
        await message.reply("❗ Ставка должна быть больше нуля.")
        return

    user_id = message.from_user.id
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.user_id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            await message.reply("❌ Вы не зарегистрированы, используйте /start.")
            return
        if user.points < bet:
            await message.reply("🚫 Недостаточно очков, вы бедность❤")
            return

        # снимаем ставку
        user.points -= bet

        # создаем сообщение для анимации
        msg = await message.reply("🎰 Запуск слотов...")

        #--------------- АНИМАЦИЯ (1 вращение) ---------------
        slots = None
        for _ in range(2):  # было 5
            slots = spin_slots()
            field = format_slots(slots)
            await msg.edit_text(f"🎰 Крутится...\n{field}")
            await asyncio.sleep(0.8)  # было 0.4

        # выбираем общий множитель
        global_multiplier = round(random.uniform(0.5, 1.5), 1)

        # ищем выигрышные линии
        winning_lines = get_winning_lines(slots)
        total_winnings = 0
        lines_text = ""

        if winning_lines:
            for symbol, line, line_mult in winning_lines:
                symbol_multiplier = SYMBOL_MULTIPLIERS.get(symbol, 1)

                # обычные линии (горизонтали, вертикали, диагонали)
                if line_mult == 1.0:
                    line_winnings = int(bet * symbol_multiplier * global_multiplier)
                    lines_text += f"{line}: {symbol} ×{symbol_multiplier} ×{global_multiplier} = {line_winnings}\n"

                total_winnings += line_winnings  # суммируем

            user.points += total_winnings  # добавляем выигрыш к балансу

            result = f"🎉 Выигрышные линии:\n{lines_text}\n💵 Общий выигрыш: {total_winnings} очков!"
        else:
            result = f"❌ Увы, вы проиграли {bet} очков.\n💸 Всё ушло админу 😉"

        session.add(user)
        await session.commit()

        await msg.edit_text(
            f"🎰 Результат:\n{format_slots(slots)}\n\n{result}\n\n💰 Баланс: {user.points} очков."
        )
#Проверка что бот работает - - - - - - - - - - - - -
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
рп топ - то РП игроков
рп админы - список администраторов''',
        parse_mode='HTML',
        reply_markup=kb.main
    )


# Для каждого ключевого слова определяем список возможных ответов
responses = {
    "женщина": [
        'ыыыыыыыыы',
        'АААААА ЖЕНЩИНЫ БЛЯТЬ',
        'НЕЕЕЕЕЕТ УБЕРИ ЭТО',
        'ЭТО ПРОСТО НЕВОЗМОЖНО!!!',
        'СПАСАЙСЯ КТО МОЖЕТ',
        'Ох Ахъ женщины топчег  \n  *Застрелил черта*  туда егооооо',
        'ЖЕНЩИНА В ЧАТЕ!!! \nСРОЧНО СПАСАЙСЯ',
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
        "ыыыыыыыыыы",
    ],
    # ... словарь для всех keywords
}
