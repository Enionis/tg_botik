from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    admin_menu_keyboard,
    channel_link_keyboard,
    hoster_menu_keyboard,
    open_lobby_keyboard,
)
from bot.states import RegistrationStates
from database import get_db
from utils.channel import is_subscribed

router = Router()

@router.message(RegistrationStates.waiting_game_id)
async def process_game_id(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Введите корректный игровой ID (только цифры).")
        return

    db = await get_db()
    await db.set_user_game_id(message.from_user.id, message.text.strip())
    await message.answer("Введите свой игровой никнейм.")
    await state.set_state(RegistrationStates.waiting_nickname)


@router.message(RegistrationStates.waiting_nickname)
async def process_nickname(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Введите корректный никнейм (минимум 2 символа).")
        return

    db = await get_db()
    await db.complete_registration(message.from_user.id, message.text.strip())
    await state.clear()

    await message.answer(
        "Поздравляю! Регистрация завершена. Теперь вы можете играть DM в нашем канале.",
        reply_markup=channel_link_keyboard(),
    )

    if await db.is_admin(message.from_user.id):
        await message.answer(
            "Приветствую! Чем могу помочь?",
            reply_markup=admin_menu_keyboard(),
        )
    elif await db.can_create_match(message.from_user.id, message.from_user.username):
        await message.answer(
            "Хотите создать новый матч?",
            reply_markup=hoster_menu_keyboard(),
        )

@router.callback_query(F.data.startswith("join_match:"))
async def join_match_callback(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user:
        return

    db = await get_db()
    db_user = await db.get_user(user.id)

    if not db_user or not db_user.get("is_registered"):
        await callback.answer(
            "Для присоединения к матчу необходима регистрация. Напишите боту /start",
            show_alert=True,
        )
        return

    subscribed = await is_subscribed(callback.bot, user.id)
    if not subscribed:
        await callback.answer(
            "Для присоединения к матчу необходима подписка на канал.",
            show_alert=True,
        )
        return

    match_id = int(callback.data.split(":")[1])
    match = await db.get_match(match_id)
    if not match:
        await callback.answer("Матч не найден.", show_alert=True)
        return

    await callback.bot.send_message(
        user.id,
        "Проверка пройдена. Нажмите кнопку ниже, чтобы открыть лобби.",
        reply_markup=open_lobby_keyboard(match["lobby_url"]),
    )
    await callback.answer("Ссылка отправлена в личные сообщения.")
