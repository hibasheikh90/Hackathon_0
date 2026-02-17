"""
Gold Tier — Email MCP Server
===============================
Exposes Gmail send and inbox operations to Claude via MCP.

Tools:
    send_email     — Send an email via Gmail SMTP
    check_inbox    — Check Gmail for new emails (IMAP)
    search_emails  — Search vault for imported email files

Run:
    python mcp_servers/email_server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "email",
    instructions=(
        "Gmail integration for the AI Employee. "
        "Send emails, check for new messages, and search imported emails. "
        "Requires EMAIL_ADDRESS and EMAIL_PASSWORD in .env."
    ),
)


@mcp.tool()
def send_email(to: str, subject: str, body: str, cc: str = "", html: bool = False) -> dict:
    """Send an email via Gmail SMTP.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body text
        cc: CC recipients (comma-separated, optional)
        html: If True, send body as HTML
    """
    from integrations.gmail.sender import GmailSender

    sender = GmailSender()
    if not sender.is_configured():
        return {"error": "Gmail not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD in .env"}

    success = sender.send(
        to=to,
        subject=subject,
        body=body,
        cc=cc or None,
        html=html,
    )

    if success:
        return {"status": "sent", "to": to, "subject": subject}
    else:
        return {"error": "Failed to send email. Check logs/error.log for details."}


@mcp.tool()
def check_inbox(max_fetch: int = 10) -> dict:
    """Check Gmail inbox for new unread emails and import them to the vault.

    Args:
        max_fetch: Maximum number of new emails to fetch (default 10)
    """
    from integrations.gmail.watcher import GmailWatcher

    watcher = GmailWatcher()
    if not watcher.is_configured():
        return {"error": "Gmail not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD in .env"}

    count = watcher.check_new(max_fetch=max_fetch)
    return {
        "new_emails_imported": count,
        "status": f"Imported {count} new email(s) to vault/Inbox/",
    }


@mcp.tool()
def search_emails(query: str) -> list[dict]:
    """Search vault for imported Gmail files by keyword.

    Args:
        query: Search term to match in email subjects and content
    """
    _ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
    _direct_vault = _PROJECT_ROOT / "vault"
    vault_dir = _ai_vault if _ai_vault.is_dir() else _direct_vault

    results = []
    query_lower = query.lower()

    for stage in ("Inbox", "Needs_Action", "Done"):
        stage_dir = vault_dir / stage
        if not stage_dir.is_dir():
            continue
        for f in stage_dir.iterdir():
            if not f.name.startswith("gmail_") or f.suffix != ".md":
                continue
            try:
                content = f.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    # Extract subject
                    subject = f.stem.replace("gmail_", "").replace("_", " ")
                    for line in content.splitlines():
                        if line.strip().startswith("# "):
                            subject = line.strip().lstrip("#").strip()
                            break
                    results.append({
                        "file": f.name,
                        "stage": stage,
                        "subject": subject,
                    })
            except OSError:
                continue

    return results


if __name__ == "__main__":
    mcp.run()
