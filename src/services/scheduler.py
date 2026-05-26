from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from . import apps_script, reporting, screenshot
from ..config import GROUP_CHAT_ID, SCREENSHOTS_DIR, TARGET_URL, TIMEZONE
import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

scheduler = AsyncIOScheduler(timezone=TIMEZONE)

async def update_web_app_before_send():
    result = await apps_script.update_web_app()
    if result.get("ok"):
        if result.get("skipped"):
            print("Apps Script update skipped:", result.get("message"))
        else:
            print("Apps Script update success:", result.get("message"))
        return

    print("Apps Script update failed:", result.get("message"))
    for step in result.get("steps", []):
        if not step.get("ok"):
            print(f"  step failed: {step.get('cmd')}")
            if step.get("stderr"):
                print(f"  stderr: {step.get('stderr')}")

async def take_and_send(bot):
    now = datetime.datetime.now(TIMEZONE)
    # caption shows previous day's date, but the dashboard screenshot + button URL
    # use today (real-time current state).
    caption_date = now - datetime.timedelta(days=1)

    if not TARGET_URL:
        print("TARGET_URL is not configured.")
        return

    today_str = now.strftime("%Y-%m-%d")
    parsed = urlparse(TARGET_URL)
    q = dict(parse_qsl(parsed.query))
    q.update({"date": today_str})
    parsed = parsed._replace(query=urlencode(q))
    url_for_capture = urlunparse(parsed)

    stamp = now.strftime("%Y%m%d-%H%M%S")
    base_name = f"screenshot-{stamp}"
    try:
        images = await screenshot.capture_sections(url_for_capture, SCREENSHOTS_DIR, base_name)
    except Exception as e:
        print("Screenshot capture failed:", e)
        return

    if not GROUP_CHAT_ID:
        print("GROUP_CHAT_ID is not configured.")
        return

    result = await reporting.send_report(
        bot, GROUP_CHAT_ID, images, now=caption_date, link_date=now
    )
    for failure in result["failed"]:
        print(
            f"Failed to send {failure['title']} to {failure['chat_id']}: {failure['error']}"
        )

def start(bot):
    # update Apps Script sources and deployment at 09:30 Asia/Tashkent
    update_trigger = CronTrigger(hour=9, minute=30, timezone=TIMEZONE)
    # schedule daily send at 10:00 Asia/Tashkent
    send_trigger_10 = CronTrigger(hour=10, minute=0, timezone=TIMEZONE)
    # Grace window: if the bot restarted close to the trigger time, still fire.
    # coalesce collapses multiple missed runs into one.
    scheduler.add_job(
        update_web_app_before_send,
        update_trigger,
        id="daily_webapp_update",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.add_job(
        take_and_send,
        send_trigger_10,
        kwargs={"bot": bot},
        id="daily_screenshot_10",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    scheduler.start()

def shutdown():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
