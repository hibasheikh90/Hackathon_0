"""
LinkedIn Login Helper
======================
Opens a visible browser, logs you into LinkedIn, and saves the session.
Run this ONCE to clear security challenges, then posting works headless.

Usage:
    python scripts/linkedin_login.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config_loader import config
from playwright.sync_api import sync_playwright

BROWSER_DATA_DIR = _PROJECT_ROOT / "integrations" / "social" / ".linkedin_browser_data"


def main():
    config.load()
    email = config.env("LINKEDIN_EMAIL", "")
    password = config.env("LINKEDIN_PASSWORD", "")

    if not email or not password:
        print("[ERROR] Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env")
        return

    print("Opening LinkedIn in a visible browser...")
    print("1. Complete any security challenge that appears")
    print("2. Once you see the feed, press Enter here to save the session")
    print()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        # Fill credentials if on login page
        if "login" in page.url:
            try:
                page.fill("#username", email)
                page.fill("#password", password)
                page.click("button[type='submit']")
            except Exception:
                print("Could not auto-fill. Please log in manually in the browser.")

        print()
        print(">>> Complete any verification in the browser window <<<")
        print(">>> Then press ENTER here once you see the LinkedIn feed <<<")
        input()

        current_url = page.url
        print(f"Current URL: {current_url}")

        if "/feed" in current_url:
            print("[OK] Login successful! Session saved.")
            print("You can now run LinkedIn posting in headless mode.")
        else:
            print(f"[WARN] Not on feed page ({current_url}). Try again.")

        context.close()


if __name__ == "__main__":
    main()
