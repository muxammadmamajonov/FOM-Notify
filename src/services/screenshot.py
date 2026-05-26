from pathlib import Path
from dataclasses import dataclass

from playwright.async_api import async_playwright

from ..config import HEADLESS


SCREENSHOT_WIDTH = 1920
SCREENSHOT_HEIGHT = 1080
FULL_DASHBOARD = ("FULL", "FULL SCREENSHOT", "full-screenshot")
PRODUCT_SECTIONS = (
    ("AA", "ArzonApteka", "product-aa"),
    ("FA", "F-Apteka", "product-fa"),
    ("FK", "F-Kassa", "product-fk"),
    ("FS", "F-Summary", "product-fs"),
)


@dataclass(frozen=True)
class CapturedSection:
    product_code: str
    title: str
    slug: str
    path: Path


@dataclass(frozen=True)
class DashboardProbe:
    page_title: str
    body_text: str
    loader_title: str
    loader_text: str
    loader_visible: bool
    app_present: bool
    card_count: int


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


async def _probe_dashboard(frame) -> DashboardProbe:
    try:
        data = await frame.evaluate(
            """() => ({
                pageTitle: document.title || "",
                bodyText: (document.body?.innerText || "").slice(0, 1500),
                loaderTitle: document.querySelector(".loader-title")?.textContent?.trim() || "",
                loaderText: document.querySelector(".loader-text")?.textContent?.trim() || "",
                loaderVisible: !!(document.querySelector("#loader") && document.querySelector("#loader").offsetParent !== null),
                appPresent: !!document.querySelector(".app"),
                cardCount: document.querySelectorAll(".pod-card").length,
            })"""
        )
    except Exception:
        return DashboardProbe(
            page_title="",
            body_text="",
            loader_title="",
            loader_text="",
            loader_visible=False,
            app_present=False,
            card_count=0,
        )

    return DashboardProbe(
        page_title=(data.get("pageTitle") or "").strip(),
        body_text=(data.get("bodyText") or "").strip(),
        loader_title=(data.get("loaderTitle") or "").strip(),
        loader_text=(data.get("loaderText") or "").strip(),
        loader_visible=bool(data.get("loaderVisible")),
        app_present=bool(data.get("appPresent")),
        card_count=int(data.get("cardCount") or 0),
    )


def _format_probe_hint(probe: DashboardProbe) -> str:
    lines = []
    if probe.page_title:
        lines.append(probe.page_title)
    if probe.loader_title:
        lines.append(probe.loader_title)
    if probe.loader_text:
        lines.append(probe.loader_text)
    if probe.body_text:
        snippet = " ".join(probe.body_text.split())
        lines.append(snippet[:220])
    return " | ".join(lines)


def _build_dashboard_error(probe: DashboardProbe, timeout_ms: int | None = None) -> str | None:
    details = "\n".join(
        part for part in (probe.page_title, probe.loader_title, probe.loader_text, probe.body_text) if part
    ).lower()

    if "access denied" in details:
        return (
            "Dashboard access denied. "
            "Check the Apps Script deployment access and confirm the /exec URL is publicly reachable."
        )

    if "sign in" in details or "login" in details:
        return (
            "Dashboard requires sign-in. "
            "Check the Apps Script deployment access and confirm the /exec URL is publicly reachable."
        )

    if probe.loader_visible:
        wait_text = f" after waiting {timeout_ms}ms" if timeout_ms else ""
        hint = _format_probe_hint(probe)
        suffix = f" Last page state: {hint}" if hint else ""
        return f"Dashboard did not finish loading{wait_text}.{suffix}"

    if not probe.app_present and probe.card_count == 0:
        hint = _format_probe_hint(probe)
        if hint:
            return f"Dashboard app did not render in Playwright. Last page state: {hint}"
        return "Dashboard app did not render in Playwright."

    return None


async def _raise_dashboard_error_if_needed(frame, timeout_ms: int | None = None):
    probe = await _probe_dashboard(frame)
    error = _build_dashboard_error(probe, timeout_ms=timeout_ms)
    if error:
        raise RuntimeError(error)


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


async def _wait_for_report_cards(frame, expected_count: int = len(PRODUCT_SECTIONS) + 1):
    timeout_ms = 45000
    try:
        await frame.wait_for_function(
            """(expectedCount) => {
                const cards = document.querySelectorAll(".pod-card");
                if (cards.length < expectedCount) return false;
                return Array.from(cards).every(card => {
                    const badge = card.querySelector(".pod-badge");
                    const name = card.querySelector(".pod-name");
                    return badge && badge.textContent && name && name.textContent;
                });
            }""",
            arg=expected_count,
            timeout=timeout_ms,
        )
    except Exception as exc:
        await _raise_dashboard_error_if_needed(frame, timeout_ms=timeout_ms)
        raise exc
    await frame.wait_for_timeout(400)


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


async def _ensure_grid_mode(frame):
    try:
        await frame.evaluate(
            """() => {
                const btn = document.querySelector('[data-mode="grid"]');
                if (btn) btn.click();
            }"""
        )
    except Exception:
        pass

    await _wait_for_report_cards(frame)


async def _capture_app_element(frame, out_path: str):
    try:
        app = frame.locator(".app")
        count = await app.count()
        if count > 0:
            await app.first.screenshot(path=out_path)
            return True
    except Exception:
        pass
    return False


async def _get_dashboard_content_height(frame) -> int:
    try:
        return int(
            await frame.evaluate(
                """() => {
                    const app = document.querySelector(".app");
                    if (!app) return 0;
                    const rect = app.getBoundingClientRect();
                    return Math.ceil(Math.max(
                        rect.height,
                        app.scrollHeight,
                        document.body.scrollHeight,
                        document.documentElement.scrollHeight
                    ));
                }"""
            )
            or 0
        )
    except Exception:
        return 0


async def _resize_viewport_to_dashboard(page, frame, width: int, min_height: int):
    content_height = await _get_dashboard_content_height(frame)
    if not content_height:
        return

    frame_top = 0
    try:
        frame_element = await frame.frame_element()
        await frame_element.evaluate(
            """(el, height) => {
                el.style.height = height + "px";
                el.style.minHeight = height + "px";
                el.style.maxHeight = "none";
            }""",
            content_height,
        )
        box = await frame_element.bounding_box()
        if box:
            frame_top = int(box.get("y") or 0)
    except Exception:
        pass

    viewport_height = max(min_height, content_height + frame_top + 8)
    try:
        await page.set_viewport_size({"width": width, "height": viewport_height})
        await frame.wait_for_timeout(300)
    except Exception:
        pass


async def _set_capture_mode(frame, enabled: bool):
    try:
        await frame.evaluate(
            """(enabled) => {
                document.body.classList.toggle("capture-mode", !!enabled);
                window.scrollTo(0, 0);
            }""",
            enabled,
        )
        await frame.wait_for_timeout(200)
    except Exception:
        pass


async def _reset_dashboard_layout(frame):
    try:
        await frame.evaluate(
            """() => {
                document.body.classList.remove("capture-mode");
                const app = document.querySelector(".app");
                if (app) {
                    app.style.transform = "";
                    app.style.transformOrigin = "";
                    app.style.width = "";
                    app.style.height = "";
                }

                document.documentElement.style.overflow = "";
                document.body.style.overflow = "";
                window.scrollTo(0, 0);
            }"""
        )
        await frame.wait_for_timeout(200)
    except Exception:
        pass


async def _capture_full_dashboard(page, frame, out_path: str, width: int, height: int):
    await _resize_viewport_to_dashboard(page, frame, width, height)
    captured = await _capture_app_element(frame, out_path)
    if captured:
        return

    await _fit_dashboard_to_viewport(frame, width, height)
    await page.wait_for_timeout(500)
    await page.screenshot(path=out_path, full_page=False)
    await _reset_dashboard_layout(frame)


async def _launch_context(playwright, width: int, height: int, desktop_ua: str):
    browser = await playwright.chromium.launch(headless=HEADLESS)
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        user_agent=desktop_ua,
    )
    return browser, context


async def _open_dashboard(context, url: str, width: int, height: int):
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": height})
    await page.goto(url, wait_until="networkidle", timeout=90000)
    frame = await _find_dashboard_context(page)
    await _wait_for_dashboard_render(frame)
    await _raise_dashboard_error_if_needed(frame)
    return page, frame


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
        browser, context = await _launch_context(p, width, height, desktop_ua)

        page = None
        frame = None
        try:
            page, frame = await _open_dashboard(context, url, width, height)
            await _set_capture_mode(frame, True)
            await _resize_viewport_to_dashboard(page, frame, width, height)
            captured = await _capture_app_element(frame, str(out))
            if not captured:
                await _fit_dashboard_to_viewport(frame, width, height)
                await page.wait_for_timeout(500)
                await page.screenshot(path=str(out), full_page=False)
        finally:
            if frame:
                await _reset_dashboard_layout(frame)
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


async def capture_sections(
    url: str,
    out_dir: str | Path,
    base_name: str,
    width: int = SCREENSHOT_WIDTH,
    height: int = SCREENSHOT_HEIGHT,
) -> list[CapturedSection]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    desktop_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )

    captures: list[CapturedSection] = []

    async with async_playwright() as p:
        browser, context = await _launch_context(p, width, height, desktop_ua)
        page = None
        frame = None
        try:
            page, frame = await _open_dashboard(context, url, width, height)
            await _ensure_grid_mode(frame)
            await _set_capture_mode(frame, True)

            full_code, full_title, full_slug = FULL_DASHBOARD
            full_path = output_dir / f"{base_name}-01-{full_slug}.png"
            await _capture_full_dashboard(page, frame, str(full_path), width, height)
            captures.append(
                CapturedSection(
                    product_code=full_code,
                    title=full_title,
                    slug=full_slug,
                    path=full_path,
                )
            )

            for product_code, title, slug in PRODUCT_SECTIONS:
                card = frame.locator(
                    ".pod-card",
                    has=frame.locator(".pod-badge", has_text=product_code),
                )
                if await card.count() == 0:
                    raise RuntimeError(f"Dashboard card for {product_code} was not found.")

                order = len(captures) + 1
                path = output_dir / f"{base_name}-{order:02d}-{slug}.png"
                await card.first.screenshot(path=str(path))
                captures.append(
                    CapturedSection(
                        product_code=product_code,
                        title=title,
                        slug=slug,
                        path=path,
                    )
                )

            expected_count = len(PRODUCT_SECTIONS) + 1
            if len(captures) != expected_count:
                found = ", ".join(item.product_code for item in captures) or "none"
                raise RuntimeError(
                    f"Expected {expected_count} report screenshots, captured {len(captures)} ({found})."
                )
        finally:
            if frame:
                await _reset_dashboard_layout(frame)
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

    return captures
