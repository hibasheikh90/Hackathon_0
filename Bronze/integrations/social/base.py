"""
Gold Tier — Social Media Platform Base Class
=============================================
Abstract interface that every social platform must implement.

Usage:
    from integrations.social.base import SocialPlatform, PostResult

    class MyPlatform(SocialPlatform):
        platform_name = "myplatform"
        ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PostResult:
    """Standardized result from any social platform post."""
    success: bool
    platform: str
    post_id: str | None = None
    url: str | None = None
    content_length: int = 0
    timestamp: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class MetricsResult:
    """Standardized engagement metrics from any platform."""
    platform: str
    post_id: str
    impressions: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    engagement_rate: float = 0.0
    fetched_at: str = ""

    def __post_init__(self):
        if not self.fetched_at:
            self.fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.impressions > 0 and self.engagement_rate == 0.0:
            total_engagement = self.likes + self.comments + self.shares + self.clicks
            self.engagement_rate = round((total_engagement / self.impressions) * 100, 2)


class SocialPlatform(ABC):
    """Abstract base class for social media platforms."""

    platform_name: str = "unknown"
    char_limit: int = 5000
    rate_limit_per_day: int = 10

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the platform. Returns True on success."""
        ...

    @abstractmethod
    def post(self, content: str, media: list[Path] | None = None) -> PostResult:
        """Publish content to the platform.

        Args:
            content: Text content to post
            media: Optional list of media file paths (images, videos)

        Returns:
            PostResult with success/failure info
        """
        ...

    @abstractmethod
    def get_metrics(self, post_id: str) -> MetricsResult:
        """Fetch engagement metrics for a specific post.

        Args:
            post_id: Platform-specific post identifier

        Returns:
            MetricsResult with engagement data
        """
        ...

    def validate_content(self, content: str) -> str | None:
        """Validate content before posting. Returns error message or None if valid."""
        if not content.strip():
            return "Post content cannot be empty"
        if len(content) > self.char_limit:
            return f"Content exceeds {self.char_limit} character limit ({len(content)} chars)"
        return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} platform={self.platform_name!r}>"
