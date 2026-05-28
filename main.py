import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.router import router
from config import settings
from database import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_finished_matches(bot: Bot) -> None:
    db = await get_db()
    matches = await db.get_matches_to_notify_finished()
    for match in matches:
        await bot.send_message(
            match["hoster_id"],
            f"Матч #{match['id']} завершён.\n\n"
            f"Карта: {match['map_name']}\n"
            f"Время: {match['time_minutes']} мин.\n"
            f"Лимит: {match['player_limit']}\n\n"
            "Отправьте скриншот результата матча в этот чат.",
        )
        await db.mark_match_end_notified(match["id"])


async def check_screenshot_timeouts(bot: Bot) -> None:
    db = await get_db()
    expired = await db.get_expired_screenshot_matches()
    for match in expired:
        hoster = await db.get_user(match["hoster_id"])
        username = f"@{hoster['username']}" if hoster and hoster.get("username") else "хостер"
        reason = (
            "отказался присылать настоящий скриншот"
            if match.get("screenshot_rejected")
            else "не прислал скриншот результата"
        )
        await bot.send_message(
            settings.admin_group_id,
            f"Хостер матча #{match['id']} ({username}) {reason}.",
        )
        await db.mark_match_expired(match["id"])


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните.")

    try:
        settings.postgres_dsn()
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    proxy_url = settings.bot_proxy_url.replace("socks5h://", "socks5://", 1)
    session = AiohttpSession(proxy=proxy_url) if proxy_url else None
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await get_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_finished_matches, "interval", minutes=1, args=[bot])
    scheduler.add_job(check_screenshot_timeouts, "interval", hours=1, args=[bot])
    scheduler.start()

    logger.info("Бот запущен (PostgreSQL)")
    try:
        await dp.start_polling(bot)
    finally:
        db = await get_db()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
