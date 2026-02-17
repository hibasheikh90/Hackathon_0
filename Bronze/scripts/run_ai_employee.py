"""
AI Employee Scheduler (Silver Tier)
====================================
Production scheduler that orchestrates the full task pipeline:

  1. Scan vault/Inbox/ for new .md files
  2. Triage each file (route to Needs_Action or Done)
  3. Generate a structured execution plan for each actionable task
  4. Optionally generate a daily summary report
  5. Log every action to scheduler.log

Modes:
  --once     Single pass then exit (for Task Scheduler / cron)
  --daemon   Continuous loop every N minutes (standalone)

Usage:
  python scripts/run_ai_employee.py --once
  python scripts/run_ai_employee.py --daemon --interval 5
"""

import json
import logging
import os
import re
import shutil
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution — works from any working directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Support both vault locations: direct vault/ or AI_Employee_Vault/vault/
# Priority: AI_Employee_Vault/vault/ if it exists, else vault/
_ai_vault = PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault

INBOX_DIR = VAULT_DIR / "Inbox"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
DONE_DIR = VAULT_DIR / "Done"

STATE_FILE = SCRIPT_DIR / ".scheduler_state.json"
LOG_FILE = SCRIPT_DIR / "scheduler.log"
LOCK_FILE = SCRIPT_DIR / ".scheduler.lock"

# ---------------------------------------------------------------------------
# Logging — dual output: file + console
# ---------------------------------------------------------------------------
def setup_logging() -> logging.Logger:
    logger = logging.getLogger("ai_employee")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — append
    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = setup_logging()

# ---------------------------------------------------------------------------
# State persistence — tracks which files have been processed
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt state file, starting fresh")
    return {"processed": {}, "cycle_count": 0, "last_run": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Lock file — prevent overlapping runs
# ---------------------------------------------------------------------------
def acquire_lock() -> bool:
    if LOCK_FILE.is_file():
        try:
            data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            pid = data.get("pid", 0)
            # Check if the locking process is still alive
            try:
                os.kill(pid, 0)
                return False  # Process is alive, lock is held
            except (OSError, ProcessLookupError):
                log.warning("Stale lock from PID %d, overriding", pid)
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt lock file, overriding")

    LOCK_FILE.write_text(
        json.dumps({"pid": os.getpid(), "started": datetime.now().isoformat()}),
        encoding="utf-8",
    )
    return True


def release_lock() -> None:
    if LOCK_FILE.is_file():
        LOCK_FILE.unlink()


# ---------------------------------------------------------------------------
# Triage constants
# ---------------------------------------------------------------------------
URGENCY_WORDS = [
    "urgent", "asap", "critical", "overdue", "immediately",
    "deadline", "emergency", "blocker", "breaking", "p0", "p1",
]

ACTION_VERBS = [
    "fix", "add", "remove", "update", "create",
    "delete", "change", "implement", "deploy", "review",
]

APPROVAL_KEYWORDS = [
    "payment", "invoice", "money", "cost", "budget", "spend",
    "homepage", "website", "banner", "public", "client", "customer",
    "delete", "remove", "drop", "permission", "access", "security",
    "password", "credential",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_title(content: str, filename: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return Path(filename).stem.replace("_", " ").replace("-", " ")


def determine_priority(content: str) -> tuple[str, str]:
    lower = content.lower()
    for word in URGENCY_WORDS:
        if re.search(r"\b" + word + r"\b", lower):
            return "High", f'Contains urgency indicator: "{word}"'
    for verb in ACTION_VERBS:
        if re.search(r"\b" + verb + r"\b", lower):
            return "Medium", "Contains action verbs with no urgency signals"
    if "?" in content:
        return "Low", "Informational or exploratory"
    return "Medium", "Default priority for actionable content"


def needs_approval(content: str) -> tuple[str, str]:
    lower = content.lower()
    for kw in APPROVAL_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", lower):
            return "Yes", f'Task involves "{kw}" -- requires human review'
    if not content.strip():
        return "Yes", "Task is empty -- needs human clarification"
    non_empty = [l for l in content.splitlines() if l.strip()]
    if len(non_empty) < 2:
        return "Yes", "Task is too brief -- may need clarification"
    return "No", "Task is clear and low-risk"


def generate_objective(content: str, title: str) -> str:
    if not content.strip():
        return "Clarify task requirements -- the original task is empty or unclear."
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        clean = re.sub(r"\*(.+?)\*", r"\1", clean)
        clean = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", clean)
        clean = clean.strip()
        if len(clean) > 10:
            return clean
    return f"Complete the task: {title}"


def generate_steps(content: str, title: str) -> list[str]:
    if not content.strip():
        return ["Request task details from the sender"]

    checklist_items = re.findall(r"- \[[ x]\]\s*(.+)", content, re.IGNORECASE)
    if checklist_items:
        steps = [item.strip() for item in checklist_items]
        steps.append("Verify all checklist items are completed")
        steps.append("Mark task as done and archive")
        return steps

    body_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body_lines.append(stripped)

    if body_lines:
        steps = [f'Review the full task: "{title}"']
        for line in body_lines:
            clean = re.sub(r"^\d+\.\s*", "", line)
            clean = re.sub(r"^[-*]\s*", "", clean)
            if clean:
                steps.append(clean)
        steps.append("Verify the result meets the task requirements")
        steps.append("Mark task as done and archive")
        return steps

    return [
        f'Interpret the task: "{title}"',
        "Gather any missing information",
        "Execute the task",
        "Verify the result",
    ]


def generate_suggested_output(content: str, title: str) -> str:
    if not content.strip():
        return "A clarified task description with actionable details."
    checklist = re.findall(r"- \[ \]\s*(.+)", content)
    if checklist:
        items = ", ".join(i.strip() for i in checklist[:3])
        return f"Completed deliverables: {items}."
    return f'Completed task: "{title}" with all requirements fulfilled.'


def unique_path(directory: Path, prefix: str, timestamp: str) -> Path:
    candidate = directory / f"{prefix}_{timestamp}.md"
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = directory / f"{prefix}_{timestamp}_{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


def decide_destination(content: str) -> tuple[Path, int, str]:
    lower = content.lower()
    if re.search(r"\bdone\b", lower) or re.search(r"\bcompleted\b", lower):
        return DONE_DIR, 1, "Done"
    if "?" in content:
        return NEEDS_ACTION_DIR, 2, "Needs Action"
    for verb in ACTION_VERBS:
        if re.search(r"\b" + verb + r"\b", lower):
            return NEEDS_ACTION_DIR, 3, "Needs Action"
    if re.search(r"- \[ \]", content):
        return NEEDS_ACTION_DIR, 4, "Needs Action"
    if re.search(r"- \[x\]", content, re.IGNORECASE) and not re.search(r"- \[ \]", content):
        return DONE_DIR, 5, "Done"
    return NEEDS_ACTION_DIR, 6, "Needs Action"


# ---------------------------------------------------------------------------
# Stage 1: Triage — read inbox file, route to correct folder
# ---------------------------------------------------------------------------
def triage_file(filepath: Path) -> tuple[Path | None, str]:
    """Triage a single inbox file. Returns (output_path, status) or (None, error)."""
    filename = filepath.name

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, f"read error: {e}"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not content.strip():
        dest_dir = NEEDS_ACTION_DIR
        rule_num = 0
        status = "Needs Action"
        title = filepath.stem.replace("_", " ").replace("-", " ")
        summary = "(empty file -- manual review required)"
    else:
        title = extract_title(content, filename)
        # Summarize: first 3 non-empty, non-heading lines
        body_lines = [
            l.strip() for l in content.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        summary = "\n".join(body_lines[:3]) if body_lines else "(no body content)"
        if len(summary) > 300:
            summary = summary[:297] + "..."
        dest_dir, rule_num, status = decide_destination(content)

    # Check for existing output
    output = dest_dir / filename
    if output.exists():
        return None, "already triaged"

    rule_label = f"#{rule_num}" if rule_num > 0 else "#0 (empty file)"
    dest_name = dest_dir.name

    response = f"""# {title}

## Metadata
- **Source:** Inbox/{filename}
- **Received:** {now_str}
- **Routed to:** {dest_name}/
- **Triage rule:** {rule_label}
- **Status:** {status}

## Summary
{summary}

## Original Task
{content}

## Agent Notes
- Triage complete. File routed by rule {rule_label}.
"""
    output.write_text(response, encoding="utf-8")
    return output, status


# ---------------------------------------------------------------------------
# Stage 2: Plan — generate structured execution plan
# ---------------------------------------------------------------------------
def create_plan(filepath: Path) -> Path | None:
    """Create a plan for an inbox file. Returns plan path or None."""
    filename = filepath.name

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        log.error("Cannot read %s: %s", filepath, e)
        return None

    now = datetime.now()
    ts_file = now.strftime("%Y%m%d_%H%M%S")
    ts_display = now.strftime("%Y-%m-%d %H:%M:%S")

    title = extract_title(content, filename)
    objective = generate_objective(content, title)
    steps = generate_steps(content, title)
    priority, priority_reason = determine_priority(content)
    approval, approval_reason = needs_approval(content)
    suggested = generate_suggested_output(content, title)

    steps_text = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))

    plan_md = f"""# Task Plan

## Original Task
**Source:** Inbox/{filename}
**Received:** {ts_display}

{content.strip()}

## Objective
{objective}

## Step-by-Step Plan
{steps_text}

## Priority
**{priority}** -- {priority_reason}

## Requires Human Approval?
**{approval}** -- {approval_reason}

## Suggested Output
{suggested}
"""

    plan_path = unique_path(NEEDS_ACTION_DIR, "Plan", ts_file)
    plan_path.write_text(plan_md, encoding="utf-8")
    return plan_path


# ---------------------------------------------------------------------------
# Stage 3: Daily report (optional, runs once per day)
# ---------------------------------------------------------------------------
def should_run_daily_report(state: dict) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    return state.get("last_report_date") != today


def run_daily_report(state: dict) -> Path | None:
    """Generate the daily report. Returns report path or None."""
    report_script = (
        PROJECT_ROOT / "AI_Employee_Vault" / ".claude" / "skills"
        / "daily-report" / "scripts" / "generate_report.py"
    )
    if not report_script.is_file():
        log.info("Daily report skill not found, skipping")
        return None

    # Import and run directly to avoid subprocess overhead
    import importlib.util
    spec = importlib.util.spec_from_file_location("generate_report", str(report_script))
    mod = importlib.util.module_from_spec(spec)

    # Temporarily override sys.argv
    old_argv = sys.argv
    sys.argv = [str(report_script)]
    try:
        spec.loader.exec_module(mod)
        mod.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    state["last_report_date"] = datetime.now().strftime("%Y-%m-%d")
    today_tag = datetime.now().strftime("%Y%m%d")
    report_path = DONE_DIR / f"DailyReport_{today_tag}.md"
    return report_path if report_path.is_file() else None


# ---------------------------------------------------------------------------
# Core pipeline — one full cycle
# ---------------------------------------------------------------------------
def run_cycle(state: dict) -> dict:
    """Execute one full pipeline cycle. Returns updated counters."""
    stats = {"scanned": 0, "triaged": 0, "planned": 0, "skipped": 0, "errors": 0}

    # Ensure directories exist
    for d in (INBOX_DIR, NEEDS_ACTION_DIR, DONE_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # Gather inbox files
    inbox_files = sorted(INBOX_DIR.glob("*.md"))
    stats["scanned"] = len(inbox_files)

    if not inbox_files:
        log.info("Inbox is empty -- nothing to process")
        return stats

    log.info("Found %d file(s) in Inbox", len(inbox_files))

    for fpath in inbox_files:
        fname = fpath.name
        file_key = fname
        file_mtime = fpath.stat().st_mtime

        # Check if already processed (by name + mtime)
        prev = state["processed"].get(file_key)
        if prev and prev.get("mtime") == file_mtime:
            log.info("  [SKIP] %s (already processed)", fname)
            stats["skipped"] += 1
            continue

        log.info("  [PROCESSING] %s", fname)

        # --- Stage 1: Triage ---
        triage_out, triage_status = triage_file(fpath)
        if triage_out is None and triage_status == "already triaged":
            log.info("    Triage: skipped (output exists)")
        elif triage_out is None:
            log.error("    Triage failed: %s", triage_status)
            stats["errors"] += 1
            continue
        else:
            log.info("    Triaged -> %s (%s)", triage_out.parent.name, triage_status)
            stats["triaged"] += 1

        # --- Stage 2: Plan ---
        plan_path = create_plan(fpath)
        if plan_path:
            log.info("    Plan created: %s", plan_path.name)
            stats["planned"] += 1
        else:
            log.warning("    Plan creation failed")
            stats["errors"] += 1

        # Mark as processed
        state["processed"][file_key] = {
            "mtime": file_mtime,
            "processed_at": datetime.now().isoformat(),
            "plan": plan_path.name if plan_path else None,
        }

    # --- Stage 3: Daily report (once per day) ---
    if should_run_daily_report(state):
        log.info("Generating daily report...")
        report = run_daily_report(state)
        if report:
            log.info("Daily report saved: %s", report.name)

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Employee Scheduler -- orchestrates the full task pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_ai_employee.py --once          # Single pass (Task Scheduler / cron)
  python scripts/run_ai_employee.py --daemon         # Loop every 5 minutes
  python scripts/run_ai_employee.py --daemon -i 10   # Loop every 10 minutes
        """,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run once and exit")
    mode.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument(
        "-i", "--interval", type=int, default=5,
        help="Minutes between cycles in daemon mode (default: 5)",
    )

    args = parser.parse_args()

    # Banner
    log.info("=" * 55)
    log.info("  AI Employee Scheduler (Silver Tier)")
    log.info("  Vault: %s", VAULT_DIR)
    log.info("  Mode:  %s", "daemon" if args.daemon else "once")
    if args.daemon:
        log.info("  Interval: %d minute(s)", args.interval)
    log.info("=" * 55)

    # Lock
    if not acquire_lock():
        log.error("Another scheduler instance is already running. Exiting.")
        sys.exit(1)

    try:
        if args.once:
            # Single pass
            state = load_state()
            state["cycle_count"] = state.get("cycle_count", 0) + 1
            state["last_run"] = datetime.now().isoformat()

            stats = run_cycle(state)
            save_state(state)

            log.info(
                "Cycle complete: scanned=%d triaged=%d planned=%d skipped=%d errors=%d",
                stats["scanned"], stats["triaged"], stats["planned"],
                stats["skipped"], stats["errors"],
            )

        elif args.daemon:
            log.info("Daemon started. Press Ctrl+C to stop.\n")
            state = load_state()

            while True:
                state["cycle_count"] = state.get("cycle_count", 0) + 1
                state["last_run"] = datetime.now().isoformat()
                cycle_num = state["cycle_count"]

                log.info("--- Cycle #%d ---", cycle_num)
                stats = run_cycle(state)
                save_state(state)

                log.info(
                    "Cycle #%d complete: scanned=%d triaged=%d planned=%d skipped=%d errors=%d",
                    cycle_num, stats["scanned"], stats["triaged"],
                    stats["planned"], stats["skipped"], stats["errors"],
                )
                log.info("Next cycle in %d minute(s)...\n", args.interval)

                time.sleep(args.interval * 60)

    except KeyboardInterrupt:
        log.info("\nShutdown requested. Saving state...")
        save_state(state)
        log.info("Scheduler stopped.")

    finally:
        release_lock()


if __name__ == "__main__":
    main()
