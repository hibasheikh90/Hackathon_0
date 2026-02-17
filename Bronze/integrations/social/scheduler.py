"""
Gold Tier — Cross-Platform Social Posting Scheduler
=====================================================
Enforces per-platform rate limits and distributes posts
across optimal time windows.

Usage:
    from integrations.social.scheduler import SocialScheduler

    sched = SocialScheduler()
    sched.can_post("linkedin")          # True/False based on daily limit
    sched.record_post("linkedin")       # Track that a post was made
    sched.next_optimal_slot("twitter")  # Returns next optimal posting time
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config_loader import config
from core.error_logger import logger as error_logger

STATE_FILE = _PROJECT_ROOT / "core" / ".social_scheduler_state.json"


class SocialScheduler:
    """Tracks post counts and enforces rate limits per platform."""

    def __init__(self) -> None:
        config.load()
        self._state = self._load_state()

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def can_post(self, platform: str) -> bool:
        """Check if we're within the daily rate limit for this platform."""
        limit = self._get_limit(platform)
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self._state.get("daily_posts", {})
        platform_today = daily.get(platform, {}).get(today, 0)
        return platform_today < limit

    def record_post(self, platform: str) -> None:
        """Record that a post was made on this platform today."""
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self._state.setdefault("daily_posts", {})
        platform_data = daily.setdefault(platform, {})
        platform_data[today] = platform_data.get(today, 0) + 1

        # Clean up old dates (keep only last 7 days)
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        platform_data_clean = {d: c for d, c in platform_data.items() if d >= cutoff}
        daily[platform] = platform_data_clean

        self._save_state()

    def posts_today(self, platform: str) -> int:
        """How many posts have been made today on this platform."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._state.get("daily_posts", {}).get(platform, {}).get(today, 0)

    def remaining_today(self, platform: str) -> int:
        """How many more posts are allowed today."""
        return max(0, self._get_limit(platform) - self.posts_today(platform))

    # ------------------------------------------------------------------
    # Optimal time windows
    # ------------------------------------------------------------------

    def next_optimal_slot(self, platform: str) -> datetime | None:
        """Calculate the next optimal posting time for a platform.

        Returns None if no optimal hours are configured.
        """
        social_cfg = config.section("social_accounts").get(platform, {})
        hours_str = social_cfg.get("optimal_hours", "")

        if not hours_str:
            return None

        if isinstance(hours_str, str):
            hours = [int(h.strip()) for h in hours_str.split(",") if h.strip().isdigit()]
        elif isinstance(hours_str, (list, tuple)):
            hours = [int(h) for h in hours_str]
        else:
            return None

        if not hours:
            return None

        now = datetime.now()
        # Find the next optimal hour today or tomorrow
        for hour in sorted(hours):
            candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if candidate > now:
                return candidate

        # All today's slots have passed — use first slot tomorrow
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=sorted(hours)[0], minute=0, second=0, microsecond=0)

    def get_weekly_stats(self) -> dict[str, int]:
        """Get total post count per platform for the current week."""
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        stats = {}
        for platform, dates in self._state.get("daily_posts", {}).items():
            total = sum(c for d, c in dates.items() if d >= cutoff)
            stats[platform] = total
        return stats

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_limit(self, platform: str) -> int:
        social_cfg = config.section("social_accounts").get(platform, {})
        return int(social_cfg.get("rate_limit_per_day", 10))

    def _load_state(self) -> dict:
        if STATE_FILE.is_file():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"daily_posts": {}}

    def _save_state(self) -> None:
        try:
            STATE_FILE.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        except OSError as e:
            error_logger.log_error("social.scheduler.save", e)
