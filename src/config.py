import os
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Project root — resolved from this file's location so the bot works no matter
# where the process is launched from (CLI, systemd, AlwaysData supervisor, etc.).
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)

SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
DATA_DIR = PROJECT_ROOT / "data"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
TARGET_URL = os.getenv("TARGET_URL")
WEB_APP_URL = os.getenv("WEB_APP_URL") or TARGET_URL
TZ = os.getenv("TZ", "Asia/Tashkent")
TIMEZONE = ZoneInfo(TZ)

# DB path: honour DB_PATH if set (relative or absolute), otherwise default
# under the project's data/ dir.
_db_env = os.getenv("DB_PATH")
if _db_env:
    _db_path = Path(_db_env)
    DB_PATH = str(_db_path if _db_path.is_absolute() else PROJECT_ROOT / _db_path)
else:
    DB_PATH = str(DATA_DIR / "subscribers.db")

APPS_SCRIPT_AUTO_UPDATE = os.getenv("APPS_SCRIPT_AUTO_UPDATE", "0") == "1"
CLASP_WORKDIR = os.getenv("CLASP_WORKDIR", str(PROJECT_ROOT))
CLASP_DEPLOYMENT_ID = os.getenv("CLASP_DEPLOYMENT_ID", "").strip()

RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
# Run Playwright headless by default. Set `HEADLESS=0` in .env to run headful.
_headless_raw = os.getenv("HEADLESS", "1").lower()
HEADLESS = _headless_raw in ("1", "true", "yes")
