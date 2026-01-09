import html
from datetime import datetime

from aiogram import Router, types, F
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from aiogram.filters import Command, CommandObject

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, Admins, History, Punishment
from app.filters import IsRPAdmin, IsCountryRuler
from app.utils.html_helpers import escape_html
from config import OWNER_ID

admin_router = Router()



# ==================== РП НАЗНАЧИТЬ ====================
@admin_router.message(F.text.lower().startswith("рп назначить"))
async def handle_set_admin_level(message: Message, session: AsyncSession):
    try:
        args = message.text.strip().split()
        if len(args) < 4 and not message.reply_to_message:
            await message.reply("❗ Формат: <code>рп назначить &lt;user_id или @username&gt; &lt;уровень&gt;</code> или ответом на сообщение")
            return

        # Поиск пользователя
        target_user = None

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            result = await session.execute(select(User).where(User.user_id == target_id))
            target_user = result.scalar_one_or_none()
            level_str = args[2] if len(args) >= 3 else None
        else:
            target_str = args[2]
            level_str = args[3]

            if target_str.isdigit():
                result = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                result = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            target_user = result.scalar_one_or_none()

        if not target_user:
            await message.reply("❌ Пользователь не найден.")
            return

        if not level_str or not level_str.isdigit():
            await message.reply("❗ Уровень должен быть числом.")
            return

        new_level = int(level_str)
        if new_level < 0 or new_level > 5:
            await message.reply("❗ Уровень должен быть от 0 до 5.")
            return

        # Проверка прав вызывающего
        caller_id = message.from_user.id
        if caller_id == OWNER_ID:
            caller_level = 5
        else:
            result = await session.execute(select(Admins.adminlevel).where(Admins.user_id == caller_id))
            caller_level = result.scalar() or 0
            if caller_level < 5:
                await message.reply("🚫 У вас нет прав для назначения админов.")
                return

        # Проверка текущего уровня цели
        result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        target_admin = result.scalar_one_or_none()
        current_level = target_admin.adminlevel if target_admin else 0

        if current_level == new_level:
            await message.reply(f"❗ Пользователь уже имеет уровень {new_level}.")
            return

        if caller_id != OWNER_ID:
            if new_level >= caller_level:
                await message.reply("🚫 Вы не можете назначить уровень равный или выше вашего.")
                return
            if target_admin and current_level >= caller_level:
                await message.reply("🚫 Вы не можете изменить уровень админа равного или выше вас.")
                return

        # Применение изменений
        if target_admin:
            target_admin.adminlevel = new_level
        else:
            session.add(Admins(user_id=target_user.user_id, adminlevel=new_level))

        # Ответ
        display_name = target_user.userfullname or f"@{target_user.username or 'без_ника'}"
        safe_name = escape_html(display_name)
        safe_id = escape_html(str(target_user.user_id))

        await message.reply(
            f"✅ Пользователь {safe_name} (ID: {safe_id})\n"
            f"Теперь имеет уровень админа: {hbold(new_level)}"
        )

    except Exception as e:
        print(f"[ADMIN SET ERROR] {e}")
        await message.reply("❌ Произошла ошибка при назначении админа.")


# ==================== РП СНЯТЬ ====================
@admin_router.message(F.text.lower().startswith("рп снять"))
async def handle_remove_admin(message: Message, session: AsyncSession):
    try:
        args = message.text.strip().split()
        reason = "Без причины"
        if len(args) > 3:
            reason = " ".join(args[3:]) if message.reply_to_message else " ".join(args[4:])

        # Поиск пользователя
        target_user = None

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            result = await session.execute(select(User).where(User.user_id == target_id))
            target_user = result.scalar_one_or_none()
        else:
            if len(args) < 3:
                await message.reply("❗ Формат: <code>рп снять &lt;user_id или @username&gt; [причина]</code> или ответом на сообщение")
                return
            target_str = args[2]
            if target_str.isdigit():
                result = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                result = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            target_user = result.scalar_one_or_none()

        if not target_user:
            await message.reply("❌ Пользователь не найден.")
            return

        result = await session.execute(select(Admins).where(Admins.user_id == target_user.user_id))
        target_admin = result.scalar_one_or_none()
        if not target_admin:
            await message.reply("❗ Этот пользователь не является админом.")
            return

        # Проверка прав
        caller_id = message.from_user.id
        if caller_id == OWNER_ID:
            caller_level = 5
        else:
            result = await session.execute(select(Admins.adminlevel).where(Admins.user_id == caller_id))
            caller_level = result.scalar() or 0
            if caller_level < 5:
                await message.reply("🚫 Недостаточно прав.")
                return
            if target_admin.adminlevel >= caller_level:
                await message.reply("🚫 Вы не можете снять админа равного или выше вас.")
                return

        # Снятие
        await session.delete(target_admin)
        if hasattr(target_user, 'adminlevel'):
            target_user.adminlevel = 0
            session.add(target_user)

        # Ответ
        display_name = target_user.userfullname or f"@{target_user.username or 'без_ника'}"
        safe_name = escape_html(display_name)
        safe_id = escape_html(str(target_user.user_id))
        safe_reason = escape_html(reason)

        await message.reply(
            f"✅ Админ {safe_name} (ID: {safe_id}) снят с должности.\n"
            f"Причина: <i>{safe_reason}</i>"
        )

    except Exception as e:
        print(f"[ADMIN REMOVE ERROR] {e}")
        await message.reply("❌ Ошибка при снятии админа.")


# ==================== РП АДМИНЫ (СПИСОК) ====================
@admin_router.message(F.text.lower().startswith("рп админы"))
async def list_admins(message: Message, session: AsyncSession):
    try:
        result = await session.execute(
            select(Admins, User)
            .join(User, Admins.user_id == User.user_id)
            .order_by(Admins.adminlevel.desc())
        )
        admins = result.all()

        if not admins:
            await message.reply("📭 Список администраторов пуст.")
            return

        lines = ["<b>🛡️ Список администрации:</b>\n"]
        for admin, user in admins:
            name = user.userfullname or user.username or "NoName"
            safe_name = escape_html(name)
            safe_id = escape_html(str(user.user_id))
            lines.append(f"• <b>{safe_name}</b> (<code>{safe_id}</code>) — уровень <b>{admin.adminlevel}</b>")

        await message.reply("\n".join(lines))

    except Exception as e:
        logger.error(f"[ADMIN LIST ERROR] {e}")
        await message.reply("❌ Ошибка при получении списка админов.")



# ==================== РП НАЧИСЛИТЬ (ОБЫЧНЫЙ АДМИН) ====================
@admin_router.message(F.text.lower().startswith("рп начислить"))
async def handle_give_points(message: Message, session: AsyncSession):
    try:
        args = message.text.strip().split()
        reason = "Без причины"

        # Определяем цель и количество очков
        if message.reply_to_message:
            if len(args) < 3:
                await message.reply("❗ Формат: ответом на сообщение <code>рп начислить &lt;очки&gt; [причина]</code>")
                return

            if message.reply_to_message.from_user.is_bot:
                await message.reply("🚫 Нельзя начислять очки ботам.")
                return

            target_id = message.reply_to_message.from_user.id
            points_str = args[2]
            if len(args) > 3:
                reason = " ".join(args[3:])

        else:
            if len(args) < 4:
                await message.reply("❗ Формат: <code>рп начислить &lt;user_id или @username&gt; &lt;очки&gt; [причина]</code>")
                return

            target_str = args[2]
            points_str = args[3]
            if len(args) > 4:
                reason = " ".join(args[4:])

            # Поиск по ID или @username
            if target_str.isdigit():
                result = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                result = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            target_user = result.scalar_one_or_none()

            if not target_user:
                await message.reply("❌ Пользователь не найден.")
                return

            target_id = target_user.user_id

        # Валидация очков
        if not points_str.lstrip("-").isdigit():
            await message.reply("❗ Очки должны быть целым числом.")
            return
        points = int(points_str)

        # Проверка прав вызывающего
        caller_id = message.from_user.id
        if caller_id == OWNER_ID:
            caller_level = 5
        else:
            result = await session.execute(select(Admins.adminlevel).where(Admins.user_id == caller_id))
            caller_level = result.scalar() or 0

        if caller_level < 1:
            await message.reply("🚫 У вас нет прав на начисление очков.")
            return

        # Получаем целевого юзера (если не по reply)
        if not message.reply_to_message:
            result = await session.execute(select(User).where(User.user_id == target_id))
            target_user = result.scalar_one_or_none()
        else:
            result = await session.execute(select(User).where(User.user_id == target_id))
            target_user = result.scalar_one_or_none()

        if not target_user:
            await message.reply("❌ Пользователь не найден в базе.")
            return

        # Проверка иерархии
        target_admin_result = await session.execute(select(Admins.adminlevel).where(Admins.user_id == target_user.user_id))
        target_level = target_admin_result.scalar() or 0

        if caller_id != OWNER_ID and target_level >= caller_level:
            await message.reply("🚫 Вы не можете изменять очки админу равного или выше вас.")
            return

        # Начисление
        target_user.points = (target_user.points or 0) + points
        session.add(target_user)

        # Запись в историю
        session.add(History(
            admin_id=caller_id,
            target_id=target_user.user_id,
            event_type="admin_give",
            points=points,
            reason=reason,
            timestamp=datetime.now()
        ))

        # Ответ
        display_name = target_user.userfullname or f"@{target_user.username or 'без_ника'}"
        safe_name = escape_html(display_name)
        safe_reason = escape_html(reason)
        icon = "📈" if points > 0 else "📉" if points < 0 else "⚖️"

        await message.reply(
            f"{icon} Пользователю {safe_name} начислено <b>{points:+}</b> RP-очков.\n"
            f"Новый баланс: <b>{target_user.points}</b>\n"
            f"Причина: <i>{safe_reason}</i>",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"[GIVE POINTS ERROR] {e}")
        await message.reply("❌ Ошибка при начислении очков.")

# ==================== РП ИСТОРИЯ (ПОСЛЕДНИЕ ДЕЙСТВИЯ) ====================
@admin_router.message(F.text.lower().startswith("рп история"))
async def admin_history(message: Message, session: AsyncSession):
    try:
        limit = 20

        # Один запрос: берём историю + юзера-цель + юзера-админа
        stmt = (
            select(History, User, Admins.userfullname.label("admin_name"))
            .join(User, History.target_id == User.user_id)
            .outerjoin(Admins, Admins.user_id == History.admin_id)
            .order_by(History.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        entries = result.all()

        if not entries:
            await message.reply("📭 История действий пуста.")
            return

        lines = ["<b>📜 Последние действия администрации:</b>\n"]

        for history, target_user, admin_name in entries:
            # Имя админа — из join или "Unknown"
            admin_display = admin_name or "Unknown"
            target_display = target_user.userfullname or target_user.username or "NoName"

            safe_admin = escape_html(admin_display)
            safe_target = escape_html(target_display)
            safe_reason = escape_html(history.reason or "Без причины")

            icon = "📈" if history.points > 0 else "📉" if history.points < 0 else "⚙️"

            lines.append(
                f"{icon} <b>{safe_admin}</b> → <b>{safe_target}</b>: "
                f"<code>{history.points:+}</code> очков\n"
                f"<i>{safe_reason}</i> ({history.timestamp.strftime('%d.%m %H:%M')})"
            )

        await message.reply("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        logger.error(f"[HISTORY ERROR] {e}")
        await message.reply("❌ Ошибка при получении истории.")

# ========================================================
# БАНИРОВАНИЕ НА СОЗДАНИЕ СТРАН (/rpbancreate)
# ========================================================
@admin_router.message(Command("rpbancreate"), IsRPAdmin())
async def ban_country_create(message: Message, session: AsyncSession, command: CommandObject):
    try:
        target_user = None
        time_hours = None
        reason = "Без причины"
        
        # 1. Логика определения цели (Реплай vs Аргументы)
        if message.reply_to_message:
            # Если есть реплай, цель — автор сообщения
            target_user_id = message.reply_to_message.from_user.id
            result = await session.execute(select(User).where(User.user_id == target_user_id))
            target_user = result.scalar_one_or_none()
            
            # В реплае аргументы смещаются: /rpbancreate [время] [причина]
            args = command.args.split() if command.args else []
            if args:
                if args[0].isdigit():
                    time_hours = int(args[0])
                    reason = " ".join(args[1:]) if len(args) > 1 else reason
                else:
                    reason = " ".join(args)
        else:
            # Если реплая нет, ищем по аргументам: /rpbancreate <id/@user> [время] [причина]
            args = command.args.split() if command.args else []
            if len(args) < 1:
                await message.answer(
                    escape_html("❗ Формат: Реплай: /rpbancreate [время] [причина] | Text: /rpbancreate <user_id/@user> [время] [причина]"),
                    parse_mode="HTML"
                )
                return

            target_str = args[0]
            if target_str.isdigit():
                result = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                result = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            target_user = result.scalar_one_or_none()

            if len(args) > 1:
                if args[1].isdigit():
                    time_hours = int(args[1])
                    reason = " ".join(args[2:]) if len(args) > 2 else reason
                else:
                    reason = " ".join(args[1:])

        if not target_user:
            await message.answer("❌ Пользователь не найден в базе данных.")
            return

        # 2. Создание наказания
        expires_at = None
        if time_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=time_hours)

        punishment = Punishment(
            user_id=target_user.user_id,
            admin_id=message.from_user.id,
            action_type="COUNTRY_CREATION_BAN",
            reason=reason,
            expires_at=expires_at,
            is_active=True
        )
        session.add(punishment)

        # 3. Красивый ответ
        safe_name = escape_html(target_user.userfullname or f"@{target_user.username or 'без_ника'}")
        await message.reply(
            f"🔨 <b>Глобальный бан на создание стран</b>\n\n"
            f"👤 Цель: {safe_name}\n"
            f"🆔 ID: <code>{target_user.user_id}</code>\n"
            f"⏳ Срок: <b>{'Перманентно' if not time_hours else f'{time_hours} ч.'}</b>\n"
            f"📝 Причина: <i>{escape_html(reason)}</i>",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"[BAN COUNTRY CREATE ERROR] {e}")
        await message.reply("❌ Произошла ошибка при обработке команды.")

# ========================================================
# СНЯТИЕ БАНА НА СОЗДАНИЕ СТРАН (/rpunban)
# ========================================================
@admin_router.message(Command("rpunban"), IsRPAdmin())
async def unban_country_create(
    message: Message,
    session: AsyncSession,
    command: CommandObject
):
    try:
        target_user: User | None = None

        # ----------------------------------------
        # Определяем цель (reply или аргументы)
        # ----------------------------------------
        if message.reply_to_message:
            target_user_id = message.reply_to_message.from_user.id

            result = await session.execute(
                select(User).where(User.user_id == target_user_id)
            )
            target_user = result.scalar_one_or_none()

        else:
            args = command.args.split() if command.args else []
            if not args:
                await message.answer(
                    "❗ Формат: реплай на пользователя или /rpunban <user_id | @username>"
                )
                return

            target = args[0]

            if target.isdigit():
                stmt = select(User).where(User.user_id == int(target))
            else:
                username = target.lstrip("@")
                stmt = select(User).where(
                    func.lower(User.username) == username.lower()
                )

            result = await session.execute(stmt)
            target_user = result.scalar_one_or_none()

        if not target_user:
            await message.answer("❌ Пользователь не найден.")
            return

        # ----------------------------------------
        # Снимаем ТОЛЬКО ОДИН активный бан (последний)
        # ----------------------------------------
        subquery = (
            select(Punishment.id)
            .where(
                Punishment.user_id == target_user.user_id,
                Punishment.action_type == "COUNTRY_CREATION_BAN",
                Punishment.is_active.is_(True),
            )
            .order_by(desc(Punishment.created_at))
            .limit(1)
            .scalar_subquery()
        )

        result = await session.execute(
            update(Punishment)
            .where(Punishment.id == subquery)
            .values(
                is_active=False,
                updated_at=func.now(),  # если поля нет — можешь убрать
            )
        )

        if result.rowcount == 0:
            await message.reply("❌ Активный бан на создание стран не найден.")
            return

        safe_name = escape_html(
            target_user.userfullname
            or f"@{target_user.username}"
            or "Без имени"
        )

        await message.reply(
            f"✅ <b>Бан снят!</b>\n"
            f"👤 Пользователь: {safe_name}\n"
            f"🆔 ID: <code>{target_user.user_id}</code>\n"
            f"Теперь может создавать страны.",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.exception("[RPUNBAN ERROR]")
        await message.reply("❌ Произошла ошибка при снятии бана.")



# ========================================================
# СПИСОК АКТИВНЫХ НАКАЗАНИЙ (/punishments)
# ========================================================
@admin_router.message(Command("punishments"), IsRPAdmin())
async def list_punishments(
    message: Message,
    session: AsyncSession
):
    try:
        stmt = (
            select(
                Punishment.user_id,
                Punishment.action_type,
                Punishment.reason,
                Punishment.created_at,
                User.userfullname,
                User.username,
            )
            .join(User, User.user_id == Punishment.user_id)
            .where(Punishment.is_active.is_(True))
            .order_by(desc(Punishment.created_at))
            .limit(10)
        )

        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            await message.reply("📭 Активных наказаний нет.")
            return

        lines = ["<b>📜 Активные наказания:</b>\n"]

        for user_id, action, reason, created_at, fullname, username in rows:
            safe_name = escape_html(fullname or username or "NoName")
            safe_reason = escape_html(reason or "Без причины")

            lines.append(
                f"• {safe_name} (ID: <code>{user_id}</code>) — <b>{action}</b>\n"
                f"  <i>{safe_reason}</i> ({created_at:%d.%m})"
            )

        await message.reply("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        logger.exception("[LIST PUNISHMENTS ERROR]")
        await message.reply("❌ Ошибка при получении списка наказаний.")

# ========================================================
# СБРОС КУЛДАУНА НА СОЗДАНИЕ СТРАН (/resetcd)
# ========================================================
@admin_router.message(Command("resetcd"), IsRPAdmin())
async def reset_country_cooldown(message: Message, session: AsyncSession, command: CommandObject):
    try:
        target_user = None
        
        # 1. Логика определения цели (Реплай vs Аргументы)
        if message.reply_to_message:
            target_user_id = message.reply_to_message.from_user.id
            result = await session.execute(select(User).where(User.user_id == target_user_id))
            target_user = result.scalar_one_or_none()
        else:
            args = command.args.split() if command.args else []
            if len(args) < 1:
                await message.answer(
                    "❗ Формат: Реплай на сообщение или <code>/resetcd &lt;user_id/@user&gt;</code>",
                    parse_mode="HTML"
                )
                return

            target_str = args[0]
            if target_str.isdigit():
                result = await session.execute(select(User).where(User.user_id == int(target_str)))
            else:
                username = target_str.lstrip("@")
                result = await session.execute(select(User).where(func.lower(User.username) == username.lower()))
            target_user = result.scalar_one_or_none()

        if not target_user:
            await message.answer("❌ Пользователь не найден в базе данных.")
            return

        # 2. Сброс кулдауна (очищаем дату последнего создания)
        target_user.last_country_creation = None

        # 3. Ответ
        safe_name = escape_html(target_user.userfullname or f"@{target_user.username or 'unknown'}")
        await message.reply(
            f"⚡️ <b>Кулдаун сброшен</b>\n\n"
            f"👤 Пользователь: {safe_name}\n"
            f"🆔 ID: <code>{target_user.user_id}</code>\n"
            f"✅ Теперь он может снова основать страну!",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"[RESET CD ERROR] {e}")
        await message.reply("❌ Ошибка при сбросе кулдауна.")