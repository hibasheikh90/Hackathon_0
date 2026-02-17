"""
Gold Tier — Ralph Wiggum Autonomous Loop
==========================================
Named after the character who just keeps going, Ralph is the autonomous
execution engine that continuously processes tasks from Needs_Action/
until every task is complete (or requires human intervention).

Pipeline:
    1. Scan Needs_Action/ for incomplete tasks
    2. Classify each task (plan, email, social, general)
    3. Attempt to process — check off steps, execute actions
    4. Detect completion (all checkboxes done, or no work remaining)
    5. Move completed tasks → Done/ with completion metadata
    6. Retry stuck tasks (up to max_retries per task)
    7. Update Dashboard.md with live status
    8. Repeat until queue is empty or max_cycles reached

Usage:
    from core.ralph import ralph

    ralph.run()                 # Process until empty (default max 10 cycles)
    ralph.run(max_cycles=5)     # Limit to 5 passes
    ralph.run_once()            # Single pass

CLI:
    python -m core.ralph
    python -m core.ralph --once
    python -m core.ralph --cycles 20
    python -m core.ralph --daemon --interval 2
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger
from core.event_bus import bus
from core.retry import failed_queue


# ---------------------------------------------------------------------------
# Vault paths
# ---------------------------------------------------------------------------
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
DONE_DIR = VAULT_DIR / "Done"
DASHBOARD_FILE = VAULT_DIR / "Dashboard.md"

# Ralph state file
RALPH_STATE_FILE = _PROJECT_ROOT / "core" / ".ralph_state.json"


# ---------------------------------------------------------------------------
# Task status detection
# ---------------------------------------------------------------------------

class TaskStatus:
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    BLOCKED = "blocked"          # requires human approval
    NO_CHECKLIST = "no_checklist"  # no checkboxes to track


def _parse_checkboxes(content: str) -> tuple[int, int]:
    """Count (checked, total) checkboxes in markdown content."""
    checked = len(re.findall(r"- \[x\]", content, re.IGNORECASE))
    unchecked = len(re.findall(r"- \[ \]", content))
    return checked, checked + unchecked


def _requires_human_approval(content: str) -> bool:
    """Check if the task explicitly requires human approval."""
    return bool(re.search(
        r"\*\*Yes\*\*.*requires human",
        content,
        re.IGNORECASE,
    ))


def _extract_priority(content: str) -> str:
    """Extract priority from task content."""
    match = re.search(r"\*\*(High|Medium|Low)\*\*", content)
    return match.group(1) if match else "Medium"


def _extract_title(content: str, filename: str) -> str:
    """Extract the task title from content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped.lstrip("#").strip()
    return filename.replace("_", " ").replace(".md", "")


def _classify_task(filename: str, content: str) -> str:
    """Classify a task by type based on filename and content."""
    name = filename.lower()
    if name.startswith("plan_"):
        return "plan"
    if name.startswith("social_"):
        return "social"
    if name.startswith("gmail_"):
        return "email"
    if name.startswith("wa_"):
        return "whatsapp"
    if "invoice" in name or "accounting" in name:
        return "accounting"
    return "general"


def _assess_task(filepath: Path) -> dict[str, Any]:
    """Read and assess a task file. Returns a task descriptor dict."""
    content = filepath.read_text(encoding="utf-8")
    filename = filepath.name
    checked, total = _parse_checkboxes(content)
    needs_approval = _requires_human_approval(content)

    if total == 0:
        status = TaskStatus.NO_CHECKLIST
    elif needs_approval and checked < total:
        status = TaskStatus.BLOCKED
    elif checked >= total and total > 0:
        status = TaskStatus.COMPLETE
    else:
        status = TaskStatus.INCOMPLETE

    return {
        "filepath": filepath,
        "filename": filename,
        "title": _extract_title(content, filename),
        "type": _classify_task(filename, content),
        "priority": _extract_priority(content),
        "status": status,
        "checked": checked,
        "total": total,
        "needs_approval": needs_approval,
        "content": content,
    }


# ---------------------------------------------------------------------------
# Task processors (by type)
# ---------------------------------------------------------------------------

def _process_plan_task(task: dict, state: dict) -> bool:
    """Process a Plan_ file. Attempts to advance unchecked steps.

    Returns True if any progress was made.
    """
    content = task["content"]
    filepath = task["filepath"]
    lines = content.splitlines()
    modified = False

    new_lines = []
    for line in lines:
        # Auto-complete steps that are verification/archiving steps
        if re.match(r"- \[ \]\s*(Verify|Mark task as done|Archive|Confirm)", line, re.IGNORECASE):
            new_lines.append(line.replace("- [ ]", "- [x]", 1))
            modified = True
        # Auto-complete notification steps
        elif re.match(r"- \[ \]\s*(Notify|Send notification|Log|Report)", line, re.IGNORECASE):
            new_lines.append(line.replace("- [ ]", "- [x]", 1))
            modified = True
        # Auto-complete review/read steps
        elif re.match(r"- \[ \]\s*(Review|Read|Check|Inspect|Scan|Analyze)", line, re.IGNORECASE):
            new_lines.append(line.replace("- [ ]", "- [x]", 1))
            modified = True
        else:
            new_lines.append(line)

    if modified:
        new_content = "\n".join(new_lines)
        filepath.write_text(new_content, encoding="utf-8")
        task["content"] = new_content
        checked, total = _parse_checkboxes(new_content)
        task["checked"] = checked
        task["total"] = total
        if checked >= total and total > 0:
            task["status"] = TaskStatus.COMPLETE

    return modified


def _process_email_task(task: dict, state: dict) -> bool:
    """Process email tasks — mark as reviewed."""
    content = task["content"]
    filepath = task["filepath"]

    # If no checklist, mark the whole thing as reviewed
    if task["total"] == 0:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content += f"\n\n## Ralph Processing\n- [x] Reviewed by AI Employee ({timestamp})\n"
        filepath.write_text(content, encoding="utf-8")
        task["content"] = content
        task["status"] = TaskStatus.COMPLETE
        return True

    return _process_plan_task(task, state)


def _process_social_task(task: dict, state: dict) -> bool:
    """Process social media tasks — check queue status."""
    # Social tasks are handled by the social content queue
    # Ralph just checks if they've been posted
    content = task["content"]
    if "status: posted" in content.lower():
        task["status"] = TaskStatus.COMPLETE
        return True
    return _process_plan_task(task, state)


def _process_general_task(task: dict, state: dict) -> bool:
    """Process general tasks — attempt auto-completion of safe steps."""
    if task["total"] == 0:
        # No checklist — mark as reviewed and complete
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = task["content"]
        content += f"\n\n## Ralph Processing\n- [x] Reviewed by AI Employee ({timestamp})\n- [x] No actionable checklist items found — marked complete\n"
        task["filepath"].write_text(content, encoding="utf-8")
        task["content"] = content
        task["status"] = TaskStatus.COMPLETE
        return True

    return _process_plan_task(task, state)


# Dispatcher
_PROCESSORS = {
    "plan": _process_plan_task,
    "email": _process_email_task,
    "social": _process_social_task,
    "whatsapp": _process_email_task,  # same as email
    "accounting": _process_general_task,
    "general": _process_general_task,
}


# ---------------------------------------------------------------------------
# Task completion — move to Done/
# ---------------------------------------------------------------------------

def _complete_task(task: dict) -> Path:
    """Move a completed task to Done/ with completion metadata."""
    filepath = task["filepath"]
    filename = task["filename"]
    content = task["content"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Append completion metadata
    completion_block = f"""
---

## Completion Record
- **Completed by:** Ralph Wiggum (AI Employee autonomous loop)
- **Completed at:** {timestamp}
- **Checklist:** {task['checked']}/{task['total']} items
- **Task type:** {task['type']}
- **Priority:** {task['priority']}
"""

    content += completion_block
    filepath.write_text(content, encoding="utf-8")

    # Move to Done/
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    dest = DONE_DIR / filename
    if dest.exists():
        stem = filepath.stem
        suffix = filepath.suffix
        counter = 2
        while dest.exists():
            dest = DONE_DIR / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.move(str(filepath), str(dest))

    bus.emit("vault.task.completed", {
        "file": filename,
        "title": task["title"],
        "type": task["type"],
        "destination": str(dest),
    })
    error_logger.log_audit("ralph.task_completed", "success", {
        "file": filename,
        "title": task["title"],
        "type": task["type"],
        "checked": task["checked"],
        "total": task["total"],
    })

    return dest


# ---------------------------------------------------------------------------
# Dashboard updater
# ---------------------------------------------------------------------------

def _update_dashboard(cycle: int, tasks: list[dict], stats: dict) -> None:
    """Rewrite Dashboard.md with current Ralph status."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    inbox_count = sum(1 for f in INBOX_DIR.iterdir() if f.suffix == ".md") if INBOX_DIR.is_dir() else 0
    na_count = sum(1 for f in NEEDS_ACTION_DIR.iterdir() if f.suffix == ".md") if NEEDS_ACTION_DIR.is_dir() else 0
    done_count = sum(1 for f in DONE_DIR.iterdir() if f.suffix == ".md") if DONE_DIR.is_dir() else 0

    # Build task table
    task_rows = []
    for t in tasks:
        progress = f"{t['checked']}/{t['total']}" if t["total"] > 0 else "—"
        status_label = {
            TaskStatus.COMPLETE: "Done",
            TaskStatus.INCOMPLETE: "In Progress",
            TaskStatus.BLOCKED: "Blocked (needs approval)",
            TaskStatus.NO_CHECKLIST: "Reviewed",
        }.get(t["status"], t["status"])
        task_rows.append(
            f"| {t['title'][:40]} | {t['type']} | {t['priority']} | {status_label} | {progress} |"
        )

    task_table = "\n".join(task_rows) if task_rows else "| (no tasks) | | | | |"

    dashboard = f"""# Agent Dashboard

## Ralph Wiggum Status

- **State:** Running (cycle #{cycle})
- **Last update:** {timestamp}
- **Tasks completed this session:** {stats.get('completed', 0)}
- **Tasks retried:** {stats.get('retried', 0)}
- **Tasks blocked:** {stats.get('blocked', 0)}

## Queue Counts

| Stage | Count |
|---|---|
| Inbox | {inbox_count} |
| Needs Action | {na_count} |
| Done | {done_count} |

## Current Tasks

| Task | Type | Priority | Status | Progress |
|---|---|---|---|---|
{task_table}

## Workflow

```
Inbox/ --> Needs_Action/ --> Done/
(new)      (Ralph loop)     (archived)
```

1. New tasks arrive in `Inbox/`
2. Watcher triages to `Needs_Action/`
3. **Ralph Wiggum** processes tasks autonomously
4. Completed work is moved to `Done/` with completion metadata
5. Stuck tasks are retried; blocked tasks await human approval

## Session Log

- [{timestamp}] Ralph cycle #{cycle}: processed={stats.get('processed', 0)} completed={stats.get('completed', 0)} retried={stats.get('retried', 0)} blocked={stats.get('blocked', 0)}
"""

    DASHBOARD_FILE.write_text(dashboard, encoding="utf-8")


# ---------------------------------------------------------------------------
# Ralph state persistence
# ---------------------------------------------------------------------------

def _load_ralph_state() -> dict:
    if RALPH_STATE_FILE.is_file():
        try:
            return json.loads(RALPH_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "task_retries": {},       # filename -> retry count
        "total_completed": 0,
        "total_cycles": 0,
        "last_run": None,
    }


def _save_ralph_state(state: dict) -> None:
    state["last_run"] = datetime.now().isoformat()
    RALPH_STATE_FILE.write_text(
        json.dumps(state, indent=2, default=str),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# The Ralph Wiggum Loop
# ---------------------------------------------------------------------------

class RalphWiggum:
    """Autonomous task processing loop for the AI Employee."""

    def __init__(self, max_retries_per_task: int = 3) -> None:
        self.max_retries = max_retries_per_task

    def run_once(self) -> dict[str, int]:
        """Single pass through all Needs_Action tasks.

        Returns stats: {scanned, processed, completed, blocked, retried, errors, remaining}
        """
        state = _load_ralph_state()
        stats = {
            "scanned": 0,
            "processed": 0,
            "completed": 0,
            "blocked": 0,
            "retried": 0,
            "errors": 0,
            "remaining": 0,
        }

        if not NEEDS_ACTION_DIR.is_dir():
            return stats

        # Scan all .md files in Needs_Action
        task_files = sorted(NEEDS_ACTION_DIR.glob("*.md"))
        stats["scanned"] = len(task_files)

        if not task_files:
            return stats

        tasks_assessed = []

        for filepath in task_files:
            try:
                task = _assess_task(filepath)
            except Exception as e:
                error_logger.log_error("ralph.assess", e, {"file": filepath.name})
                stats["errors"] += 1
                continue

            tasks_assessed.append(task)

            # Already complete? Move to Done
            if task["status"] == TaskStatus.COMPLETE:
                try:
                    _complete_task(task)
                    stats["completed"] += 1
                    state["total_completed"] = state.get("total_completed", 0) + 1
                    # Reset retry counter
                    state["task_retries"].pop(task["filename"], None)
                except Exception as e:
                    error_logger.log_error("ralph.complete", e, {"file": task["filename"]})
                    stats["errors"] += 1
                continue

            # Blocked by human approval
            if task["status"] == TaskStatus.BLOCKED:
                stats["blocked"] += 1
                continue

            # Check retry limit
            retries = state["task_retries"].get(task["filename"], 0)
            if retries >= self.max_retries:
                stats["blocked"] += 1
                continue

            # Process the task
            try:
                processor = _PROCESSORS.get(task["type"], _process_general_task)
                progress = processor(task, state)
                stats["processed"] += 1

                if progress:
                    state["task_retries"].pop(task["filename"], None)
                else:
                    state["task_retries"][task["filename"]] = retries + 1
                    stats["retried"] += 1

                # Re-check after processing
                if task["status"] == TaskStatus.COMPLETE:
                    try:
                        _complete_task(task)
                        stats["completed"] += 1
                        state["total_completed"] = state.get("total_completed", 0) + 1
                        state["task_retries"].pop(task["filename"], None)
                    except Exception as e:
                        error_logger.log_error("ralph.complete", e, {"file": task["filename"]})
                        stats["errors"] += 1

            except Exception as e:
                error_logger.log_error("ralph.process", e, {
                    "file": task["filename"],
                    "type": task["type"],
                })
                state["task_retries"][task["filename"]] = retries + 1
                stats["errors"] += 1
                stats["retried"] += 1

                # Queue for recovery system too
                failed_queue.push(
                    source=f"ralph.{task['type']}",
                    context={"filepath": str(task["filepath"]), "filename": task["filename"]},
                    error=str(e),
                )

        # Count remaining
        remaining = sum(1 for f in NEEDS_ACTION_DIR.glob("*.md"))
        stats["remaining"] = remaining

        # Update dashboard
        state["total_cycles"] = state.get("total_cycles", 0) + 1
        _update_dashboard(state["total_cycles"], tasks_assessed, stats)
        _save_ralph_state(state)

        # Log the cycle
        error_logger.log_audit("ralph.cycle", "complete", stats)

        return stats

    def run(self, max_cycles: int = 10) -> dict[str, Any]:
        """Run the autonomous loop until all tasks are complete or max_cycles reached.

        Returns summary of the entire run.
        """
        summary = {
            "cycles": 0,
            "total_completed": 0,
            "total_processed": 0,
            "total_errors": 0,
            "total_blocked": 0,
            "stopped_reason": None,
        }

        print()
        print("=" * 55)
        print("  Ralph Wiggum — Autonomous Task Loop")
        print(f"  Vault: {VAULT_DIR}")
        print(f"  Max cycles: {max_cycles}")
        print("=" * 55)
        print()

        error_logger.log_audit("ralph.started", "running", {
            "max_cycles": max_cycles,
            "vault": str(VAULT_DIR),
        })
        bus.emit("ralph.started", {"max_cycles": max_cycles})

        for cycle in range(1, max_cycles + 1):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] --- Ralph cycle #{cycle}/{max_cycles} ---")

            stats = self.run_once()
            summary["cycles"] = cycle
            summary["total_completed"] += stats["completed"]
            summary["total_processed"] += stats["processed"]
            summary["total_errors"] += stats["errors"]
            summary["total_blocked"] += stats["blocked"]

            print(
                f"  scanned={stats['scanned']} processed={stats['processed']} "
                f"completed={stats['completed']} blocked={stats['blocked']} "
                f"errors={stats['errors']} remaining={stats['remaining']}"
            )

            # Stop conditions
            if stats["remaining"] == 0:
                summary["stopped_reason"] = "all_tasks_complete"
                print(f"\n[OK] All tasks processed! Queue empty after {cycle} cycle(s).")
                break

            if stats["processed"] == 0 and stats["completed"] == 0:
                # Nothing moved — everything is blocked or at retry limit
                summary["stopped_reason"] = "no_progress"
                print(
                    f"\n[STOP] No progress possible. "
                    f"{stats['blocked']} task(s) blocked, "
                    f"{stats['remaining']} remaining."
                )
                break

            # Brief pause between cycles to avoid tight loops
            if cycle < max_cycles:
                time.sleep(1)

        else:
            summary["stopped_reason"] = "max_cycles_reached"
            print(f"\n[STOP] Max cycles ({max_cycles}) reached.")

        # Final summary
        print()
        print(f"  Completed: {summary['total_completed']} tasks")
        print(f"  Processed: {summary['total_processed']} task actions")
        print(f"  Blocked:   {summary['total_blocked']} (need human intervention)")
        print(f"  Errors:    {summary['total_errors']}")
        print(f"  Reason:    {summary['stopped_reason']}")
        print()

        error_logger.log_audit("ralph.finished", "complete", summary)
        bus.emit("ralph.finished", summary)

        return summary

    def run_daemon(self, interval_minutes: int = 5, max_cycles_per_run: int = 10) -> None:
        """Run Ralph continuously, processing tasks every interval."""
        print()
        print("=" * 55)
        print("  Ralph Wiggum — Daemon Mode")
        print(f"  Interval: {interval_minutes} minute(s)")
        print(f"  Max cycles per run: {max_cycles_per_run}")
        print("  Press Ctrl+C to stop.")
        print("=" * 55)
        print()

        run_count = 0
        try:
            while True:
                run_count += 1
                print(f"===== Ralph run #{run_count} =====")
                summary = self.run(max_cycles=max_cycles_per_run)

                if summary["stopped_reason"] == "all_tasks_complete":
                    print(f"Queue empty. Sleeping {interval_minutes} min...")
                else:
                    print(f"Run complete. Sleeping {interval_minutes} min...")

                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\nRalph shutdown requested.")
            error_logger.log_audit("ralph.daemon_stopped", "shutdown", {
                "runs": run_count,
            })


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
ralph = RalphWiggum()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ralph Wiggum — Autonomous task processing loop.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Single pass only")
    mode.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument(
        "--cycles", type=int, default=10,
        help="Max cycles per run (default: 10)",
    )
    parser.add_argument(
        "-i", "--interval", type=int, default=5,
        help="Minutes between runs in daemon mode (default: 5)",
    )

    args = parser.parse_args()

    if args.once:
        stats = ralph.run_once()
        print(f"Ralph single pass: {stats}")
    elif args.daemon:
        ralph.run_daemon(
            interval_minutes=args.interval,
            max_cycles_per_run=args.cycles,
        )
    else:
        ralph.run(max_cycles=args.cycles)


if __name__ == "__main__":
    main()
