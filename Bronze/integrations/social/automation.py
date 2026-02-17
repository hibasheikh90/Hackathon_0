"""
Gold Tier — Social Media Automation Engine
============================================
Orchestrates cross-platform posting (Facebook + Instagram + others),
vault logging, and engagement summary generation.

Features:
    - Post content to Facebook and Instagram via Playwright
    - Save detailed post logs into the Obsidian vault
    - Generate weekly engagement summary reports
    - Process the content queue automatically
    - Track all activity with audit logging

Usage:
    from integrations.social.automation import SocialAutomation

    auto = SocialAutomation()

    # Post to a single platform
    result = auto.post("facebook", "Exciting update!", media=[Path("img.jpg")])

    # Post to multiple platforms at once
    results = auto.post_multi(["facebook", "instagram"], "New launch!", media=[Path("img.jpg")])

    # Process the content queue (drafts → posts)
    stats = auto.process_queue()

    # Generate engagement summary
    summary = auto.generate_engagement_summary()

CLI:
    python -m integrations.social.automation --post facebook "Hello world!"
    python -m integrations.social.automation --queue
    python -m integrations.social.automation --summary
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config
from integrations.social.base import SocialPlatform, PostResult, MetricsResult
from integrations.social.scheduler import SocialScheduler
from integrations.social.content_queue import ContentQueue

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
DONE_DIR = VAULT_DIR / "Done"
SOCIAL_LOG_DIR = DONE_DIR / "social_logs"
SUMMARY_DIR = DONE_DIR / "social_summaries"

# Post history file (JSON) for tracking engagement over time
HISTORY_FILE = _PROJECT_ROOT / "core" / ".social_post_history.json"


def _get_platform(name: str) -> SocialPlatform | None:
    """Lazily import and instantiate a platform by name."""
    name = name.lower().strip()
    if name == "facebook":
        from integrations.social.facebook import FacebookPlatform
        return FacebookPlatform()
    elif name == "instagram":
        from integrations.social.instagram import InstagramPlatform
        return InstagramPlatform()
    elif name == "linkedin":
        from integrations.social.linkedin import LinkedInPlatform
        return LinkedInPlatform()
    elif name == "twitter":
        from integrations.social.twitter import TwitterPlatform
        return TwitterPlatform()
    return None


class SocialAutomation:
    """Cross-platform social media automation with vault logging."""

    def __init__(self) -> None:
        config.load()
        self.scheduler = SocialScheduler()
        self.queue = ContentQueue()
        self._history = self._load_history()

    # ------------------------------------------------------------------
    # Core: Post to a single platform
    # ------------------------------------------------------------------

    def post(
        self,
        platform_name: str,
        content: str,
        media: list[Path] | None = None,
    ) -> PostResult:
        """Post content to a single platform with rate-limit checks and vault logging.

        Args:
            platform_name: 'facebook', 'instagram', 'linkedin', or 'twitter'
            content: Text content to post
            media: Optional list of media file paths

        Returns:
            PostResult with success/failure info
        """
        platform = _get_platform(platform_name)
        if not platform:
            return PostResult(
                success=False, platform=platform_name,
                error=f"Unknown platform: {platform_name}",
            )

        # Check rate limit
        if not self.scheduler.can_post(platform_name):
            remaining = self.scheduler.remaining_today(platform_name)
            return PostResult(
                success=False, platform=platform_name,
                error=f"Rate limit reached for {platform_name} today (0 remaining)",
            )

        # Execute the post
        result = platform.post(content, media=media)

        # Track in scheduler
        if result.success:
            self.scheduler.record_post(platform_name)

        # Save to history
        self._record_history(platform_name, content, result)

        # Log to vault
        self._log_post_to_vault(platform_name, content, result, media)

        return result

    # ------------------------------------------------------------------
    # Core: Post to multiple platforms
    # ------------------------------------------------------------------

    def post_multi(
        self,
        platforms: list[str],
        content: str,
        media: list[Path] | None = None,
    ) -> list[PostResult]:
        """Post the same content to multiple platforms.

        Returns a list of PostResult, one per platform.
        """
        results = []
        for platform_name in platforms:
            result = self.post(platform_name, content, media=media)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Queue processing
    # ------------------------------------------------------------------

    def process_queue(self) -> dict:
        """Process the content queue: post all ready items.

        Returns stats dict with counts of posted, failed, skipped items.
        """
        ready = self.queue.get_ready_posts()
        stats = {"posted": 0, "failed": 0, "skipped": 0, "details": []}

        for item in ready:
            all_results = []
            all_success = True

            for platform_name in item.platforms:
                platform = _get_platform(platform_name)
                if not platform:
                    error_logger.log_error("social.automation.queue",
                                           f"Unknown platform: {platform_name}")
                    stats["skipped"] += 1
                    continue

                if not self.scheduler.can_post(platform_name):
                    stats["skipped"] += 1
                    continue

                result = platform.post(item.body)
                all_results.append({
                    "platform": platform_name,
                    "success": result.success,
                    "post_id": result.post_id,
                    "error": result.error,
                })

                if result.success:
                    self.scheduler.record_post(platform_name)
                    self._record_history(platform_name, item.body, result)
                else:
                    all_success = False

            if all_success and all_results:
                self.queue.mark_posted(item.filename, all_results)
                self._log_post_to_vault(
                    ",".join(item.platforms), item.body,
                    PostResult(success=True, platform=",".join(item.platforms)),
                )
                stats["posted"] += 1
            elif all_results:
                errors = "; ".join(
                    f"{r['platform']}: {r['error']}" for r in all_results if r.get("error")
                )
                self.queue.mark_failed(item.filename, errors)
                stats["failed"] += 1

            stats["details"].append({
                "file": item.filename,
                "platforms": item.platforms,
                "results": all_results,
            })

        # Log queue run to vault
        if ready:
            self._log_queue_run_to_vault(stats)

        return stats

    # ------------------------------------------------------------------
    # Engagement summary
    # ------------------------------------------------------------------

    def generate_engagement_summary(self, days: int = 7) -> dict:
        """Generate an engagement summary for the last N days.

        Collects metrics from post history and writes a summary
        report into the Obsidian vault.

        Returns the summary data dict.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        recent_posts = [
            h for h in self._history
            if h.get("timestamp", "") >= cutoff
        ]

        # Aggregate by platform
        by_platform: dict[str, dict] = {}
        for post in recent_posts:
            plat = post.get("platform", "unknown")
            if plat not in by_platform:
                by_platform[plat] = {
                    "posts": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_content_length": 0,
                    "with_media": 0,
                }
            stats = by_platform[plat]
            stats["posts"] += 1
            if post.get("success"):
                stats["successful"] += 1
            else:
                stats["failed"] += 1
            stats["total_content_length"] += post.get("content_length", 0)
            if post.get("has_media"):
                stats["with_media"] += 1

        # Overall stats
        total_posts = len(recent_posts)
        total_success = sum(1 for p in recent_posts if p.get("success"))
        total_failed = total_posts - total_success
        success_rate = round((total_success / total_posts * 100), 1) if total_posts else 0.0

        summary = {
            "period_days": days,
            "period_start": cutoff[:10],
            "period_end": datetime.now().strftime("%Y-%m-%d"),
            "total_posts": total_posts,
            "total_successful": total_success,
            "total_failed": total_failed,
            "success_rate_pct": success_rate,
            "by_platform": by_platform,
            "rate_limits": {},
        }

        # Current rate limit status
        for plat in ["facebook", "instagram", "linkedin", "twitter"]:
            summary["rate_limits"][plat] = {
                "posts_today": self.scheduler.posts_today(plat),
                "remaining_today": self.scheduler.remaining_today(plat),
            }
            slot = self.scheduler.next_optimal_slot(plat)
            if slot:
                summary["rate_limits"][plat]["next_optimal"] = slot.strftime("%Y-%m-%d %H:%M")

        # Write to vault
        self._write_engagement_summary_to_vault(summary)

        return summary

    # ------------------------------------------------------------------
    # Vault logging
    # ------------------------------------------------------------------

    def _log_post_to_vault(
        self,
        platform_name: str,
        content: str,
        result: PostResult,
        media: list[Path] | None = None,
    ) -> Path:
        """Write a post log entry into vault/Done/social_logs/."""
        SOCIAL_LOG_DIR.mkdir(parents=True, exist_ok=True)

        ts = datetime.now()
        status = "SUCCESS" if result.success else "FAILED"
        safe_plat = platform_name.replace(",", "_")
        filename = f"{ts:%Y%m%d_%H%M%S}_{safe_plat}_{status}.md"
        path = SOCIAL_LOG_DIR / filename

        # Content preview (truncated)
        preview = content[:200] + "..." if len(content) > 200 else content

        lines = [
            f"# Social Post Log — {platform_name.title()}",
            "",
            f"**Status:** {status}",
            f"**Platform:** {platform_name}",
            f"**Timestamp:** {ts:%Y-%m-%d %H:%M:%S}",
            f"**Content Length:** {len(content)} chars",
        ]

        if result.post_id:
            lines.append(f"**Post ID:** {result.post_id}")
        if result.url:
            lines.append(f"**URL:** {result.url}")
        if media:
            lines.append(f"**Media:** {', '.join(str(m) for m in media)}")

        lines.extend([
            "",
            "---",
            "",
            "## Content",
            "",
            f"```",
            preview,
            f"```",
            "",
        ])

        if result.error:
            lines.extend([
                "## Error",
                "",
                f"> {result.error}",
                "",
            ])

        lines.append(f"#social #{platform_name} #{status.lower()}")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

        error_logger.log_audit("social.automation.vault_log", "saved", {
            "file": filename, "platform": platform_name, "success": result.success,
        })

        return path

    def _log_queue_run_to_vault(self, stats: dict) -> Path:
        """Log a queue processing run to the vault."""
        SOCIAL_LOG_DIR.mkdir(parents=True, exist_ok=True)

        ts = datetime.now()
        filename = f"{ts:%Y%m%d_%H%M%S}_queue_run.md"
        path = SOCIAL_LOG_DIR / filename

        lines = [
            f"# Content Queue Run — {ts:%Y-%m-%d %H:%M}",
            "",
            f"**Posted:** {stats['posted']}",
            f"**Failed:** {stats['failed']}",
            f"**Skipped:** {stats['skipped']}",
            "",
            "---",
            "",
        ]

        for detail in stats.get("details", []):
            lines.append(f"### {detail['file']}")
            lines.append(f"Platforms: {', '.join(detail['platforms'])}")
            for r in detail.get("results", []):
                icon = "+" if r.get("success") else "x"
                lines.append(f"  [{icon}] {r['platform']}: {r.get('post_id', r.get('error', 'n/a'))}")
            lines.append("")

        lines.append("#social #queue_run")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _write_engagement_summary_to_vault(self, summary: dict) -> Path:
        """Write the engagement summary report to the vault."""
        SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

        ts = datetime.now()
        filename = f"engagement_{summary['period_start']}_to_{summary['period_end']}.md"
        path = SUMMARY_DIR / filename

        lines = [
            f"# Social Media Engagement Summary",
            "",
            f"**Period:** {summary['period_start']} to {summary['period_end']} ({summary['period_days']} days)",
            f"**Generated:** {ts:%Y-%m-%d %H:%M:%S}",
            "",
            "---",
            "",
            "## Overview",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Total Posts | {summary['total_posts']} |",
            f"| Successful | {summary['total_successful']} |",
            f"| Failed | {summary['total_failed']} |",
            f"| Success Rate | {summary['success_rate_pct']}% |",
            "",
            "---",
            "",
            "## By Platform",
            "",
        ]

        for plat, stats in summary["by_platform"].items():
            lines.extend([
                f"### {plat.title()}",
                "",
                f"| Metric | Value |",
                f"|---|---|",
                f"| Posts | {stats['posts']} |",
                f"| Successful | {stats['successful']} |",
                f"| Failed | {stats['failed']} |",
                f"| With Media | {stats['with_media']} |",
                f"| Avg Content Length | {stats['total_content_length'] // max(stats['posts'], 1)} chars |",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Current Rate Limits",
            "",
            f"| Platform | Posted Today | Remaining |",
            f"|---|---|---|",
        ])

        for plat, rl in summary["rate_limits"].items():
            lines.append(
                f"| {plat.title()} | {rl['posts_today']} | {rl['remaining_today']} |"
            )

        lines.extend([
            "",
            "#social #engagement #summary",
            "",
        ])

        path.write_text("\n".join(lines), encoding="utf-8")

        error_logger.log_audit("social.automation.summary", "generated", {
            "file": filename,
            "total_posts": summary["total_posts"],
            "success_rate": summary["success_rate_pct"],
        })

        return path

    # ------------------------------------------------------------------
    # Post history persistence
    # ------------------------------------------------------------------

    def _load_history(self) -> list[dict]:
        if HISTORY_FILE.is_file():
            try:
                return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save_history(self) -> None:
        # Keep only last 90 days
        cutoff = (datetime.now() - timedelta(days=90)).isoformat()
        self._history = [h for h in self._history if h.get("timestamp", "") >= cutoff]
        try:
            HISTORY_FILE.write_text(
                json.dumps(self._history, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            error_logger.log_error("social.automation.history_save", e)

    def _record_history(self, platform: str, content: str, result: PostResult) -> None:
        self._history.append({
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
            "success": result.success,
            "post_id": result.post_id,
            "url": result.url,
            "content_length": len(content),
            "content_preview": content[:100],
            "has_media": bool(result.metadata.get("has_media")),
            "error": result.error,
        })
        self._save_history()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Social media automation engine")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--post", nargs=2, metavar=("PLATFORM", "CONTENT"),
                       help="Post content to a platform")
    group.add_argument("--queue", action="store_true",
                       help="Process the content queue")
    group.add_argument("--summary", action="store_true",
                       help="Generate engagement summary")
    parser.add_argument("--days", type=int, default=7,
                        help="Days to include in summary (default: 7)")

    args = parser.parse_args()
    auto = SocialAutomation()

    if args.post:
        platform, content = args.post
        result = auto.post(platform, content)
        status = "OK" if result.success else "FAILED"
        print(f"[{status}] {result.platform}: {result.post_id or result.error}")

    elif args.queue:
        stats = auto.process_queue()
        print(f"Queue: {stats['posted']} posted, {stats['failed']} failed, {stats['skipped']} skipped")

    elif args.summary:
        summary = auto.generate_engagement_summary(days=args.days)
        print(f"Engagement Summary ({summary['period_start']} to {summary['period_end']})")
        print(f"  Total: {summary['total_posts']} posts, {summary['success_rate_pct']}% success rate")
        for plat, s in summary["by_platform"].items():
            print(f"  {plat}: {s['posts']} posts ({s['successful']} ok, {s['failed']} failed)")


if __name__ == "__main__":
    main()
