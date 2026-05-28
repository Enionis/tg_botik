from aiogram import Router

from bot.handlers import admin, hoster, registration, screenshot, start

router = Router()
router.include_router(start.router)
router.include_router(registration.router)
router.include_router(hoster.router)
router.include_router(admin.router)
router.include_router(screenshot.router)
