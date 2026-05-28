from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings

def subscribe_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Подписаться", url=settings.channel_url)
    )
    builder.row(
        InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")
    )
    return builder.as_markup()

def channel_link_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Перейти в канал с матчами", url=settings.channel_url
        )
    )
    return builder.as_markup()

def hoster_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Создать матч", callback_data="match:create"))
    return builder.as_markup()

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Создать матч", callback_data="match:create"))
    builder.row(InlineKeyboardButton(text="Список хостеров", callback_data="admin:hosters"))
    builder.row(InlineKeyboardButton(text="Посмотреть метрики", callback_data="admin:metrics"))
    builder.row(InlineKeyboardButton(text="Список админов", callback_data="admin:roles"))
    return builder.as_markup()

def match_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Подтвердить", callback_data="match_confirm"),
        InlineKeyboardButton(text="Начать заново", callback_data="match_restart"),
    )
    return builder.as_markup()

def hosters_list_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Добавить хостера", callback_data="hosters:add"))
    builder.row(InlineKeyboardButton(text="Удалить хостера", callback_data="hosters:remove"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back"))
    return builder.as_markup()

def confirm_cancel_inline(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Подтвердить", callback_data=f"{prefix}:confirm"),
        InlineKeyboardButton(text="Отменить", callback_data=f"{prefix}:cancel"),
    )
    return builder.as_markup()

def roles_list_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Добавить", callback_data="roles:add"),
        InlineKeyboardButton(text="Удалить", callback_data="roles:remove"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back"))
    return builder.as_markup()


def join_match_keyboard(match_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Присоединиться",
            callback_data=f"join_match:{match_id}",
        )
    )
    return builder.as_markup()

def open_lobby_keyboard(lobby_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Открыть лобби", url=lobby_url))
    return builder.as_markup()

def log_match_keyboard(match_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Зарегистрировать", callback_data=f"log_register:{match_id}"
        ),
        InlineKeyboardButton(
            text="Скриншот не верный", callback_data=f"log_reject:{match_id}"
        ),
    )
    return builder.as_markup()
