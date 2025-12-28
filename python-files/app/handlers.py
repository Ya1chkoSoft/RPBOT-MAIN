from email import message
import random
import pickle
import re
import sys
import os
import html
import logging
import asyncio
import ast
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

# Импортируем только функции-обёртки для работы с БД
from app.database.requests import get_or_create_user, get_top_users, add_admin, get_user_by_username, get_full_user_profile
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
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


# -----------------------------------------------------------------
#ИМПОРТ КОНСТАНТЫ
from config import (
    SLOT_SYMBOLS, 
    SYMBOL_WEIGHTS, 
    SYMBOL_MULTIPLIERS,
    SLOT3X3_MULTIPLIERS,
)
# -----------------------------------------------------------------

# Вспомогательная функция для безопасного вывода HTML
def escape_html(text: str) -> str:
    """Экранирует специальные символы HTML: <, >, &, ", '."""
    if not text: 
        return ""
    # Всегда использовать str() для избежания ошибок, если text внезапно не строка
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')

# -----------------------------------------------------------------
# ХЕНДЛЕР /START (ГДЕ ДОБАВЛЕН КОММИТ)
# -----------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    # 1. Вызываем функцию для получения/создания пользователя
    await get_or_create_user(
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        userfullname=message.from_user.full_name
    )
    try:
        # Без этого вызова, все изменения (INSERT/UPDATE) будут откачены (ROLLBACK)
        await session.commit()
    except Exception as e:
        # Логирование и откат при ошибке COMMIT
        await session.rollback()
        # В реальном приложении здесь лучше использовать logger.error(f"Commit error: {e}")
        print(f"Ошибка при COMMIT: {e}") 
        
    # 3. Ответ пользователю
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


#передача очков  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text.lower().startswith("рп передать"))
async def transfer_points(message: Message, session: AsyncSession):
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

# --- КАЗИНО (1x3) ---

#Путь к GIF должен быть константой модуля.
# Используем os.path.abspath(__file__) для надежного определения пути
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOTS_PATH = os.path.join(BASE_DIR, "assets", "slots")

@router.message(F.text.lower().startswith("рп казино"))
async def casino(message: Message, session: AsyncSession):
    args = message.text.strip().split()
    if len(args) < 3:
        await message.reply("❗ Формат: <code>рп казино &lt;ставка&gt;</code>", parse_mode='HTML')
        return

    # 1. Извлекаем и проверяем ставку
    bet_str = args[2] 
    if not bet_str.isdigit() or int(bet_str) <= 0:
        await message.reply("❗ Ставка должна быть положительным числом.", parse_mode='HTML')
        return
        
    bet = int(bet_str)
    user_id = message.from_user.id
    
    # 2. Получение пользователя и проверка баланса
    user_result = await session.execute(select(User).where(User.user_id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        await message.reply("❌ Вы не зарегистрированы в системе. Используйте /start.", parse_mode='HTML') 
        return
    if user.points < bet:
        await message.reply("🚫 У вас недостаточно очков для этой ставки.", parse_mode='HTML') 
        return

    await asyncio.sleep(1.0) # Задержка 1.0 секунды

    # 4. Снятие ставки
    user.points -= bet

    # 5. Крутим слоты (логика остаётся прежней)
    slot1 = random.choices(SLOT_SYMBOLS, weights=SYMBOL_WEIGHTS, k=1)[0]
    slot2 = random.choices(SLOT_SYMBOLS, weights=SYMBOL_WEIGHTS, k=1)[0]
    slot3 = random.choices(SLOT_SYMBOLS, weights=SYMBOL_WEIGHTS, k=1)[0]

    # 6. Расчет выигрыша (логика остаётся прежней)
    winnings = 0
    final_multiplier = 0.0
    winning_symbol = None
    win_message = "❌ Увы, вы проиграли."

    if slot1 == slot2 == slot3:
        winning_symbol = slot1
        # Логика джекпота
        final_multiplier = SYMBOL_MULTIPLIERS[winning_symbol] * 3.0
        win_message = f"✨ Джекпот! Три одинаковых символа:"
            
    elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
        if slot1 == slot2: winning_symbol = slot1
        elif slot2 == slot3: winning_symbol = slot2
        elif slot1 == slot3: winning_symbol = slot1
            
        final_multiplier = SYMBOL_MULTIPLIERS[winning_symbol]
        win_message = "🎉 Поздравляем! Два одинаковых символа:"
        
    if final_multiplier > 0:
        winnings = int(bet * final_multiplier)
        user.points += winnings

    # 7. Обновление БД и запись истории
    session.add(user) 
    
    history = History(
        admin_id=message.from_user.id,
        target_id=user.user_id,
        points=winnings if winnings > 0 else -bet, 
        reason="Казино: Слоты",
        timestamp=datetime.now()
    )
    session.add(history)
    
    # 8. 🛑 ФИКСАЦИЯ: COMMIT! Гарантируем сохранение.
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        # 🔥 ИЗМЕНЕНИЕ: Отправляем новое сообщение об ошибке, так как старое не существует
        await message.reply(
            f"❌ Критическая ошибка БД при игре в слоты. Ставка отменена: <code>{escape_html(str(e))}</code>", 
            parse_mode='HTML'
        )
        return

    # 9. Формирование финального сообщения
    safe_points = escape_html(f"{user.points}")
    safe_bet = escape_html(f"{bet}")
    safe_multiplier = escape_html(f"{final_multiplier:.1f}x") 
    safe_winnings = escape_html(f"{winnings}")

    if winnings > 0:
        result_text = (
            f"{win_message} <b>{winning_symbol}</b>!\n"
            f"💎 Множитель: {safe_multiplier}\n"
            f"🏆 Вы выиграли <b>{safe_winnings}</b> очков!"
        )
    else:
        result_text = (
            f"{win_message}\n"
            f"💰 Ваша ставка: <b>{safe_bet}</b> очков"
        )
        
    caption_text = (
        f"🎰 | {slot1} | {slot2} | {slot3} |\n\n{result_text}\n\n"
        f"💰 Ваш баланс: <b>{safe_points}</b> очков.\n"
        f"Проверьте через 'рп профиль'."
    )
        
    # 10. Выбор и отправка GIF (логика не меняется, просто больше нет msg.edit_text)
    
    slot_gifs = []
    try:
        slot_gifs = [f for f in os.listdir(SLOTS_PATH) if f.endswith(".gif") and f.startswith("slot")]
    except FileNotFoundError:
        pass

    chosen_gif = random.choice(slot_gifs) if slot_gifs else None

    if chosen_gif:
        gif_path = os.path.join(SLOTS_PATH, chosen_gif)
        
        with open(gif_path, "rb") as gif_file:
            animation_file = FSInputFile(gif_path)
            
            # 🔥 Отправляем GIF с результатом
            await message.reply_animation(
                animation_file,
                caption=caption_text,
                parse_mode='HTML'
            )
    else:
        # Если GIF не найден, отправляем просто текст
        await message.reply(
            f"🚨 Нет GIF-файлов.\n\n{caption_text}", 
            parse_mode='HTML'
        )

# --- СЛОТЫ 3x3 ---
def spin_slots():
    """Крутит слоты 3x3 с использованием весов символов."""
    # Используем SYMBOL_WEIGHTS для каждого символа (k=9 - 9 слотов)
    all_symbols = random.choices(SLOT_SYMBOLS, weights=SYMBOL_WEIGHTS, k=9)
    # Делим на 3 ряда
    slots = [all_symbols[i:i + 3] for i in range(0, 9, 3)]
    return slots

def format_slots(slots):
    """Форматирует слоты для вывода в сообщении."""
    return "\n".join(" | ".join(row) for row in slots)

def get_winning_lines(slots):
    """
    Возвращает список всех выигрышных линий, где три символа совпадают.
    """
    winning_lines = []
    n = 3 

    # --- Горизонтали, Вертикали, Диагонали ---
    
    # Горизонтали
    for i in range(n):
        if slots[i][0] == slots[i][1] == slots[i][2]:
            winning_lines.append((slots[i][0], f"Горизонталь {i+1}", 1.0))

    # Вертикали
    for j in range(n):
        if slots[0][j] == slots[1][j] == slots[2][j]:
            winning_lines.append((slots[0][j], f"Вертикаль {j+1}", 1.0))

    # Диагонали
    if slots[0][0] == slots[1][1] == slots[2][2]:
        winning_lines.append((slots[0][0], "Главная диагональ", 1.0))
    if slots[0][2] == slots[1][1] == slots[2][0]:
        winning_lines.append((slots[0][2], "Побочная диагональ", 1.0))

    return winning_lines

# ==========================================
# 🎰 ХЕНДЛЕР: РП СЛОТЫ (3x3)
# ==========================================

@router.message(F.text.lower().startswith("рп слоты"))
@router.message(Command("slot")) # Поддержка текстового триггера и команды /slot
async def slot_machine(message: Message, session: AsyncSession):
    
    # 1. Парсинг аргументов и проверка ставки
    args = message.text.strip().split()
    
    # Проверка формата: "рп слоты <ставка>" или "/slot <ставка>"
    if len(args) < 2 and not message.text.startswith("/"):
        await message.reply("❗ Формат: <code>рп слоты &lt;ставка&gt;</code>", parse_mode='HTML')
        return
    
    # Извлекаем ставку (последний аргумент)
    bet_str = args[-1] 
    
    if not bet_str.isdigit():
        await message.reply("❗ Ставка должна быть числом.", parse_mode='HTML')
        return

    bet = int(bet_str)
    if bet <= 0:
        await message.reply("❗ Ставка должна быть больше нуля.", parse_mode='HTML')
        return

    user_id = message.from_user.id

    # 2. Получение пользователя и проверка баланса
    user_result = await session.execute(select(User).where(User.user_id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        await message.reply("❌ Вы не зарегистрированы. Используйте /start.", parse_mode='HTML')
        return
    
    if user.points < bet:
        await message.reply("🚫 У вас недостаточно очков для этой ставки.", parse_mode='HTML')
        return

    # Обновляем время последнего использования (оставлено для корректной работы user-модели)
    if hasattr(user, 'last_slot_time'):
        user.last_slot_time = datetime.now()

    # 4. Списываем ставку
    user.points -= bet 
    
    # 5. Искусственная задержка (имитация анимации)
    await asyncio.sleep(0.01)

    # 6. Запуск логики и расчет выигрыша
    # Убедитесь, что spin_slots() в app/casino.py использует SLOT3X3_SYMBOLS/WEIGHTS
    slots = spin_slots() 
    
    # Случайный множитель удачи (например, от 0.8x до 1.2x)
    global_multiplier = round(random.uniform(0.8, 1.2), 2)
    
    winning_lines = get_winning_lines(slots)

    total_winnings = 0
    lines_text = ""
    
    if winning_lines:
        for symbol, line_name, line_mult in winning_lines:
            
            #Теперь используется SLOT3X3_MULTIPLIERS
            symbol_val = SLOT3X3_MULTIPLIERS.get(symbol, 0)
            
            # Формула выигрыша: Ставка * Ценность символа * Глобальная удача
            line_win = int(bet * symbol_val * global_multiplier)

            lines_text += (f"🏆 {escape_html(line_name)} ({escape_html(symbol)}): "
                           f"{bet} ×{symbol_val:.1f} ×{global_multiplier} = {line_win}\n")

            total_winnings += line_win

        user.points += total_winnings
        result_text = (
            "🎉 <b>Выигрышные линии:</b>\n"
            f"{lines_text}\n"
            f"💵 <b>Общий выигрыш:</b> <b>{total_winnings}</b> очков!"
        )
    else:
        result_text = f"❌ Увы, вы проиграли <b>{bet}</b> очков.\n💸 Всё ушло админу 😉"

    # 7. Транзакция в БД и COMMIT
    try:
        history = History(
            admin_id=user_id,
            target_id=user.user_id,
            points=(total_winnings if total_winnings > 0 else -bet),
            reason="Казино: Слоты",
            timestamp=datetime.now()
        )
        session.add(history)
        session.add(user) # Сохраняем пользователя (включая last_slot_time)
        await session.commit()
    
    # 💥 ОТКАТ ТРАНЗАКЦИИ при ошибке
    except Exception as e:
        await session.rollback()
        logger.exception("Ошибка БД при слотах, возвращаем ставку: %s", e)
        user.points += bet # 🛑 ВОЗВРАТ СТАВКИ
        
        await message.reply(f"❌ Критическая ошибка БД! Ставка <b>{bet}</b> очков возвращена.", parse_mode='HTML')
        return

    # 8. Формирование финального сообщения
    safe_field = escape_html(format_slots(slots))
    safe_balance = escape_html(str(user.points))

    html_output = (
        f"🎰 <b>Результат:</b>\n"
        f"<code>{safe_field}</code>\n\n"
        f"{result_text}\n\n"
        f"💰 Баланс: <b>{safe_balance}</b> очков."
    )
    
    # 9. Отправка GIF + подпись
    slot_gifs = []
    chosen_gif = None

    try:
        if os.path.exists(SLOTS_PATH):
            all_gifs = [f for f in os.listdir(SLOTS_PATH) if f.endswith(".gif")]
            # Фильтр по "slot" (если нужно, иначе используйте all_gifs)
            slot_gifs = [f for f in all_gifs if f.startswith("slot")] 
            
            if slot_gifs:
                chosen_gif = random.choice(slot_gifs)
    except Exception as e:
        logger.warning("Ошибка чтения ассетов слотов: %s", e)
    
    if chosen_gif:
        gif_path = os.path.join(SLOTS_PATH, chosen_gif)
        try:
            animation_file = FSInputFile(gif_path)
            # 🚨 ОТПРАВЛЯЕМ GIF с финальной подписью
            await message.reply_animation(
                animation_file, 
                caption=html_output,
                parse_mode='HTML'
            )
            return 
        except Exception as e:
            logger.error("Ошибка при отправке GIF: %s. Отправляем текстом.", e)
            
    # 10. Фоллбэк (Только текст)
    prefix = ""
    if not os.path.exists(SLOTS_PATH):
        prefix = f"🚨 Папка ассетов не найдена: <code>{SLOTS_PATH}</code>\n\n"
    elif chosen_gif:
        prefix = "🚨 Ошибка отправки GIF. Результат текстом:\n\n"
        
    await message.reply(f"{prefix}{html_output}", parse_mode='HTML')

#Проверка что бот работает - - - - - - - - - - - - -
@router.message(Command("ping"))
async def test_ping(message: Message, session: AsyncSession):
    await message.reply("pong")

# ОСНОВНЫЕ ХЕНДЛЕРЫ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
@router.message(F.text)
async def randomizer1(message: Message, session: AsyncSession):
    global rand, rand1_100
    text = message.text.strip().lower()
    rand = random.randint(1, 10)
    rand1_100 = random.randint(1, 100)
    
    # 1. Сначала обрабатываем простые, не связанные с БД, кейсы
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
    
    # 2. Обрабатываем кейсы, связанные с БД (требующие транзакции)
    
    # 2.1. Создание/обновление пользователя для всех команд
    if text in ('рп профиль', 'рп топ'):
        
        # Гарантируем, что пользователь существует в БД перед запросом его данных
        try:
            await get_or_create_user(
                session=session,
                user_id=message.from_user.id,
                username=message.from_user.username or "",
                userfullname=message.from_user.full_name
            )
            
            # 🚀 ФИКСИРУЕМ изменения (если пользователь был создан/обновлен)
            await session.commit()
            
        except Exception as e:
            # Откат в случае ошибки
            await session.rollback()
            print(f"Ошибка при сохранении пользователя или COMMIT: {e}") 
            # Не прерываем выполнение, чтобы попытаться хотя бы прочитать данные
            
        
        # 2.2. Обработка 'рп профиль'
        if text == 'рп профиль':
            
            # Получаем полный профиль с присоединенными данными страны
            profile_user = await get_full_user_profile(session, message.from_user.id)
            
            if not profile_user:
                await message.reply("⛔ Произошла ошибка при загрузке вашего профиля.")
                return

            # Определение статуса и страны
            country_info = profile_user.country.name if profile_user.country else "Не состоит"
            #Определяем статус пользователя в стране
            ruler_status = "Гражданин"
            
            if profile_user.country:
                # 1. Проверяем, является ли пользователь правителем
                if profile_user.country.ruler_id == profile_user.user_id:
                    ruler_status = "Правитель"
                # 2. Если не правитель, берем его должность в стране (position)
                elif profile_user.position:
                    ruler_status = profile_user.position
            
            # 3) Отвечаем пользователю с его НОВЫМИ данными
            await message.reply(
                "👑 **Ваш РП Профиль**\n"
                "---------------------------------\n"
                f"• Имя: **{profile_user.userfullname}**\n"
                f"• ID: `{profile_user.user_id}`\n"
                f"• РП очки: **{profile_user.points}**\n"
                f"• Страна: **{country_info}**\n"
                f"• Статус в стране: **{ruler_status}**",
                parse_mode='Markdown'
            )
            return

        # 2.3. Обработка 'рп топ'
        elif text == 'рп топ':
            top_users = await get_top_users(session=session, limit=10)
            
            if not top_users:
                await message.answer("Топ рпшеров пуст.")
                return

            response_lines = ["🏆 **Топ РП игроков:**\n---"]
            for i, user in enumerate(top_users, start=1):
                # Для отображения берем полное имя или никнейм
                display_name = user.userfullname or (user.username or f"ID {user.user_id}")
                
                # Добавляем название страны
                country_name = f" ({user.country.name})" if user.country else ""
                
                response_lines.append(f"**{i}.** {display_name}{country_name} — **{user.points}** баллов")

            response_text = "\n".join(response_lines)
            await message.answer(response_text, parse_mode='Markdown')
            return
            
    # 3. Обработка ключевых слов через pattern (если не сработал match)
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


# Слова для обработки которые ищем в сообщении и ответы
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