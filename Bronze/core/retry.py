"""
Gold Tier — Retry & Failed Task Queue
=======================================
Provides a retry decorator with exponential backoff and a persistent
failed-task queue so the recovery manager can re-attempt later.

Usage:
    from core.retry import retry, failed_queue

    @retry(max_attempts=3, backoff=2.0)
    def risky_operation():
        ...

    # Manual queue management
    failed_queue.push("watcher.process_file", {"filepath": "/path/to/file.md"}, error_msg)
    tasks = failed_queue.pending()
    failed_queue.resolve(task_id)
"""

from __future__ import annotations

import functools
import json
import time
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
FAILED_QUEUE_FILE = _PROJECT_ROOT / "Logs" / "failed_tasks.json"


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    initial_delay: float = 1.0,
    exceptions: tuple = (Exception,),
    on_failure: Callable | None = None,
):
    """Decorator that retries a function with exponential backoff.

    Args:
        max_attempts: Total attempts (including the first try).
        backoff: Multiplier applied to delay after each failure.
        initial_delay: Seconds to wait before the first retry.
        exceptions: Tuple of exception types to catch and retry.
        on_failure: Optional callback(func_name, args, kwargs, error)
                    called after all attempts are exhausted.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_error = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_attempts:
                        time.sleep(delay)
                        delay *= backoff
                    else:
                        # All attempts exhausted
                        if on_failure:
                            on_failure(func.__name__, args, kwargs, e)
                        raise

            return None  # unreachable but keeps type checkers happy
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Failed Task Queue (persistent JSON file)
# ---------------------------------------------------------------------------

class FailedTaskQueue:
    """Persistent queue of tasks that failed and need retry."""

    def __init__(self, queue_file: Path = FAILED_QUEUE_FILE) -> None:
        self._file = queue_file
        self._lock = threading.Lock()
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def push(
        self,
        source: str,
        context: dict[str, Any],
        error: str,
        max_retries: int = 3,
    ) -> str:
        """Add a failed task to the queue. Returns the task ID."""
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        entry = {
            "id": task_id,
            "source": source,
            "context": context,
            "error": error,
            "status": "pending",
            "retry_count": 0,
            "max_retries": max_retries,
            "created_at": datetime.now().isoformat(),
            "last_attempt": None,
            "resolved_at": None,
        }

        with self._lock:
            queue = self._load()
            queue.append(entry)
            self._save(queue)

        return task_id

    def pending(self) -> list[dict]:
        """Return all tasks with status 'pending'."""
        with self._lock:
            queue = self._load()
        return [t for t in queue if t["status"] == "pending"]

    def get(self, task_id: str) -> dict | None:
        """Get a specific task by ID."""
        with self._lock:
            queue = self._load()
        for t in queue:
            if t["id"] == task_id:
                return t
        return None

    def update(self, task_id: str, **fields) -> bool:
        """Update fields on a task. Returns True if found."""
        with self._lock:
            queue = self._load()
            for task in queue:
                if task["id"] == task_id:
                    task.update(fields)
                    self._save(queue)
                    return True
        return False

    def resolve(self, task_id: str) -> bool:
        """Mark a task as resolved."""
        return self.update(
            task_id,
            status="resolved",
            resolved_at=datetime.now().isoformat(),
        )

    def fail_permanently(self, task_id: str) -> bool:
        """Mark a task as permanently failed (exhausted retries)."""
        return self.update(
            task_id,
            status="failed",
            resolved_at=datetime.now().isoformat(),
        )

    def increment_retry(self, task_id: str) -> bool:
        """Bump retry_count and update last_attempt timestamp."""
        with self._lock:
            queue = self._load()
            for task in queue:
                if task["id"] == task_id:
                    task["retry_count"] += 1
                    task["last_attempt"] = datetime.now().isoformat()
                    if task["retry_count"] >= task["max_retries"]:
                        task["status"] = "failed"
                    self._save(queue)
                    return True
        return False

    def stats(self) -> dict[str, int]:
        """Return counts by status."""
        with self._lock:
            queue = self._load()
        counts = {"pending": 0, "resolved": 0, "failed": 0}
        for t in queue:
            status = t.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        counts["total"] = len(queue)
        return counts

    def cleanup(self, keep_days: int = 7) -> int:
        """Remove resolved/failed tasks older than keep_days. Returns count removed."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        removed = 0
        with self._lock:
            queue = self._load()
            new_queue = []
            for task in queue:
                resolved_at = task.get("resolved_at")
                if task["status"] in ("resolved", "failed") and resolved_at and resolved_at < cutoff:
                    removed += 1
                else:
                    new_queue.append(task)
            self._save(new_queue)
        return removed

    # Internal helpers
    def _load(self) -> list[dict]:
        if not self._file.is_file():
            return []
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, queue: list[dict]) -> None:
        self._file.write_text(
            json.dumps(queue, indent=2, default=str),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
failed_queue = FailedTaskQueue()
