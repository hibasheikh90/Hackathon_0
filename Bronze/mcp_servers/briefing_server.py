"""
Gold Tier — Briefing MCP Server
==================================
Exposes CEO briefing generation and retrieval to Claude via MCP.

Tools:
    generate_weekly_briefing — Generate the weekly CEO briefing now
    get_last_briefing        — Read the most recent weekly briefing
    get_vault_stats          — Get current task pipeline statistics
    get_collector_data       — Get raw data from any individual collector

Run:
    python mcp_servers/briefing_server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
DONE_DIR = VAULT_DIR / "Done"

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "briefing",
    instructions=(
        "Weekly CEO briefing system for the AI Employee. "
        "Generate on-demand briefings, read past briefings, "
        "and query individual data collectors (vault stats, "
        "financials, social metrics, email digest)."
    ),
)


@mcp.tool()
def generate_weekly_briefing() -> dict:
    """Generate the weekly CEO briefing right now.

    Collects data from all sources (vault, Odoo, social, email)
    and writes a briefing to vault/Done/WeeklyBrief_YYYYWNN.md.
    """
    from briefings.weekly_ceo import generate_briefing

    try:
        path = generate_briefing()
        if path:
            return {
                "status": "generated",
                "file": path.name,
                "path": str(path),
            }
        else:
            return {"error": "Briefing generation returned no path"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@mcp.tool()
def get_last_briefing() -> dict:
    """Read the most recently generated weekly CEO briefing."""
    if not DONE_DIR.is_dir():
        return {"error": "vault/Done/ directory not found"}

    briefings = sorted(
        [f for f in DONE_DIR.iterdir() if f.name.startswith("WeeklyBrief_") and f.suffix == ".md"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not briefings:
        return {"error": "No weekly briefings found. Use generate_weekly_briefing first."}

    latest = briefings[0]
    try:
        content = latest.read_text(encoding="utf-8")
        return {
            "file": latest.name,
            "content": content,
        }
    except OSError as e:
        return {"error": str(e)}


@mcp.tool()
def get_vault_stats() -> dict:
    """Get current task pipeline statistics from the vault."""
    from briefings.data_collectors.vault_stats import collect
    return collect()


@mcp.tool()
def get_collector_data(collector: str) -> dict:
    """Get raw data from a specific briefing data collector.

    Args:
        collector: One of 'vault_stats', 'financial_summary', 'social_metrics', 'email_digest'
    """
    collector_map = {
        "vault_stats": "briefings.data_collectors.vault_stats",
        "financial_summary": "briefings.data_collectors.financial_summary",
        "social_metrics": "briefings.data_collectors.social_metrics",
        "email_digest": "briefings.data_collectors.email_digest",
    }

    module_path = collector_map.get(collector.lower())
    if not module_path:
        return {
            "error": f"Unknown collector: {collector}. "
                     f"Options: {', '.join(collector_map.keys())}"
        }

    import importlib
    try:
        mod = importlib.import_module(module_path)
        return mod.collect()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    mcp.run()
