from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.hoster import start_match_creation
from bot.keyboards import (
    admin_menu_keyboard,
    confirm_cancel_inline,
    hosters_list_keyboard,
    roles_list_keyboard,
)
from bot.states import AdminStates
from database import get_db
from utils.validators import format_display_name, parse_hoster_info, parse_role_input

router = Router()

@router.callback_query(F.data == "admin:back")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    if callback.message:
        await callback.message.answer(
            "Приветствую! Чем могу помочь?",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer()

@router.callback_query(F.data == "admin:hosters")
async def list_hosters(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    hosters = await db.get_all_hosters()
    if not hosters:
        text = "Вот весь список хостеров:\n\nСписок пуст."
    else:
        lines = ["Вот весь список хостеров:"]
        for i, h in enumerate(hosters, 1):
            username = f"@{h['username']}" if h.get("username") else "нет username"
            lines.append(f"{i}. {h['nickname']}, {h['game_id']}, {username}")
        text = "\n".join(lines)

    if callback.message:
        await callback.message.answer(text, reply_markup=hosters_list_keyboard())
    await callback.answer()


@router.callback_query(F.data == "hosters:add")
async def add_hoster_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminStates.add_hoster)
    if callback.message:
        await callback.message.answer(
            "Напишите никнейм, айди, и @юзернейм нового хостера через запятую.\n"
            "Пример: ProPlayer, 123456789, @proplayer"
        )
    await callback.answer()

@router.message(AdminStates.add_hoster)
async def add_hoster_process(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите данные через запятую.")
        return

    parsed = parse_hoster_info(message.text)
    if not parsed:
        await message.answer(
            "Неверный формат. Пример: ProPlayer, 123456789, @proplayer"
        )
        return

    nickname, game_id, username = parsed
    db = await get_db()
    user = await db.find_user_by_username(username)

    if not user:
        await state.update_data(
            pending_hoster={
                "nickname": nickname,
                "game_id": game_id,
                "username": username.lstrip("@"),
                "telegram_id": None,
            }
        )
        await state.set_state(AdminStates.confirm_add_hoster)
        await message.answer(
            f"Пользователь {username} ещё не писал боту.\n"
            f"Проверьте информацию:\n"
            f"Никнейм: {nickname}\n"
            f"Айди: {game_id}\n"
            f"Username: {username}\n\n"
            "Подтвердите для добавления в базу хостеров.",
            reply_markup=confirm_cancel_inline("add_hoster"),
        )
        return

    await state.update_data(
        pending_hoster={
            "nickname": nickname,
            "game_id": game_id,
            "username": username.lstrip("@"),
            "telegram_id": user["telegram_id"],
        }
    )
    await state.set_state(AdminStates.confirm_add_hoster)
    await message.answer(
        f"Проверьте информацию пользователя.\n"
        f"Никнейм: {nickname}\n"
        f"Айди: {game_id}\n"
        f"Username: {username}\n\n"
        "Подтвердите для добавления в базу хостеров.",
        reply_markup=confirm_cancel_inline("add_hoster"),
    )

@router.callback_query(F.data == "add_hoster:confirm")
async def add_hoster_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    data = await state.get_data()
    hoster = data.get("pending_hoster")
    if not hoster:
        await callback.answer("Данные не найдены.", show_alert=True)
        return

    await db.add_hoster(
        telegram_id=hoster.get("telegram_id"),
        nickname=hoster["nickname"],
        game_id=hoster["game_id"],
        username=hoster["username"],
    )

    username = f"@{hoster['username']}"
    await state.clear()
    if callback.message:
        await callback.message.answer(
            f"{hoster['nickname']}, {hoster['game_id']}, {username} был добавлен в список хостеров!",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer()

@router.callback_query(F.data == "add_hoster:cancel")
async def add_hoster_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.answer(
            "Добавление отменено.",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer()

@router.callback_query(F.data == "hosters:remove")
async def remove_hoster_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminStates.remove_hoster)
    if callback.message:
        await callback.message.answer("Напишите @юзернейм хостера, которого хотите удалить.")
    await callback.answer()

@router.message(AdminStates.remove_hoster)
async def remove_hoster_process(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите @юзернейм хостера.")
        return

    db = await get_db()
    hoster = await db.remove_hoster_by_username(message.text.strip())

    if not hoster:
        await message.answer(
            "Такой хостер не найден. Проверьте юзернейм и попробуйте ещё раз!",
        )
        return

    username = f"@{hoster['username']}" if hoster.get("username") else "нет username"
    await state.update_data(pending_remove_hoster=hoster)
    await state.set_state(AdminStates.confirm_remove_hoster)
    await message.answer(
        f"Подтвердите, вы хотите удалить из списка хостеров "
        f"{hoster['nickname']}, {hoster['game_id']}, {username}?",
        reply_markup=confirm_cancel_inline("remove_hoster"),
    )

@router.callback_query(F.data == "remove_hoster:confirm")
async def remove_hoster_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    hoster = data.get("pending_remove_hoster")
    await state.clear()
    username = f"@{hoster['username']}" if hoster and hoster.get("username") else "хостер"
    if callback.message:
        await callback.message.answer(
            f"{username} был удален из списка хостеров.",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer()

@router.callback_query(F.data == "remove_hoster:cancel")
async def remove_hoster_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.remove_hoster)
    if callback.message:
        await callback.message.answer("Напишите @юзернейм хостера, которого хотите удалить.")
    await callback.answer()


@router.callback_query(F.data == "admin:metrics")
async def show_metrics(callback: CallbackQuery) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    players = await db.count_users()
    hosters = await db.count_hosters()
    total = await db.count_matches_total()
    monthly = await db.count_matches_month()

    if callback.message:
        await callback.message.answer(
            f"📊 Метрики:\n\n"
            f"Количество игроков: {players}\n"
            f"Количество хостеров: {hosters}\n"
            f"Сыгранных матчей (всего): {total}\n"
            f"Сыгранных матчей (за месяц): {monthly}"
        )
    await callback.answer()

@router.callback_query(F.data == "admin:roles")
async def list_roles(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    admins = await db.get_roles_by_type("admin")

    lines = [f"Администраторы ({len(admins)}):"]
    for a in admins:
        name = format_display_name(a)
        tag = f"@{a['username']}" if a.get("username") else f"id{a['telegram_id']}"
        lines.append(f"{name} | {tag}")

    await state.update_data(in_roles_menu=True)
    if callback.message:
        await callback.message.answer("\n".join(lines), reply_markup=roles_list_keyboard())
    await callback.answer()

@router.callback_query(F.data == "roles:add")
async def add_role_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    data = await state.get_data()
    if not data.get("in_roles_menu"):
        await callback.answer("Сначала откройте список админов.", show_alert=True)
        return
    current = await state.get_state()
    if current == AdminStates.add_hoster:
        await callback.answer()
        return
    await state.set_state(AdminStates.add_role)
    if callback.message:
        await callback.message.answer(
            "Напишите @usertag и роль пользователя для добавления администратора.\n"
            "Пример: @adamad, администратор"
        )
    await callback.answer()


@router.message(AdminStates.add_role)
async def add_role_process(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите данные в формате: @username, роль")
        return

    parsed = parse_role_input(message.text)
    if not parsed:
        await message.answer(
            "Вы неправильно написали роль! Напишите корректно: администратор."
        )
        return

    username, role = parsed
    db = await get_db()
    user = await db.find_user_by_username(username)

    if not user:
        await message.answer("Такой пользователь не найден! Попробуйте ещё раз.")
        return

    display_name = format_display_name(user)
    await db.add_role(user["telegram_id"], role, display_name)

    await state.clear()
    await message.answer(
        f"{username} стал администратором!",
        reply_markup=admin_menu_keyboard(),
    )

@router.callback_query(F.data == "roles:remove")
async def remove_role_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    data = await state.get_data()
    if not data.get("in_roles_menu"):
        await callback.answer("Сначала откройте список админов.", show_alert=True)
        return
    await state.set_state(AdminStates.remove_role)
    if callback.message:
        await callback.message.answer(
            "Напишите @usertag для удаления администратора.\n"
            "Пример: @adamad"
        )
    await callback.answer()


@router.message(AdminStates.remove_role)
async def remove_role_process(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите @usertag.")
        return

    username = message.text.strip()
    if not username.startswith("@"):
        username = f"@{username}"

    db = await get_db()
    user = await db.find_user_by_username(username)
    if not user:
        await message.answer("Такой пользователь не найден! Попробуйте ещё раз.")
        return

    removed = await db.remove_role(user["telegram_id"])
    if not removed:
        await message.answer("У этого пользователя нет роли администратора.")
        return

    await state.clear()
    await message.answer(
        f"{username} удален из администраторов!",
        reply_markup=admin_menu_keyboard(),
    )
