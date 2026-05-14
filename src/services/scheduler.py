from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path
from . import screenshot, subscriptions
from ..config import TARGET_URL, DB_PATH, TIMEZONE
import datetime

from apscheduler.jobstores.base import JobLookupError

scheduler = AsyncIOScheduler(timezone=TIMEZONE)

async def take_and_send(bot):
    stamp = datetime.datetime.now().astimezone(TIMEZONE).strftime("%Y%m%d-%H%M%S")
    out = Path("screenshots") / f"screenshot-{stamp}.png"
    try:
        await screenshot.capture(TARGET_URL, str(out))
    except Exception as e:
        print("Screenshot capture failed:", e)
        return

    subs = await subscriptions.list_subscribers(DB_PATH)
    if not subs:
        print("No subscribers to send to.")
        return

    with open(out, "rb") as f:
        data = f.read()
        for chat_id in subs:
            try:
                await bot.send_photo(chat_id, data)
            except Exception as exc:
                print(f"Failed to send to {chat_id}: {exc}")

def start(bot):
    # schedule daily job at 10:00 Asia/Tashkent
    trigger = CronTrigger(hour=10, minute=0, timezone=TIMEZONE)
    try:
        scheduler.add_job(take_and_send, trigger, kwargs={"bot": bot}, id="daily_screenshot")
    except Exception:
        # job may already exist
        try:
            scheduler.remove_job("daily_screenshot")
            scheduler.add_job(take_and_send, trigger, kwargs={"bot": bot}, id="daily_screenshot")
        except JobLookupError:
            pass

    scheduler.start()

def shutdown():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
