from pathlib import Path
import json

from playwright.async_api import async_playwright

from ..config import COOKIES_FILE, HEADLESS, PLAYWRIGHT_USER_DATA_DIR


SCREENSHOT_WIDTH = 1920
SCREENSHOT_HEIGHT = 1080


async def _find_dashboard_context(page):
    for _ in range(50):
        for frame in page.frames:
            try:
                has_app = await frame.evaluate(
                    """() => !!(
                        document.querySelector(".app") ||
                        document.querySelector("#stage") ||
                        document.querySelector(".pod-card")
                    )"""
                )
            except Exception:
                continue

            if has_app:
                return frame

        await page.wait_for_timeout(200)

    return page.main_frame


async def _wait_for_dashboard_render(frame):
    try:
        await frame.wait_for_function(
            """() => {
                const app = document.querySelector(".app");
                const cards = document.querySelectorAll(".pod-card");
                const loader = document.querySelector("#loader");
                if (!app) return false;
                if (cards.length > 0) return true;
                return !loader || loader.offsetParent === null;
            }""",
            timeout=45000,
        )
    except Exception:
        pass

    try:
        await frame.evaluate(
            """async () => {
                if (document.fonts && document.fonts.ready) {
                    await document.fonts.ready;
                }
            }"""
        )
    except Exception:
        pass

    await frame.evaluate("() => window.scrollTo(0, 0)")
    await frame.wait_for_timeout(900)


async def _fit_dashboard_to_viewport(frame, width: int, height: int):
    try:
        await frame.evaluate(
            """({ width, height }) => {
                const app = document.querySelector(".app");
                if (!app) return;

                app.style.transform = "none";
                app.style.transformOrigin = "top left";
                app.style.width = "";
                app.style.height = "";

                const rect = app.getBoundingClientRect();
                const appW = Math.max(rect.width, app.scrollWidth);
                const appH = Math.max(rect.height, app.scrollHeight);
                if (!appW || !appH) return;

                const ratio = Math.min(width / appW, height / appH, 1);
                if (ratio < 1) {
                    app.style.width = appW + "px";
                    app.style.height = appH + "px";
                    app.style.transform = "scale(" + ratio + ")";
                }

                document.documentElement.style.overflow = "hidden";
                document.body.style.overflow = "hidden";
                window.scrollTo(0, 0);
            }""",
            {"width": width, "height": height},
        )
        await frame.wait_for_timeout(300)
    except Exception:
        pass


async def capture(
    url: str,
    out_path: str,
    width: int = SCREENSHOT_WIDTH,
    height: int = SCREENSHOT_HEIGHT,
):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    desktop_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )

    async with async_playwright() as p:
        context = None
        browser = None

        headless_mode = HEADLESS
        if PLAYWRIGHT_USER_DATA_DIR:
            headless_mode = False

        if PLAYWRIGHT_USER_DATA_DIR:
            try:
                context = await p.chromium.launch_persistent_context(
                    PLAYWRIGHT_USER_DATA_DIR,
                    headless=headless_mode,
                    viewport={"width": width, "height": height},
                    user_agent=desktop_ua,
                    channel="msedge",
                )
            except Exception:
                try:
                    context = await p.chromium.launch_persistent_context(
                        PLAYWRIGHT_USER_DATA_DIR,
                        headless=headless_mode,
                        viewport={"width": width, "height": height},
                        user_agent=desktop_ua,
                    )
                except Exception:
                    browser = await p.chromium.launch(headless=HEADLESS)
                    context = await browser.new_context(
                        viewport={"width": width, "height": height},
                        user_agent=desktop_ua,
                    )
        else:
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=desktop_ua,
            )

        page = None
        try:
            if COOKIES_FILE:
                cf = Path(COOKIES_FILE)
                if cf.exists():
                    try:
                        raw = json.loads(cf.read_text(encoding="utf-8"))
                        await context.add_cookies(raw)
                    except Exception:
                        pass

            page = await context.new_page()
            await page.set_viewport_size({"width": width, "height": height})
            await page.goto(url, wait_until="networkidle", timeout=90000)
            frame = await _find_dashboard_context(page)
            await _wait_for_dashboard_render(frame)
            await _fit_dashboard_to_viewport(frame, width, height)
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(out), full_page=False)
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            try:
                await context.close()
            except Exception:
                pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    return str(out)
