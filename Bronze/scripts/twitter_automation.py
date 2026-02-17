"""
Gold Tier — Twitter/X Automation Skill
========================================
Standalone automation script for the AI Employee's Twitter presence.

Features:
    - Auto-post single tweets
    - Post multi-tweet threads
    - Upload images with tweets
    - Fetch per-tweet engagement metrics
    - Generate weekly engagement reports saved to vault
    - Log every action to vault/Done/twitter_logs/

Usage:
    # Post a single tweet
    python scripts/twitter_automation.py --tweet "Hello from the AI Employee! #automation"

    # Post with an image
    python scripts/twitter_automation.py --tweet "Look at this!" --media photo.jpg

    # Post a thread (pipe-separated tweets)
    python scripts/twitter_automation.py --thread "First tweet|Second tweet|Final tweet"

    # Fetch metrics for a specific tweet
    python scripts/twitter_automation.py --metrics 1234567890

    # Generate weekly engagement report
    python scripts/twitter_automation.py --report

    # Show recent tweet history
    python scripts/twitter_automation.py --history
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config
from integrations.social.twitter import TwitterPlatform
from integrations.social.scheduler import SocialScheduler

# ---------------------------------------------------------------------------
# Vault paths
# ---------------------------------------------------------------------------
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
DONE_DIR = VAULT_DIR / "Done"
TWITTER_LOG_DIR = DONE_DIR / "twitter_logs"
TWITTER_REPORT_DIR = DONE_DIR / "twitter_reports"

# Post history persistence
HISTORY_FILE = _PROJECT_ROOT / "core" / ".twitter_post_history.json"


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------

def _load_history() -> list[dict]:
    if HISTORY_FILE.is_file():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_history(history: list[dict]) -> None:
    # Keep 90 days
    cutoff = (datetime.now() - timedelta(days=90)).isoformat()
    history = [h for h in history if h.get("timestamp", "") >= cutoff]
    try:
        HISTORY_FILE.write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")
    except OSError as e:
        error_logger.log_error("twitter.history_save", e)


def _record(history: list[dict], tweet_id: str | None, content: str,
            success: bool, error: str | None = None, **extra) -> None:
    history.append({
        "tweet_id": tweet_id,
        "timestamp": datetime.now().isoformat(),
        "content_preview": content[:140],
        "content_length": len(content),
        "success": success,
        "error": error,
        "url": f"https://x.com/i/web/status/{tweet_id}" if tweet_id else None,
        **extra,
    })
    _save_history(history)


# ---------------------------------------------------------------------------
# Vault logging
# ---------------------------------------------------------------------------

def _log_tweet_to_vault(content: str, result, *, thread_pos: int = 0,
                        thread_len: int = 0, media: list[str] | None = None) -> Path:
    """Write a tweet log entry into vault/Done/twitter_logs/."""
    TWITTER_LOG_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now()
    status = "SUCCESS" if result.success else "FAILED"
    filename = f"{ts:%Y%m%d_%H%M%S}_tweet_{status}.md"
    path = TWITTER_LOG_DIR / filename

    lines = [
        f"# Tweet Log — {status}",
        "",
        f"**Timestamp:** {ts:%Y-%m-%d %H:%M:%S}",
        f"**Tweet ID:** {result.post_id or 'N/A'}",
    ]

    if result.url:
        lines.append(f"**URL:** {result.url}")
    if thread_pos:
        lines.append(f"**Thread:** {thread_pos}/{thread_len}")
    if media:
        lines.append(f"**Media:** {', '.join(media)}")

    lines.extend([
        f"**Characters:** {len(content)}/280",
        "",
        "---",
        "",
        "## Content",
        "",
        f"> {content}",
        "",
    ])

    if result.error:
        lines.extend([
            "## Error",
            "",
            f"```",
            result.error,
            f"```",
            "",
        ])

    lines.extend([f"#twitter #tweet #{status.lower()}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _log_thread_to_vault(tweets: list[str], results) -> Path:
    """Write a complete thread log to the vault."""
    TWITTER_LOG_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now()
    successful = sum(1 for r in results if r.success)
    filename = f"{ts:%Y%m%d_%H%M%S}_thread_{successful}of{len(tweets)}.md"
    path = TWITTER_LOG_DIR / filename

    lines = [
        f"# Thread Log — {successful}/{len(tweets)} tweets posted",
        "",
        f"**Timestamp:** {ts:%Y-%m-%d %H:%M:%S}",
        f"**Total Tweets:** {len(tweets)}",
        f"**Successful:** {successful}",
    ]

    if results and results[0].success:
        lines.append(f"**Root Tweet:** https://x.com/i/web/status/{results[0].post_id}")

    lines.extend(["", "---", ""])

    for i, (text, result) in enumerate(zip(tweets, results)):
        icon = "+" if result.success else "x"
        lines.append(f"### [{icon}] Tweet {i+1}")
        lines.append("")
        lines.append(f"> {text}")
        lines.append("")
        if result.post_id:
            lines.append(f"ID: `{result.post_id}`")
        if result.error:
            lines.append(f"Error: {result.error}")
        lines.append("")

    lines.extend(["#twitter #thread", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_tweet(content: str, media_paths: list[str] | None = None) -> None:
    """Post a single tweet."""
    tw = TwitterPlatform()
    scheduler = SocialScheduler()
    history = _load_history()

    if not scheduler.can_post("twitter"):
        print(f"[SKIP] Rate limit reached ({scheduler.posts_today('twitter')} "
              f"tweets today, limit {scheduler.remaining_today('twitter') + scheduler.posts_today('twitter')})")
        return

    media = [Path(p) for p in media_paths] if media_paths else None
    result = tw.post(content, media=media)

    if result.success:
        scheduler.record_post("twitter")

    _record(history, result.post_id, content, result.success, result.error,
            has_media=bool(media))

    vault_path = _log_tweet_to_vault(content, result,
                                      media=media_paths)

    status = "OK" if result.success else "FAILED"
    print(f"[{status}] Tweet: {result.post_id or result.error}")
    if result.url:
        print(f"  URL: {result.url}")
    print(f"  Vault log: {vault_path.relative_to(_PROJECT_ROOT)}")


def cmd_thread(parts: list[str]) -> None:
    """Post a multi-tweet thread."""
    tw = TwitterPlatform()
    scheduler = SocialScheduler()
    history = _load_history()

    if not scheduler.can_post("twitter"):
        print("[SKIP] Rate limit reached for today")
        return

    print(f"Posting thread ({len(parts)} tweets)...")
    results = tw.post_thread(parts)

    for i, (text, result) in enumerate(zip(parts, results)):
        status = "OK" if result.success else "FAIL"
        print(f"  [{status}] Tweet {i+1}: {result.post_id or result.error}")

        if result.success:
            scheduler.record_post("twitter")
            _record(history, result.post_id, text, True,
                    thread_position=i + 1, thread_length=len(parts))
        else:
            _record(history, None, text, False, result.error,
                    thread_position=i + 1, thread_length=len(parts))

    vault_path = _log_thread_to_vault(parts, results)
    successful = sum(1 for r in results if r.success)
    print(f"\nThread: {successful}/{len(parts)} posted")
    print(f"Vault log: {vault_path.relative_to(_PROJECT_ROOT)}")


def cmd_metrics(tweet_id: str) -> None:
    """Fetch and display metrics for a tweet."""
    tw = TwitterPlatform()
    m = tw.get_metrics(tweet_id)

    print(f"Metrics for tweet {tweet_id}:")
    print(f"  Impressions:  {m.impressions:,}")
    print(f"  Likes:        {m.likes:,}")
    print(f"  Replies:      {m.comments:,}")
    print(f"  Retweets:     {m.shares:,}")
    print(f"  Engagement:   {m.engagement_rate:.2f}%")


def cmd_report(days: int = 7) -> None:
    """Generate a weekly engagement report and save to vault."""
    tw = TwitterPlatform()
    history = _load_history()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    recent = [h for h in history if h.get("timestamp", "") >= cutoff and h.get("success")]

    if not recent:
        print(f"No tweets found in the last {days} days.")
        # Still generate an empty report
        _write_report_to_vault([], [], days)
        return

    # Fetch live metrics for all recent tweet IDs
    tweet_ids = [h["tweet_id"] for h in recent if h.get("tweet_id")]

    print(f"Fetching metrics for {len(tweet_ids)} tweets...")
    metrics_list = tw.get_metrics_batch(tweet_ids) if tweet_ids else []

    # Build metrics lookup
    metrics_by_id: dict[str, dict] = {}
    for m in metrics_list:
        metrics_by_id[m.post_id] = {
            "impressions": m.impressions,
            "likes": m.likes,
            "replies": m.comments,
            "retweets": m.shares,
            "engagement_rate": m.engagement_rate,
        }

    # Merge history + metrics
    enriched = []
    for h in recent:
        tid = h.get("tweet_id", "")
        entry = {
            "tweet_id": tid,
            "timestamp": h.get("timestamp", ""),
            "content": h.get("content_preview", ""),
            "url": h.get("url", ""),
            "metrics": metrics_by_id.get(tid, {}),
        }
        enriched.append(entry)

    report_path = _write_report_to_vault(enriched, metrics_list, days)

    # Print summary
    total_impressions = sum(m.get("impressions", 0) for m in metrics_by_id.values())
    total_likes = sum(m.get("likes", 0) for m in metrics_by_id.values())
    total_replies = sum(m.get("replies", 0) for m in metrics_by_id.values())
    total_retweets = sum(m.get("retweets", 0) for m in metrics_by_id.values())

    print(f"\n=== Twitter Weekly Report ({days} days) ===")
    print(f"  Tweets posted:   {len(recent)}")
    print(f"  Impressions:     {total_impressions:,}")
    print(f"  Likes:           {total_likes:,}")
    print(f"  Replies:         {total_replies:,}")
    print(f"  Retweets:        {total_retweets:,}")
    if total_impressions > 0:
        eng = (total_likes + total_replies + total_retweets) / total_impressions * 100
        print(f"  Engagement rate: {eng:.2f}%")
    print(f"\n  Report: {report_path.relative_to(_PROJECT_ROOT)}")


def _write_report_to_vault(enriched: list[dict], metrics_list: list, days: int) -> Path:
    """Write the weekly engagement report as Markdown into the vault."""
    TWITTER_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now()
    period_start = (ts - timedelta(days=days)).strftime("%Y-%m-%d")
    period_end = ts.strftime("%Y-%m-%d")
    filename = f"twitter_report_{period_start}_to_{period_end}.md"
    path = TWITTER_REPORT_DIR / filename

    # Aggregate totals
    total_impressions = 0
    total_likes = 0
    total_replies = 0
    total_retweets = 0

    for entry in enriched:
        m = entry.get("metrics", {})
        total_impressions += m.get("impressions", 0)
        total_likes += m.get("likes", 0)
        total_replies += m.get("replies", 0)
        total_retweets += m.get("retweets", 0)

    total_engagement = total_likes + total_replies + total_retweets
    eng_rate = (total_engagement / total_impressions * 100) if total_impressions > 0 else 0.0

    lines = [
        f"# Twitter/X Weekly Engagement Report",
        "",
        f"**Period:** {period_start} to {period_end} ({days} days)",
        f"**Generated:** {ts:%Y-%m-%d %H:%M:%S}",
        f"**Source:** AI Employee Twitter Automation",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Tweets Posted | {len(enriched)} |",
        f"| Total Impressions | {total_impressions:,} |",
        f"| Total Likes | {total_likes:,} |",
        f"| Total Replies | {total_replies:,} |",
        f"| Total Retweets | {total_retweets:,} |",
        f"| Engagement Rate | {eng_rate:.2f}% |",
        "",
        "---",
        "",
        "## Per-Tweet Breakdown",
        "",
        "| # | Date | Tweet | Impr. | Likes | Replies | RTs | Eng% |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for i, entry in enumerate(enriched, 1):
        m = entry.get("metrics", {})
        date_str = entry.get("timestamp", "")[:10]
        preview = entry.get("content", "")[:60].replace("|", "/")
        impr = m.get("impressions", 0)
        likes = m.get("likes", 0)
        replies = m.get("replies", 0)
        rts = m.get("retweets", 0)
        eng = m.get("engagement_rate", 0.0)
        url = entry.get("url", "")

        tweet_text = f"[{preview}...]({url})" if url else f"{preview}..."
        lines.append(
            f"| {i} | {date_str} | {tweet_text} | {impr:,} | {likes} | {replies} | {rts} | {eng:.1f}% |"
        )

    lines.extend([
        "",
        "---",
        "",
    ])

    # Top performing tweet
    if enriched:
        best = max(enriched, key=lambda e: e.get("metrics", {}).get("likes", 0))
        best_m = best.get("metrics", {})
        if best_m.get("likes", 0) > 0:
            lines.extend([
                "## Top Performing Tweet",
                "",
                f"> {best.get('content', 'N/A')}",
                "",
                f"- **Likes:** {best_m.get('likes', 0)}",
                f"- **Impressions:** {best_m.get('impressions', 0):,}",
                f"- **Engagement:** {best_m.get('engagement_rate', 0):.2f}%",
                "",
                "---",
                "",
            ])

    # Recommendations
    lines.extend([
        "## Recommendations",
        "",
    ])

    if len(enriched) == 0:
        lines.append("- No tweets posted this period. Consider posting 3-5 times per week.")
    elif eng_rate < 1.0:
        lines.append("- Engagement rate is below 1%. Try more questions, polls, or visual content.")
    elif eng_rate >= 3.0:
        lines.append("- Strong engagement! Keep up the current content strategy.")
    else:
        lines.append("- Engagement is moderate. Experiment with different posting times and content types.")

    scheduler = SocialScheduler()
    remaining = scheduler.remaining_today("twitter")
    lines.append(f"- Rate limit today: {remaining} tweets remaining")
    lines.append("")

    lines.extend(["#twitter #engagement #report #weekly", ""])

    path.write_text("\n".join(lines), encoding="utf-8")

    error_logger.log_audit("twitter.report", "generated", {
        "file": filename,
        "tweets": len(enriched),
        "total_impressions": total_impressions,
        "engagement_rate": round(eng_rate, 2),
    })

    return path


def cmd_history(limit: int = 20) -> None:
    """Show recent tweet history from the log."""
    history = _load_history()
    recent = history[-limit:]
    recent.reverse()

    if not recent:
        print("No tweet history found.")
        return

    print(f"Recent tweets ({len(recent)} of {len(history)} total):\n")
    for h in recent:
        status = "OK" if h.get("success") else "FAIL"
        ts = h.get("timestamp", "")[:16]
        preview = h.get("content_preview", "")[:60]
        tid = h.get("tweet_id", "N/A")
        thread_info = ""
        if h.get("thread_position"):
            thread_info = f" [thread {h['thread_position']}/{h['thread_length']}]"
        print(f"  [{status}] {ts} | {tid} | {preview}...{thread_info}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Twitter/X automation for the AI Employee",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --tweet "Hello world! #AI"
  %(prog)s --tweet "Check this out!" --media photo.jpg
  %(prog)s --thread "First|Second|Third"
  %(prog)s --metrics 1234567890
  %(prog)s --report
  %(prog)s --report --days 30
  %(prog)s --history""",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tweet", type=str, help="Post a single tweet")
    group.add_argument("--thread", type=str,
                       help="Post a thread (pipe-separated tweets)")
    group.add_argument("--metrics", type=str,
                       help="Fetch metrics for a tweet ID")
    group.add_argument("--report", action="store_true",
                       help="Generate weekly engagement report")
    group.add_argument("--history", action="store_true",
                       help="Show recent tweet history")

    parser.add_argument("--media", type=str, nargs="*",
                        help="Image file(s) to attach (with --tweet)")
    parser.add_argument("--days", type=int, default=7,
                        help="Days to include in report (default: 7)")

    args = parser.parse_args()

    if args.tweet:
        cmd_tweet(args.tweet, args.media)
    elif args.thread:
        parts = [t.strip() for t in args.thread.split("|") if t.strip()]
        if len(parts) < 2:
            print("Thread requires at least 2 tweets (pipe-separated).")
            sys.exit(1)
        cmd_thread(parts)
    elif args.metrics:
        cmd_metrics(args.metrics)
    elif args.report:
        cmd_report(days=args.days)
    elif args.history:
        cmd_history()


if __name__ == "__main__":
    main()
