"""
Gmail Watcher — IMAP poller for the AI Employee pipeline.

Connects to Gmail via IMAP, fetches UNSEEN emails, and creates .md files
in vault/Inbox/ for the scheduler to triage.

Modes:
  --once     Single poll then exit
  --daemon   Continuous polling every N seconds

Usage:
  python scripts/gmail_watcher.py --once
  python scripts/gmail_watcher.py --daemon --interval 60
"""

import argparse
import email
import email.header
import email.utils
import imaplib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Load .env (walk up from script dir, same pattern as send_email.py)
try:
    from dotenv import load_dotenv
    for _parent in [SCRIPT_DIR] + list(SCRIPT_DIR.parents):
        _env = _parent / ".env"
        if _env.is_file():
            load_dotenv(_env)
            break
except ImportError:
    pass  # dotenv not installed, rely on environment variables

# Vault paths
_ai_vault = PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"

STATE_FILE = SCRIPT_DIR / ".gmail_watcher_state.json"

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


# ---------------------------------------------------------------------------
# State persistence — tracks processed email UIDs
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"processed_uids": [], "last_poll": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def decode_header_value(raw: str) -> str:
    """Decode an RFC 2047 encoded header value."""
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def sanitize_filename(text: str) -> str:
    """Create a safe filename from text."""
    clean = re.sub(r"[^\w\s-]", "", text)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean[:60] if clean else "no_subject"


def extract_body(msg: email.message.Message) -> str:
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback to text/html if no text/plain
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/html" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Strip HTML tags for a rough plain-text version
                    text = re.sub(r"<[^>]+>", " ", html)
                    text = re.sub(r"\s+", " ", text).strip()
                    return text
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return "(no body content)"


def list_attachments(msg: email.message.Message) -> list[str]:
    """List attachment filenames without downloading."""
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                fname = part.get_filename()
                if fname:
                    attachments.append(decode_header_value(fname))
    return attachments


# ---------------------------------------------------------------------------
# Core: poll Gmail INBOX for unseen emails
# ---------------------------------------------------------------------------
def poll_inbox(email_address: str, email_password: str, state: dict) -> int:
    """Poll Gmail for unseen emails and create .md files. Returns count of new emails."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    processed_uids = set(state.get("processed_uids", []))
    new_count = 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(email_address, email_password)
        mail.select("INBOX")
    except imaplib.IMAP4.error as e:
        print(f"[ERROR] IMAP login failed: {e}")
        print("        Make sure you are using a Gmail App Password.")
        return 0
    except OSError as e:
        print(f"[ERROR] Connection failed: {e}")
        return 0

    try:
        # Search for UNSEEN (unread) emails
        status, data = mail.search(None, "UNSEEN")
        if status != "OK":
            print("[WARN] IMAP search failed")
            return 0

        uid_list = data[0].split()
        if not uid_list:
            print("[INFO] No unread emails found")
            return 0

        print(f"[INFO] Found {len(uid_list)} unread email(s)")

        for uid_bytes in uid_list:
            uid = uid_bytes.decode()
            if uid in processed_uids:
                continue

            # Fetch the email
            status, msg_data = mail.fetch(uid_bytes, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Parse headers
            subject = decode_header_value(msg.get("Subject", "(no subject)"))
            from_addr = decode_header_value(msg.get("From", "unknown"))
            date_str = msg.get("Date", "")
            parsed_date = email.utils.parsedate_to_datetime(date_str) if date_str else datetime.now()
            date_display = parsed_date.strftime("%Y-%m-%d %H:%M:%S")

            # Extract body and attachments
            body = extract_body(msg)
            attachments = list_attachments(msg)

            # Truncate very long bodies
            if len(body) > 5000:
                body = body[:5000] + "\n\n... (truncated)"

            # Build markdown file
            safe_subject = sanitize_filename(subject)
            filename = f"gmail_{safe_subject}.md"
            filepath = INBOX_DIR / filename

            # Avoid overwriting existing files
            if filepath.exists():
                counter = 2
                while True:
                    filename = f"gmail_{safe_subject}_{counter}.md"
                    filepath = INBOX_DIR / filename
                    if not filepath.exists():
                        break
                    counter += 1

            attachment_section = ""
            if attachments:
                att_list = "\n".join(f"  - {a}" for a in attachments)
                attachment_section = f"\n- **Attachments:**\n{att_list}"

            md_content = f"""# {subject}

## Metadata
- **From:** {from_addr}
- **Date:** {date_display}
- **Source:** Gmail IMAP
- **UID:** {uid}{attachment_section}

## Body
{body}
"""
            filepath.write_text(md_content, encoding="utf-8")
            print(f"  [NEW] {filename}")

            # Mark as read (add SEEN flag)
            mail.store(uid_bytes, "+FLAGS", "\\Seen")

            processed_uids.add(uid)
            new_count += 1

    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass

    # Update state
    state["processed_uids"] = list(processed_uids)
    state["last_poll"] = datetime.now().isoformat()
    return new_count


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
def get_credentials() -> tuple[str, str]:
    address = os.environ.get("EMAIL_ADDRESS", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()
    if not address:
        print("[ERROR] EMAIL_ADDRESS environment variable is not set.")
        sys.exit(1)
    if not password:
        print("[ERROR] EMAIL_PASSWORD environment variable is not set.")
        print("        Use a Gmail App Password: https://myaccount.google.com/apppasswords")
        sys.exit(1)
    return address, password


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Poll Gmail for unread emails and create vault tasks.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Poll once and exit")
    mode.add_argument("--daemon", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between polls in daemon mode (default: 60)")
    args = parser.parse_args()

    address, password = get_credentials()
    state = load_state()

    if args.once:
        count = poll_inbox(address, password, state)
        save_state(state)
        print(f"[OK] Gmail poll complete: {count} new email(s) ingested")
    elif args.daemon:
        print(f"[INFO] Gmail watcher started (interval: {args.interval}s). Ctrl+C to stop.")
        try:
            while True:
                count = poll_inbox(address, password, state)
                save_state(state)
                print(f"[OK] Poll complete: {count} new | Next poll in {args.interval}s")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            save_state(state)
            print("\n[INFO] Gmail watcher stopped.")


if __name__ == "__main__":
    main()
