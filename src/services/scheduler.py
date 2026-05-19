from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path
from . import apps_script, reporting, screenshot
from ..config import GROUP_CHAT_ID, TARGET_URL, TIMEZONE
import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from apscheduler.jobstores.base import JobLookupError

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
    now = datetime.datetime.now().astimezone(TIMEZONE)
    # send data for previous day
    send_date = (now - datetime.timedelta(days=1)).astimezone(TIMEZONE)

    stamp = now.strftime("%Y%m%d-%H%M%S")
    base_name = f"screenshot-{stamp}"
    try:
        # append date to TARGET_URL as `date=YYYY-MM-DD` if TARGET_URL is set
        target = TARGET_URL or ""
        if not target:
            print("TARGET_URL is not configured.")
            return
        url_for_capture = target
        if target:
            parsed = urlparse(target)
            q = dict(parse_qsl(parsed.query))
            q.update({"date": send_date.strftime("%Y-%m-%d")})
            parsed = parsed._replace(query=urlencode(q))
            url_for_capture = urlunparse(parsed)

        images = await screenshot.capture_sections(url_for_capture, Path("screenshots"), base_name)
    except Exception as e:
        print("Screenshot capture failed:", e)
        return

    if not GROUP_CHAT_ID:
        print("GROUP_CHAT_ID is not configured.")
        return

    result = await reporting.send_report(bot, GROUP_CHAT_ID, images, now=send_date)
    for failure in result["failed"]:
        print(
            f"Failed to send {failure['title']} to {failure['chat_id']}: {failure['error']}"
        )

def start(bot):
    # update Apps Script sources and deployment at 09:30 Asia/Tashkent
    update_trigger = CronTrigger(hour=9, minute=30, timezone=TIMEZONE)
    # schedule daily send at 10:00 Asia/Tashkent
    send_trigger_10 = CronTrigger(hour=10, minute=0, timezone=TIMEZONE)
    send_trigger_19 = CronTrigger(hour=19, minute=0, timezone=TIMEZONE)
    try:
        scheduler.add_job(update_web_app_before_send, update_trigger, id="daily_webapp_update")
        scheduler.add_job(take_and_send, send_trigger_10, kwargs={"bot": bot}, id="daily_screenshot_10")
        scheduler.add_job(take_and_send, send_trigger_19, kwargs={"bot": bot}, id="daily_screenshot_19")
    except Exception:
        # job may already exist
        try:
            scheduler.remove_job("daily_webapp_update")
            scheduler.remove_job("daily_screenshot_10")
            scheduler.remove_job("daily_screenshot_19")
            scheduler.add_job(update_web_app_before_send, update_trigger, id="daily_webapp_update")
            scheduler.add_job(take_and_send, send_trigger_10, kwargs={"bot": bot}, id="daily_screenshot_10")
            scheduler.add_job(take_and_send, send_trigger_19, kwargs={"bot": bot}, id="daily_screenshot_19")
        except JobLookupError:
            pass

    scheduler.start()

def shutdown():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
