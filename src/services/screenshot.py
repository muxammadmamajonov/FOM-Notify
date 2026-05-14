from pathlib import Path
import json

from playwright.async_api import async_playwright

from ..config import COOKIES_FILE, HEADLESS, PLAYWRIGHT_USER_DATA_DIR


SCREENSHOT_WIDTH = 1920
SCREENSHOT_HEIGHT = 1080


async def _find_dashboard_context(page):
    for _ in range(40):
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

        await page.wait_for_timeout(250)

    return page.main_frame


async def _wait_for_dashboard_render(target):
    if hasattr(target, "wait_for_load_state"):
        await target.wait_for_load_state("domcontentloaded")
        await target.wait_for_load_state("networkidle")

    try:
        await target.evaluate(
            """async () => {
                if (document.fonts && document.fonts.ready) {
                    await document.fonts.ready;
                }
            }"""
        )
    except Exception:
        pass

    try:
        await target.wait_for_function(
            """() => {
                const app = document.querySelector(".app");
                const loader = document.querySelector("#loader");
                const cards = document.querySelectorAll(".pod-card");
                const status = document.querySelector("#statusText");

                if (!app) {
                    return false;
                }

                if (cards.length > 0) {
                    return true;
                }

                if (status && /загрузка/i.test(status.textContent || "")) {
                    return false;
                }

                return !loader || loader.offsetParent === null;
            }""",
            timeout=30000,
        )
    except Exception:
        pass

    await target.wait_for_timeout(1200)


async def _load_dashboard_page(context, url: str):
    bootstrap_page = await context.new_page()
    try:
        await bootstrap_page.set_viewport_size(
            {"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT}
        )
        await bootstrap_page.goto(url, wait_until="networkidle", timeout=60000)
        frame = await _find_dashboard_context(bootstrap_page)

        if frame != bootstrap_page.main_frame:
            try:
                direct_url = await frame.evaluate("() => location.href")
            except Exception:
                direct_url = frame.url

            if direct_url:
                capture_page = await context.new_page()
                await capture_page.set_viewport_size(
                    {"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT}
                )
                await capture_page.goto(direct_url, wait_until="networkidle", timeout=60000)
                return bootstrap_page, capture_page

        return None, bootstrap_page
    except Exception:
        await bootstrap_page.close()
        raise


async def capture(url: str, out_path: str, width: int = SCREENSHOT_WIDTH, height: int = SCREENSHOT_HEIGHT):
    """Capture a fixed 1920x1080 dashboard screenshot and save it to `out_path`."""
    del width, height

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
                    viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT},
                    user_agent=desktop_ua,
                    channel="msedge",
                )
            except Exception:
                try:
                    context = await p.chromium.launch_persistent_context(
                        PLAYWRIGHT_USER_DATA_DIR,
                        headless=headless_mode,
                        viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT},
                        user_agent=desktop_ua,
                    )
                except Exception:
                    browser = await p.chromium.launch(headless=HEADLESS)
                    context = await browser.new_context(
                        viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT},
                        user_agent=desktop_ua,
                    )
        else:
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(
                viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT},
                user_agent=desktop_ua,
            )

        bootstrap_page = None
        capture_page = None

        try:
            if COOKIES_FILE:
                cf = Path(COOKIES_FILE)
                if cf.exists():
                    try:
                        raw = json.loads(cf.read_text(encoding="utf8"))
                        await context.add_cookies(raw)
                    except Exception:
                        pass

            bootstrap_page, capture_page = await _load_dashboard_page(context, url)
            await _wait_for_dashboard_render(capture_page)
            await capture_page.set_viewport_size(
                {"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT}
            )
            await capture_page.screenshot(path=str(out))
        finally:
            for page in (capture_page, bootstrap_page):
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
