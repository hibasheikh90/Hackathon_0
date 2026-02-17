"""
Gold Tier — Daily Error Summary Report
=========================================
Reads error.log and the failed task queue, aggregates errors by source
and severity, and generates a daily summary report in Logs/.

Runs daily via the Gold scheduler (alongside the daily report).

Usage:
    from briefings.daily_error_summary import generate_error_summary

    path = generate_error_summary()  # returns Path to the report

CLI:
    python -m briefings.daily_error_summary
    python -m briefings.daily_error_summary --stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger

# Paths
LOGS_DIR = _PROJECT_ROOT / "Logs"
ERROR_LOG = _PROJECT_ROOT / "logs" / "error.log"
AUDIT_LOG = _PROJECT_ROOT / "logs" / "audit.log"
FAILED_QUEUE_FILE = _PROJECT_ROOT / "Logs" / "failed_tasks.json"


def _read_log_entries(log_path: Path, since: datetime) -> list[dict]:
    """Read JSON Lines entries from a log file since the given timestamp."""
    if not log_path.is_file():
        return []

    entries = []
    since_str = since.isoformat()

    try:
        for line in log_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = record.get("ts", "")
            if ts >= since_str:
                entries.append(record)
    except OSError:
        pass

    return entries


def _load_failed_queue() -> list[dict]:
    """Load the failed task queue."""
    if not FAILED_QUEUE_FILE.is_file():
        return []
    try:
        return json.loads(FAILED_QUEUE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _aggregate_errors(errors: list[dict]) -> dict:
    """Aggregate error entries by source and severity."""
    by_source: dict[str, list[dict]] = defaultdict(list)
    by_severity: dict[str, int] = defaultdict(int)
    error_types: dict[str, int] = defaultdict(int)

    for err in errors:
        source = err.get("source", "unknown")
        severity = err.get("severity", "ERROR")
        error_type = err.get("error_type", "unknown")

        by_source[source].append(err)
        by_severity[severity] += 1
        error_types[error_type] += 1

    return {
        "by_source": dict(by_source),
        "by_severity": dict(by_severity),
        "error_types": dict(error_types),
        "total": len(errors),
    }


def _aggregate_audit(audit_entries: list[dict]) -> dict:
    """Aggregate audit entries for recovery stats."""
    recovery_stats = {"attempted": 0, "recovered": 0, "failed": 0}

    for entry in audit_entries:
        action = entry.get("action", "")
        if action == "recovery.success":
            recovery_stats["recovered"] += 1
            recovery_stats["attempted"] += 1
        elif action == "recovery.cycle":
            details = entry.get("details", {})
            # Use the cycle summary if available
            if "attempted" in details:
                recovery_stats["attempted"] = max(
                    recovery_stats["attempted"], details["attempted"]
                )

    return recovery_stats


def generate_error_summary(
    stdout_only: bool = False,
    hours_back: int = 24,
) -> Path | None:
    """Generate the daily error summary report.

    Args:
        stdout_only: Print to stdout instead of writing to file.
        hours_back: How many hours of history to include.

    Returns:
        Path to the generated file, or None if stdout_only.
    """
    now = datetime.now()
    since = now - timedelta(hours=hours_back)
    date_str = now.strftime("%Y-%m-%d")

    # Collect data
    errors = _read_log_entries(ERROR_LOG, since)
    audit_entries = _read_log_entries(AUDIT_LOG, since)
    failed_tasks = _load_failed_queue()

    agg = _aggregate_errors(errors)
    recovery = _aggregate_audit(audit_entries)

    # Failed queue stats
    queue_pending = [t for t in failed_tasks if t.get("status") == "pending"]
    queue_failed = [t for t in failed_tasks if t.get("status") == "failed"]
    queue_resolved = [t for t in failed_tasks if t.get("status") == "resolved"]

    # Determine health status
    if agg["total"] == 0:
        health = "HEALTHY"
        health_icon = "[OK]"
    elif agg["total"] <= 5:
        health = "MINOR ISSUES"
        health_icon = "[WARN]"
    elif agg["by_severity"].get("CRITICAL", 0) > 0:
        health = "CRITICAL"
        health_icon = "[CRIT]"
    else:
        health = "DEGRADED"
        health_icon = "[ERR]"

    # Build report
    lines = [
        f"# Daily Error Summary — {date_str}",
        "",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M')}",
        f"**Period:** Last {hours_back} hours (since {since.strftime('%Y-%m-%d %H:%M')})",
        f"**System Health:** {health_icon} {health}",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"| Metric | Count |",
        f"|---|---|",
        f"| Total errors | {agg['total']} |",
        f"| Critical | {agg['by_severity'].get('CRITICAL', 0)} |",
        f"| Errors | {agg['by_severity'].get('ERROR', 0)} |",
        f"| Warnings | {agg['by_severity'].get('WARNING', 0)} |",
        "",
    ]

    # Errors by source
    if agg["by_source"]:
        lines.extend([
            "---",
            "",
            "## Errors by Source",
            "",
            "| Source | Count | Last Error | Severity |",
            "|---|---|---|---|",
        ])
        for source, source_errors in sorted(
            agg["by_source"].items(),
            key=lambda x: len(x[1]),
            reverse=True,
        ):
            last = source_errors[-1]
            last_msg = last.get("error", "")[:60]
            if len(last.get("error", "")) > 60:
                last_msg += "..."
            severity = last.get("severity", "ERROR")
            lines.append(f"| `{source}` | {len(source_errors)} | {last_msg} | {severity} |")
        lines.append("")

    # Error types
    if agg["error_types"]:
        lines.extend([
            "---",
            "",
            "## Error Types",
            "",
            "| Type | Count |",
            "|---|---|",
        ])
        for etype, count in sorted(agg["error_types"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| `{etype}` | {count} |")
        lines.append("")

    # Recovery stats
    lines.extend([
        "---",
        "",
        "## Recovery & Retry Status",
        "",
        "| Metric | Count |",
        "|---|---|",
        f"| Tasks retried | {recovery['attempted']} |",
        f"| Successfully recovered | {recovery['recovered']} |",
        f"| Queue — pending retry | {len(queue_pending)} |",
        f"| Queue — permanently failed | {len(queue_failed)} |",
        f"| Queue — resolved | {len(queue_resolved)} |",
        "",
    ])

    # Pending tasks detail
    if queue_pending:
        lines.extend([
            "### Pending Retry Tasks",
            "",
        ])
        for task in queue_pending:
            retry_count = task.get("retry_count", 0)
            max_retries = task.get("max_retries", 3)
            lines.append(
                f"- **{task['source']}** (attempt {retry_count}/{max_retries}) "
                f"— {task.get('error', 'unknown')[:80]}"
            )
        lines.append("")

    # Permanently failed tasks
    if queue_failed:
        lines.extend([
            "### Permanently Failed Tasks (require manual intervention)",
            "",
        ])
        for task in queue_failed:
            lines.append(
                f"- **{task['source']}** — {task.get('error', 'unknown')[:80]} "
                f"— created {task.get('created_at', 'unknown')[:10]}"
            )
        lines.append("")

    # Recent error timeline (last 10)
    if errors:
        lines.extend([
            "---",
            "",
            "## Recent Error Timeline",
            "",
        ])
        for err in errors[-10:]:
            ts = err.get("ts", "")[:19]
            source = err.get("source", "unknown")
            msg = err.get("error", "")[:80]
            severity = err.get("severity", "ERROR")
            lines.append(f"- `{ts}` [{severity}] **{source}** — {msg}")
        lines.append("")

    # No errors message
    if agg["total"] == 0 and not queue_pending:
        lines.extend([
            "---",
            "",
            "No errors recorded in the last 24 hours. All systems operating normally.",
            "",
        ])

    lines.extend([
        "---",
        "",
        f"*Generated {now.strftime('%Y-%m-%d %H:%M')} by AI Employee Error Monitor*",
        "",
    ])

    output = "\n".join(lines)

    if stdout_only:
        print(output)
        return None

    # Write to Logs/
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"DailyErrorSummary_{now.strftime('%Y%m%d')}.md"
    output_path = LOGS_DIR / filename

    output_path.write_text(output, encoding="utf-8")

    error_logger.log_audit("error_summary.daily", "generated", {
        "file": filename,
        "total_errors": agg["total"],
        "health": health,
        "pending_retries": len(queue_pending),
    })

    print(f"[OK] Daily error summary generated: Logs/{filename}")
    print(f"  Health: {health_icon} {health}")
    print(f"  Errors: {agg['total']} | Pending retries: {len(queue_pending)}")

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily error summary report.")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout only")
    parser.add_argument("--hours", type=int, default=24, help="Hours of history (default: 24)")
    args = parser.parse_args()

    generate_error_summary(stdout_only=args.stdout, hours_back=args.hours)


if __name__ == "__main__":
    main()
