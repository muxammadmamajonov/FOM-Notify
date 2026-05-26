import asyncio
import logging
from aiogram import Bot, Dispatcher
from .handlers.start import router as start_router
from .handlers.admin import router as admin_router
from .services import reporting, screenshot, scheduler as scheduler_service
from .config import TELEGRAM_BOT_TOKEN, RUN_ONCE, TARGET_URL

async def run_once_capture():
    images = await screenshot.capture_sections(TARGET_URL, "screenshots", "run-once")
    print("Screenshots saved to:")
    for image in images:
        print(" -", image.path)

async def main():
    logging.basicConfig(level=logging.INFO)
    reporting.sync_web_app_url_env()

    if RUN_ONCE:
        # run a single capture and exit (no bot required)
        await run_once_capture()
        return

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(admin_router)

    # start scheduler (it will call take_and_send with the bot)
    scheduler_service.start(bot)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler_service.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
