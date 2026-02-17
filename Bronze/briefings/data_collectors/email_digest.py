"""
Gold Tier — Email Digest Collector
=====================================
Summarizes email activity from vault Gmail imports and audit logs
for the CEO briefing.

Metrics:
    - Emails sent this week
    - Emails received (imported to vault)
    - Average response time (estimate)
    - Key threads (high-priority email subjects)

Usage:
    from briefings.data_collectors.email_digest import collect

    data = collect()
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
DONE_DIR = VAULT_DIR / "Done"

# Audit log for sent email counts
AUDIT_LOG = _PROJECT_ROOT / "logs" / "audit.log"


def _count_gmail_vault_files(since: datetime) -> list[dict]:
    """Find gmail_*.md files across all vault stages, modified since cutoff."""
    files = []
    since_ts = since.timestamp()

    for stage_dir in (INBOX_DIR, NEEDS_ACTION_DIR, DONE_DIR):
        if not stage_dir.is_dir():
            continue
        for f in stage_dir.iterdir():
            if not f.name.startswith("gmail_") or f.suffix != ".md":
                continue
            if f.stat().st_mtime < since_ts:
                continue

            # Extract subject and sender from file
            subject = f.stem.replace("gmail_", "").replace("_", " ")
            sender = ""
            try:
                content = f.read_text(encoding="utf-8")
                subj_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                if subj_match:
                    subject = subj_match.group(1).strip()
                from_match = re.search(r"\*\*From:\*\*\s*(.+)", content)
                if from_match:
                    sender = from_match.group(1).strip()
            except OSError:
                pass

            files.append({
                "file": f.name,
                "subject": subject,
                "from": sender,
                "stage": stage_dir.name,
            })

    return files


def _count_sent_emails(since: datetime) -> int:
    """Count emails sent by reading audit log entries."""
    if not AUDIT_LOG.is_file():
        return 0

    count = 0
    since_str = since.isoformat()

    try:
        for line in AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("action") != "gmail.send":
                continue
            if record.get("status") != "success":
                continue
            ts = record.get("ts", "")
            if ts >= since_str:
                count += 1
    except OSError:
        pass

    return count


def _identify_key_threads(emails: list[dict], max_threads: int = 5) -> list[dict]:
    """Identify key email threads worth highlighting in the briefing.

    Prioritizes emails still in Needs_Action (unresolved) and those
    with keywords suggesting importance.
    """
    priority_keywords = [
        "invoice", "payment", "contract", "urgent", "deadline",
        "proposal", "renewal", "overdue", "meeting", "approval",
    ]

    scored = []
    for email_info in emails:
        score = 0
        subject_lower = email_info["subject"].lower()

        # Boost unresolved emails
        if email_info["stage"] == "Needs_Action":
            score += 3
        elif email_info["stage"] == "Inbox":
            score += 2

        # Boost priority keywords
        for kw in priority_keywords:
            if kw in subject_lower:
                score += 2

        scored.append((score, email_info))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "subject": item["subject"],
            "from": item["from"],
            "status": "Awaiting action" if item["stage"] in ("Inbox", "Needs_Action") else "Resolved",
        }
        for _, item in scored[:max_threads]
    ]


def collect(weeks_back: int = 1) -> dict:
    """Collect email activity digest for the CEO briefing.

    Returns a dict with:
        emails_received, emails_sent, key_threads,
        avg_response_hours
    """
    cutoff = datetime.now() - timedelta(weeks=weeks_back)

    # Received emails (Gmail imports to vault)
    received_emails = _count_gmail_vault_files(cutoff)
    emails_received = len(received_emails)

    # Sent emails (from audit log)
    emails_sent = _count_sent_emails(cutoff)

    # Key threads
    key_threads = _identify_key_threads(received_emails)

    # Response time estimate: based on how quickly emails moved from
    # Inbox to Needs_Action/Done (rough proxy)
    avg_response_hours = None
    # This would require timestamp comparison between import and triage
    # For now, report as N/A — can be refined once we have more data

    result = {
        "emails_received": emails_received,
        "emails_sent": emails_sent,
        "key_threads": key_threads,
        "avg_response_hours": avg_response_hours,
    }

    error_logger.log_audit("briefing.collector.email_digest", "success", {
        "received": emails_received,
        "sent": emails_sent,
        "threads": len(key_threads),
    })

    return result
