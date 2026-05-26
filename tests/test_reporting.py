import asyncio
import datetime

from src.config import TIMEZONE
from src.services import reporting
from src.services.screenshot import CapturedSection, DashboardProbe, _build_dashboard_error


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_photo(self, **kwargs):
        self.calls.append(kwargs)


def test_build_report_caption():
    stamp = datetime.datetime(2026, 5, 14, 10, 0, tzinfo=TIMEZONE)
    caption = reporting.build_report_caption(stamp)
    assert caption == "2026-yil 14-may holatiga ko'ra savdo natijalari hisoboti."


def test_build_report_markup():
    markup = reporting.build_report_markup("https://example.com/app")
    assert markup is not None
    assert markup.inline_keyboard[0][0].url == "https://example.com/app"


def test_build_section_caption():
    report_caption = "2026-yil 14-may holatiga ko'ra savdo natijalari hisoboti."
    assert (
        reporting.build_section_caption(report_caption, "FULL", "FULL SCREENSHOT")
        == "2026-yil 14-may holatiga ko'ra savdo natijalari hisoboti."
    )
    assert (
        reporting.build_section_caption(report_caption, "AA", "ArzonApteka")
        == "ArzonApteka bo'yicha top 3ta o'rin."
    )


def test_send_report_sends_all_images_and_deletes_screenshots(tmp_path, monkeypatch):
    async def run():
        bot = FakeBot()
        images = []
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()
        monkeypatch.setattr(reporting, "SCREENSHOTS_DIR", screenshots_dir)

        for index, (code, title) in enumerate(
            [
                ("FULL", "FULL SCREENSHOT"),
                ("AA", "ArzonApteka"),
                ("FA", "F-Apteka"),
                ("FK", "F-Kassa"),
                ("FS", "F-Summary"),
            ],
            start=1,
        ):
            path = screenshots_dir / f"{index}.png"
            path.write_bytes(b"fake")
            images.append(
                CapturedSection(
                    product_code=code,
                    title=title,
                    slug=title.lower().replace(" ", "-"),
                    path=path,
                )
            )

        result = await reporting.send_report(bot, -100123, images)
        expected_caption = reporting.build_report_caption()

        assert len(bot.calls) == 5
        assert bot.calls[0]["chat_id"] == -100123
        assert bot.calls[0]["caption"] == expected_caption
        assert bot.calls[0]["reply_markup"] is not None
        assert bot.calls[1]["caption"] == "ArzonApteka bo'yicha top 3ta o'rin."
        assert bot.calls[1]["reply_markup"] is None
        assert len(result["sent"]) == 5
        assert result["failed"] == []
        assert len(result["deleted"]) == 5
        assert result["cleanup_failed"] == []
        assert result["caption"] == expected_caption
        assert not any(image.path.exists() for image in images)

    asyncio.run(run())


def test_build_dashboard_error_for_access_denied():
    probe = DashboardProbe(
        page_title="Access denied",
        body_text="You do not have permission to access this page.",
        loader_title="",
        loader_text="",
        loader_visible=False,
        app_present=False,
        card_count=0,
    )

    error = _build_dashboard_error(probe)
    assert error is not None
    assert error == (
        "Dashboard access denied. "
        "Check the Apps Script deployment access and confirm the /exec URL is publicly reachable."
    )


def test_build_dashboard_error_for_stuck_loader():
    probe = DashboardProbe(
        page_title="",
        body_text="",
        loader_title="Connecting to Google Sheets...",
        loader_text="Dashboard initialization and data loading.",
        loader_visible=True,
        app_present=True,
        card_count=0,
    )

    error = _build_dashboard_error(probe, timeout_ms=45000)
    assert error == (
        "Dashboard did not finish loading after waiting 45000ms. "
        "Last page state: Connecting to Google Sheets... | Dashboard initialization and data loading."
    )
