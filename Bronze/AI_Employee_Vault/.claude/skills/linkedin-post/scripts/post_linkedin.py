"""
Skill: linkedin-post
Creates real LinkedIn text posts using Playwright browser automation.
Uses persistent browser state to avoid repeated login challenges.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env from Bronze directory (walk up from this script to find it)
_script_dir = Path(__file__).resolve().parent
for _parent in _script_dir.parents:
    _env_path = _parent / ".env"
    if _env_path.is_file():
        load_dotenv(_env_path)
        break

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[ERROR] Playwright is not installed.")
    print("        Run: pip install playwright && playwright install chromium")
    sys.exit(1)

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
POST_CHAR_LIMIT = 3000
# Persistent browser data directory (keeps cookies/session across runs)
USER_DATA_DIR = _script_dir / ".browser_data"


def get_credentials() -> tuple[str, str]:
    email = os.environ.get("LINKEDIN_EMAIL", "").strip()
    password = os.environ.get("LINKEDIN_PASSWORD", "").strip()

    if not email:
        print("[ERROR] LINKEDIN_EMAIL environment variable is not set.")
        sys.exit(1)
    if not password:
        print("[ERROR] LINKEDIN_PASSWORD environment variable is not set.")
        sys.exit(1)

    return email, password


def validate_content(content: str) -> None:
    if not content.strip():
        print("[ERROR] Post content cannot be empty.")
        sys.exit(1)
    if len(content) > POST_CHAR_LIMIT:
        print(f"[ERROR] Post exceeds {POST_CHAR_LIMIT} characters ({len(content)} given).")
        sys.exit(1)


def is_logged_in(page) -> bool:
    """Check if we're already logged in by navigating to the feed."""
    page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    return "/feed" in page.url and "login" not in page.url


def login(page, email: str, password: str) -> None:
    print("[INFO] Logging in to LinkedIn...")
    page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    page.fill("#username", email)
    page.fill("#password", password)
    page.click("button[type='submit']")

    # Wait for feed to confirm login succeeded
    try:
        page.wait_for_url("**/feed/**", timeout=60000)
        print("[INFO] Login successful.")
    except PlaywrightTimeout:
        screenshot_path = str(_script_dir / "debug_login.png")
        page.screenshot(path=screenshot_path)
        print(f"[DEBUG] Screenshot saved to {screenshot_path}")
        if "checkpoint" in page.url.lower() or "challenge" in page.url.lower():
            print("[ERROR] LinkedIn security challenge detected.")
            print("        The browser window should be open — complete the")
            print("        verification manually, then re-run this script.")
            sys.exit(1)
        print("[ERROR] Login failed — did not reach the feed.")
        print(f"        Current URL: {page.url}")
        sys.exit(1)


def _find_editor(page):
    """Try to find the post editor on the current page."""
    editor_selectors = [
        "[role='textbox'][contenteditable='true']",
        "[contenteditable='true'][data-placeholder]",
        ".ql-editor[contenteditable='true']",
        "div[contenteditable='true']",
    ]
    for sel in editor_selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def _try_open_composer(page) -> bool:
    """Attempt to open the post composer modal. Returns True if editor found."""
    # Attempt 1: click button containing "Start a post"
    try:
        btn = page.locator("button").filter(has_text="Start a post").first
        if btn.count() > 0:
            btn.click(force=True, timeout=5000)
            page.wait_for_timeout(3000)
            if _find_editor(page):
                return True
    except Exception:
        pass

    # Attempt 2: click by exact text
    try:
        page.get_by_text("Start a post").first.click(force=True, timeout=5000)
        page.wait_for_timeout(3000)
        if _find_editor(page):
            return True
    except Exception:
        pass

    # Attempt 3: use keyboard shortcut / tab + enter
    try:
        page.keyboard.press("Tab")
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
        if _find_editor(page):
            return True
    except Exception:
        pass

    return False


def create_post(page, content: str, dry_run: bool = False) -> None:
    print("[INFO] Opening post composer...")

    # Retry loop — LinkedIn's feed is dynamic and sometimes needs multiple attempts
    editor = None
    for attempt in range(3):
        # Navigate to the feed fresh each attempt
        page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        # Scroll to top to ensure share box is visible
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)

        # Check if editor is already open
        editor = _find_editor(page)
        if editor:
            print(f"[DEBUG] Editor found immediately (attempt {attempt + 1})")
            break

        # Try to open the composer
        if _try_open_composer(page):
            editor = _find_editor(page)
            if editor:
                print(f"[DEBUG] Editor found after click (attempt {attempt + 1})")
                break

        print(f"[DEBUG] Attempt {attempt + 1} failed, retrying...")

    if editor is None:
        screenshot_path = str(_script_dir / "debug_editor.png")
        page.screenshot(path=screenshot_path)
        print(f"[DEBUG] Screenshot saved to {screenshot_path}")
        print("[ERROR] Could not open the post editor after 3 attempts.")
        sys.exit(1)

    # Type the post content
    editor.click()
    editor.fill(content)
    page.wait_for_timeout(1000)
    print(f"[INFO] Post content entered ({len(content)} chars).")

    if dry_run:
        screenshot_path = str(_script_dir / "debug_dryrun.png")
        page.screenshot(path=screenshot_path)
        print(f"[DEBUG] Screenshot saved to {screenshot_path}")
        print("[DRY-RUN] Post composed but not published.")
        print(f"  Content preview: {content[:100]}{'...' if len(content) > 100 else ''}")
        return

    # Click the Post / Publish button
    post_btn = page.locator("button.share-actions__primary-action")
    if post_btn.count() == 0:
        post_btn = page.get_by_role("button", name="Post", exact=True)

    post_btn.click()

    # Wait for the modal to close, confirming the post was sent
    try:
        editor.wait_for(state="hidden", timeout=15000)
    except PlaywrightTimeout:
        print("[WARN] Could not confirm post was published. Check LinkedIn manually.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[OK] LinkedIn post published successfully")
    print(f"  Length: {len(content)} characters")
    print(f"  Timestamp: {timestamp}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a text post to LinkedIn.")
    parser.add_argument("--content", required=True, help="Text content for the LinkedIn post")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--dry-run", action="store_true", help="Compose post without publishing")
    args = parser.parse_args()

    email, password = get_credentials()
    validate_content(args.content)

    with sync_playwright() as p:
        # Use persistent context to keep cookies/session across runs
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=args.headless,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            if is_logged_in(page):
                print("[INFO] Already logged in (session restored).")
            else:
                login(page, email, password)

            create_post(page, args.content, dry_run=args.dry_run)
        except PlaywrightTimeout as e:
            screenshot_path = str(_script_dir / "debug_timeout.png")
            try:
                page.screenshot(path=screenshot_path)
                print(f"[DEBUG] Screenshot saved to {screenshot_path}")
            except Exception:
                pass
            print(f"[ERROR] Timeout during LinkedIn automation: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] LinkedIn post failed: {e}")
            sys.exit(1)
        finally:
            context.close()


if __name__ == "__main__":
    main()
