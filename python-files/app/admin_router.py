import html as python_html
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from .database.models import User, Admins, History
from .database.requests import get_or_create_user
from aiogram import html
import logging
from config import OWNER_ID
admin_router = Router()
logger = logging.getLogger(__name__)

@admin_router.message(F.text.lower().startswith("рп назначить"))
async def handle_set_admin_level(message: Message, session: AsyncSession):
    try:
        args = message.text.strip().split()
        target_user = None
        level_str = None

        # 1. Определение цели (Reply или Аргументы)
        if message.reply_to_message:
            if len(args) < 3:
                await message.reply("❗ Формат: <code>рп назначить уровень</code>")
                return
            
            target_id = message.reply_to_message.from_user.id
            level_str = args[2]
            
            res = await session.execute(select(User).where(User.user_id == target_id))
            target_user = res.scalar_one_or_none()
            
            if not target_user:
                chat = message.reply_to_message.from_user
                target_user = User(
                    user_id=chat.id, 
                    username=chat.username, 
                    userfullname=chat.full_name
                )
                session.add(target_user)
        else:
            if len(args) < 4:
                await message.reply("❗ Формат: <code>рп назначить id уровень</code>")
                return
            
            target_str = args[2]
            level_str = args[3]

            if target_str.isdigit():
                res = await session.execute(select(User).where(User.user_id == int(target_str)))
                target_user = res.scalar_one_or_none()
            else:
                username = target_str.lstrip("@")
                res = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
                target_user = res.scalar_one_or_none()

        # 2. Базовые проверки
        if not target_user:
            await message.reply("❌ Юзер не найден в базе.")
            return

        if not level_str.isdigit():
            await message.reply("❗ Уровень должен быть числом.")
            return

        new_level = int(level_str)
        caller_id = message.from_user.id
        
        # 3. Проверка прав и иерархии
        if caller_id == OWNER_ID:
            caller_level = 5
        else:
            res = await session.execute(select(Admins.adminlevel).where(Admins.user_id == caller_id))
            caller_level = res.scalar() or 0
            if caller_level < 5:
                await message.reply("🚫 Недостаточно прав.")
                return

        res = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        target_admin = res.scalar_one_or_none()
        current_level = target_admin.adminlevel if target_admin else 0

        if caller_id != OWNER_ID:
            if new_level >= caller_level or current_level >= caller_level:
                await message.reply("🚫 Ошибка иерархии.")
                return

        # 4. Сохранение (Коммит сделает Middleware, но тут для верности оставим)
        if target_admin:
            target_admin.adminlevel = new_level
        else:
            session.add(Admins(user_id=target_user.user_id, adminlevel=new_level))
        
        await session.commit()

        # 5. Тот самый неубиваемый парсер (Secure Option)
        disp_name = str(target_user.userfullname or target_user.username or "NoName")
        # Экранируем всё, что может сломать HTML
        safe_name = python_html.escape(disp_name)
        safe_id = python_html.escape(str(target_user.user_id))
        
        # Собираем строку через F-строку и ручные теги
        reply_text = (
            f"✅ Пользователь <b>{safe_name}</b> (ID: <code>{safe_id}</code>)\n"
            f"Уровень админа: <b>{new_level}</b>"
        )

        await message.answer(reply_text, parse_mode="HTML")

    except Exception as e:
        print(f"[ADMIN SET ERROR] {e}")
        await message.answer("❌ Ошибка при назначении. Проверь логи.")


# --- ОВНЕР НАЗНАЧИТЬ АДМИНА ---
@admin_router.message(F.text.lower().startswith("рп овнер назначить"))
async def owner_assign_admin(message: Message, session: AsyncSession):
    try:
        args = message.text.strip().split()

        if len(args) < 4:
            # Используем html.quote для безопасности при выводе примеров, хотя тут статический текст
            await message.reply(
                "❗ Формат: <code>рп овнер назначить &lt;user_id или @username&gt; &lt;уровень&gt;</code>"
            )
            return

        target_str = args[2]
        level_str = args[3]

        # === Проверки ===
        if not level_str.isdigit():
            await message.reply("❗ Уровень должен быть числом.")
            return

        new_level = int(level_str)
        if not (0 <= new_level <= 5):
            await message.reply("❗ Уровень должен быть от 0 до 5.")
            return

        caller_id = message.from_user.id
        if caller_id != OWNER_ID:
            await message.reply("🚫 Только владелец бота может использовать эту команду.")
            return

        # === Поиск пользователя ===
        target_user: User | None = None

        if target_str.isdigit():
            result = await session.execute(select(User).where(User.user_id == int(target_str)))
            target_user = result.scalar_one_or_none()
        else:
            username = target_str.lstrip("@")
            result = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            target_user = result.scalar_one_or_none()

        if not target_user:
            await message.reply("❌ Пользователь не найден в базе.")
            return

        # === Логика обновления БД ===
        if hasattr(target_user, 'adminlevel'):
            target_user.adminlevel = new_level
            session.add(target_user)

        admin_result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        admin = admin_result.scalar_one_or_none()

        if not admin:
            session.add(Admins(
                user_id=target_user.user_id,
                username=target_user.username,
                userfullname=target_user.userfullname,
                adminlevel=new_level
            ))
        else:
            admin.adminlevel = new_level
            session.add(admin)
        

        # === Безопасный ответ (Secure Option) ===
        # Используем aiogram.html.quote вместо самописной функции
        display_name = target_user.userfullname or f"@{target_user.username or 'без_ника'}"
        safe_name = html.quote(display_name)
        safe_id = html.quote(str(target_user.user_id))
        
        # Формируем ответ, используя встроенные методы html
        reply_text = (
            f"✅ Пользователь {safe_name} (ID: {safe_id})\n"
            f"Теперь имеет административный уровень: {html.bold(new_level)}"
        )

        await message.reply(reply_text)

    except Exception as e:
        # Логируем реальную ошибку в консоль
        print(f"[OWNER ASSIGN ADMIN ERROR] {e}")
        await message.reply("❌ Произошла ошибка при назначении.")


@admin_router.message(F.text.lower().startswith("рп овнер начислить"))
async def owner_add_points(message: Message, session: AsyncSession):
    args = message.text.strip().split()

    # 1. Проверка синтаксиса
    if len(args) < 6: 
        await message.reply(
            "❗ Формат: <code>рп овнер начислить &lt;user_id или @username&gt; &lt;очки&gt; &lt;причина&gt;</code> (Причина обязательна)", 
            parse_mode='HTML'
        )
        return
    
    caller_id = message.from_user.id
    # 2. Проверка прав (Предполагается, что OWNER_ID определен где-то)
    if caller_id != OWNER_ID:
        await message.reply("🚫 Только владелец может использовать эту команду.", parse_mode='HTML')
        return

    target_str = args[3]  # Цель
    points_str = args[4]  # Очки
    reason = " ".join(args[5:]) # Причина

    # 3. Проверка очков
    if not points_str.isdigit():
        await message.reply("❗ Количество очков должно быть положительным целым числом.", parse_mode='HTML')
        return

    points = int(points_str)
    
    if points <= 0:
        await message.reply("❗ Количество очков должно быть больше нуля.", parse_mode='HTML')
        return

    # 4. 🔍 УНИВЕРСАЛЬНЫЙ ПОИСК ПОЛЬЗОВАТЕЛЯ
    if target_str.isdigit():
        stmt = select(User).where(User.user_id == int(target_str))
    else:
        username = target_str.lstrip("@")
        stmt = select(User).where(User.username == username)
        
    result = await session.execute(stmt)
    target_user = result.scalar_one_or_none()

    if not target_user:
        await message.reply("❌ Пользователь не найден в базе.", parse_mode='HTML')
        return

    # 5. Подготовка данных для сохранения (Обновление очков и запись истории)
    # 5a. Обновление User
    target_user.points += points
    session.add(target_user)

    # 5b. Запись History
    history = History(
        admin_id=caller_id,
        target_id=target_user.user_id,
        points=points,
        reason=reason,
        timestamp=datetime.now() 
    )
    session.add(history)

    # 6. Ответ пользователю (ТОЛЬКО ПОСЛЕ УСПЕШНОГО COMMIT)
    # Если мы дошли до этого шага, данные гарантированно сохранены.
    display_name = target_user.userfullname or ('@' + (target_user.username or f"ID {target_user.user_id}"))
    
    safe_reason = escape_html(reason)
    safe_display_name = escape_html(display_name)
    
    await message.reply(
        f"✅ Пользователю <b>{safe_display_name}</b> (ID: <code>{target_user.user_id}</code>) успешно начислено <b>{points}</b> очков.\n"
        f"💰 Новый баланс: <b>{target_user.points}</b> очков.\n"
        f"Причина: <i>{safe_reason}</i>",
        parse_mode='HTML'
    )
    # 8. Возвращаем управление
    return


# --- ОВНЕР ОТНЯТЬ ОЧКИ (ФИНАЛЬНО ИСПРАВЛЕННЫЙ) ---
@admin_router.message(F.text.lower().startswith("рп овнер отнять"))
async def owner_remove_points(message: Message, session: AsyncSession):
    args = message.text.strip().split()

    # 1. Проверка синтаксиса
    if len(args) < 5:
        await message.reply(
            "❗ Формат: <code>рп овнер отнять &lt;user_id или @username&gt; &lt;очки&gt; &lt;причина&gt;</code>",
            parse_mode='HTML'
        )
        return

    caller_id = message.from_user.id
    if caller_id != OWNER_ID:
        # Возвращаем HTML для простоты
        await message.reply("🚫 Только владелец может использовать эту команду.", parse_mode='HTML')
        return

    target_str = args[2] 
    points_str = args[3]
    reason = " ".join(args[4:]) or "Без причины"
    
    # 2. Проверка количества очков
    if not points_str.isdigit():
        # Возвращаем HTML для простоты
        await message.reply("❗ Количество очков должно быть положительным целым числом.", parse_mode='HTML')
        return

    points = int(points_str)
    if points <= 0:
        # Возвращаем HTML для простоты
        await message.reply("❗ Количество очков должно быть больше нуля.", parse_mode='HTML')
        return

    # 3. 🔍 УНИВЕРСАЛЬНЫЙ ПОИСК ПОЛЬЗОВАТЕЛЯ
    target_user = None
    if target_str.isdigit():
        result = await session.execute(select(User).where(User.user_id == int(target_str)))
    else:
        username = target_str.lstrip("@")
        result = await session.execute(select(User).where(User.username == username))
        
    target_user = result.scalar_one_or_none()

    if not target_user:
        # ✅ Возвращаем HTML для простоты
        await message.reply("❌ Пользователь не найден в базе.", parse_mode='HTML')
        return

    # 4. Вычитаем очки с защитой от отрицательного баланса
    target_user.points -= points
    
    # Защита от отрицательного баланса
    if target_user.points < 0:
        target_user.points = 0
    
    session.add(target_user)

    # 5. Сохраняем историю
    history = History(
        admin_id=caller_id,
        target_id=target_user.user_id,
        points=-points, # Минусовые очки для истории
        reason=reason,
        timestamp=datetime.now()
    )
    session.add(history)

    # 6. Ответ пользователю
    display_name = target_user.userfullname or ('@' + (target_user.username or f"ID {target_user.user_id}"))

    # ИСПОЛЬЗУЕМ HTML для форматирования
    await message.reply(
        f"❌ У пользователя <b>{display_name}</b> отнято <b>{points}</b> очков.<br>"
        f"💰 Новый баланс: <b>{target_user.points}</b> очков.<br>"
        f"Причина: <i>{reason}</i>",
        parse_mode='HTML'
    )

@admin_router.message(F.text.lower().startswith("рп снять"))
async def handle_remove_admin(message: Message, session: AsyncSession):
    try:
        args = message.text.strip().split()
        target_user = None
        reason = "Без причины"

        # 1. Определение цели (Reply или Аргументы)
        if message.reply_to_message:
            # Формат: рп снять [причина]
            target_id = message.reply_to_message.from_user.id
            if len(args) >= 3:
                reason = " ".join(args[2:])
            
            res = await session.execute(select(User).where(User.user_id == target_id))
            target_user = res.scalar_one_or_none()
        else:
            # Формат: рп снять <id/@nick> [причина]
            if len(args) < 3:
                await message.reply("❗ Формат: <code>рп снять id причина</code> или ответ на сообщение.")
                return
            
            target_str = args[2]
            if len(args) > 3:
                reason = " ".join(args[3:])
            
            if target_str.isdigit():
                res = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                res = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            
            target_user = res.scalar_one_or_none()

        # 2. Проверки существования
        if not target_user:
            await message.reply("❌ Пользователь не найден в базе.")
            return

        target_admin_res = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        target_admin = target_admin_res.scalar_one_or_none()

        if not target_admin:
            await message.reply("❌ Этот пользователь не является админом.")
            return

        # 3. Проверка прав вызывающего
        caller_id = message.from_user.id
        if caller_id == OWNER_ID:
            caller_level = 5
        else:
            remover_res = await session.execute(select(Admins.adminlevel).where(Admins.user_id == caller_id))
            caller_level = remover_res.scalar() or 0
            if caller_level < 5:
                await message.reply("🚫 Недостаточно прав для снятия админов.")
                return

        # 4. Проверка иерархии
        if caller_id != OWNER_ID:
            if target_admin.adminlevel >= caller_level:
                await message.reply("🚫 Вы не можете снять админа равного или выше вас по уровню.")
                return

        # 5. Процесс снятия
        await session.delete(target_admin)
        if hasattr(target_user, 'adminlevel'):
            target_user.adminlevel = 0
            session.add(target_user)
        
        await session.commit()

        # 6. Безопасный вывод
        disp_name = str(target_user.userfullname or target_user.username or "NoName")
        safe_name = python_html.escape(disp_name)
        safe_id = python_html.escape(str(target_user.user_id))
        safe_reason = python_html.escape(reason)

        reply_text = (
            f"✅ Пользователь <b>{safe_name}</b> (ID: <code>{safe_id}</code>) <b>снят</b> с поста администратора.\n"
            f"📄 Причина: <i>{safe_reason}</i>"
        )

        await message.answer(reply_text, parse_mode="HTML")

    except Exception as e:
        print(f"[ADMIN REMOVE ERROR] {e}")
        await message.answer("❌ Ошибка при снятии админа.")


@admin_router.message(F.text.lower().startswith("рп админы"))
async def list_admins(message: Message, session: AsyncSession):
    try:
        query = (
            select(Admins, User)
            .join(User, Admins.user_id == User.user_id)
            .order_by(Admins.adminlevel.desc())
        )
        result = await session.execute(query)
        rows = result.all()

        if not rows:
            await message.reply("<b>Список администраторов пуст.</b>", parse_mode="HTML")
            return

        admin_list = []
        admin_list.append("<b>🛡 Список администрации:</b>\n")

        for admin_obj, user_obj in rows:
            # Экранируем имя и ID
            disp_name = str(user_obj.userfullname or user_obj.username or "NoName")
            safe_name = python_html.escape(disp_name)
            safe_id = python_html.escape(str(user_obj.user_id))
            level = admin_obj.adminlevel

            # Формируем строку для каждого админа
            admin_list.append(
                f"• <b>{safe_name}</b> (<code>{safe_id}</code>) — [<b>{level}</b>]"
            )

        # Собираем всё в одно сообщение
        final_text = "\n".join(admin_list)
        
        await message.answer(final_text, parse_mode="HTML")

    except Exception as e:
        print(f"[ADMIN LIST ERROR] {e}")
        await message.answer("❌ Ошибка при получении списка админов.")

#НАЧИСЛЕНИЕ ОЧКОВ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import html as python_html
from datetime import datetime

@admin_router.message(F.text.lower().startswith("рп начислить"))
async def handle_give_points_rp(message: Message, session: AsyncSession):
    try:
        args = message.text.strip().split()
        target_user = None
        points = 0
        reason = "Без причины"
        event_type = "award" if points > 0 else "penalty"
        # 1. Разбор аргументов (Reply vs Текст)
        if message.reply_to_message:
            # Формат: рп начислить <очки> [причина]
            if len(args) < 3:
                await message.reply("❗ Формат: <code>рп начислить очки причина</code> (ответом на сообщение)")
                return
            
            points_str = args[2]
            if len(args) > 3:
                reason = " ".join(args[3:])
            
            target_id = message.reply_to_message.from_user.id
            res = await session.execute(select(User).where(User.user_id == target_id))
            target_user = res.scalar_one_or_none()
            
            # Если юзера нет в базе — создаем
            if not target_user:
                chat = message.reply_to_message.from_user
                target_user = User(user_id=chat.id, username=chat.username, userfullname=chat.full_name)
                session.add(target_user)
        else:
            # Формат: рп начислить <id/@nick> <очки> [причина]
            if len(args) < 4:
                await message.reply("❗ Формат: <code>рп начислить id очки причина</code>")
                return
            
            target_str = args[2]
            points_str = args[3]
            if len(args) > 4:
                reason = " ".join(args[4:])

            if target_str.isdigit():
                res = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                res = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            target_user = res.scalar_one_or_none()

        # 2. Валидация данных
        if not target_user:
            await message.reply("❌ Пользователь не найден в базе.")
            return

        if not points_str.lstrip("-").isdigit():
            await message.reply("❗ Количество очков должно быть целым числом.")
            return
        points = int(points_str)

        # 3. Проверка прав и иерархии
        caller_id = message.from_user.id
        if caller_id == OWNER_ID:
            caller_level = 5
        else:
            admin_res = await session.execute(select(Admins.adminlevel).where(Admins.user_id == caller_id))
            caller_level = admin_res.scalar() or 0
            if caller_level < 1: # Или твой минимальный уровень для начисления
                await message.reply("🚫 У вас нет прав на начисление очков.")
                return

        target_admin_res = await session.execute(select(Admins.adminlevel).where(Admins.user_id == target_user.user_id))
        target_level = target_admin_res.scalar() or 0

        if caller_id != OWNER_ID and target_level >= caller_level:
            await message.reply("🚫 Вы не можете изменять очки админу равного или выше вашего уровня.")
            return

# 4. Выполнение операции

# === ЗАПРЕТ НАЧИСЛЕНИЯ ОЧКОВ БОТАМ ===
        if message.reply_to_message:
            # Если команда ответом на сообщение — берём from_user из reply
            target_from_user = message.reply_to_message.from_user
        else:
            # Если по ID/юзернейму — нужно получить объект User из Telegram
            # Для этого используем bot.get_chat()
            try:
                chat_info = await message.bot.get_chat(target_user.user_id)
                target_from_user = chat_info  # Это объект types.User или types.Chat
            except Exception:
                await message.answer("❌ Не удалось получить информацию о пользователе.")
                return

# Проверяем флаг is_bot
        if getattr(target_from_user, "is_bot", False):
            await message.answer("🚫 Нельзя начислять или снимать очки ботам.")
            return
# =====================================

        target_user.points = (target_user.points or 0) + points

        # Определяем тип события
        if points > 0:
            event_type = "award"
        elif points < 0:
            event_type = "penalty"
        else:
            event_type = "adjustment"

        # Добавляем в историю
        new_history = History(
            admin_id=caller_id,
            target_id=target_user.user_id,
            event_type=event_type,
            points=points,
            reason=reason,
            timestamp=datetime.now()
        )
        session.add(new_history)

        await session.commit()

        # 5. Безопасный вывод
        disp_name = str(target_user.userfullname or target_user.username or "NoName")
        safe_name = python_html.escape(disp_name)
        safe_reason = python_html.escape(reason)
        
        status_icon = "📈" if points > 0 else "📉"
        
        reply_text = (
            f"{status_icon} <b>Очки изменены!</b>\n"
            f"👤 Юзер: <b>{safe_name}</b>\n"
            f"💰 Изменение: <code>{points:+d}</code>\n"
            f"📄 Причина: <i>{safe_reason}</i>"
        )

        await message.answer(reply_text, parse_mode="HTML")

    except Exception as e:
        print(f"[POINTS ERROR] {e}")
        await message.answer("❌ Ошибка при начислении очков.")