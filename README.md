# FOM-Notify — Daily Dashboard Telegram Bot

`aiogram`-based Telegram bot that screenshots the FOM Apps Script dashboard
every day at **10:00 Asia/Tashkent** and posts the report to one Telegram group.

Files of interest:
- `src/main.py` — entrypoint (`python -m src.main`)
- `src/config.py` — env + project paths (all paths are project-root-relative)
- `src/services/screenshot.py` — Playwright capture logic
- `src/services/scheduler.py` — APScheduler triggers (09:30 + 10:00 Tashkent)
- `src/services/reporting.py` — caption + Telegram delivery
- `src/handlers/` — `/start`, `/report`, `/run_screenshot` commands

Report behaviour:
- Captures and sends five screenshots in this order: `FULL SCREENSHOT`,
  `ArzonApteka`, `F-Apteka`, `F-Kassa`, `F-Summary`.
- Product captions are in Uzbek: e.g. `F-Apteka bo'yicha top 3ta o'rin.`
- Sends only to `GROUP_CHAT_ID`. `subscribers.db` is no longer used for
  delivery (kept for future use).

---

## Local development

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, GROUP_CHAT_ID, TARGET_URL
python -m src.main
```

### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, GROUP_CHAT_ID, TARGET_URL
python -m src.main
```

### One-shot capture (no bot needed)

```bash
RUN_ONCE=1 venv/bin/python -m src.main          # Linux/macOS
$env:RUN_ONCE = "1"; venv\Scripts\python.exe -m src.main   # Windows
```

### Tests

```bash
venv/bin/python -m pytest tests/
```

The Playwright-based smoke test against the live dashboard is opt-in:

```bash
TEST_REAL_DASHBOARD=1 venv/bin/python -m pytest tests/test_screenshot.py
```

---

## Deploy on AlwaysData

AlwaysData is a Linux shared host; the bot runs as a **long-running user
program**. Steps assume SSH access is enabled on your account.

### 1. Clone the repo

```bash
ssh <account>@ssh-<account>.alwaysdata.net
cd ~
git clone https://github.com/<your-github-user>/FOM-Notify.git
cd FOM-Notify
```

### 2. Pick a Python version + create venv

In the AlwaysData admin panel, set the Python version for your site to **3.11+**
(under *Environment → Python*). Then in SSH:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

> **Playwright tip:** Use `python -m playwright install chromium` (not
> `--with-deps`). `--with-deps` calls `apt-get` and requires root, which you
> don't have on shared hosting. AlwaysData's base image already ships the
> shared libraries Chromium needs.

### 3. Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in:

```dotenv
TELEGRAM_BOT_TOKEN=<from BotFather>
ADMIN_CHAT_ID=<your numeric chat id>
GROUP_CHAT_ID=<target group id, negative number for supergroups>
TARGET_URL=https://script.google.com/macros/s/.../exec
WEB_APP_URL=                      # optional, defaults to TARGET_URL
TZ=Asia/Tashkent
APPS_SCRIPT_AUTO_UPDATE=0         # set to 1 only if you also install clasp
```

### 4. Smoke-test before turning it into a service

```bash
RUN_ONCE=1 venv/bin/python -m src.main
ls screenshots/   # should contain 5 PNGs
```

If you see `Dashboard access denied` or a Chromium error, fix it now — the
service will hit the same wall.

### 5. Register the AlwaysData long-running process

In the AlwaysData admin panel, go to **Sites → Add a site** and choose
**"User program"** (or under **Tools → Processes** depending on UI version)
with the following settings:

| Field             | Value                                                                 |
| ----------------- | --------------------------------------------------------------------- |
| Command           | `/home/<account>/FOM-Notify/venv/bin/python -m src.main`              |
| Working directory | `/home/<account>/FOM-Notify`                                          |
| Environment       | (none needed — `.env` is read from the working directory)             |
| Restart on exit   | **Yes** (auto-restart so it survives crashes + AlwaysData maintenance)|

Save, then start the process from the panel.

### 6. Verify it's running

```bash
# Should show one python process for your account:
ps -fu <account> | grep src.main

# Tail the bot's stderr/stdout (AlwaysData captures them per-process; check
# the panel's "Logs" tab for the process you created).
```

Then in Telegram, send `/start` to your bot — it should reply. Send `/report`
to trigger a manual capture-and-send round-trip.

### 7. Apps Script auto-update (optional)

If you want the `09:30` auto-deploy of `Index.html` / `Code.gs`, you'll also
need Node.js + `clasp` on the AlwaysData account:

```bash
# Pick a Node version in the AlwaysData panel, then:
npm i -g @google/clasp
clasp login --no-localhost     # follow the OAuth URL it prints
```

Copy `~/.clasprc.json` into place, set `APPS_SCRIPT_AUTO_UPDATE=1` in `.env`,
and provide `CLASP_DEPLOYMENT_ID`. Otherwise leave `APPS_SCRIPT_AUTO_UPDATE=0`
— the scheduler will skip cleanly.

### 8. Updating the bot

```bash
ssh <account>@ssh-<account>.alwaysdata.net
cd ~/FOM-Notify
git pull
source venv/bin/activate
pip install -r requirements.txt   # only if requirements changed
# Restart the process from the AlwaysData panel.
```

---

## Windows-only autostart (legacy)

The `tools/*.ps1` scripts wire the bot into Windows Task Scheduler. They are
not used on AlwaysData and can be ignored on Linux:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Install
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Status
powershell -ExecutionPolicy Bypass -File tools\install_autostart.ps1 -Action Restart
```

---

## Deployment access notes

The screenshot bot opens the Apps Script `/exec` URL as an anonymous public
client. If capture fails with `Dashboard access denied`, check the Web App
deployment access in the Apps Script editor and confirm the `/exec` URL is
publicly reachable in a browser.
