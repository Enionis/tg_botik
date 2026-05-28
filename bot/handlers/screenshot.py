from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import log_match_keyboard
from bot.states import AdminStates
from config import settings
from database import get_db
from utils.validators import parse_player_stats

router = Router()

def _format_log_message(match: dict, hoster: dict | None, registered: bool) -> str:
    username = f"@{hoster['username']}" if hoster and hoster.get("username") else "хостер"
    status = "✅" if registered else "❌"
    return (
        f"Матч #{match['id']}\n"
        f"Создан: {username}\n"
        f"Карта лобби: {match['map_name']}\n"
        f"Время в минутах: {match['time_minutes']}\n"
        f"Ограничение игроков в лобби: {match['player_limit']}\n"
        f"Зарегистрировано: {status}"
    )


@router.message(F.photo)
async def hoster_screenshot(message: Message) -> None:
    db = await get_db()
    user_id = message.from_user.id

    if not await db.can_create_match(user_id, message.from_user.username):
        return

    match = await db.get_pending_screenshot_match(user_id)
    if not match:
        await message.answer(
            "У вас нет активных матчей для отправки скриншота.\n"
            "Сначала создайте матч."
        )
        return

    photo = message.photo[-1]
    if match.get("screenshot_rejected"):
        await db.resubmit_screenshot(match["id"], photo.file_id)
    else:
        await db.set_match_screenshot(match["id"], photo.file_id)

    hoster = await db.get_user(user_id)
    log_text = _format_log_message(match, hoster, registered=False)

    await message.bot.send_photo(
        settings.admin_group_id,
        photo.file_id,
        caption=log_text,
        reply_markup=log_match_keyboard(match["id"]),
    )
    await message.answer(
        f"Скриншот матча #{match['id']} отправлен на проверку администраторам."
    )

@router.callback_query(F.data.startswith("log_register:"))
async def log_register_start(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    match_id = int(callback.data.split(":")[1])
    match = await db.get_match(match_id)
    if not match:
        await callback.answer("Матч не найден.", show_alert=True)
        return

    await state.set_state(AdminStates.register_match_stats)
    await state.update_data(register_match_id=match_id)

    if callback.message:
        await callback.message.answer(
            "Напишите никнейм, kills, deaths, assists.\n"
            "Строго по порядку, всех игроков через Enter!\n\n"
            "Пример:\n"
            "Player1, 15, 8, 3\n"
            "Player2, 10, 12, 5"
        )
    await callback.answer()

@router.message(AdminStates.register_match_stats)
async def log_register_stats(message: Message, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer("Отправьте статистику игроков текстом.")
        return

    stats = parse_player_stats(message.text)
    if not stats:
        await message.answer(
            "Неверный формат. Каждая строка: никнейм, kills, deaths, assists"
        )
        return

    data = await state.get_data()
    match_id = data.get("register_match_id")
    if not match_id:
        await state.clear()
        return

    not_found = []
    enriched_stats = []
    for stat in stats:
        user = await db.find_user_by_nickname(stat["nickname"])
        if not user:
            not_found.append(stat["nickname"])
        enriched_stats.append({**stat, "user_id": user["telegram_id"] if user else None})

    if not_found:
        await message.bot.send_message(
            settings.admin_group_id,
            "⚠️ Игроки не найдены в базе: "
            f"{', '.join(not_found)}\n\n"
            "Матч не зарегистрирован. Исправьте никнеймы и отправьте статистику заново.",
        )
        await message.answer(
            "Матч не зарегистрирован: есть игроки, которых нет среди зарегистрированных пользователей.\n"
            "Исправьте никнеймы и отправьте статистику заново."
        )
        return

    await db.register_match(match_id, enriched_stats)
    await state.clear()

    match = await db.get_match(match_id)
    hoster = await db.get_user(match["hoster_id"]) if match else None
    if match:
        await message.bot.send_message(
            settings.admin_group_id,
            _format_log_message(match, hoster, registered=True),
        )

    await message.answer("Матч был зарегистрирован!")

@router.callback_query(F.data.startswith("log_reject:"))
async def log_reject_screenshot(callback: CallbackQuery) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    match_id = int(callback.data.split(":")[1])
    match = await db.get_match(match_id)
    if not match:
        await callback.answer("Матч не найден.", show_alert=True)
        return

    await db.reject_screenshot(match_id)

    hoster = await db.get_user(match["hoster_id"])
    username = f"@{hoster['username']}" if hoster and hoster.get("username") else "хостер"

    if hoster:
        await callback.bot.send_message(
            match["hoster_id"],
            f"⚠️ Скриншот матча #{match_id} не принят.\n\n"
            f"Карта: {match['map_name']}\n"
            f"Время: {match['time_minutes']} мин.\n"
            f"Лимит: {match['player_limit']}\n\n"
            "Пожалуйста, отправьте настоящий скриншот матча в ответ на это сообщение.",
        )

    if callback.message:
        await callback.message.answer(
            f"Отправил сообщение хостеру {username}, что скриншот не верный. "
            "Ждём ответа. Напишу если ничего не поменяется!"
        )
    await callback.answer()
