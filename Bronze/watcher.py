"""
Bronze Tier — Inbox Watcher
Monitors vault/Inbox/ for new .md files, triages them using the 6-rule
decision table from SKILL.md, and writes structured output files.

All errors are logged via the centralized error logger and failed tasks
are queued for automatic retry by the recovery manager.
"""

import re
import time
import os
import sys
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

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
DONE_DIR = os.path.join(VAULT_DIR, "Done")

ACTION_VERBS = [
    "fix", "add", "remove", "update", "create",
    "delete", "change", "implement", "deploy", "review",
]


# ---------------------------------------------------------------------------
# Helper — extract a title from the file (first heading or filename)
# ---------------------------------------------------------------------------
def extract_title(content: str, filename: str) -> str:
    """Pull the first markdown heading, or fall back to the filename."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")


# ---------------------------------------------------------------------------
# Helper — build a short summary from the task body (Step 2)
# ---------------------------------------------------------------------------
def summarize(content: str, max_lines: int = 5, max_chars: int = 300) -> str:
    """Return a plain-text summary following the SKILL.md rules."""
    lines = content.splitlines()

    # Check for a TL;DR or Summary: line first
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("TL;DR") or stripped.startswith("Summary:"):
            summary = stripped
            if len(summary) > max_chars:
                summary = summary[: max_chars - 3] + "..."
            return summary

    # Strip markdown formatting and blank lines
    body_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Remove headings, bold, links, images
        plain = re.sub(r"^#+\s*", "", stripped)
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", plain)
        plain = re.sub(r"\*(.+?)\*", r"\1", plain)
        plain = re.sub(r"!\[.*?\]\(.*?\)", "", plain)
        plain = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", plain)
        plain = plain.strip()
        if plain:
            body_lines.append(plain)

    if not body_lines:
        return "(no body content)"

    summary = "\n".join(body_lines[:max_lines])
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3] + "..."
    return summary


# ---------------------------------------------------------------------------
# Core — decide destination using the 6-rule decision table (Step 3)
# ---------------------------------------------------------------------------
def decide_destination(content: str) -> tuple[str, int, str]:
    """
    Evaluate content against the triage rules.
    Returns (destination_dir, rule_number, status_label).
    """
    body_lower = content.lower()

    # Rule 1: "DONE" or "COMPLETED" anywhere (case-insensitive)
    if re.search(r"\bdone\b", body_lower) or re.search(r"\bcompleted\b", body_lower):
        return DONE_DIR, 1, "Done"

    # Rule 2: Any line contains a question mark
    if "?" in content:
        return NEEDS_ACTION_DIR, 2, "Needs Action"

    # Rule 3: Body contains action verbs
    for verb in ACTION_VERBS:
        if re.search(r"\b" + verb + r"\b", body_lower):
            return NEEDS_ACTION_DIR, 3, "Needs Action"

    # Rule 4: Checklist with at least one unchecked item
    if re.search(r"- \[ \]", content):
        return NEEDS_ACTION_DIR, 4, "Needs Action"

    # Rule 5: Checklist where every item is checked
    if re.search(r"- \[x\]", content, re.IGNORECASE) and not re.search(r"- \[ \]", content):
        return DONE_DIR, 5, "Done"

    # Rule 6: Default — route to Needs_Action
    return NEEDS_ACTION_DIR, 6, "Needs Action"


# ---------------------------------------------------------------------------
# Helper — find a non-conflicting output path (Step 5 edge case)
# ---------------------------------------------------------------------------
def unique_output_path(dest_dir: str, filename: str) -> str:
    """If the filename already exists in dest_dir, append _2, _3, etc."""
    candidate = os.path.join(dest_dir, filename)
    if not os.path.exists(candidate):
        return candidate

    name, ext = os.path.splitext(filename)
    counter = 2
    while True:
        candidate = os.path.join(dest_dir, f"{name}_{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# Core — process a single inbox file (with retry support)
# ---------------------------------------------------------------------------
@retry(max_attempts=2, backoff=1.5, initial_delay=0.5)
def process_file(filepath: str) -> None:
    """Read an inbox .md file, triage it, and write the structured output."""
    filename = os.path.basename(filepath)

    # --- Step 5: encoding error handling ---
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        error_logger.log_error("watcher.process_file", e, {
            "filepath": filepath,
            "phase": "read",
        })
        raise  # Let retry handle it

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Step 5: empty / whitespace-only file ---
    if not content.strip():
        dest_dir = NEEDS_ACTION_DIR
        rule_num = 0
        status = "Needs Action"
        title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
        summary = "(empty file — manual review required)"
    else:
        title = extract_title(content, filename)
        summary = summarize(content)
        dest_dir, rule_num, status = decide_destination(content)

    # --- Step 5: idempotency — skip if already processed ---
    output_path = unique_output_path(dest_dir, filename)
    base_check = os.path.join(dest_dir, filename)
    if os.path.exists(base_check):
        print(f"[SKIP]  Already processed: {filename} exists in {os.path.basename(dest_dir)}/")
        return

    # --- Step 4: write the output file using the SKILL.md template ---
    dest_folder_name = os.path.basename(dest_dir)
    rule_label = f"#{rule_num}" if rule_num > 0 else "#0 (empty file)"

    response = f"""# {title}

## Metadata
- **Source:** Inbox/{filename}
- **Received:** {timestamp}
- **Routed to:** {dest_folder_name}/
- **Triage rule:** {rule_label}
- **Status:** {status}

## Summary
{summary}

## Original Task
{content}

## Agent Notes
- Triage complete. File routed by rule {rule_label}.
"""

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response)
    except OSError as e:
        error_logger.log_error("watcher.process_file", e, {
            "filepath": filepath,
            "output_path": output_path,
            "phase": "write",
        })
        raise

    error_logger.log_audit("watcher.triage", "success", {
        "file": filename,
        "destination": dest_folder_name,
        "rule": rule_num,
    })
    print(f"[{timestamp}]  Processed: Inbox/{filename}  -->  {dest_folder_name}/{os.path.basename(output_path)}")


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------
class InboxHandler(FileSystemEventHandler):
    """React to new .md files appearing in the Inbox folder."""

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".md"):
            return

        # Small delay so the OS finishes writing the file
        time.sleep(0.5)

        try:
            process_file(event.src_path)
        except Exception as e:
            error_logger.log_error("watcher.on_created", e, {
                "filepath": event.src_path,
                "phase": "handler",
            })
            # Queue for recovery
            failed_queue.push(
                source="watcher.process_file",
                context={"filepath": event.src_path},
                error=str(e),
            )
            print(f"[ERROR] Failed to process {event.src_path}: {e} (queued for retry)")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    for folder in (INBOX_DIR, NEEDS_ACTION_DIR, DONE_DIR):
        os.makedirs(folder, exist_ok=True)

    # Process any .md files already sitting in the Inbox
    existing = sorted(f for f in os.listdir(INBOX_DIR) if f.endswith(".md"))
    if existing:
        print(f"Found {len(existing)} existing file(s) in Inbox — processing now.")
        for fname in existing:
            fpath = os.path.join(INBOX_DIR, fname)
            try:
                process_file(fpath)
            except Exception as e:
                error_logger.log_error("watcher.startup", e, {
                    "filepath": fpath,
                    "phase": "initial_scan",
                })
                failed_queue.push(
                    source="watcher.process_file",
                    context={"filepath": fpath},
                    error=str(e),
                )
                print(f"[ERROR] {fname}: {e} (queued for retry)")

    # Start watching for new files
    handler = InboxHandler()
    observer = Observer()
    observer.schedule(handler, path=INBOX_DIR, recursive=False)
    observer.start()

    error_logger.log_audit("watcher.started", "running", {
        "watching": INBOX_DIR,
    })

    print()
    print("=" * 55)
    print("  Bronze Agent — Inbox Watcher running")
    print(f"  Watching: {INBOX_DIR}")
    print("  Drop a .md file into vault/Inbox/ to trigger it.")
    print("  Press Ctrl+C to stop.")
    print("=" * 55)
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down watcher...")
        observer.stop()
        error_logger.log_audit("watcher.stopped", "shutdown", {})

    observer.join()
    print("Watcher stopped.")


if __name__ == "__main__":
    main()
