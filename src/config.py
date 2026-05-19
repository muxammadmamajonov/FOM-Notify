import os
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

ENV_FILE = Path(".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
TARGET_URL = os.getenv("TARGET_URL")
WEB_APP_URL = os.getenv("WEB_APP_URL") or TARGET_URL
TZ = os.getenv("TZ", "Asia/Tashkent")
TIMEZONE = ZoneInfo(TZ)
DB_PATH = os.getenv("DB_PATH", "data/subscribers.db")
APPS_SCRIPT_AUTO_UPDATE = os.getenv("APPS_SCRIPT_AUTO_UPDATE", "0") == "1"
CLASP_WORKDIR = os.getenv("CLASP_WORKDIR", ".")
CLASP_DEPLOYMENT_ID = os.getenv("CLASP_DEPLOYMENT_ID", "").strip()

RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
# Run Playwright headless by default. Set `HEADLESS=0` in .env to run headful.
_headless_raw = os.getenv("HEADLESS", "1").lower()
HEADLESS = _headless_raw in ("1", "true", "yes")
