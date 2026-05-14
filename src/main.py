import asyncio
import logging
from aiogram import Bot, Dispatcher
from .handlers.start import router as start_router
from .handlers.admin import router as admin_router
from .services import subscriptions, scheduler as scheduler_service
from .config import TELEGRAM_BOT_TOKEN, DB_PATH, RUN_ONCE, TARGET_URL, INITIAL_SUBSCRIBERS

async def run_once_capture():
    await subscriptions.init_db(DB_PATH)
    from .services.screenshot import capture
    out = "screenshots/run-once.png"
    await capture(TARGET_URL, out)
    print("Screenshot saved to", out)

async def main():
    logging.basicConfig(level=logging.INFO)

    # ensure DB
    await subscriptions.init_db(DB_PATH)

    # populate any initial subscribers from env
    if INITIAL_SUBSCRIBERS:
        for chat in INITIAL_SUBSCRIBERS:
            try:
                await subscriptions.add_subscriber(DB_PATH, chat)
            except Exception:
                pass

    if RUN_ONCE:
        # run a single capture and exit (no bot required)
        await run_once_capture()
        return

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment")

    bot = Bot(TELEGRAM_BOT_TOKEN)
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
