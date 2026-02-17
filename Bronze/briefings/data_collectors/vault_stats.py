"""
Gold Tier — Vault Stats Collector
===================================
Collects task pipeline metrics from the Obsidian vault for the CEO briefing.

Metrics:
    - New tasks received this week
    - Tasks completed this week
    - Current backlog (Needs_Action)
    - Average time from Inbox to Done (SLA)

Usage:
    from briefings.data_collectors.vault_stats import collect

    data = collect(weeks_back=1)
"""

from __future__ import annotations

import os
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


def _count_md_files(directory: Path) -> int:
    """Count .md files in a directory."""
    if not directory.is_dir():
        return 0
    return sum(1 for f in directory.iterdir() if f.suffix == ".md")


def _files_modified_since(directory: Path, since: datetime) -> list[Path]:
    """Return .md files modified on or after *since*."""
    if not directory.is_dir():
        return []
    results = []
    since_ts = since.timestamp()
    for f in directory.iterdir():
        if f.suffix == ".md" and f.stat().st_mtime >= since_ts:
            results.append(f)
    return results


def _extract_received_timestamp(content: str) -> datetime | None:
    """Try to extract a 'Received:' timestamp from file metadata."""
    match = re.search(r"\*\*Received:\*\*\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", content)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return None


def _compute_avg_completion_time(done_files: list[Path]) -> float | None:
    """Compute average hours from Received timestamp to file mtime (completion).

    Returns None if no files have parsable timestamps.
    """
    durations = []
    for f in done_files:
        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue
        received = _extract_received_timestamp(content)
        if received is None:
            continue
        completed = datetime.fromtimestamp(f.stat().st_mtime)
        delta = (completed - received).total_seconds()
        if delta >= 0:
            durations.append(delta / 3600)  # convert to hours

    if not durations:
        return None
    return round(sum(durations) / len(durations), 1)


def collect(weeks_back: int = 1) -> dict:
    """Collect vault statistics for the weekly CEO briefing.

    Returns a dict with keys:
        inbox_count, needs_action_count, done_this_week,
        new_this_week, backlog, avg_completion_hours,
        high_priority_items
    """
    now = datetime.now()
    cutoff = now - timedelta(weeks=weeks_back)

    inbox_count = _count_md_files(INBOX_DIR)
    needs_action_count = _count_md_files(NEEDS_ACTION_DIR)

    done_this_week = _files_modified_since(DONE_DIR, cutoff)
    new_this_week = _files_modified_since(INBOX_DIR, cutoff)

    # Also count newly created Needs_Action files as "received"
    na_this_week = _files_modified_since(NEEDS_ACTION_DIR, cutoff)
    total_new = len(new_this_week) + len(na_this_week)

    avg_hours = _compute_avg_completion_time(done_this_week)

    # Find high-priority items in Needs_Action
    high_priority_items = []
    if NEEDS_ACTION_DIR.is_dir():
        for f in NEEDS_ACTION_DIR.iterdir():
            if f.suffix != ".md":
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except OSError:
                continue
            if re.search(r"\*\*High\*\*", content) or re.search(
                r"\*\*Yes\*\*.*requires human", content, re.IGNORECASE
            ):
                # Extract title
                title = f.stem.replace("_", " ")
                for line in content.splitlines():
                    if line.strip().startswith("#") and not line.strip().startswith("##"):
                        title = line.strip().lstrip("#").strip()
                        break
                high_priority_items.append({
                    "file": f.name,
                    "title": title,
                })

    result = {
        "inbox_count": inbox_count,
        "needs_action_count": needs_action_count,
        "done_this_week": len(done_this_week),
        "new_this_week": total_new,
        "backlog": needs_action_count,
        "avg_completion_hours": avg_hours,
        "avg_completion_days": round(avg_hours / 24, 1) if avg_hours else None,
        "high_priority_items": high_priority_items,
    }

    error_logger.log_audit("briefing.collector.vault_stats", "success", {
        "inbox": inbox_count,
        "backlog": needs_action_count,
        "done": len(done_this_week),
    })

    return result
