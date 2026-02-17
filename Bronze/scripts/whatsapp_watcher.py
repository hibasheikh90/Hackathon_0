"""
WhatsApp Watcher — Playwright poller for the AI Employee pipeline.

Uses Playwright with persistent browser context to check WhatsApp Web
for unread messages and creates .md files in vault/Inbox/.

Reuses .browser_data/ from the whatsapp-send skill (no second QR scan).

Modes:
  --once     Single check then exit
  --daemon   Continuous polling every N seconds

Usage:
  python scripts/whatsapp_watcher.py --once
  python scripts/whatsapp_watcher.py --daemon --interval 120
  python scripts/whatsapp_watcher.py --once --headless
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[ERROR] Playwright is not installed.")
    print("        Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Vault paths
_ai_vault = PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"

# Reuse whatsapp-send browser data (already authenticated)
BROWSER_DATA_DIR = (
    PROJECT_ROOT / "AI_Employee_Vault" / ".claude" / "skills"
    / "whatsapp-send" / "scripts" / ".browser_data"
)

STATE_FILE = SCRIPT_DIR / ".whatsapp_watcher_state.json"
WHATSAPP_WEB_URL = "https://web.whatsapp.com"


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"processed_messages": [], "last_poll": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sanitize_filename(text: str) -> str:
    """Create a safe filename from text."""
    clean = re.sub(r"[^\w\s-]", "", text)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean[:40] if clean else "unknown"


def make_message_key(contact: str, message: str) -> str:
    """Create a unique key for deduplication."""
    short_msg = message[:80] if message else ""
    return f"{contact}::{short_msg}"


# ---------------------------------------------------------------------------
# Core: check WhatsApp Web for unread messages
# ---------------------------------------------------------------------------
def check_unread(headless: bool, state: dict) -> int:
    """Open WhatsApp Web, find unread chats, create .md files. Returns count."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    processed = set(state.get("processed_messages", []))
    new_count = 0

    if not BROWSER_DATA_DIR.is_dir():
        print("[ERROR] WhatsApp browser data not found at:")
        print(f"        {BROWSER_DATA_DIR}")
        print("        Run the whatsapp-send skill first to authenticate.")
        return 0

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            # Navigate to WhatsApp Web
            page.goto(WHATSAPP_WEB_URL, wait_until="domcontentloaded")

            # Wait for either the chat list or QR code
            try:
                page.wait_for_selector(
                    '[aria-label="Search input textbox"], [data-ref]',
                    timeout=20000,
                )
            except PlaywrightTimeout:
                print("[ERROR] WhatsApp Web did not load in time.")
                return 0

            # Check if logged in
            search = page.locator('[aria-label="Search input textbox"]')
            if search.count() == 0:
                print("[ERROR] Not logged in to WhatsApp Web.")
                print("        Run whatsapp-send skill first to scan QR code.")
                return 0

            print("[INFO] WhatsApp Web loaded. Scanning for unread chats...")

            # Wait for chat list to fully render
            page.wait_for_timeout(3000)

            # Find unread chat indicators (badge with unread count)
            # WhatsApp uses spans with aria-label containing unread count
            unread_badges = page.locator(
                'span[aria-label*="unread message"], '
                'span[aria-label*="unread messages"]'
            )
            badge_count = unread_badges.count()

            if badge_count == 0:
                print("[INFO] No unread messages found")
                return 0

            print(f"[INFO] Found {badge_count} chat(s) with unread messages")

            # Process each unread chat
            for i in range(min(badge_count, 10)):  # Cap at 10 chats per poll
                try:
                    badge = unread_badges.nth(i)

                    # Navigate up to the chat list item to get the contact name
                    # The chat row is typically a few levels up from the badge
                    chat_row = badge.locator("xpath=ancestor::div[@role='listitem' or @data-testid='cell-frame-container' or contains(@class, 'chat')]").first

                    if chat_row.count() == 0:
                        # Fallback: try parent traversal
                        chat_row = badge.locator("xpath=ancestor::div[contains(@class, '_')]").nth(4)

                    # Extract contact name from the chat row
                    # Contact names are typically in a span with a title attribute
                    name_el = chat_row.locator("span[title]").first
                    if name_el.count() > 0:
                        contact = name_el.get_attribute("title") or "Unknown"
                    else:
                        contact = f"Chat_{i+1}"

                    # Extract last message preview
                    # The message preview is typically in a span within the chat row
                    msg_preview_el = chat_row.locator("span[title]").nth(1)
                    if msg_preview_el.count() > 0:
                        last_message = msg_preview_el.get_attribute("title") or ""
                    else:
                        # Try to get any text from the lower part of the chat row
                        last_message = "(message preview unavailable)"

                    # Deduplication
                    msg_key = make_message_key(contact, last_message)
                    if msg_key in processed:
                        continue

                    # Create inbox file
                    safe_contact = sanitize_filename(contact)
                    keyword = sanitize_filename(last_message[:20]) if last_message else "msg"
                    filename = f"wa_{safe_contact}_{keyword}.md"
                    filepath = INBOX_DIR / filename

                    # Avoid overwriting
                    if filepath.exists():
                        counter = 2
                        while True:
                            filename = f"wa_{safe_contact}_{keyword}_{counter}.md"
                            filepath = INBOX_DIR / filename
                            if not filepath.exists():
                                break
                            counter += 1

                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    md_content = f"""# WhatsApp Message from {contact}

## Metadata
- **From:** {contact}
- **Date:** {now_str}
- **Source:** WhatsApp Web
- **Type:** Incoming message

## Message
{last_message}
"""
                    filepath.write_text(md_content, encoding="utf-8")
                    print(f"  [NEW] {filename}")

                    processed.add(msg_key)
                    new_count += 1

                except Exception as e:
                    print(f"  [WARN] Could not process chat #{i+1}: {e}")
                    continue

        except PlaywrightTimeout as e:
            print(f"[ERROR] Timeout during WhatsApp polling: {e}")
        except Exception as e:
            print(f"[ERROR] WhatsApp watcher failed: {e}")
        finally:
            context.close()

    # Update state
    state["processed_messages"] = list(processed)
    state["last_poll"] = datetime.now().isoformat()
    return new_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Poll WhatsApp Web for unread messages and create vault tasks.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Check once and exit")
    mode.add_argument("--daemon", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=120, help="Seconds between polls in daemon mode (default: 120)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    state = load_state()

    if args.once:
        count = check_unread(args.headless, state)
        save_state(state)
        print(f"[OK] WhatsApp poll complete: {count} new message(s) ingested")
    elif args.daemon:
        print(f"[INFO] WhatsApp watcher started (interval: {args.interval}s). Ctrl+C to stop.")
        try:
            while True:
                count = check_unread(args.headless, state)
                save_state(state)
                print(f"[OK] Poll complete: {count} new | Next poll in {args.interval}s")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            save_state(state)
            print("\n[INFO] WhatsApp watcher stopped.")


if __name__ == "__main__":
    main()
