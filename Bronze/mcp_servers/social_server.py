"""
Gold Tier — Social Media MCP Server
======================================
Exposes cross-platform social media operations to Claude via MCP.

Tools:
    create_draft            — Create a social media draft in the content queue
    list_queue              — List all items in the content queue
    schedule_post           — Set a scheduled time for a draft
    approve_post            — Approve a draft for posting
    post_now                — Immediately post to a platform (with vault logging)
    post_multi              — Post to multiple platforms at once
    process_queue           — Auto-post all ready items from the queue
    get_rate_limits         — Check remaining daily posts per platform
    engagement_summary      — Generate engagement summary report
    get_post_history        — View recent post history

Supported platforms: facebook, instagram, linkedin, twitter

Run:
    python mcp_servers/social_server.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"

ALL_PLATFORMS = ["facebook", "instagram", "linkedin", "twitter"]

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "social",
    instructions=(
        "Multi-platform social media manager for the AI Employee. "
        "Create drafts, approve content, schedule posts, auto-post, "
        "and generate engagement reports. "
        "Supports Facebook, Instagram, LinkedIn, and Twitter/X."
    ),
)


@mcp.tool()
def create_draft(content: str, platforms: str, scheduled_time: str = "") -> dict:
    """Create a social media draft in the content queue.

    Args:
        content: The post text content
        platforms: Comma-separated platforms (e.g. 'facebook, instagram')
        scheduled_time: Optional time to post (YYYY-MM-DD HH:MM)
    """
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"social_draft_{ts}.md"
    filepath = NEEDS_ACTION_DIR / filename

    status = "draft"
    if scheduled_time:
        status = "scheduled"

    meta_lines = [
        "---",
        f"platforms: {platforms}",
    ]
    if scheduled_time:
        meta_lines.append(f"scheduled_time: {scheduled_time}")
    meta_lines.extend([
        f"status: {status}",
        f"created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "---",
        content,
        "",
    ])

    filepath.write_text("\n".join(meta_lines), encoding="utf-8")

    return {
        "status": "created",
        "file": filename,
        "platforms": platforms,
        "post_status": status,
    }


@mcp.tool()
def list_queue() -> list[dict]:
    """List all social media content items in the queue."""
    from integrations.social.content_queue import ContentQueue

    queue = ContentQueue()
    items = queue.scan()

    return [
        {
            "file": item.filename,
            "platforms": item.platforms,
            "status": item.status,
            "scheduled_time": str(item.scheduled_time) if item.scheduled_time else None,
            "is_ready": item.is_ready,
            "preview": item.body[:100] + "..." if len(item.body) > 100 else item.body,
        }
        for item in items
    ]


@mcp.tool()
def schedule_post(filename: str, scheduled_time: str) -> dict:
    """Set a scheduled posting time for a draft.

    Args:
        filename: The social_*.md filename
        scheduled_time: When to post (YYYY-MM-DD HH:MM)
    """
    from integrations.social.content_queue import ContentQueue

    queue = ContentQueue()
    success = queue.schedule(filename, scheduled_time)

    if success:
        return {"status": "scheduled", "file": filename, "time": scheduled_time}
    else:
        return {"error": f"File not found: {filename}"}


@mcp.tool()
def approve_post(filename: str) -> dict:
    """Approve a draft for posting (will be posted at next scheduled time or immediately).

    Args:
        filename: The social_*.md filename to approve
    """
    from integrations.social.content_queue import ContentQueue

    queue = ContentQueue()
    success = queue.approve(filename)

    if success:
        return {"status": "approved", "file": filename}
    else:
        return {"error": f"File not found: {filename}"}


@mcp.tool()
def post_now(content: str, platform: str) -> dict:
    """Post content to a platform immediately with vault logging.

    Args:
        content: The text to post
        platform: Target platform: 'facebook', 'instagram', 'linkedin', or 'twitter'
    """
    from integrations.social.automation import SocialAutomation

    auto = SocialAutomation()
    result = auto.post(platform, content)

    return {
        "success": result.success,
        "platform": result.platform,
        "post_id": result.post_id,
        "error": result.error,
        "timestamp": result.timestamp,
    }


@mcp.tool()
def post_multi(content: str, platforms: str) -> dict:
    """Post the same content to multiple platforms at once.

    Each platform gets its own rate-limit check and vault log entry.

    Args:
        content: The text to post
        platforms: Comma-separated platforms (e.g. 'facebook, instagram')
    """
    from integrations.social.automation import SocialAutomation

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    auto = SocialAutomation()
    results = auto.post_multi(platform_list, content)

    return {
        "results": [
            {
                "platform": r.platform,
                "success": r.success,
                "post_id": r.post_id,
                "error": r.error,
            }
            for r in results
        ],
        "total": len(results),
        "successful": sum(1 for r in results if r.success),
    }


@mcp.tool()
def process_queue() -> dict:
    """Process the content queue: auto-post all ready items.

    Posts are logged to the Obsidian vault automatically.
    Respects per-platform rate limits.
    """
    from integrations.social.automation import SocialAutomation

    auto = SocialAutomation()
    stats = auto.process_queue()

    return {
        "posted": stats["posted"],
        "failed": stats["failed"],
        "skipped": stats["skipped"],
        "details": stats["details"],
    }


@mcp.tool()
def get_rate_limits() -> dict:
    """Check remaining daily post allowance for each platform."""
    from integrations.social.scheduler import SocialScheduler

    sched = SocialScheduler()
    limits = {}
    for p in ALL_PLATFORMS:
        limits[p] = {
            "posts_today": sched.posts_today(p),
            "remaining": sched.remaining_today(p),
            "can_post": sched.can_post(p),
        }
        slot = sched.next_optimal_slot(p)
        if slot:
            limits[p]["next_optimal_slot"] = slot.strftime("%Y-%m-%d %H:%M")

    return limits


@mcp.tool()
def engagement_summary(days: int = 7) -> dict:
    """Generate an engagement summary report for the last N days.

    Creates a Markdown report in vault/Done/social_summaries/ and
    returns the summary data.

    Args:
        days: Number of days to include (default: 7)
    """
    from integrations.social.automation import SocialAutomation

    auto = SocialAutomation()
    return auto.generate_engagement_summary(days=days)


@mcp.tool()
def get_post_history(limit: int = 20) -> dict:
    """View recent social media post history.

    Args:
        limit: Max number of recent posts to return (default: 20)
    """
    from integrations.social.automation import SocialAutomation

    auto = SocialAutomation()
    history = auto._history[-limit:] if auto._history else []
    history.reverse()  # Most recent first

    return {
        "total_in_history": len(auto._history),
        "showing": len(history),
        "posts": history,
    }


if __name__ == "__main__":
    mcp.run()
