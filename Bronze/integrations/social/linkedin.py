"""
Gold Tier — LinkedIn Integration
==================================
Upgraded from Silver skill. Uses Playwright browser automation.
Now implements the SocialPlatform interface and emits events.

Usage:
    from integrations.social.linkedin import LinkedInPlatform

    li = LinkedInPlatform()
    result = li.post("Excited to share our latest update! #AI")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config
from integrations.social.base import SocialPlatform, PostResult, MetricsResult

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
BROWSER_DATA_DIR = _PROJECT_ROOT / "integrations" / "social" / ".linkedin_browser_data"


class LinkedInPlatform(SocialPlatform):
    """LinkedIn posting via Playwright browser automation."""

    platform_name = "linkedin"
    char_limit = 3000
    rate_limit_per_day = 1

    def __init__(self, headless: bool = True) -> None:
        config.load()
        self.email = config.env("LINKEDIN_EMAIL", "")
        self.password = config.env("LINKEDIN_PASSWORD", "")
        self.headless = headless

    def authenticate(self) -> bool:
        """Verify credentials are available."""
        if not self.email or not self.password:
            error_logger.log_error("social.linkedin", "Missing LINKEDIN_EMAIL or LINKEDIN_PASSWORD")
            return False
        return True

    def post(self, content: str, media: list[Path] | None = None) -> PostResult:
        """Publish a text post to LinkedIn using Playwright."""
        # Validate
        error = self.validate_content(content)
        if error:
            return PostResult(success=False, platform=self.platform_name, error=error)

        if not self.authenticate():
            return PostResult(
                success=False, platform=self.platform_name,
                error="Authentication failed — check LINKEDIN_EMAIL and LINKEDIN_PASSWORD",
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
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(BROWSER_DATA_DIR),
                    headless=self.headless,
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()

                try:
                    # Check login state
                    page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(3000)

                    if "login" in page.url:
                        page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(2000)
                        page.fill("#username", self.email)
                        page.fill("#password", self.password)
                        page.click("button[type='submit']")
                        page.wait_for_timeout(5000)

                        # Handle security checkpoint (CAPTCHA/2FA/email verify)
                        if "checkpoint" in page.url or "challenge" in page.url:
                            print("[LinkedIn] Security challenge detected.")
                            print("[LinkedIn] Please complete the verification in the browser window.")
                            print("[LinkedIn] Waiting up to 3 minutes...")
                            page.wait_for_url("**/feed/**", timeout=180000)

                        if "/feed" not in page.url:
                            page.wait_for_url("**/feed/**", timeout=60000)

                    # Open composer
                    page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(1000)

                    # Find and click "Start a post"
                    editor = None
                    for attempt in range(3):
                        try:
                            btn = page.locator("button").filter(has_text="Start a post").first
                            if btn.count() > 0:
                                btn.click(force=True, timeout=5000)
                                page.wait_for_timeout(3000)
                        except Exception:
                            pass

                        for sel in [
                            "[role='textbox'][contenteditable='true']",
                            "[contenteditable='true'][data-placeholder]",
                            ".ql-editor[contenteditable='true']",
                            "div[contenteditable='true']",
                        ]:
                            loc = page.locator(sel).first
                            try:
                                if loc.count() > 0 and loc.is_visible():
                                    editor = loc
                                    break
                            except Exception:
                                continue
                        if editor:
                            break

                    if not editor:
                        return PostResult(
                            success=False, platform=self.platform_name,
                            error="Could not open LinkedIn post editor after 3 attempts",
                        )

                    # Type and publish
                    editor.click()
                    editor.fill(content)
                    page.wait_for_timeout(1000)

                    post_btn = page.locator("button.share-actions__primary-action")
                    if post_btn.count() == 0:
                        post_btn = page.get_by_role("button", name="Post", exact=True)
                    post_btn.click()

                    try:
                        editor.wait_for(state="hidden", timeout=15000)
                    except PlaywrightTimeout:
                        pass

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
            error_logger.log_error("social.linkedin.post", e)
            return PostResult(
                success=False, platform=self.platform_name, error=error_msg,
            )

    def get_metrics(self, post_id: str) -> MetricsResult:
        """LinkedIn does not expose public metrics API — returns empty metrics."""
        return MetricsResult(
            platform=self.platform_name,
            post_id=post_id,
        )
