# FOM-Notify — Daily Screenshot Telegram Bot

This project is a small aiogram-based Telegram bot that captures a desktop screenshot of a target URL every day at 10:00 Asia/Tashkent and sends it to subscribers.

Quick setup (Windows PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
copy .env.example .env
# edit .env to add TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID
python -m src.main
```

Run a one-shot capture (no bot required):

```powershell
$env:RUN_ONCE = "1"
venv\Scripts\python.exe -m src.main
```

Files of interest:
- `src/main.py` — entrypoint
- `src/services/screenshot.py` — Playwright capture logic
Authenticated pages
-------------------
If the target page requires Google sign-in you have three safe options (no passwords required):

- Make the Apps Script deployment public: in the Google Apps Script editor, choose "Deploy" → "Manage deployments" → edit the deployment and set "Who has access" to "Anyone" or "Anyone, even anonymous" (and "Execute as" to your account if needed). This is the simplest fix.
- Export your browser cookies for the target domain to a JSON file and set `COOKIES_FILE` in `.env` to point to that file. The bot will load those cookies before navigating.
- Use a persistent browser profile: create a copy of your Chrome user profile and set `PLAYWRIGHT_USER_DATA_DIR` in `.env` to that copied folder; Playwright will launch a persistent context that reuses the signed-in session.

Do NOT share Google credentials. Prefer the public-deploy option when possible.

- `src/services/scheduler.py` — APScheduler setup
- `src/services/subscriptions.py` — aiosqlite subscription store
- `src/handlers/` — Telegram command handlers
