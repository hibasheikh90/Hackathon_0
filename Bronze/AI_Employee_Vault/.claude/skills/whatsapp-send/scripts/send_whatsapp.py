"""
Skill: whatsapp-send
Sends WhatsApp messages using Playwright browser automation via WhatsApp Web.
Uses persistent browser state to keep the QR code session alive across runs.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[ERROR] Playwright is not installed.")
    print("        Run: pip install playwright && playwright install chromium")
    sys.exit(1)

_script_dir = Path(__file__).resolve().parent

WHATSAPP_WEB_URL = "https://web.whatsapp.com"
USER_DATA_DIR = _script_dir / ".browser_data"


def is_logged_in(page) -> bool:
    """Check if WhatsApp Web is already authenticated."""
    page.goto(WHATSAPP_WEB_URL, wait_until="domcontentloaded")
    # Wait up to 15s for either the chat list or the QR code to appear
    try:
        page.wait_for_selector(
            '[aria-label="Search input textbox"], [data-ref]',
            timeout=15000,
        )
    except PlaywrightTimeout:
        return False

    # If the search box is present, we're logged in
    search = page.locator('[aria-label="Search input textbox"]')
    return search.count() > 0


def wait_for_login(page) -> None:
    """Wait for the user to scan the QR code."""
    print("[INFO] QR code displayed — scan it with your phone.")
    print("       Open WhatsApp > Settings > Linked Devices > Link a Device")
    try:
        page.wait_for_selector(
            '[aria-label="Search input textbox"]',
            timeout=120000,
        )
        print("[INFO] WhatsApp Web authenticated.")
    except PlaywrightTimeout:
        print("[ERROR] Timed out waiting for QR code scan (2 minutes).")
        sys.exit(1)


def _find_editor(page):
    """Find the message input box."""
    selectors = [
        '[aria-label="Type a message"]',
        'div[contenteditable="true"][data-tab="10"]',
        'footer div[contenteditable="true"]',
        'div[contenteditable="true"]',
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def open_chat(page, phone: str) -> None:
    """Open a chat with the given phone number using the wa.me deep link."""
    # Strip any non-digit characters
    clean_number = "".join(c for c in phone if c.isdigit())
    url = f"https://web.whatsapp.com/send?phone={clean_number}"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # Check if WhatsApp shows an "invalid phone" popup
    invalid = page.locator("text=Phone number shared via url is invalid")
    if invalid.count() > 0:
        print(f"[ERROR] Invalid phone number: {phone}")
        sys.exit(1)

    # Wait for the message input to appear (chat loaded)
    editor = None
    for _ in range(3):
        editor = _find_editor(page)
        if editor:
            break
        page.wait_for_timeout(3000)

    if editor is None:
        screenshot_path = str(_script_dir / "debug_chat.png")
        page.screenshot(path=screenshot_path)
        print(f"[DEBUG] Screenshot saved to {screenshot_path}")
        print("[ERROR] Could not open chat. Make sure the phone number is correct")
        print(f"        (include country code, e.g. +923001234567).")
        sys.exit(1)


def send_message(page, message: str, dry_run: bool = False) -> None:
    """Type and send a message in the currently open chat."""
    editor = _find_editor(page)
    if editor is None:
        print("[ERROR] Message input not found.")
        sys.exit(1)

    editor.click()
    editor.fill(message)
    page.wait_for_timeout(1000)

    if dry_run:
        screenshot_path = str(_script_dir / "debug_dryrun.png")
        page.screenshot(path=screenshot_path)
        print(f"[DEBUG] Screenshot saved to {screenshot_path}")
        print("[DRY-RUN] Message composed but not sent.")
        print(f"  Preview: {message[:100]}{'...' if len(message) > 100 else ''}")
        return

    # Click the send button
    send_btn_selectors = [
        '[aria-label="Send"]',
        'button[aria-label="Send"]',
        'span[data-icon="send"]',
    ]

    sent = False
    for sel in send_btn_selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                sent = True
                break
        except Exception:
            continue

    if not sent:
        # Fallback: press Enter to send
        page.keyboard.press("Enter")

    page.wait_for_timeout(2000)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[OK] WhatsApp message sent successfully")
    print(f"  Length: {len(message)} characters")
    print(f"  Timestamp: {timestamp}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a WhatsApp message via WhatsApp Web.")
    parser.add_argument("--phone", required=True, help="Recipient phone number with country code (e.g. +923001234567)")
    parser.add_argument("--message", required=True, help="Message text to send")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (not recommended for first run)")
    parser.add_argument("--dry-run", action="store_true", help="Compose message without sending")
    args = parser.parse_args()

    if not args.message.strip():
        print("[ERROR] Message cannot be empty.")
        sys.exit(1)

    with sync_playwright() as p:
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
                wait_for_login(page)

            open_chat(page, args.phone)
            send_message(page, args.message, dry_run=args.dry_run)
        except PlaywrightTimeout as e:
            screenshot_path = str(_script_dir / "debug_timeout.png")
            try:
                page.screenshot(path=screenshot_path)
                print(f"[DEBUG] Screenshot saved to {screenshot_path}")
            except Exception:
                pass
            print(f"[ERROR] Timeout during WhatsApp automation: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] WhatsApp message failed: {e}")
            sys.exit(1)
        finally:
            context.close()


if __name__ == "__main__":
    main()
