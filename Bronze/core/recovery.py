"""
Gold Tier — Recovery Manager
===============================
Processes the failed task queue, retrying tasks that previously errored.

Runs as part of each scheduler cycle.  For each pending task in the queue:
    1. Look up the appropriate handler by source name
    2. Re-attempt the operation
    3. On success → mark resolved
    4. On failure → increment retry count (permanently fail after max retries)

Usage:
    from core.recovery import recovery_manager

    stats = recovery_manager.run_recovery()
    # {"attempted": 3, "recovered": 2, "failed": 1, "skipped": 0}

CLI:
    python -m core.recovery
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.retry import failed_queue
from core.error_logger import logger as error_logger
from core.event_bus import bus


class RecoveryManager:
    """Retry failed tasks from the persistent queue."""

    def __init__(self) -> None:
        # Registry of recovery handlers keyed by source name
        self._handlers: dict[str, Callable[[dict], Any]] = {}
        self._register_builtin_handlers()

    def register(self, source: str, handler: Callable[[dict], Any]) -> None:
        """Register a recovery handler for a given source name."""
        self._handlers[source] = handler

    def run_recovery(self) -> dict[str, int]:
        """Process all pending tasks in the failed queue.

        Returns stats dict with attempted/recovered/failed/skipped counts.
        """
        stats = {"attempted": 0, "recovered": 0, "failed": 0, "skipped": 0}

        pending = failed_queue.pending()
        if not pending:
            return stats

        for task in pending:
            source = task["source"]
            task_id = task["id"]
            context = task.get("context", {})

            handler = self._handlers.get(source)
            if handler is None:
                stats["skipped"] += 1
                continue

            stats["attempted"] += 1

            try:
                handler(context)
                failed_queue.resolve(task_id)
                stats["recovered"] += 1

                error_logger.log_audit("recovery.success", "recovered", {
                    "task_id": task_id,
                    "source": source,
                    "retry_count": task.get("retry_count", 0) + 1,
                })
                bus.emit("recovery.task.recovered", {
                    "task_id": task_id,
                    "source": source,
                })

            except Exception as e:
                failed_queue.increment_retry(task_id)
                updated = failed_queue.get(task_id)

                if updated and updated.get("status") == "failed":
                    stats["failed"] += 1
                    error_logger.log_error("recovery.exhausted", e, {
                        "task_id": task_id,
                        "source": source,
                        "retry_count": updated.get("retry_count", 0),
                    }, severity="CRITICAL")
                    bus.emit("recovery.task.exhausted", {
                        "task_id": task_id,
                        "source": source,
                        "error": str(e),
                    })
                else:
                    error_logger.log_error("recovery.retry_failed", e, {
                        "task_id": task_id,
                        "source": source,
                        "retry_count": updated.get("retry_count", 0) if updated else 0,
                    })

        # Cleanup old resolved/failed entries
        cleaned = failed_queue.cleanup(keep_days=7)
        if cleaned:
            error_logger.log_audit("recovery.cleanup", "success", {"removed": cleaned})

        if stats["attempted"] > 0:
            error_logger.log_audit("recovery.cycle", "complete", stats)

        return stats

    # ------------------------------------------------------------------
    # Built-in recovery handlers
    # ------------------------------------------------------------------

    def _register_builtin_handlers(self) -> None:
        """Register handlers for known task sources."""
        self.register("watcher.process_file", self._recover_watcher)
        self.register("planner.create_plan", self._recover_planner)
        self.register("vault.triage", self._recover_vault_triage)
        self.register("vault.plan", self._recover_vault_plan)
        self.register("social.queue_check", self._recover_social)
        self.register("odoo.sync", self._recover_odoo_sync)
        self.register("gmail.watcher", self._recover_gmail)

    @staticmethod
    def _recover_watcher(ctx: dict) -> None:
        """Re-process a file through the watcher."""
        filepath = ctx.get("filepath")
        if not filepath:
            raise ValueError("No filepath in context")
        fpath = Path(filepath)
        if not fpath.is_file():
            raise FileNotFoundError(f"File no longer exists: {filepath}")

        from watcher import process_file
        process_file(filepath)

    @staticmethod
    def _recover_planner(ctx: dict) -> None:
        """Re-run the planner on a file."""
        filepath = ctx.get("filepath")
        if not filepath:
            raise ValueError("No filepath in context")
        fpath = Path(filepath)
        if not fpath.is_file():
            raise FileNotFoundError(f"File no longer exists: {filepath}")

        from planner import create_plan
        create_plan(filepath)

    @staticmethod
    def _recover_vault_triage(ctx: dict) -> None:
        """Re-triage a vault file."""
        filepath = ctx.get("filepath") or ctx.get("file")
        if not filepath:
            raise ValueError("No filepath in context")
        fpath = Path(filepath)
        if not fpath.is_file():
            # File may have been moved — skip silently
            return

        from watcher import process_file
        process_file(str(fpath))

    @staticmethod
    def _recover_vault_plan(ctx: dict) -> None:
        """Re-plan a vault file."""
        filepath = ctx.get("filepath") or ctx.get("file")
        if not filepath:
            raise ValueError("No filepath in context")
        fpath = Path(filepath)
        if not fpath.is_file():
            return

        from planner import create_plan
        create_plan(str(fpath))

    @staticmethod
    def _recover_social(ctx: dict) -> None:
        """Re-process the social content queue."""
        try:
            from integrations.social.content_queue import process_queue
            process_queue()
        except ImportError:
            pass

    @staticmethod
    def _recover_odoo_sync(ctx: dict) -> None:
        """Re-run Odoo sync."""
        try:
            from integrations.odoo.sync import run_sync
            run_sync()
        except ImportError:
            pass

    @staticmethod
    def _recover_gmail(ctx: dict) -> None:
        """Re-check Gmail inbox."""
        try:
            from integrations.gmail.watcher import GmailWatcher
            watcher = GmailWatcher()
            if watcher.is_configured():
                watcher.check_new()
        except ImportError:
            pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
recovery_manager = RecoveryManager()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    stats = recovery_manager.run_recovery()
    print(f"Recovery complete: {stats}")
    queue_stats = failed_queue.stats()
    print(f"Queue: {queue_stats}")


if __name__ == "__main__":
    main()
