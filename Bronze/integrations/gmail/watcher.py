"""
Gold Tier — Gmail IMAP Watcher
================================
Monitors Gmail inbox via IMAP and routes new emails to vault/Inbox/
so the triage pipeline picks them up automatically.

Prerequisites:
    Enable IMAP in Gmail settings.
    Use App Password (same as EMAIL_PASSWORD).

Usage:
    from integrations.gmail.watcher import GmailWatcher

    watcher = GmailWatcher()
    new_count = watcher.check_new()   # called by Gold scheduler every 5 min
"""

from __future__ import annotations

import email
import email.header
import imaplib
import json
import re
import sys
from datetime import datetime
from email.message import Message
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"

# State: track which email UIDs we've already processed
STATE_FILE = _PROJECT_ROOT / "core" / ".gmail_watcher_state.json"


def _decode_header(raw: str | None) -> str:
    """Decode an email header value (handles encoded-word syntax)."""
    if not raw:
        return ""
    decoded_parts = email.header.decode_header(raw)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _extract_body(msg: Message) -> str:
    """Extract plain-text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: try HTML
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Strip HTML tags for vault file
                    return re.sub(r"<[^>]+>", "", html).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")

    return "(no body)"


def _safe_filename(text: str, max_length: int = 60) -> str:
    """Convert a string to a safe filename."""
    safe = re.sub(r"[^\w\s\-]", "", text)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_length] if safe else "email"


class GmailWatcher:
    """IMAP watcher that routes new emails to the Obsidian vault."""

    def __init__(self) -> None:
        config.load()
        self.address = config.env("EMAIL_ADDRESS", "")
        self.password = config.env("EMAIL_PASSWORD", "")
        self._seen_uids: set[str] = self._load_state()

    def is_configured(self) -> bool:
        return bool(self.address and self.password)

    def check_new(self, folder: str = "INBOX", max_fetch: int = 20) -> int:
        """Check for new emails and create vault files.

        Returns the number of new emails processed.
        """
        if not self.is_configured():
            return 0

        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        count = 0

        try:
            conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            conn.login(self.address, self.password)
            conn.select(folder, readonly=True)

            # Search for unseen messages
            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data[0]:
                conn.close()
                conn.logout()
                return 0

            uids = data[0].split()
            # Only process the most recent ones
            uids_to_check = uids[-max_fetch:]

            for uid_bytes in uids_to_check:
                uid = uid_bytes.decode("utf-8")
                if uid in self._seen_uids:
                    continue

                status, msg_data = conn.fetch(uid_bytes, "(RFC822)")
                if status != "OK" or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = _decode_header(msg.get("Subject"))
                sender = _decode_header(msg.get("From"))
                date_str = _decode_header(msg.get("Date"))
                body = _extract_body(msg)

                # Create vault file
                safe_subj = _safe_filename(subject)
                vault_file = INBOX_DIR / f"gmail_{safe_subj}.md"

                # Avoid overwrites
                if vault_file.exists():
                    vault_file = INBOX_DIR / f"gmail_{safe_subj}_{uid}.md"

                vault_content = f"""# {subject}

## Email Metadata
- **From:** {sender}
- **Date:** {date_str}
- **Subject:** {subject}
- **Source:** Gmail IMAP (auto-import)

## Body
{body}

## Agent Notes
- Imported by Gmail Watcher at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

                try:
                    vault_file.write_text(vault_content, encoding="utf-8")
                    self._seen_uids.add(uid)
                    count += 1

                    bus.emit("email.received", {
                        "from": sender,
                        "subject": subject,
                        "file": vault_file.name,
                    })
                    error_logger.log_audit("gmail.watcher", "imported", {
                        "from": sender, "subject": subject, "file": vault_file.name,
                    })
                except OSError as e:
                    error_logger.log_error("gmail.watcher.write", e, {
                        "subject": subject,
                    })

            conn.close()
            conn.logout()

        except imaplib.IMAP4.error as e:
            error_logger.log_error("gmail.watcher.imap", e)
        except Exception as e:
            error_logger.log_error("gmail.watcher", e)

        self._save_state()
        return count

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> set[str]:
        if STATE_FILE.is_file():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                return set(data.get("seen_uids", []))
            except (json.JSONDecodeError, OSError):
                pass
        return set()

    def _save_state(self) -> None:
        try:
            STATE_FILE.write_text(
                json.dumps({"seen_uids": sorted(self._seen_uids)}),
                encoding="utf-8",
            )
        except OSError:
            pass
