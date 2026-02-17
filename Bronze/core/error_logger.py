"""
Gold Tier — Centralized Error & Audit Logger
=============================================
Every module logs through this single system.  No silent failures.

Usage:
    from core.error_logger import logger

    # Log an error
    logger.log_error("odoo.invoices", exc, {"host": "odoo.example.com"})

    # Log an audit action
    logger.log_audit("social.post", "success", {"platform": "linkedin"})

Files:
    logs/error.log   — JSON Lines, one error per line
    logs/audit.log   — JSON Lines, one action per line
    logs/archive/    — Rotated logs (weekly)

Alert escalation:
    3+ errors from the same source within 1 hour triggers an alert event
    on the event bus ("error.alert_triggered").
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = _PROJECT_ROOT / "Logs"
ARCHIVE_DIR = LOGS_DIR / "archive"
ERROR_LOG = LOGS_DIR / "error.log"
AUDIT_LOG = LOGS_DIR / "audit.log"


class ErrorLogger:
    """Centralized JSON Lines logger with alert escalation."""

    def __init__(
        self,
        error_log: Path = ERROR_LOG,
        audit_log: Path = AUDIT_LOG,
        archive_dir: Path = ARCHIVE_DIR,
        alert_threshold: int = 3,
        alert_window_seconds: int = 3600,
        max_file_size_mb: int = 50,
    ) -> None:
        self._error_log = error_log
        self._audit_log = audit_log
        self._archive_dir = archive_dir
        self._alert_threshold = alert_threshold
        self._alert_window = alert_window_seconds
        self._max_file_bytes = max_file_size_mb * 1024 * 1024

        # Track recent errors per source for alert escalation
        self._recent_errors: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._event_bus = None  # set later to avoid circular import

        # Ensure directories exist
        self._error_log.parent.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def set_event_bus(self, bus) -> None:
        """Attach the event bus for alert escalation."""
        self._event_bus = bus

    # ------------------------------------------------------------------
    # Error logging
    # ------------------------------------------------------------------

    def log_error(
        self,
        source: str,
        error: Exception | str,
        context: dict[str, Any] | None = None,
        severity: str = "ERROR",
    ) -> dict:
        """Write a structured error record to error.log.

        Returns the record dict.
        """
        now = time.time()
        error_str = str(error)
        error_type = type(error).__name__ if isinstance(error, Exception) else "str"

        record = {
            "ts": datetime.fromtimestamp(now).isoformat(),
            "severity": severity,
            "source": source,
            "error_type": error_type,
            "error": error_str,
            "context": context or {},
            "resolved": False,
        }

        self._append(self._error_log, record)
        self._check_alert_escalation(source, now)

        return record

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def log_audit(
        self,
        action: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> dict:
        """Write a structured audit record to audit.log.

        Returns the record dict.
        """
        record = {
            "ts": datetime.now().isoformat(),
            "action": action,
            "status": status,
            "details": details or {},
        }

        self._append(self._audit_log, record)
        return record

    # ------------------------------------------------------------------
    # Log rotation
    # ------------------------------------------------------------------

    def rotate_if_needed(self) -> list[str]:
        """Rotate logs that exceed max file size.  Returns list of archived filenames."""
        archived = []
        for log_path in (self._error_log, self._audit_log):
            if log_path.is_file() and log_path.stat().st_size > self._max_file_bytes:
                archived_name = self._rotate(log_path)
                if archived_name:
                    archived.append(archived_name)
        return archived

    def force_rotate(self) -> list[str]:
        """Force rotate all logs regardless of size.  Returns list of archived filenames."""
        archived = []
        for log_path in (self._error_log, self._audit_log):
            if log_path.is_file() and log_path.stat().st_size > 0:
                archived_name = self._rotate(log_path)
                if archived_name:
                    archived.append(archived_name)
        return archived

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def recent_errors(self, limit: int = 20) -> list[dict]:
        """Read the last *limit* errors from error.log."""
        return self._tail(self._error_log, limit)

    def recent_audit(self, limit: int = 20) -> list[dict]:
        """Read the last *limit* audit entries from audit.log."""
        return self._tail(self._audit_log, limit)

    def error_count_since(self, source: str, since_seconds: int = 3600) -> int:
        """Count errors from *source* in the last *since_seconds*."""
        cutoff = time.time() - since_seconds
        with self._lock:
            timestamps = self._recent_errors.get(source, [])
            return sum(1 for t in timestamps if t >= cutoff)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, log_path: Path, record: dict) -> None:
        """Thread-safe append of a JSON record to a log file."""
        line = json.dumps(record, default=str) + "\n"
        with self._lock:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)

    def _check_alert_escalation(self, source: str, now: float) -> None:
        """Track error frequency and emit alert if threshold exceeded."""
        cutoff = now - self._alert_window
        with self._lock:
            self._recent_errors[source].append(now)
            # Prune old entries
            self._recent_errors[source] = [
                t for t in self._recent_errors[source] if t >= cutoff
            ]
            count = len(self._recent_errors[source])

        if count >= self._alert_threshold and self._event_bus:
            self._event_bus.emit("error.alert_triggered", {
                "source": source,
                "error_count": count,
                "window_seconds": self._alert_window,
                "ts": datetime.fromtimestamp(now).isoformat(),
            })

    def _rotate(self, log_path: Path) -> str | None:
        """Move a log file to the archive directory with a timestamp suffix."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{log_path.stem}_{ts}{log_path.suffix}"
        archive_path = self._archive_dir / archive_name
        try:
            shutil.move(str(log_path), str(archive_path))
            return archive_name
        except OSError:
            return None

    def _tail(self, log_path: Path, limit: int) -> list[dict]:
        """Read the last *limit* lines from a JSON Lines file."""
        if not log_path.is_file():
            return []
        try:
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            tail = lines[-limit:] if len(lines) > limit else lines
            results = []
            for line in tail:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return results
        except OSError:
            return []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
logger = ErrorLogger()
