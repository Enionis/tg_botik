from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bot.keyboards import (
    admin_menu_keyboard,
    channel_link_keyboard,
    hoster_menu_keyboard,
    subscribe_keyboard,
)
from bot.states import RegistrationStates
from database import get_db
from utils.channel import is_subscribed

router = Router()

@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    chat = message.chat
    await message.answer(
        "ID этого чата:\n"
        f"<code>{chat.id}</code>\n\n"
        f"Тип чата: <code>{chat.type}</code>\n\n"
        "Если это группа логов, вставьте этот ID в ADMIN_GROUP_ID."
    )

@router.message(F.forward_origin)
async def forwarded_chat_id(message: Message) -> None:
    origin = message.forward_origin
    chat = getattr(origin, "chat", None)
    if not chat:
        await message.answer(
            "Это пересланное сообщение, но Telegram не передал ID исходного чата.\n"
            "Попробуйте переслать обычный пост из канала."
        )
        return

    title = getattr(chat, "title", None) or getattr(chat, "username", None) or "без названия"
    await message.answer(
        "ID исходного чата/канала:\n"
        f"<code>{chat.id}</code>\n\n"
        f"Название: {title}\n"
        f"Тип: <code>{chat.type}</code>\n\n"
        "Если это канал с матчами, вставьте этот ID в CHANNEL_ID."
    )


async def _send_registration_prompt(message: Message) -> None:
    await message.answer(
        "Введите свой игровой ID в Standoff 2.",
    )
    await message.answer("Пример: 123456789")

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Обновляю меню.", reply_markup=ReplyKeyboardRemove())
    db = await get_db()
    user = message.from_user
    if not user:
        return

    await db.upsert_user_basic(
        user.id, user.username, user.first_name, user.last_name
    )
    await db.link_hoster_by_username(user.id, user.username)

    subscribed = await is_subscribed(message.bot, user.id)
    db_user = await db.get_user(user.id)

    if not subscribed:
        await message.answer(
            "Чтобы начать регистрацию, подпишитесь на канал.",
            reply_markup=subscribe_keyboard(),
        )
        return

    if db_user and db_user.get("is_registered"):
        if await db.is_admin(user.id):
            await message.answer(
                "Приветствую! Чем могу помочь?",
                reply_markup=admin_menu_keyboard(),
            )
            return
        if await db.can_create_match(user.id, user.username):
            await message.answer(
                "Приветствую! Хотите создать новый матч?",
                reply_markup=hoster_menu_keyboard(),
            )
            return
        await message.answer(
            "Вы уже зарегистрированы! Можете присоединяться к матчам в нашем канале.",
            reply_markup=channel_link_keyboard(),
        )
        return

    await _send_registration_prompt(message)
    await state.set_state(RegistrationStates.waiting_game_id)

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return

    subscribed = await is_subscribed(callback.bot, user.id)
    if not subscribed:
        await callback.answer("Подписка не найдена. Подпишитесь на канал.", show_alert=True)
        return

    db = await get_db()
    db_user = await db.get_user(user.id)

    await callback.answer("Подписка подтверждена!")

    if db_user and db_user.get("is_registered"):
        if await db.is_admin(user.id):
            await callback.message.answer(
                "Приветствую! Чем могу помочь?",
                reply_markup=admin_menu_keyboard(),
            )
        elif await db.can_create_match(user.id, user.username):
            await callback.message.answer(
                "Приветствую! Хотите создать новый матч?",
                reply_markup=hoster_menu_keyboard(),
            )
        else:
            await callback.message.answer(
                "Вы уже зарегистрированы!",
                reply_markup=channel_link_keyboard(),
            )
        return

    await callback.message.answer("Введите свой игровой ID в Standoff 2.")
    await state.set_state(RegistrationStates.waiting_game_id)
