from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import admin_menu_keyboard, hoster_menu_keyboard, match_confirm_keyboard
from bot.states import MatchCreationStates
from config import settings
from database import get_db
from utils.validators import parse_match_info, validate_lobby_url, validate_match_info

router = Router()


def _format_match_preview(data: dict) -> str:
    return (
        "Информация о матче:\n\n"
        f"🗺 Карта: {data['map_name']}\n"
        f"⏱ Время: {data['time_minutes']} мин.\n"
        f"👥 Лимит игроков: {data['player_limit']}\n"
        f"🔗 Ссылка: {data['lobby_url']}"
    )


def _format_channel_post(match_id: int, data: dict, hoster_username: str | None) -> str:
    username = f"@{hoster_username}" if hoster_username else "хостер"
    return (
        f"🎮 DM Матч #{match_id}\n\n"
        f"🗺 Карта: {data['map_name']}\n"
        f"⏱ Время: {data['time_minutes']} мин.\n"
        f"👥 Лимит игроков: {data['player_limit']}\n"
        f"👤 Создал: {username}\n\n"
        "Нажмите «Присоединиться», чтобы войти в лобби!"
    )

async def start_match_creation(message: Message, state: FSMContext) -> None:
    await state.set_state(MatchCreationStates.waiting_lobby_url)
    await message.answer("Отправьте ссылку на матч ДМ.")


@router.callback_query(F.data == "match:create")
async def create_match_button(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.can_create_match(callback.from_user.id, callback.from_user.username):
        await callback.answer("У вас нет доступа к созданию матчей.", show_alert=True)
        return
    if callback.message:
        await start_match_creation(callback.message, state)
    await callback.answer()

@router.message(MatchCreationStates.waiting_lobby_url)
async def process_lobby_url(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Отправьте текстовую ссылку на лобби.")
        return

    lobby_url = validate_lobby_url(message.text)
    if not lobby_url:
        await message.answer(
            "Ссылка не соответствует стандарту.\n"
            "Ссылка должна содержать «link.standoff2.com».\n\n"
            "Пример:\n"
            "https://link.standoff2.com/ru/lobby/join/..."
        )
        return

    await state.update_data(lobby_url=lobby_url)
    await state.set_state(MatchCreationStates.waiting_match_info)
    await message.answer(
        "Напишите информацию о матче ДМ через запятую по порядку в примере.\n"
        "Карта, время в минутах, лимит игроков в лобби.\n\n"
        "Пример: Rust, 10, 20"
    )

@router.message(MatchCreationStates.waiting_match_info)
async def process_match_info(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите данные в формате: Карта, время, лимит игроков.")
        return

    parsed = parse_match_info(message.text)
    if not parsed:
        await message.answer(
            "Вы ввели значения неправильно! Попробуйте ещё раз, следуя примеру.\n\n"
            "Пример: Rust, 10, 20"
        )
        return

    map_name, time_minutes, player_limit = parsed

    for m in settings.valid_maps:
        if m.lower() == map_name.lower():
            map_name = m
            break

    error = validate_match_info(map_name, time_minutes, player_limit)
    if error:
        await message.answer(
            f"{error}\n\nПопробуйте ещё раз.\nПример: Rust, 10, 20"
        )
        return

    data = await state.get_data()
    match_data = {
        "lobby_url": data["lobby_url"],
        "map_name": map_name,
        "time_minutes": time_minutes,
        "player_limit": player_limit,
    }
    await state.update_data(**match_data)
    await state.set_state(MatchCreationStates.waiting_confirmation)

    await message.answer("Подтвердите правильность данных.")
    await message.answer(
        _format_match_preview(match_data),
        reply_markup=match_confirm_keyboard(),
    )

@router.callback_query(F.data == "match_restart")
async def match_restart(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await start_match_creation(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "match_confirm")
async def match_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return

    db = await get_db()
    data = await state.get_data()

    match_id = await db.create_match(
        hoster_id=user.id,
        lobby_url=data["lobby_url"],
        map_name=data["map_name"],
        time_minutes=data["time_minutes"],
        player_limit=data["player_limit"],
    )

    from bot.keyboards import join_match_keyboard

    db_user = await db.get_user(user.id)
    post_text = _format_channel_post(match_id, data, db_user.get("username") if db_user else None)

    channel_msg = await callback.bot.send_message(
        settings.channel_id,
        post_text,
        reply_markup=join_match_keyboard(match_id),
    )
    await db.set_match_channel_message(match_id, channel_msg.message_id)

    await state.clear()
    await callback.message.answer(
        "Отлично! Вы создали матч, отправили его в наш Telegram канал."
    )

    if await db.is_admin(user.id):
        await callback.message.answer(
            "Приветствую! Чем могу помочь?",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await callback.message.answer(
            "Хотите создать ещё один матч?",
            reply_markup=hoster_menu_keyboard(),
        )
    await callback.answer()
