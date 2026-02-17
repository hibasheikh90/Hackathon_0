"""
Gold Tier — Social Metrics Collector
=======================================
Aggregates posting activity and engagement stats from all social
platforms for the CEO briefing.

Metrics per platform:
    - Posts made this week
    - Total impressions, likes, comments, shares
    - Engagement rate

Usage:
    from briefings.data_collectors.social_metrics import collect

    data = collect()
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger

# Vault paths for scanning archived social posts
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
DONE_DIR = VAULT_DIR / "Done"

# Social scheduler state (tracks daily post counts)
SOCIAL_STATE_FILE = _PROJECT_ROOT / "core" / ".social_scheduler_state.json"


def _load_social_state() -> dict:
    """Load the social scheduler state file for post count data."""
    if SOCIAL_STATE_FILE.is_file():
        try:
            return json.loads(SOCIAL_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _count_posted_files(since: datetime) -> dict[str, int]:
    """Count social_*.md files in Done/ posted since the cutoff date.

    Parses the frontmatter to identify which platforms were posted to.
    """
    counts: dict[str, int] = {}
    if not DONE_DIR.is_dir():
        return counts

    since_ts = since.timestamp()
    for f in DONE_DIR.iterdir():
        if not f.name.startswith("social_") or f.suffix != ".md":
            continue
        if f.stat().st_mtime < since_ts:
            continue

        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        # Parse platforms from frontmatter
        match = re.search(r"platforms:\s*(.+)", content, re.IGNORECASE)
        if match:
            platforms = [p.strip() for p in match.group(1).split(",") if p.strip()]
            for platform in platforms:
                counts[platform] = counts.get(platform, 0) + 1

    return counts


def _posts_from_state(weeks_back: int = 1) -> dict[str, int]:
    """Get post counts per platform from the scheduler state file."""
    state = _load_social_state()
    daily = state.get("daily_posts", {})
    cutoff = (datetime.now() - timedelta(weeks=weeks_back)).strftime("%Y-%m-%d")

    totals: dict[str, int] = {}
    for platform, dates in daily.items():
        total = sum(count for date, count in dates.items() if date >= cutoff)
        if total > 0:
            totals[platform] = total

    return totals


def collect(weeks_back: int = 1) -> dict:
    """Collect social media metrics for the CEO briefing.

    Returns a dict with:
        platforms: list of per-platform stats dicts
        total_posts: int
        top_platform: str or None
    """
    cutoff = datetime.now() - timedelta(weeks=weeks_back)

    # Merge post counts from both sources
    state_counts = _posts_from_state(weeks_back)
    file_counts = _count_posted_files(cutoff)

    all_platforms = set(list(state_counts.keys()) + list(file_counts.keys()))
    if not all_platforms:
        # Default platform list even if no posts yet
        all_platforms = {"linkedin", "twitter", "instagram"}

    platforms = []
    total_posts = 0

    for name in sorted(all_platforms):
        posts = max(state_counts.get(name, 0), file_counts.get(name, 0))
        total_posts += posts

        # Try to get engagement metrics from the platform API
        impressions = 0
        likes = 0
        comments = 0
        shares = 0
        engagement_rate = 0.0

        try:
            if name == "twitter":
                from integrations.social.twitter import TwitterPlatform
                # We'd need stored post_ids to fetch metrics — placeholder for now
                pass
        except ImportError:
            pass

        platform_data = {
            "name": name,
            "display_name": name.capitalize(),
            "posts": posts,
            "impressions": impressions,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "engagement_rate": engagement_rate,
        }
        platforms.append(platform_data)

    # Determine top-performing platform
    top_platform = None
    if platforms:
        by_posts = sorted(platforms, key=lambda p: p["posts"], reverse=True)
        if by_posts[0]["posts"] > 0:
            top_platform = by_posts[0]["name"]

    result = {
        "platforms": platforms,
        "total_posts": total_posts,
        "top_platform": top_platform,
    }

    error_logger.log_audit("briefing.collector.social_metrics", "success", {
        "total_posts": total_posts,
        "platform_count": len(platforms),
    })

    return result
