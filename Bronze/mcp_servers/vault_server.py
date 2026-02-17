"""
Gold Tier — Vault MCP Server
==============================
Exposes Obsidian vault operations to Claude via MCP.

Tools:
    vault_status      — File counts per stage
    list_tasks        — List .md files in a vault stage
    read_task         — Read full content of a vault file
    move_task         — Move a file between stages
    search_vault      — Search file names and content
    get_dashboard     — Read the vault Dashboard.md

Run:
    python mcp_servers/vault_server.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Vault paths
# ---------------------------------------------------------------------------
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
DONE_DIR = VAULT_DIR / "Done"

STAGE_MAP = {
    "inbox": INBOX_DIR,
    "needs_action": NEEDS_ACTION_DIR,
    "done": DONE_DIR,
}

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "vault",
    instructions=(
        "Obsidian vault file manager for the AI Employee. "
        "Tasks flow through Inbox → Needs_Action → Done. "
        "Use vault_status for an overview, list_tasks to browse, "
        "and search_vault to find specific items."
    ),
)


@mcp.tool()
def vault_status() -> dict:
    """Get file counts for each vault stage (Inbox, Needs_Action, Done)."""
    counts = {}
    for name, directory in STAGE_MAP.items():
        if directory.is_dir():
            counts[name] = sum(1 for f in directory.iterdir() if f.suffix == ".md")
        else:
            counts[name] = 0
    counts["total"] = sum(counts.values())
    return counts


@mcp.tool()
def list_tasks(stage: str = "needs_action") -> list[dict]:
    """List all .md task files in a vault stage.

    Args:
        stage: One of 'inbox', 'needs_action', 'done'
    """
    directory = STAGE_MAP.get(stage.lower())
    if not directory or not directory.is_dir():
        return [{"error": f"Unknown or empty stage: {stage}"}]

    results = []
    for f in sorted(directory.iterdir()):
        if f.suffix != ".md":
            continue
        # Extract first heading as title
        title = f.stem.replace("_", " ")
        try:
            content = f.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("#") and not line.strip().startswith("##"):
                    title = line.strip().lstrip("#").strip()
                    break
        except OSError:
            pass

        results.append({
            "file": f.name,
            "title": title,
            "stage": stage,
            "size_bytes": f.stat().st_size,
        })

    return results


@mcp.tool()
def read_task(filename: str) -> dict:
    """Read the full content of a vault task file.

    Args:
        filename: The .md filename (e.g. 'task_report.md')
    """
    for directory in STAGE_MAP.values():
        path = directory / filename
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                return {
                    "file": filename,
                    "stage": directory.name,
                    "content": content,
                }
            except OSError as e:
                return {"error": str(e)}

    return {"error": f"File not found: {filename}"}


@mcp.tool()
def move_task(filename: str, to_stage: str) -> dict:
    """Move a task file from its current stage to another stage.

    Args:
        filename: The .md filename to move
        to_stage: Target stage: 'inbox', 'needs_action', or 'done'
    """
    target_dir = STAGE_MAP.get(to_stage.lower())
    if not target_dir:
        return {"error": f"Unknown stage: {to_stage}"}

    # Find the file
    source_path = None
    source_stage = None
    for name, directory in STAGE_MAP.items():
        candidate = directory / filename
        if candidate.is_file():
            source_path = candidate
            source_stage = name
            break

    if not source_path:
        return {"error": f"File not found: {filename}"}

    target_path = target_dir / filename
    if target_path.exists():
        return {"error": f"File already exists in {to_stage}"}

    target_dir.mkdir(parents=True, exist_ok=True)
    source_path.rename(target_path)

    return {
        "file": filename,
        "from": source_stage,
        "to": to_stage,
        "status": "moved",
    }


@mcp.tool()
def search_vault(query: str) -> list[dict]:
    """Search vault file names and content for a keyword.

    Args:
        query: Search term (case-insensitive)
    """
    results = []
    query_lower = query.lower()

    for stage_name, directory in STAGE_MAP.items():
        if not directory.is_dir():
            continue
        for f in directory.iterdir():
            if f.suffix != ".md":
                continue

            matched_in = []
            if query_lower in f.name.lower():
                matched_in.append("filename")

            try:
                content = f.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    matched_in.append("content")
            except OSError:
                continue

            if matched_in:
                results.append({
                    "file": f.name,
                    "stage": stage_name,
                    "matched_in": matched_in,
                })

    return results


@mcp.tool()
def get_dashboard() -> dict:
    """Read the vault Dashboard.md file if it exists."""
    for base in (VAULT_DIR, _PROJECT_ROOT / "vault"):
        dash = base / "Dashboard.md"
        if dash.is_file():
            try:
                return {"content": dash.read_text(encoding="utf-8")}
            except OSError as e:
                return {"error": str(e)}
    return {"error": "Dashboard.md not found"}


if __name__ == "__main__":
    mcp.run()
