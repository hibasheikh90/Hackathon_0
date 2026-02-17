"""
Gold Tier — Weekly CEO Briefing Generator
============================================
Orchestrates all data collectors, renders the Jinja2 template,
and writes the briefing to vault/Done/WeeklyBrief_YYYYWNN.md.

Runs every Monday at 08:00 via the Gold scheduler.

Usage:
    from briefings.weekly_ceo import generate_briefing

    path = generate_briefing()   # returns Path to the generated file

CLI:
    python -m briefings.weekly_ceo
    python -m briefings.weekly_ceo --stdout
    python -m briefings.weekly_ceo --week 2026-W07
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
DONE_DIR = VAULT_DIR / "Done"

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_FILE = "ceo_briefing.md.j2"


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _collect_all() -> dict[str, Any]:
    """Run every data collector and return a merged context dict."""
    from briefings.data_collectors import vault_stats, financial_summary, social_metrics, email_digest

    config.load()
    briefing_cfg = config.briefing

    data: dict[str, Any] = {}

    # Always collect vault stats
    data["vault"] = vault_stats.collect()

    # Financial data (if configured)
    if briefing_cfg.get("include_financials", True):
        data["financials"] = financial_summary.collect()
    else:
        data["financials"] = {"available": False}

    # Social metrics
    if briefing_cfg.get("include_social_metrics", True):
        data["social"] = social_metrics.collect()
    else:
        data["social"] = {"platforms": [], "total_posts": 0}

    # Email digest
    if briefing_cfg.get("include_email_digest", True):
        data["email"] = email_digest.collect()
    else:
        data["email"] = {"emails_received": 0, "emails_sent": 0, "key_threads": []}

    return data


# ---------------------------------------------------------------------------
# Executive summary generation
# ---------------------------------------------------------------------------

def _build_executive_summary(data: dict[str, Any]) -> str:
    """Build the executive summary paragraph from collected data."""
    parts = []

    vault = data.get("vault", {})
    done = vault.get("done_this_week", 0)
    new = vault.get("new_this_week", 0)
    backlog = vault.get("backlog", 0)

    parts.append(
        f"AI Employee processed **{done}** tasks this week "
        f"({new} new received, {backlog} in backlog)."
    )

    # Financial headline
    financials = data.get("financials", {})
    if financials.get("available"):
        rev = financials.get("revenue_this_week")
        change = financials.get("revenue_change_pct")
        if rev is not None and change is not None:
            direction = "up" if change >= 0 else "down"
            parts.append(f"Revenue ${rev:,.2f} ({direction} {abs(change):.1f}%).")
        cash = financials.get("cash_position")
        if cash is not None:
            parts.append(f"Cash position: ${cash:,.2f}.")

    # Social headline
    social = data.get("social", {})
    total_posts = social.get("total_posts", 0)
    if total_posts:
        parts.append(f"{total_posts} social media posts published.")

    # Action items count
    action_items = data.get("action_items", [])
    if action_items:
        parts.append(f"**{len(action_items)} item(s) require your decision.**")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Action items extraction
# ---------------------------------------------------------------------------

def _extract_action_items(data: dict[str, Any]) -> list[dict]:
    """Extract items requiring CEO decision from collected data."""
    items = []

    # From vault high-priority items
    vault = data.get("vault", {})
    for hp in vault.get("high_priority_items", []):
        items.append({
            "title": hp["title"],
            "file": hp["file"],
            "priority": "HIGH",
        })

    # From overdue invoices (financial data)
    financials = data.get("financials", {})
    if financials.get("available") and financials.get("ar_aging"):
        overdue_90 = financials["ar_aging"].get("over_90_days", 0)
        if overdue_90 > 0:
            items.append({
                "title": f"AR over 90 days: ${overdue_90:,.2f} — escalate collections?",
                "file": "Odoo AR Aging Report",
                "priority": "HIGH",
            })

    # From unresolved email threads
    email_data = data.get("email", {})
    for thread in email_data.get("key_threads", []):
        if thread.get("status") == "Awaiting action":
            items.append({
                "title": f"Email: {thread['subject']}",
                "file": "Gmail import",
                "priority": "MEDIUM",
            })

    return items


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _render_template(context: dict[str, Any]) -> str:
    """Render the Jinja2 template with collected data.

    Falls back to a plain-text builder if Jinja2 is not installed.
    """
    try:
        import jinja2

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
            undefined=jinja2.Undefined,
            keep_trailing_newline=True,
        )
        template = env.get_template(TEMPLATE_FILE)
        return template.render(**context)

    except ImportError:
        # Fallback: build a simpler version without Jinja2
        return _render_fallback(context)


def _render_fallback(ctx: dict[str, Any]) -> str:
    """Plain-text fallback renderer when Jinja2 is unavailable."""
    lines = [
        f"# Weekly CEO Briefing — Week {ctx['week_number']}, {ctx['year']}",
        "",
        f"**Generated:** {ctx['generated_at']}",
        f"**Period:** {ctx['period_start']} to {ctx['period_end']}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        ctx.get("executive_summary", ""),
        "",
        "---",
        "",
        "## Task Pipeline",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| New tasks received | {ctx['vault']['new_this_week']} |",
        f"| Tasks completed | {ctx['vault']['done_this_week']} |",
        f"| Current backlog | {ctx['vault']['backlog']} |",
        f"| Items in Inbox | {ctx['vault']['inbox_count']} |",
        "",
    ]

    # Financial section
    fin = ctx.get("financials", {})
    if fin.get("available"):
        lines.extend([
            "---",
            "",
            "## Financial Snapshot",
            "",
            f"- Revenue this week: ${fin.get('revenue_this_week', 0):,.2f}",
            f"- Expenses this week: ${fin.get('expenses_this_week', 0):,.2f}",
            f"- Outstanding AR: ${fin.get('ar_total', 0):,.2f}",
            f"- Cash position: ${fin.get('cash_position', 0):,.2f}",
            "",
        ])
    else:
        lines.extend([
            "---",
            "",
            "## Financial Snapshot",
            "",
            "*Odoo not connected — financial data unavailable.*",
            "",
        ])

    # Social section
    social = ctx.get("social", {})
    lines.extend([
        "---",
        "",
        "## Social Media",
        "",
        f"Total posts: {social.get('total_posts', 0)}",
        "",
    ])
    for p in social.get("platforms", []):
        lines.append(f"- {p['display_name']}: {p['posts']} posts")
    lines.append("")

    # Email section
    email_data = ctx.get("email", {})
    lines.extend([
        "---",
        "",
        "## Email Activity",
        "",
        f"- Received: {email_data.get('emails_received', 0)}",
        f"- Sent: {email_data.get('emails_sent', 0)}",
        "",
    ])

    # Action items
    action_items = ctx.get("action_items", [])
    lines.extend(["---", "", "## Action Items Requiring Your Decision", ""])
    if action_items:
        for i, item in enumerate(action_items, 1):
            lines.append(
                f"{i}. [{item.get('priority', 'MEDIUM')}] "
                f"**{item['title']}** ({item['file']})"
            )
    else:
        lines.append("No items require your decision this week.")
    lines.append("")

    lines.extend([
        "---",
        "",
        f"*Generated {ctx['generated_at']} by AI Employee (Gold Tier)*",
        "",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_briefing(stdout_only: bool = False) -> Path | None:
    """Generate the weekly CEO briefing.

    Args:
        stdout_only: If True, print to stdout instead of writing to file.

    Returns:
        Path to the generated file, or None if stdout_only.
    """
    now = datetime.now()
    week_num = int(now.strftime("%W"))
    year = now.year
    period_end = now.date()
    period_start = period_end - timedelta(days=6)

    # Collect all data
    data = _collect_all()

    # Extract action items
    action_items = _extract_action_items(data)
    data["action_items"] = action_items

    # Build executive summary
    executive_summary = _build_executive_summary(data)

    # Build template context
    context = {
        "week_number": f"{week_num:02d}",
        "year": year,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "executive_summary": executive_summary,
        **data,
    }

    # Render
    output = _render_template(context)

    if stdout_only:
        print(output)
        return None

    # Write to vault
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"WeeklyBrief_{year}W{week_num:02d}.md"
    output_path = DONE_DIR / filename

    # Avoid overwriting (append suffix if exists)
    if output_path.exists():
        counter = 2
        while True:
            filename = f"WeeklyBrief_{year}W{week_num:02d}_{counter}.md"
            output_path = DONE_DIR / filename
            if not output_path.exists():
                break
            counter += 1

    output_path.write_text(output, encoding="utf-8")

    # Also write a canonical CEO_Briefing.md at the project root
    ceo_briefing_path = _PROJECT_ROOT / "CEO_Briefing.md"
    ceo_briefing_path.write_text(output, encoding="utf-8")

    bus.emit("briefing.generated", {
        "week": f"{year}-W{week_num:02d}",
        "file": filename,
        "action_items": len(action_items),
    })
    error_logger.log_audit("briefing.weekly", "generated", {
        "file": filename,
        "tasks_completed": data["vault"]["done_this_week"],
        "action_items": len(action_items),
    })

    print(f"[OK] Weekly CEO briefing generated: {filename}")
    print(f"  Also saved to: CEO_Briefing.md")
    print(f"  Period: {period_start} to {period_end}")
    print(f"  Action items: {len(action_items)}")

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the weekly CEO briefing.")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout only")
    args = parser.parse_args()

    generate_briefing(stdout_only=args.stdout)


if __name__ == "__main__":
    main()
