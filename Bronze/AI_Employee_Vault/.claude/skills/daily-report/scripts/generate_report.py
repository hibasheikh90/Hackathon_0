"""
Skill: daily-report
Scans the vault and generates a structured daily activity report.
"""

import argparse
import os
import re
import sys
from datetime import datetime

# Resolve vault path relative to this script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
VAULT_DIR = os.path.join(PROJECT_ROOT, "vault")

STAGES = {
    "Inbox": os.path.join(VAULT_DIR, "Inbox"),
    "Needs_Action": os.path.join(VAULT_DIR, "Needs_Action"),
    "Done": os.path.join(VAULT_DIR, "Done"),
}


def list_md_files(directory: str) -> list[dict]:
    """List all .md files in a directory with metadata."""
    if not os.path.isdir(directory):
        return []

    results = []
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(directory, fname)
        stat = os.stat(fpath)
        modified = datetime.fromtimestamp(stat.st_mtime)

        # Extract title and metadata from content
        title = fname
        priority = "-"
        approval = "-"
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            # Title: first heading
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") and not stripped.startswith("##"):
                    title = stripped.lstrip("#").strip()
                    break
            # Priority from plan files
            m = re.search(r"\*\*Priority[:\s]*\*\*\s*(\w+)", content, re.IGNORECASE)
            if not m:
                m = re.search(r"^## Priority\s*\n\*\*(\w+)\*\*", content, re.MULTILINE)
            if m:
                priority = m.group(1)
            # Approval
            m = re.search(r"Requires Human Approval[?]?\s*\n\*\*(\w+)\*\*", content, re.IGNORECASE)
            if not m:
                m = re.search(r"Human Approval[?]?\s*$\s*\*\*(\w+)\*\*", content, re.MULTILINE)
            if m:
                approval = m.group(1)
        except (OSError, UnicodeDecodeError):
            pass

        results.append({
            "file": fname,
            "title": title,
            "modified": modified,
            "priority": priority,
            "approval": approval,
        })

    return results


def files_on_date(files: list[dict], target_date: datetime) -> list[dict]:
    """Filter files modified on a specific date."""
    return [f for f in files if f["modified"].date() == target_date.date()]


def build_attention_items(needs_action: list[dict]) -> list[str]:
    """Identify items that need human attention."""
    items = []
    for f in needs_action:
        reasons = []
        if f["priority"].lower() == "high":
            reasons.append("high priority")
        if f["approval"].lower() == "yes":
            reasons.append("requires human approval")
        if reasons:
            reason_str = ", ".join(reasons)
            items.append(f"- **[{f['priority'].upper()}]** {f['file']} — {f['title']} ({reason_str})")
    return items


def generate(target_date: datetime) -> str:
    """Build the full report markdown."""
    date_str = target_date.strftime("%Y-%m-%d")

    inbox = list_md_files(STAGES["Inbox"])
    needs_action = list_md_files(STAGES["Needs_Action"])
    done_all = list_md_files(STAGES["Done"])
    done_today = files_on_date(done_all, target_date)
    attention = build_attention_items(needs_action)

    # ---- Build report ----
    lines = [
        f"# Daily Report — {date_str}",
        "",
        "## Summary",
        f"- **Inbox:** {len(inbox)} task(s)",
        f"- **Needs Action:** {len(needs_action)} task(s) pending",
        f"- **Completed today:** {len(done_today)} task(s)",
        f"- **Attention items:** {len(attention)}",
        "",
    ]

    # Inbox
    lines.append("## Inbox (New)")
    if inbox:
        lines.append("| File | Title | Last Modified |")
        lines.append("|------|-------|---------------|")
        for f in inbox:
            ts = f["modified"].strftime("%Y-%m-%d %H:%M")
            lines.append(f"| {f['file']} | {f['title']} | {ts} |")
    else:
        lines.append("_No items in Inbox._")
    lines.append("")

    # Needs Action
    lines.append("## Needs Action (Pending)")
    if needs_action:
        lines.append("| File | Title | Priority | Approval Needed |")
        lines.append("|------|-------|----------|-----------------|")
        for f in needs_action:
            lines.append(f"| {f['file']} | {f['title']} | {f['priority']} | {f['approval']} |")
    else:
        lines.append("_No pending tasks._")
    lines.append("")

    # Completed today
    lines.append("## Completed Today")
    if done_today:
        lines.append("| File | Title | Completed |")
        lines.append("|------|-------|-----------|")
        for f in done_today:
            ts = f["modified"].strftime("%Y-%m-%d %H:%M")
            lines.append(f"| {f['file']} | {f['title']} | {ts} |")
    else:
        lines.append("_No tasks completed today._")
    lines.append("")

    # Attention
    lines.append("## Attention Required")
    if attention:
        lines.extend(attention)
    else:
        lines.append("_No items require immediate attention._")
    lines.append("")

    # Footer
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("---")
    lines.append(f"_Generated {timestamp} by AI Employee (Silver Tier)_")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a daily vault activity report.")
    parser.add_argument(
        "--date",
        default=None,
        help="Target date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout only, do not write a file.",
    )
    args = parser.parse_args()

    # Parse target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"[ERROR] Invalid date format: '{args.date}'. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date = datetime.now()

    # Ensure vault directories exist
    for path in STAGES.values():
        os.makedirs(path, exist_ok=True)

    report = generate(target_date)

    if args.stdout:
        print(report)
        return

    # Write report file
    date_tag = target_date.strftime("%Y%m%d")
    report_name = f"DailyReport_{date_tag}.md"
    report_path = os.path.join(STAGES["Done"], report_name)

    # Don't overwrite existing reports
    if os.path.exists(report_path):
        counter = 2
        while True:
            report_name = f"DailyReport_{date_tag}_{counter}.md"
            report_path = os.path.join(STAGES["Done"], report_name)
            if not os.path.exists(report_path):
                break
            counter += 1

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Summary output
    inbox_count = len(list_md_files(STAGES["Inbox"]))
    pending_count = len(list_md_files(STAGES["Needs_Action"]))
    done_today_count = len(files_on_date(list_md_files(STAGES["Done"]), target_date))

    print(f"[OK] Daily report generated: {report_name}")
    print(f"  Inbox: {inbox_count} | Pending: {pending_count} | Done today: {done_today_count}")


if __name__ == "__main__":
    main()
