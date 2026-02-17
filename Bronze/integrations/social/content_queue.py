"""
Gold Tier — Social Media Content Queue
========================================
Manages draft → approved → scheduled → posted lifecycle for social content.

Content files live in vault/Needs_Action/ with the prefix ``social_``.
Each file has YAML-style frontmatter for metadata.

File format:
    ---
    platforms: linkedin, twitter
    scheduled_time: 2026-02-17 09:00
    status: draft
    ---
    Your post content goes here. #hashtag

Usage:
    from integrations.social.content_queue import ContentQueue

    queue = ContentQueue()
    ready = queue.get_ready_posts()      # approved + past scheduled_time
    queue.mark_posted("social_launch.md", post_results)
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
DONE_DIR = VAULT_DIR / "Done"

SOCIAL_PREFIX = "social_"
VALID_STATUSES = {"draft", "approved", "scheduled", "posted", "failed"}


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML-style frontmatter from a markdown file.

    Returns (metadata_dict, body_content).
    """
    meta: dict[str, Any] = {}
    body = content

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return meta, body

    frontmatter_text = match.group(1)
    body = match.group(2).strip()

    for line in frontmatter_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()

        # Parse lists (comma-separated)
        if "," in value:
            meta[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            meta[key] = value

    return meta, body


def _write_frontmatter(meta: dict[str, Any], body: str) -> str:
    """Serialize metadata and body back into frontmatter format."""
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}: {', '.join(value)}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append(body)
    return "\n".join(lines) + "\n"


class ContentItem:
    """A single piece of social content from the queue."""

    def __init__(self, path: Path, meta: dict[str, Any], body: str) -> None:
        self.path = path
        self.filename = path.name
        self.meta = meta
        self.body = body

    @property
    def platforms(self) -> list[str]:
        p = self.meta.get("platforms", [])
        if isinstance(p, str):
            return [p]
        return p

    @property
    def status(self) -> str:
        return self.meta.get("status", "draft")

    @property
    def scheduled_time(self) -> datetime | None:
        ts = self.meta.get("scheduled_time", "")
        if not ts:
            return None
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None

    @property
    def is_ready(self) -> bool:
        """True if approved/scheduled and past the scheduled time."""
        if self.status not in ("approved", "scheduled"):
            return False
        sched = self.scheduled_time
        if sched is None:
            return self.status == "approved"  # no time = post immediately
        return datetime.now() >= sched

    def __repr__(self) -> str:
        return f"<ContentItem {self.filename!r} status={self.status!r} platforms={self.platforms}>"


class ContentQueue:
    """Manages the social content queue in the vault."""

    def __init__(self, queue_dir: Path | None = None) -> None:
        self.queue_dir = queue_dir or NEEDS_ACTION_DIR

    def scan(self) -> list[ContentItem]:
        """Scan for all social content files in Needs_Action/."""
        items = []
        if not self.queue_dir.is_dir():
            return items

        for md_file in sorted(self.queue_dir.glob(f"{SOCIAL_PREFIX}*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(content)
                items.append(ContentItem(md_file, meta, body))
            except OSError as e:
                error_logger.log_error("social.queue.scan", e, {"file": md_file.name})

        return items

    def get_ready_posts(self) -> list[ContentItem]:
        """Get all content items ready to publish (approved + past scheduled time)."""
        return [item for item in self.scan() if item.is_ready]

    def get_drafts(self) -> list[ContentItem]:
        """Get all draft items awaiting approval."""
        return [item for item in self.scan() if item.status == "draft"]

    def approve(self, filename: str) -> bool:
        """Move a draft to approved status."""
        return self._update_status(filename, "approved")

    def schedule(self, filename: str, time_str: str) -> bool:
        """Set a scheduled time and move to scheduled status."""
        path = self.queue_dir / filename
        if not path.is_file():
            return False

        content = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        meta["status"] = "scheduled"
        meta["scheduled_time"] = time_str
        path.write_text(_write_frontmatter(meta, body), encoding="utf-8")
        return True

    def mark_posted(self, filename: str, results: list[dict] | None = None) -> bool:
        """Mark content as posted and move to Done/."""
        path = self.queue_dir / filename
        if not path.is_file():
            return False

        content = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        meta["status"] = "posted"
        meta["posted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if results:
            summaries = []
            for r in results:
                summaries.append(f"{r.get('platform', '?')}: {r.get('post_id', 'ok')}")
            meta["post_results"] = "; ".join(summaries)

        # Move to Done
        DONE_DIR.mkdir(parents=True, exist_ok=True)
        done_path = DONE_DIR / filename
        done_path.write_text(_write_frontmatter(meta, body), encoding="utf-8")

        # Remove from queue
        try:
            path.unlink()
        except OSError:
            pass

        bus.emit("social.post.archived", {"file": filename})
        return True

    def mark_failed(self, filename: str, error: str) -> bool:
        """Mark content as failed with an error message."""
        path = self.queue_dir / filename
        if not path.is_file():
            return False

        content = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        meta["status"] = "failed"
        meta["failed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta["error"] = error
        path.write_text(_write_frontmatter(meta, body), encoding="utf-8")
        return True

    def _update_status(self, filename: str, new_status: str) -> bool:
        path = self.queue_dir / filename
        if not path.is_file():
            return False

        content = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        meta["status"] = new_status
        path.write_text(_write_frontmatter(meta, body), encoding="utf-8")
        return True


# ---------------------------------------------------------------------------
# Entry point for Gold scheduler
# ---------------------------------------------------------------------------
def process_queue() -> int:
    """Process the content queue — post all ready items.

    Returns the number of posts published.
    Called by core/scheduler.py on each cycle.
    """
    from integrations.social.facebook import FacebookPlatform
    from integrations.social.linkedin import LinkedInPlatform
    from integrations.social.twitter import TwitterPlatform
    from integrations.social.instagram import InstagramPlatform

    platforms = {
        "facebook": FacebookPlatform(),
        "linkedin": LinkedInPlatform(),
        "twitter": TwitterPlatform(),
        "instagram": InstagramPlatform(),
    }

    queue = ContentQueue()
    ready = queue.get_ready_posts()

    if not ready:
        return 0

    posted_count = 0
    for item in ready:
        results = []
        all_success = True

        for platform_name in item.platforms:
            platform = platforms.get(platform_name)
            if not platform:
                error_logger.log_error("social.queue", f"Unknown platform: {platform_name}")
                continue

            result = platform.post(item.body)
            results.append({
                "platform": platform_name,
                "success": result.success,
                "post_id": result.post_id,
                "error": result.error,
            })

            if not result.success:
                all_success = False

        if all_success and results:
            queue.mark_posted(item.filename, results)
            posted_count += 1
        elif results:
            errors = "; ".join(
                f"{r['platform']}: {r['error']}" for r in results if r.get("error")
            )
            queue.mark_failed(item.filename, errors)

    return posted_count
