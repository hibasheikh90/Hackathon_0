"""
Gold Tier — Facebook Integration
===================================
Posts to Facebook Pages and Profiles via Playwright browser automation.

Prerequisites:
    pip install playwright && playwright install chromium

Environment variables:
    FACEBOOK_EMAIL, FACEBOOK_PASSWORD

Usage:
    from integrations.social.facebook import FacebookPlatform

    fb = FacebookPlatform()
    result = fb.post("Exciting news from our team!")
    result = fb.post("New product!", media=[Path("photo.jpg")])
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

FACEBOOK_URL = "https://www.facebook.com/"
FACEBOOK_MOBILE_URL = "https://m.facebook.com/"
BROWSER_DATA_DIR = _PROJECT_ROOT / "integrations" / "social" / ".facebook_browser_data"


class FacebookPlatform(SocialPlatform):
    """Facebook posting via Playwright browser automation.

    Uses the mobile web interface (m.facebook.com) which has a simpler
    DOM structure and is more reliable for automation than the desktop
    React-based SPA.
    """

    platform_name = "facebook"
    char_limit = 63206
    rate_limit_per_day = 3

    def __init__(self) -> None:
        config.load()
        self.email = config.env("FACEBOOK_EMAIL", "")
        self.password = config.env("FACEBOOK_PASSWORD", "")

    def authenticate(self) -> bool:
        """Verify credentials are available."""
        if not self.email or not self.password:
            error_logger.log_error(
                "social.facebook",
                "Missing FACEBOOK_EMAIL or FACEBOOK_PASSWORD in .env",
            )
            return False
        return True

    def post(self, content: str, media: list[Path] | None = None) -> PostResult:
        """Publish a post to Facebook using Playwright.

        Supports text-only posts and posts with a single image.
        Uses m.facebook.com for a simpler, more stable DOM.
        """
        error = self.validate_content(content)
        if error:
            return PostResult(success=False, platform=self.platform_name, error=error)

        if not self.authenticate():
            return PostResult(
                success=False, platform=self.platform_name,
                error="Authentication failed — check FACEBOOK_EMAIL and FACEBOOK_PASSWORD",
            )

        # Verify media files if provided
        if media:
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
                    result = self._do_post(page, content, media)
                    return result
                finally:
                    context.close()

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            bus.emit("social.post.failed", {
                "platform": self.platform_name, "error": error_msg,
            })
            error_logger.log_error("social.facebook.post", e)
            return PostResult(
                success=False, platform=self.platform_name, error=error_msg,
            )

    def _do_post(self, page, content: str, media: list[Path] | None) -> PostResult:
        """Internal: execute the posting flow on the mobile FB page."""

        # Navigate to mobile Facebook feed
        page.goto(FACEBOOK_MOBILE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # Login if needed
        if self._needs_login(page):
            self._login(page)
            # Handle save-device redirect after login
            if "save-device" in page.url or "save_device" in page.url:
                page.goto(FACEBOOK_MOBILE_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

        # Open composer via JS click (bypasses pointer-event interception)
        clicked = page.evaluate(
            "var el = document.querySelector('[aria-label*=\"What\\'s on your mind\"]');"
            "if (el) { el.click(); return true; } return false;"
        )
        if not clicked:
            return PostResult(
                success=False, platform=self.platform_name,
                error="Could not open Facebook post composer",
            )
        page.wait_for_timeout(3000)

        # Find the text input (contenteditable div in composer)
        textarea = None
        for selector in ["[contenteditable='true']", "textarea", "[role='textbox']"]:
            loc = page.locator(selector).first
            if loc.count() > 0 and loc.is_visible():
                textarea = loc
                break

        if not textarea:
            return PostResult(
                success=False, platform=self.platform_name,
                error="Could not find Facebook text input area",
            )

        # Type the content
        textarea.click()
        textarea.type(content)
        page.wait_for_timeout(1000)

        # Upload media if provided
        if media:
            # Click "Photos" option to reveal file input
            photos_btn = page.get_by_text("Photos", exact=True).first
            if photos_btn.count() > 0 and photos_btn.is_visible():
                photos_btn.click()
                page.wait_for_timeout(2000)

            file_input = page.locator("input[type='file']").first
            if file_input.count() > 0:
                file_input.set_input_files(str(media[0]))
                page.wait_for_timeout(4000)

        # Click POST button (by visible text)
        posted = False
        post_btn = page.get_by_text("POST", exact=True).first
        if post_btn.count() > 0 and post_btn.is_visible():
            post_btn.evaluate("el => el.click()")
            posted = True

        if not posted:
            for lbl in ["Post", "Share", "Publish"]:
                btn = page.locator(f"[aria-label='{lbl}']").first
                if btn.count() > 0 and btn.is_visible():
                    btn.evaluate("el => el.click()")
                    posted = True
                    break

        if not posted:
            return PostResult(
                success=False, platform=self.platform_name,
                error="Could not find Facebook submit/post button",
            )

        # Wait for submission
        page.wait_for_timeout(5000)

        result = PostResult(
            success=True,
            platform=self.platform_name,
            content_length=len(content),
            metadata={"has_media": bool(media)},
        )

        bus.emit("social.post.success", {
            "platform": self.platform_name,
            "content_length": len(content),
            "has_media": bool(media),
        })
        error_logger.log_audit("social.post", "success", {
            "platform": self.platform_name,
            "content_length": len(content),
        })

        return result

    def _needs_login(self, page) -> bool:
        """Check if we need to log in."""
        url = page.url.lower()
        if "login" in url:
            return True
        login_form = page.locator("input[name='email'], #m_login_email").first
        return login_form.count() > 0

    def _login(self, page) -> None:
        """Perform Facebook login on the mobile site."""
        page.goto(f"{FACEBOOK_MOBILE_URL}login/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Fill email
        for sel in ["input[name='email']", "#m_login_email"]:
            field = page.locator(sel).first
            if field.count() > 0:
                field.fill(self.email)
                break

        # Fill password
        for sel in ["input[name='pass']", "#m_login_password"]:
            field = page.locator(sel).first
            if field.count() > 0:
                field.fill(self.password)
                break

        # Submit — try standard buttons, then JS-click the div login button
        submitted = False
        for sel in ["button[name='login']", "input[name='login']",
                    "button[type='submit']:not(.cancelButton):not([data-sigil*='cancel'])"]:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                submitted = True
                break

        if not submitted:
            # Facebook mobile uses a <div aria-label="لاگ ان کریں"> as the login button.
            # Find it by position: it is the first visible div[aria-label] that is NOT
            # an input field (email/password inputs also carry aria-label).
            page.evaluate(
                "var divs = Array.from(document.querySelectorAll('div[aria-label]'));"
                "var btn = divs.find(function(d) {"
                "  return d.offsetParent !== null && d.tagName === 'DIV';"
                "});"
                "if (btn) btn.click();"
                "else { var f = document.querySelector('form'); if (f) f.submit(); }"
            )

        page.wait_for_timeout(5000)

        # Dismiss "Save login info" or cookie banners
        for dismiss_text in ["Not Now", "OK", "Continue"]:
            try:
                btn = page.get_by_role("button", name=dismiss_text).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

    def get_metrics(self, post_id: str) -> MetricsResult:
        """Scrape basic engagement metrics from a Facebook post.

        Facebook's mobile web shows like/comment/share counts on posts.
        This attempts to read them via Playwright.
        """
        if not post_id:
            return MetricsResult(platform=self.platform_name, post_id=post_id)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return MetricsResult(platform=self.platform_name, post_id=post_id)

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(BROWSER_DATA_DIR),
                    headless=True,
                    viewport={"width": 414, "height": 896},
                    is_mobile=True,
                )
                page = context.new_page()

                try:
                    page.goto(
                        f"{FACEBOOK_MOBILE_URL}story.php?story_fbid={post_id}",
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_timeout(3000)

                    likes = self._extract_count(page, "like")
                    comments = self._extract_count(page, "comment")
                    shares = self._extract_count(page, "share")

                    return MetricsResult(
                        platform=self.platform_name,
                        post_id=post_id,
                        likes=likes,
                        comments=comments,
                        shares=shares,
                    )
                finally:
                    context.close()

        except Exception as e:
            error_logger.log_error("social.facebook.metrics", e, {"post_id": post_id})
            return MetricsResult(platform=self.platform_name, post_id=post_id)

    @staticmethod
    def _extract_count(page, metric_type: str) -> int:
        """Try to extract a numeric count from the post engagement area."""
        import re

        try:
            text = page.locator("body").inner_text()
            patterns = {
                "like": r"(\d+)\s*(?:likes?|reactions?)",
                "comment": r"(\d+)\s*comments?",
                "share": r"(\d+)\s*shares?",
            }
            pattern = patterns.get(metric_type, "")
            if pattern:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        return 0
