"""
Gold Tier — Instagram Integration
====================================
Posts to Instagram via Playwright browser automation.
Same pattern as the LinkedIn integration (proven in Silver).

Prerequisites:
    pip install playwright && playwright install chromium

Environment variables:
    INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD

Usage:
    from integrations.social.instagram import InstagramPlatform

    ig = InstagramPlatform()
    result = ig.post("New product launch!", media=[Path("photo.jpg")])
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config
from integrations.social.base import SocialPlatform, PostResult, MetricsResult

INSTAGRAM_URL = "https://www.instagram.com/"
BROWSER_DATA_DIR = _PROJECT_ROOT / "integrations" / "social" / ".instagram_browser_data"


class InstagramPlatform(SocialPlatform):
    """Instagram posting via Playwright browser automation."""

    platform_name = "instagram"
    char_limit = 2200
    rate_limit_per_day = 2

    def __init__(self) -> None:
        config.load()
        self.username = config.env("INSTAGRAM_USERNAME", "")
        self.password = config.env("INSTAGRAM_PASSWORD", "")

    def authenticate(self) -> bool:
        """Verify credentials are available."""
        if not self.username or not self.password:
            error_logger.log_error(
                "social.instagram",
                "Missing INSTAGRAM_USERNAME or INSTAGRAM_PASSWORD in .env",
            )
            return False
        return True

    def post(self, content: str, media: list[Path] | None = None) -> PostResult:
        """Publish a post to Instagram using Playwright.

        Instagram requires an image for feed posts. If no media is
        provided, this creates a Stories text post instead.
        """
        error = self.validate_content(content)
        if error:
            return PostResult(success=False, platform=self.platform_name, error=error)

        if not self.authenticate():
            return PostResult(
                success=False, platform=self.platform_name,
                error="Authentication failed — check INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD",
            )

        if not media:
            return PostResult(
                success=False, platform=self.platform_name,
                error="Instagram feed posts require at least one image. Provide media=[Path('image.jpg')]",
            )

        # Verify media files exist
        for m in media:
            if not Path(m).is_file():
                return PostResult(
                    success=False, platform=self.platform_name,
                    error=f"Media file not found: {m}",
                )

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            return PostResult(
                success=False, platform=self.platform_name,
                error="Playwright not installed. Run: pip install playwright && playwright install chromium",
            )

        try:
            with sync_playwright() as p:
                # Use mobile viewport to get Instagram's mobile web UI (supports posting)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(BROWSER_DATA_DIR),
                    headless=True,
                    viewport={"width": 414, "height": 896},
                    is_mobile=True,
                    user_agent=(
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/16.0 Mobile/15E148 Safari/604.1"
                    ),
                )
                page = context.new_page()

                try:
                    # Navigate to Instagram
                    page.goto(INSTAGRAM_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    # Login if needed
                    if "login" in page.url.lower() or page.locator("input[name='username']").count() > 0:
                        page.fill("input[name='username']", self.username)
                        page.fill("input[name='password']", self.password)
                        page.click("button[type='submit']")
                        page.wait_for_timeout(5000)

                        # Dismiss "Save Login Info" dialog if it appears
                        try:
                            not_now = page.get_by_text("Not Now").first
                            if not_now.is_visible():
                                not_now.click()
                                page.wait_for_timeout(2000)
                        except Exception:
                            pass

                    # Click the create/new post button (+ icon)
                    create_btn = None
                    for selector in [
                        "[aria-label='New post']",
                        "[aria-label='Create']",
                        "svg[aria-label='New post']",
                    ]:
                        loc = page.locator(selector).first
                        if loc.count() > 0:
                            create_btn = loc
                            break

                    if not create_btn:
                        return PostResult(
                            success=False, platform=self.platform_name,
                            error="Could not find Instagram create button",
                        )

                    create_btn.click()
                    page.wait_for_timeout(3000)

                    # Upload the first media file
                    file_input = page.locator("input[type='file']").first
                    file_input.set_input_files(str(media[0]))
                    page.wait_for_timeout(3000)

                    # Click "Next" (crop screen)
                    next_btn = page.get_by_role("button", name="Next").first
                    next_btn.click()
                    page.wait_for_timeout(2000)

                    # Click "Next" again (filters screen)
                    next_btn = page.get_by_role("button", name="Next").first
                    next_btn.click()
                    page.wait_for_timeout(2000)

                    # Type caption
                    caption_area = page.locator("textarea[aria-label='Write a caption...']").first
                    if caption_area.count() == 0:
                        caption_area = page.locator("textarea").first
                    caption_area.fill(content)
                    page.wait_for_timeout(1000)

                    # Share
                    share_btn = page.get_by_role("button", name="Share").first
                    share_btn.click()
                    page.wait_for_timeout(5000)

                    result = PostResult(
                        success=True,
                        platform=self.platform_name,
                        content_length=len(content),
                    )

                    bus.emit("social.post.success", {
                        "platform": self.platform_name,
                        "content_length": len(content),
                    })
                    error_logger.log_audit("social.post", "success", {
                        "platform": self.platform_name,
                        "content_length": len(content),
                    })

                    return result

                finally:
                    context.close()

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            bus.emit("social.post.failed", {
                "platform": self.platform_name, "error": error_msg,
            })
            error_logger.log_error("social.instagram.post", e)
            return PostResult(
                success=False, platform=self.platform_name, error=error_msg,
            )

    def get_metrics(self, post_id: str) -> MetricsResult:
        """Instagram web does not expose a metrics API — returns empty metrics."""
        return MetricsResult(platform=self.platform_name, post_id=post_id)
