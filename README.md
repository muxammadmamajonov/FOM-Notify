# FOM-Notify - Daily Dashboard Telegram Bot

This project is an aiogram-based Telegram bot that captures the dashboard from a target URL every day at `10:00` (Asia/Tashkent) and sends it sequentially to one Telegram group.

Quick setup (Windows PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
copy .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, GROUP_CHAT_ID, TARGET_URL
python -m src.main
```

Run a one-shot capture (no bot required):

```powershell
$env:RUN_ONCE = "1"
venv\Scripts\python.exe -m src.main
```

Files of interest:
- `src/main.py` - entrypoint
- `src/services/screenshot.py` - Playwright capture logic
- `src/services/scheduler.py` - APScheduler setup
- `src/handlers/` - Telegram command handlers

Report behavior
---------------
- Captures and sends five screenshots in this order: `FULL SCREENSHOT`, `ArzonApteka`, `F-Apteka`, `F-Kassa`, `F-Summary`
- Product screenshots use Uzbek captions like `F-Apteka bo'yicha top 3ta o'rin.`
- Sends only to `GROUP_CHAT_ID`
- Does not use `subscribers.db` for deliveries

Deployment access
-----------------
The screenshot bot opens the Apps Script `/exec` URL as an anonymous public client.
If capture fails with `Dashboard access denied`, check the web app deployment access and confirm the `/exec` URL is publicly reachable.

Autostart on Windows
--------------------
Install and start the Windows scheduled task so the bot runs after reboot/logon and restarts if it exits:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Install
```

Check status:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Status
```

Restart after updating bot code:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Restart
```

Stop the currently running bot but keep autostart installed:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Stop
```

Start it again:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Start
```

Remove the autostart task completely:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Remove
```

Runner logs are written under `data\logs\`.

Daily Apps Script auto-update before send
-----------------------------------------
Scheduler supports:
- `09:30` - auto-update `Index.html`/`Code.gs` to Apps Script via `clasp`
- `10:00` - capture and send screenshot

Setup:
1. Install and login `clasp`:
```powershell
npm i -g @google/clasp
clasp login
```
2. Set `.env`:
```dotenv
APPS_SCRIPT_AUTO_UPDATE=1
CLASP_WORKDIR=.
CLASP_DEPLOYMENT_ID=<your_web_app_deployment_id>
```
3. Keep `Index.html` and `Code.gs` in this repo as your source of truth.
