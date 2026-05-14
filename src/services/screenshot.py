from pathlib import Path
import json
from playwright.async_api import async_playwright
from ..config import COOKIES_FILE, PLAYWRIGHT_USER_DATA_DIR, HEADLESS


MAX_CAPTURE_HEIGHT = 20000
LAYOUT_STABILITY_CHECKS = 4
LAYOUT_STABILITY_INTERVAL_MS = 400


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


async def _wait_for_dashboard_render(page):
    if hasattr(page, "wait_for_load_state"):
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_load_state("networkidle")

    try:
        await page.evaluate(
            """async () => {
                if (document.fonts && document.fonts.ready) {
                    await document.fonts.ready;
                }
            }"""
        )
    except Exception:
        pass

    try:
        await page.wait_for_function(
            """() => {
                const loader = document.querySelector("#loader");
                const cards = document.querySelectorAll(".pod-card");
                const app = document.querySelector(".app");

                if (cards.length > 0) {
                    return true;
                }

                if (!app) {
                    return false;
                }

                return !loader || loader.offsetParent === null;
            }""",
            timeout=30000,
        )
    except Exception:
        pass

    await _wait_for_stable_layout(page)


async def _wait_for_stable_layout(page):
    stable_checks = 0
    last_size = None

    while stable_checks < LAYOUT_STABILITY_CHECKS:
        size = await _measure_page(page)

        if size == last_size:
            stable_checks += 1
        else:
            stable_checks = 0
            last_size = size

        await page.wait_for_timeout(LAYOUT_STABILITY_INTERVAL_MS)


async def _measure_page(page):
    return await page.evaluate(
        """() => {
            const doc = document.documentElement;
            const body = document.body;
            const width = Math.max(
                doc ? doc.clientWidth : 0,
                doc ? doc.scrollWidth : 0,
                doc ? doc.offsetWidth : 0,
                body ? body.clientWidth : 0,
                body ? body.scrollWidth : 0,
                body ? body.offsetWidth : 0
            );
            const height = Math.max(
                doc ? doc.clientHeight : 0,
                doc ? doc.scrollHeight : 0,
                doc ? doc.offsetHeight : 0,
                body ? body.clientHeight : 0,
                body ? body.scrollHeight : 0,
                body ? body.offsetHeight : 0
            );

            return { width, height };
        }"""
    )


async def _capture_dashboard_frame(frame, out):
    await _wait_for_dashboard_render(frame)

    locator = frame.locator(".app")
    if await locator.count() == 0:
        locator = frame.locator("body")

    await locator.screenshot(path=str(out))


async def capture(url: str, out_path: str, width: int = 1920, height: int = 1080):
    """Capture a desktop-style screenshot of `url` and save to `out_path`.

    If `PLAYWRIGHT_USER_DATA_DIR` is set in env, launch a persistent context using that
    directory (useful to reuse an already-signed-in browser profile). If `COOKIES_FILE`
    is set and exists, the cookie JSON will be loaded into the context before navigation.

    Note: this avoids asking for Google credentials. Prefer making the Google Apps Script
    deployment publicly accessible if possible.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    desktop_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )

    async with async_playwright() as p:
        context = None
        browser = None

        # Decide headless: if we're using a persistent profile, prefer headful
        # so the profile's real signed-in state is used by the browser.
        # The `HEADLESS` env var can still override when necessary.
        headless_mode = HEADLESS
        if PLAYWRIGHT_USER_DATA_DIR:
            headless_mode = False

        if PLAYWRIGHT_USER_DATA_DIR:
            # Try launching Edge (msedge) with the copied profile so signed-in state is preserved.
            try:
                context = await p.chromium.launch_persistent_context(
                    PLAYWRIGHT_USER_DATA_DIR,
                    headless=headless_mode,
                    viewport={"width": width, "height": height},
                    user_agent=desktop_ua,
                    channel="msedge",
                )
            except Exception:
                # Fallback: try launching persistent context without explicit channel,
                # then finally fall back to a fresh browser context.
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

        try:
            # Load cookies if provided (expected to be a list of cookie dicts)
            if COOKIES_FILE:
                cf = Path(COOKIES_FILE)
                if cf.exists():
                    try:
                        raw = json.loads(cf.read_text(encoding="utf8"))
                        # Playwright expects cookie dicts with at least 'name' and 'value' and 'domain'.
                        await context.add_cookies(raw)
                    except Exception:
                        # ignore cookie load errors and continue
                        pass

            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)
            dashboard_context = await _find_dashboard_context(page)

            if dashboard_context != page.main_frame:
                await _capture_dashboard_frame(dashboard_context, out)
                return str(out)

            await _wait_for_dashboard_render(page)

            content_size = await _measure_page(page)
            capture_width = max(width, int(content_size["width"]))
            capture_height = max(height, int(content_size["height"]))
            capture_height = min(capture_height, MAX_CAPTURE_HEIGHT)

            await page.set_viewport_size(
                {
                    "width": capture_width,
                    "height": capture_height,
                }
            )
            await _wait_for_stable_layout(page)
            await page.screenshot(path=str(out), full_page=True)
        finally:
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
