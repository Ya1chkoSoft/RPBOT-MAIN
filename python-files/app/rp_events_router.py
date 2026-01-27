from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.requests.rp_events import (
    create_rp_event,
    add_participant,
    leave_rp_event,
    kick_participant,
    get_event_participants_with_users,
    end_rp_event,
    get_chat_rp_events,
    clear_rp_events
)
from app.database.requests.admins import get_current_user_admin_level
from app.database.models import RPEvent, User
from app.keyboard import event_admin_keyboard, event_join_keyboard, event_participant_keyboard
from app.database.middleware import SessionMiddleware
from app.utils.html_helpers import hcode

router = Router()
router.message.middleware(SessionMiddleware())
router.callback_query.middleware(SessionMiddleware())

@router.message(Command("create_rp_event"))
async def cmd_create_rp_event(message: Message, session: AsyncSession):
    """Хендлер для создания РП-ивента"""
    # Проверяем, что пользователь - администратор
    admin_level = await get_current_user_admin_level(session, message.from_user.id)
    if not admin_level or admin_level < 1:
        return await message.answer("Только администраторы могут создавать ивенты!")

    # Разбираем команду: /create_rp_event "название" [описание] [ревард]
    # Убираем команду и разбираем остаток
    command_text = message.text[len("/create_rp_event "):].strip()
    if not command_text:
        return await message.answer(f"Используйте: /create_rp_event {hcode('название')} [описание], по желанию рп очки [10]")

    # Ищем последнее число в тексте (это будут reward points)
    reward_points = 10
    last_space_pos = -1
    
    # Ищем последнее число в тексте
    for i in range(len(command_text) - 1, -1, -1):
        if command_text[i] == ' ':
            last_space_pos = i
            try:
                rppoints = int(command_text[i+1:])
                if rppoints > 0:
                    reward_points = rppoints
                    command_text = command_text[:i].strip()
                    break
            except ValueError:
                continue

    # Теперь разбираем название и описание
    # Если название в кавычках, берем его целиком
    if command_text.startswith('"') and command_text.count('"') >= 2:
        # Название в кавычках
        end_quote = command_text.find('"', 1)
        title = command_text[1:end_quote]
        description = command_text[end_quote+1:].strip()
        if description == '"':
            description = None
    else:
        # Название - первое слово
        first_space = command_text.find(' ')
        if first_space == -1:
            title = command_text
            description = None
        else:
            title = command_text[:first_space]
            description = command_text[first_space+1:].strip()
            if not description:
                description = None

    success, text, event_id = await create_rp_event(
        session=session,
        admin_id=message.from_user.id,
        chat_id=message.chat.id,
        title=title,
        description=description,
        reward_points=reward_points
    )

    if success:
        event_info = f"🎉 <b>Новый RP-ивент создан!</b>\n\n"
        event_info += f"📜 <b>Название:</b> {title}\n"
        if description:
            event_info += f"📝 <b>Описание:</b> {description}\n"
        event_info += f"🏆 <b>Награда:</b> {reward_points} RP-очков\n"
        event_info += f"🆔 <b>ID ивента:</b> {event_id}\n"
        
        # Отправляем сообщение и закрепляем его
        sent_message = await message.answer(
            event_info,
            parse_mode="HTML",
            reply_markup=event_admin_keyboard(event_id)
        )
        
        # Пробуем закрепить сообщение в чате
        try:
            await message.bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=sent_message.message_id,
                disable_notification=True
            )
        except Exception as e:
            # Если не получилось закрепить (например, нет прав), просто игнорируем
            print(f"Не удалось закрепить сообщение: {e}")
    else:
        await message.answer(text)

@router.callback_query(F.data.startswith("join_rp_"))
async def cb_join_rp_event(query: CallbackQuery, session: AsyncSession):
    """Хендлер для присоединения к РП-ивенту"""
    event_id = int(query.data.split("_")[-1])

    success, text = await add_participant(
        session=session,
        event_id=event_id,
        user_id=query.from_user.id
    )

    await query.answer(text, show_alert=True)
    if success:
        await query.message.answer(
            f"👥 {query.from_user.full_name} присоединился к ивенту!",
            reply_markup=event_participant_keyboard(event_id)
        )

@router.callback_query(F.data.startswith("list_participants_"))
async def cb_list_participants(query: CallbackQuery, session: AsyncSession):
    """Хендлер для просмотра участников"""
    event_id = int(query.data.split("_")[-1])

    participants = await get_event_participants_with_users(session, event_id)

    if not participants:
        await query.answer("Участников пока нет", show_alert=True)
        return

    response = "👥 Участники РП-ивента:\n\n"
    for idx, (participant, user) in enumerate(participants, start=1):
        response += f"{idx}. {user.userfullname} (@{user.username})\n"

    await query.message.answer(
        response,
        reply_markup=event_participant_keyboard(event_id)
    )


@router.callback_query(F.data.startswith("leave_rp_"))
async def cb_leave_rp_event(query: CallbackQuery, session: AsyncSession):
    """Хендлер для выхода из РП-ивента"""
    event_id = int(query.data.split("_")[-1])

    success, text = await leave_rp_event(
        session=session,
        event_id=event_id,
        user_id=query.from_user.id
    )

    await query.answer(text, show_alert=True)
    if success:
        await query.message.answer(f"🚪 {query.from_user.full_name} покинул ивент!")


@router.message(Command("kick_rp"))
async def cmd_kick_rp_participants(message: Message, session: AsyncSession):
    """Хендлер для кика участников по команде /kick_rp <event_id> <user_ids>"""
    # Проверяем права администратора
    admin_level = await get_current_user_admin_level(session, message.from_user.id)
    if not admin_level or admin_level < 1:
        return await message.answer("Только администраторы могут кикать участников!")

    # Парсим команду: /kick_rp <event_id> <user_ids>
    parts = message.text.split()
    if len(parts) < 3:
        return await message.answer("Используйте: /kick_rp <ID_ивента> <номера_участников>")

    try:
        event_id = int(parts[1])
    except ValueError:
        return await message.answer("Неверный ID ивента!")

    # Получаем список участников
    participants = await get_event_participants_with_users(session, event_id)
    if not participants:
        return await message.answer("В этом ивенте нет участников!")

    # Парсим номера участников
    user_indices = []
    for part in parts[2:]:
        try:
            idx = int(part)
            if 1 <= idx <= len(participants):
                user_indices.append(idx - 1)  # Конвертируем в индекс (0-based)
        except ValueError:
            continue

    if not user_indices:
        return await message.answer("Неверные номера участников!")

    # Кикаем участников
    kicked_count = 0
    for idx in user_indices:
        participant, user = participants[idx]
        success, _ = await kick_participant(
            session=session,
            event_id=event_id,
            user_id=user.user_id,
            admin_id=message.from_user.id
        )
        if success:
            kicked_count += 1

    await message.answer(f"🦵 Кикнуто {kicked_count} участников из ивента!")

@router.callback_query(F.data.startswith("end_rp_"))
async def cb_end_rp_event(query: CallbackQuery, session: AsyncSession):
    """Хендлер для завершения РП-ивента"""
    event_id = int(query.data.split("_")[-1])

    success, text = await end_rp_event(
        session=session,
        event_id=event_id,
        admin_id=query.from_user.id
    )

    await query.answer(text, show_alert=True)
    if success:
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.answer("🎉 Ивент завершен! Очки начислены всем участникам!")


@router.message(Command("rp_history"))
async def cmd_rp_history(message: Message, session: AsyncSession):
    """Хендлер для просмотра истории RP-ивентов в чате"""
    chat_id = message.chat.id
    events = await get_chat_rp_events(session, chat_id)
    
    if not events:
        return await message.answer("В этом чате ещё не было RP-ивентов.")
    
    response = "📜 <b>История RP-ивентов в чате:</b>\n\n"
    for event in events:
        status_emoji = "🟢" if event.status == 'active' else "✅"
        response += (
            f"{status_emoji} <b>{event.title}</b>\n"
            f"   📝 {event.description or 'Без описания'}\n"
            f"   🆔 ID: {event.event_id}\n"
            f"   📅 Дата: {event.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"   🏆 Статус: {event.status}\n\n"
        )
    
    await message.answer(response, parse_mode="HTML")


@router.message(Command("clear_rp_events"))
async def cmd_clear_rp_events(message: Message, session: AsyncSession):
    """Хендлер для очистки всех RP-ивентов и участников"""
    success, text = await clear_rp_events(session, message.from_user.id)
    await message.answer(text)



