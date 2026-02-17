"""
MCP Server — Model Context Protocol server wrapping all AI Employee skills.

Exposes existing skill scripts as MCP tools via stdio transport.
Each tool calls the underlying Python script via subprocess.

Usage:
  python scripts/mcp_server.py

Register in .claude/settings.json for Claude Code integration.
"""

import json
import subprocess
import sys
from pathlib import Path

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("[ERROR] MCP SDK is not installed.")
    print("        Run: pip install mcp")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Skill script paths
SKILLS_BASE = PROJECT_ROOT / "AI_Employee_Vault" / ".claude" / "skills"

SKILL_SCRIPTS = {
    "send_email": SKILLS_BASE / "gmail-send" / "scripts" / "send_email.py",
    "post_linkedin": SKILLS_BASE / "linkedin-post" / "scripts" / "post_linkedin.py",
    "send_whatsapp": SKILLS_BASE / "whatsapp-send" / "scripts" / "send_whatsapp.py",
    "manage_vault": SKILLS_BASE / "vault-file-manager" / "scripts" / "manage_files.py",
    "check_gmail": SCRIPT_DIR / "gmail_watcher.py",
    "check_whatsapp": SCRIPT_DIR / "whatsapp_watcher.py",
}

SUBPROCESS_TIMEOUT = 120  # seconds

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
TOOL_DEFINITIONS = [
    Tool(
        name="send_email",
        description="Send an email via Gmail SMTP using App Passwords.",
        inputSchema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text",
                },
                "cc": {
                    "type": "string",
                    "description": "CC recipients (comma-separated)",
                },
                "html": {
                    "type": "boolean",
                    "description": "Send body as HTML",
                    "default": False,
                },
            },
            "required": ["to", "subject", "body"],
        },
    ),
    Tool(
        name="post_linkedin",
        description="Create a text post on LinkedIn using browser automation.",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Text content for the LinkedIn post (max 3000 chars)",
                },
                "headless": {
                    "type": "boolean",
                    "description": "Run browser in headless mode",
                    "default": False,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Compose post without publishing",
                    "default": False,
                },
            },
            "required": ["content"],
        },
    ),
    Tool(
        name="send_whatsapp",
        description="Send a WhatsApp message using browser automation via WhatsApp Web.",
        inputSchema={
            "type": "object",
            "properties": {
                "phone": {
                    "type": "string",
                    "description": "Recipient phone number with country code (e.g. +923001234567)",
                },
                "message": {
                    "type": "string",
                    "description": "Message text to send",
                },
                "headless": {
                    "type": "boolean",
                    "description": "Run browser in headless mode",
                    "default": False,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Compose message without sending",
                    "default": False,
                },
            },
            "required": ["phone", "message"],
        },
    ),
    Tool(
        name="manage_vault",
        description="Manage vault task files: list, move, archive, search, or status.",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute: list, move, archive, search, status",
                    "enum": ["list", "move", "archive", "search", "status"],
                },
                "stage": {
                    "type": "string",
                    "description": "Vault stage (for list command): inbox, needs_action, done",
                },
                "file": {
                    "type": "string",
                    "description": "Filename (for move/archive commands)",
                },
                "to": {
                    "type": "string",
                    "description": "Target stage (for move command): inbox, needs_action, done",
                },
                "query": {
                    "type": "string",
                    "description": "Search keyword (for search command)",
                },
            },
            "required": ["command"],
        },
    ),
    Tool(
        name="check_gmail",
        description="Poll Gmail for unread emails and create vault tasks in Inbox.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="check_whatsapp",
        description="Check WhatsApp Web for unread messages and create vault tasks in Inbox.",
        inputSchema={
            "type": "object",
            "properties": {
                "headless": {
                    "type": "boolean",
                    "description": "Run browser in headless mode",
                    "default": True,
                },
            },
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool execution — builds CLI args and runs subprocess
# ---------------------------------------------------------------------------
def build_args(tool_name: str, params: dict) -> list[str]:
    """Build command-line arguments for the underlying script."""
    script = SKILL_SCRIPTS.get(tool_name)
    if not script or not script.is_file():
        raise FileNotFoundError(f"Script not found for tool '{tool_name}': {script}")

    cmd = [sys.executable, str(script)]

    if tool_name == "send_email":
        cmd.extend(["--to", params["to"]])
        cmd.extend(["--subject", params["subject"]])
        cmd.extend(["--body", params["body"]])
        if params.get("cc"):
            cmd.extend(["--cc", params["cc"]])
        if params.get("html"):
            cmd.append("--html")

    elif tool_name == "post_linkedin":
        cmd.extend(["--content", params["content"]])
        if params.get("headless"):
            cmd.append("--headless")
        if params.get("dry_run"):
            cmd.append("--dry-run")

    elif tool_name == "send_whatsapp":
        cmd.extend(["--phone", params["phone"]])
        cmd.extend(["--message", params["message"]])
        if params.get("headless"):
            cmd.append("--headless")
        if params.get("dry_run"):
            cmd.append("--dry-run")

    elif tool_name == "manage_vault":
        subcmd = params["command"]
        cmd.append(subcmd)
        if subcmd == "list" and params.get("stage"):
            cmd.extend(["--stage", params["stage"]])
        elif subcmd == "move":
            if params.get("file"):
                cmd.extend(["--file", params["file"]])
            if params.get("to"):
                cmd.extend(["--to", params["to"]])
        elif subcmd == "archive" and params.get("file"):
            cmd.extend(["--file", params["file"]])
        elif subcmd == "search" and params.get("query"):
            cmd.extend(["--query", params["query"]])

    elif tool_name == "check_gmail":
        cmd.append("--once")

    elif tool_name == "check_whatsapp":
        cmd.append("--once")
        if params.get("headless", True):
            cmd.append("--headless")

    return cmd


def run_tool(tool_name: str, params: dict) -> str:
    """Execute a tool and return its output."""
    try:
        cmd = build_args(tool_name, params)
    except FileNotFoundError as e:
        return f"[ERROR] {e}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR] {result.stderr}"
        if result.returncode != 0:
            output += f"\n[EXIT CODE] {result.returncode}"
        return output.strip() if output.strip() else "[OK] Command completed with no output."
    except subprocess.TimeoutExpired:
        return f"[ERROR] Tool '{tool_name}' timed out after {SUBPROCESS_TIMEOUT}s."
    except OSError as e:
        return f"[ERROR] Failed to run tool '{tool_name}': {e}"


# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------
def create_server() -> Server:
    server = Server("ai-employee")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name not in SKILL_SCRIPTS:
            return [TextContent(type="text", text=f"[ERROR] Unknown tool: {name}")]
        output = run_tool(name, arguments or {})
        return [TextContent(type="text", text=output)]

    return server


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    print("[INFO] AI Employee MCP Server starting (stdio transport)...", file=sys.stderr)
    asyncio.run(main())
