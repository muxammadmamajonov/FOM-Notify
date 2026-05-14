import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
TARGET_URL = os.getenv("TARGET_URL")
TZ = os.getenv("TZ", "Asia/Tashkent")
TIMEZONE = ZoneInfo(TZ)
DB_PATH = os.getenv("DB_PATH", "data/subscribers.db")

# Optional comma-separated list of initial subscriber chat IDs (e.g. -12345,-67890)
INITIAL_SUBSCRIBERS_RAW = os.getenv("INITIAL_SUBSCRIBERS", "")
if INITIAL_SUBSCRIBERS_RAW:
	INITIAL_SUBSCRIBERS = [int(x.strip()) for x in INITIAL_SUBSCRIBERS_RAW.split(",") if x.strip()]
else:
	INITIAL_SUBSCRIBERS = []

# Optional path to a JSON cookie export file (Playwright cookie format) to use for authenticated pages
COOKIES_FILE = os.getenv("COOKIES_FILE", "")

# Optional path to a persistent browser profile directory to reuse an existing signed-in profile.
# Prefer copying a profile to a new folder to avoid concurrent access to your real browser profile.
PLAYWRIGHT_USER_DATA_DIR = os.getenv("PLAYWRIGHT_USER_DATA_DIR", "")

RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
# Run Playwright headless by default. Set `HEADLESS=0` in .env to run headful.
_headless_raw = os.getenv("HEADLESS", "1").lower()
HEADLESS = _headless_raw in ("1", "true", "yes")
