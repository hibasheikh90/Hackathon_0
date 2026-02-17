"""
Bronze Tier — Reasoning Planner
Reads tasks from vault/Inbox/, generates detailed plan files in vault/Needs_Action/.
Plans only — never executes tasks.

All errors are logged via the centralized error logger and failed tasks
are queued for automatic retry by the recovery manager.
"""

import re
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger
from core.retry import retry, failed_queue

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault")
INBOX_DIR = os.path.join(VAULT_DIR, "Inbox")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")

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
# Helper — extract title
# ---------------------------------------------------------------------------
def extract_title(content: str, filename: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")


# ---------------------------------------------------------------------------
# Helper — determine priority
# ---------------------------------------------------------------------------
def determine_priority(content: str) -> tuple[str, str]:
    body_lower = content.lower()
    for word in URGENCY_WORDS:
        if re.search(r"\b" + word + r"\b", body_lower):
            return "High", f"Contains urgency indicator: \"{word}\""

    for verb in ACTION_VERBS:
        if re.search(r"\b" + verb + r"\b", body_lower):
            return "Medium", "Contains action verbs with no urgency signals"

    if "?" in content:
        return "Low", "Informational or exploratory — contains questions only"

    return "Medium", "Default priority for actionable content"


# ---------------------------------------------------------------------------
# Helper — determine if human approval is needed
# ---------------------------------------------------------------------------
def needs_approval(content: str) -> tuple[str, str]:
    body_lower = content.lower()
    for keyword in APPROVAL_KEYWORDS:
        if re.search(r"\b" + keyword + r"\b", body_lower):
            return "Yes", f"Task involves \"{keyword}\" — requires human review"

    if not content.strip():
        return "Yes", "Task is empty or unclear — needs human clarification"

    # Check for ambiguity (very short body, no clear action)
    non_empty_lines = [l for l in content.splitlines() if l.strip()]
    if len(non_empty_lines) < 2:
        return "Yes", "Task is too brief — may need clarification"

    return "No", "Task is clear and does not involve sensitive operations"


# ---------------------------------------------------------------------------
# Helper — generate step-by-step plan from content
# ---------------------------------------------------------------------------
def generate_steps(content: str, title: str) -> list[str]:
    steps = []

    if not content.strip():
        return ["Request task details from the sender"]

    # Extract checklist items as steps
    checklist_items = re.findall(r"- \[[ x]\]\s*(.+)", content, re.IGNORECASE)
    if checklist_items:
        for item in checklist_items:
            item = item.strip()
            steps.append(item)
        steps.append("Verify all checklist items are completed")
        steps.append("Mark task as done and archive")
        return steps

    # Extract action sentences from body
    body_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body_lines.append(stripped)

    if body_lines:
        steps.append(f"Review the full task: \"{title}\"")
        for line in body_lines:
            clean = re.sub(r"^\d+\.\s*", "", line)  # strip numbered lists
            clean = re.sub(r"^[-*]\s*", "", clean)   # strip bullet points
            if clean:
                steps.append(clean)
        steps.append("Verify the result meets the task requirements")
        steps.append("Mark task as done and archive")
    else:
        steps.append(f"Interpret the task: \"{title}\"")
        steps.append("Gather any missing information")
        steps.append("Execute the task")
        steps.append("Verify the result")

    return steps


# ---------------------------------------------------------------------------
# Helper — generate objective from content
# ---------------------------------------------------------------------------
def generate_objective(content: str, title: str) -> str:
    if not content.strip():
        return "Clarify task requirements — the original task is empty or unclear."

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


# ---------------------------------------------------------------------------
# Helper — generate suggested output
# ---------------------------------------------------------------------------
def generate_suggested_output(content: str, title: str) -> str:
    if not content.strip():
        return "A clarified task description with actionable details."

    checklist_items = re.findall(r"- \[ \]\s*(.+)", content)
    if checklist_items:
        items_text = ", ".join(item.strip() for item in checklist_items[:3])
        return f"Completed deliverables: {items_text}."

    return f"Completed task: \"{title}\" with all requirements fulfilled."


# ---------------------------------------------------------------------------
# Helper — unique plan path
# ---------------------------------------------------------------------------
def unique_plan_path(timestamp_str: str) -> str:
    candidate = os.path.join(NEEDS_ACTION_DIR, f"Plan_{timestamp_str}.md")
    if not os.path.exists(candidate):
        return candidate

    counter = 2
    while True:
        candidate = os.path.join(NEEDS_ACTION_DIR, f"Plan_{timestamp_str}_{counter}.md")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# Core — create a plan for a single inbox file (with retry support)
# ---------------------------------------------------------------------------
@retry(max_attempts=2, backoff=1.5, initial_delay=0.5)
def create_plan(filepath: str) -> str | None:
    """Read an inbox .md file and generate a plan. Returns the plan path or None."""
    filename = os.path.basename(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        error_logger.log_error("planner.create_plan", e, {
            "filepath": filepath,
            "phase": "read",
        })
        raise

    now = datetime.now()
    timestamp_file = now.strftime("%Y%m%d_%H%M%S")
    timestamp_display = now.strftime("%Y-%m-%d %H:%M:%S")

    title = extract_title(content, filename)
    objective = generate_objective(content, title)
    steps = generate_steps(content, title)
    priority, priority_reason = determine_priority(content)
    approval, approval_reason = needs_approval(content)
    suggested_output = generate_suggested_output(content, title)

    # Format steps
    steps_text = "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))

    plan_content = f"""# Task Plan

## Original Task
**Source:** Inbox/{filename}
**Received:** {timestamp_display}

{content.strip()}

## Objective
{objective}

## Step-by-Step Plan
{steps_text}

## Priority
**{priority}** — {priority_reason}

## Requires Human Approval?
**{approval}** — {approval_reason}

## Suggested Output
{suggested_output}
"""

    try:
        plan_path = unique_plan_path(timestamp_file)
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_content)
    except OSError as e:
        error_logger.log_error("planner.create_plan", e, {
            "filepath": filepath,
            "phase": "write",
        })
        raise

    plan_name = os.path.basename(plan_path)
    error_logger.log_audit("planner.plan_created", "success", {
        "source_file": filename,
        "plan_file": plan_name,
        "priority": priority,
        "needs_approval": approval,
    })
    print(f"[{timestamp_display}]  Plan created: {plan_name}  (from Inbox/{filename})")
    return plan_path


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------
class InboxPlannerHandler(FileSystemEventHandler):
    """React to new .md files in Inbox by generating plan files."""

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".md"):
            return
        time.sleep(0.5)
        try:
            create_plan(event.src_path)
        except Exception as e:
            error_logger.log_error("planner.on_created", e, {
                "filepath": event.src_path,
                "phase": "handler",
            })
            failed_queue.push(
                source="planner.create_plan",
                context={"filepath": event.src_path},
                error=str(e),
            )
            print(f"[ERROR] Failed to plan {event.src_path}: {e} (queued for retry)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(INBOX_DIR, exist_ok=True)
    os.makedirs(NEEDS_ACTION_DIR, exist_ok=True)

    # Process any .md files already in the Inbox
    existing = sorted(f for f in os.listdir(INBOX_DIR) if f.endswith(".md"))
    if existing:
        print(f"Found {len(existing)} task(s) in Inbox — generating plans.\n")
        for fname in existing:
            fpath = os.path.join(INBOX_DIR, fname)
            try:
                create_plan(fpath)
            except Exception as e:
                error_logger.log_error("planner.startup", e, {
                    "filepath": fpath,
                    "phase": "initial_scan",
                })
                failed_queue.push(
                    source="planner.create_plan",
                    context={"filepath": fpath},
                    error=str(e),
                )
                print(f"[ERROR] {fname}: {e} (queued for retry)")
        print()

    # If --once flag, exit after processing existing files
    if "--once" in sys.argv:
        print("Done (--once mode).")
        return

    # Start watching for new files
    handler = InboxPlannerHandler()
    observer = Observer()
    observer.schedule(handler, path=INBOX_DIR, recursive=False)
    observer.start()

    error_logger.log_audit("planner.started", "running", {
        "watching": INBOX_DIR,
    })

    print("=" * 55)
    print("  Bronze Agent — Reasoning Planner running")
    print(f"  Watching: {INBOX_DIR}")
    print("  Drop a .md file into vault/Inbox/ to trigger it.")
    print("  Press Ctrl+C to stop.")
    print("=" * 55)
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down planner...")
        observer.stop()
        error_logger.log_audit("planner.stopped", "shutdown", {})

    observer.join()
    print("Planner stopped.")


if __name__ == "__main__":
    main()
