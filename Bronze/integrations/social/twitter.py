"""
Gold Tier — Twitter/X Integration
===================================
Posts to X (Twitter) via the v2 API using OAuth 1.0a.

Supports:
    - Single tweets
    - Thread posting (multi-tweet chains)
    - Image media upload (via v1.1 media/upload)
    - Per-tweet engagement metrics (impressions, likes, replies, retweets)
    - User timeline reading

Prerequisites:
    pip install requests requests-oauthlib

Environment variables:
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET

Usage:
    from integrations.social.twitter import TwitterPlatform

    tw = TwitterPlatform()
    result = tw.post("Check out our latest product launch! #startup")
    metrics = tw.get_metrics(result.post_id)
    thread_ids = tw.post_thread(["Tweet 1", "Tweet 2 in the chain", "Final tweet!"])
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config
from integrations.social.base import SocialPlatform, PostResult, MetricsResult

TWEET_CREATE_URL = "https://api.twitter.com/2/tweets"
TWEET_LOOKUP_URL = "https://api.twitter.com/2/tweets"
TWEET_METRICS_URL = "https://api.twitter.com/2/tweets/{tweet_id}"
MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
USER_TWEETS_URL = "https://api.twitter.com/2/users/{user_id}/tweets"
USER_ME_URL = "https://api.twitter.com/2/users/me"


class TwitterPlatform(SocialPlatform):
    """X/Twitter posting via API v2 with OAuth 1.0a."""

    platform_name = "twitter"
    char_limit = 280
    rate_limit_per_day = 5

    def __init__(self) -> None:
        config.load()
        self.api_key = config.env("TWITTER_API_KEY", "")
        self.api_secret = config.env("TWITTER_API_SECRET", "")
        self.access_token = config.env("TWITTER_ACCESS_TOKEN", "")
        self.access_secret = config.env("TWITTER_ACCESS_SECRET", "")
        self._auth = None
        self._user_id: str | None = None

    def authenticate(self) -> bool:
        """Set up OAuth 1.0a authentication."""
        if not all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            error_logger.log_error(
                "social.twitter",
                "Missing Twitter API credentials — set TWITTER_API_KEY, TWITTER_API_SECRET, "
                "TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET in .env",
            )
            return False

        try:
            from requests_oauthlib import OAuth1
            self._auth = OAuth1(
                self.api_key,
                client_secret=self.api_secret,
                resource_owner_key=self.access_token,
                resource_owner_secret=self.access_secret,
            )
            return True
        except ImportError:
            error_logger.log_error(
                "social.twitter",
                "requests-oauthlib not installed. Run: pip install requests requests-oauthlib",
            )
            return False

    # ------------------------------------------------------------------
    # Single tweet
    # ------------------------------------------------------------------

    def post(self, content: str, media: list[Path] | None = None) -> PostResult:
        """Create a tweet via the X API v2.

        Args:
            content: Tweet text (max 280 chars)
            media: Optional list of image paths to attach (max 4)
        """
        error = self.validate_content(content)
        if error:
            return PostResult(success=False, platform=self.platform_name, error=error)

        if not self.authenticate():
            return PostResult(
                success=False, platform=self.platform_name,
                error="Twitter authentication failed — check API credentials",
            )

        try:
            import requests
        except ImportError:
            return PostResult(
                success=False, platform=self.platform_name,
                error="requests library not installed",
            )

        try:
            payload: dict[str, Any] = {"text": content}

            # Upload media if provided
            if media:
                media_ids = self._upload_media(media)
                if media_ids:
                    payload["media"] = {"media_ids": media_ids}

            resp = requests.post(
                TWEET_CREATE_URL,
                auth=self._auth,
                json=payload,
                timeout=30,
            )

            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                tweet_id = data.get("id")

                result = PostResult(
                    success=True,
                    platform=self.platform_name,
                    post_id=tweet_id,
                    url=f"https://x.com/i/web/status/{tweet_id}" if tweet_id else None,
                    content_length=len(content),
                    metadata={"has_media": bool(media)},
                )

                bus.emit("social.post.success", {
                    "platform": self.platform_name,
                    "post_id": tweet_id,
                    "content_length": len(content),
                })
                error_logger.log_audit("social.post", "success", {
                    "platform": self.platform_name,
                    "post_id": tweet_id,
                })

                return result
            else:
                error_detail = resp.text[:500]
                error_logger.log_error("social.twitter.post", f"HTTP {resp.status_code}: {error_detail}")
                bus.emit("social.post.failed", {
                    "platform": self.platform_name,
                    "status_code": resp.status_code,
                })
                return PostResult(
                    success=False, platform=self.platform_name,
                    error=f"Twitter API returned {resp.status_code}: {error_detail}",
                )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            bus.emit("social.post.failed", {
                "platform": self.platform_name, "error": error_msg,
            })
            error_logger.log_error("social.twitter.post", e)
            return PostResult(
                success=False, platform=self.platform_name, error=error_msg,
            )

    # ------------------------------------------------------------------
    # Thread posting
    # ------------------------------------------------------------------

    def post_thread(self, tweets: list[str]) -> list[PostResult]:
        """Post a thread — a chain of tweets where each replies to the previous.

        Args:
            tweets: Ordered list of tweet texts. First is the root tweet.

        Returns:
            List of PostResult, one per tweet in the thread.
        """
        if not tweets:
            return []

        if not self.authenticate():
            return [PostResult(
                success=False, platform=self.platform_name,
                error="Twitter authentication failed",
            )]

        try:
            import requests
        except ImportError:
            return [PostResult(
                success=False, platform=self.platform_name,
                error="requests library not installed",
            )]

        results: list[PostResult] = []
        previous_tweet_id: str | None = None

        for i, text in enumerate(tweets):
            error = self.validate_content(text)
            if error:
                results.append(PostResult(
                    success=False, platform=self.platform_name,
                    error=f"Tweet {i+1}: {error}",
                ))
                break  # Stop the thread on validation failure

            payload: dict[str, Any] = {"text": text}
            if previous_tweet_id:
                payload["reply"] = {"in_reply_to_tweet_id": previous_tweet_id}

            try:
                resp = requests.post(
                    TWEET_CREATE_URL,
                    auth=self._auth,
                    json=payload,
                    timeout=30,
                )

                if resp.status_code in (200, 201):
                    data = resp.json().get("data", {})
                    tweet_id = data.get("id")
                    previous_tweet_id = tweet_id

                    results.append(PostResult(
                        success=True,
                        platform=self.platform_name,
                        post_id=tweet_id,
                        url=f"https://x.com/i/web/status/{tweet_id}" if tweet_id else None,
                        content_length=len(text),
                        metadata={"thread_position": i + 1, "thread_length": len(tweets)},
                    ))
                else:
                    error_detail = resp.text[:300]
                    results.append(PostResult(
                        success=False, platform=self.platform_name,
                        error=f"Tweet {i+1}: HTTP {resp.status_code}: {error_detail}",
                    ))
                    break  # Stop the thread on API failure

            except Exception as e:
                results.append(PostResult(
                    success=False, platform=self.platform_name,
                    error=f"Tweet {i+1}: {type(e).__name__}: {e}",
                ))
                break

        # Emit summary event
        successful = sum(1 for r in results if r.success)
        bus.emit("social.thread.posted", {
            "platform": self.platform_name,
            "total": len(tweets),
            "successful": successful,
            "root_tweet_id": results[0].post_id if results and results[0].success else None,
        })

        return results

    # ------------------------------------------------------------------
    # Media upload (v1.1 endpoint)
    # ------------------------------------------------------------------

    def _upload_media(self, media: list[Path]) -> list[str]:
        """Upload images via the v1.1 media/upload endpoint.

        Returns list of media_id strings (max 4).
        """
        import requests

        media_ids = []
        for path in media[:4]:  # Twitter allows max 4 images
            path = Path(path)
            if not path.is_file():
                error_logger.log_error("social.twitter.media", f"File not found: {path}")
                continue

            try:
                with open(path, "rb") as f:
                    resp = requests.post(
                        MEDIA_UPLOAD_URL,
                        auth=self._auth,
                        files={"media": f},
                        timeout=60,
                    )

                if resp.status_code in (200, 201):
                    media_id = resp.json().get("media_id_string")
                    if media_id:
                        media_ids.append(media_id)
                else:
                    error_logger.log_error(
                        "social.twitter.media",
                        f"Upload failed HTTP {resp.status_code}: {resp.text[:200]}",
                    )
            except Exception as e:
                error_logger.log_error("social.twitter.media", e, {"file": str(path)})

        return media_ids

    # ------------------------------------------------------------------
    # Engagement metrics
    # ------------------------------------------------------------------

    def get_metrics(self, post_id: str) -> MetricsResult:
        """Fetch engagement metrics for a tweet."""
        if not self.authenticate():
            return MetricsResult(platform=self.platform_name, post_id=post_id)

        try:
            import requests

            url = TWEET_METRICS_URL.format(tweet_id=post_id)
            params = {
                "tweet.fields": "public_metrics,created_at",
            }
            resp = requests.get(url, auth=self._auth, params=params, timeout=30)

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                metrics = data.get("public_metrics", {})

                return MetricsResult(
                    platform=self.platform_name,
                    post_id=post_id,
                    impressions=metrics.get("impression_count", 0),
                    likes=metrics.get("like_count", 0),
                    comments=metrics.get("reply_count", 0),
                    shares=metrics.get("retweet_count", 0) + metrics.get("quote_count", 0),
                )
            else:
                error_logger.log_error("social.twitter.metrics",
                    f"HTTP {resp.status_code}", {"post_id": post_id})

        except ImportError:
            pass
        except Exception as e:
            error_logger.log_error("social.twitter.metrics", e, {"post_id": post_id})

        return MetricsResult(platform=self.platform_name, post_id=post_id)

    def get_metrics_batch(self, post_ids: list[str]) -> list[MetricsResult]:
        """Fetch metrics for multiple tweets in a single API call (up to 100)."""
        if not post_ids or not self.authenticate():
            return []

        try:
            import requests

            # v2 allows comma-separated IDs lookup
            ids_str = ",".join(post_ids[:100])
            params = {
                "ids": ids_str,
                "tweet.fields": "public_metrics,created_at",
            }
            resp = requests.get(TWEET_LOOKUP_URL, auth=self._auth, params=params, timeout=30)

            if resp.status_code == 200:
                results = []
                for tweet in resp.json().get("data", []):
                    metrics = tweet.get("public_metrics", {})
                    results.append(MetricsResult(
                        platform=self.platform_name,
                        post_id=tweet["id"],
                        impressions=metrics.get("impression_count", 0),
                        likes=metrics.get("like_count", 0),
                        comments=metrics.get("reply_count", 0),
                        shares=metrics.get("retweet_count", 0) + metrics.get("quote_count", 0),
                    ))
                return results

        except Exception as e:
            error_logger.log_error("social.twitter.metrics_batch", e)

        return []

    # ------------------------------------------------------------------
    # User timeline
    # ------------------------------------------------------------------

    def get_my_user_id(self) -> str | None:
        """Fetch the authenticated user's ID."""
        if self._user_id:
            return self._user_id

        if not self.authenticate():
            return None

        try:
            import requests
            resp = requests.get(USER_ME_URL, auth=self._auth, timeout=30)
            if resp.status_code == 200:
                self._user_id = resp.json().get("data", {}).get("id")
                return self._user_id
        except Exception as e:
            error_logger.log_error("social.twitter.user_me", e)

        return None

    def get_recent_tweets(self, limit: int = 20) -> list[dict]:
        """Fetch the authenticated user's recent tweets with metrics.

        Returns list of dicts with tweet data and public_metrics.
        """
        user_id = self.get_my_user_id()
        if not user_id:
            return []

        try:
            import requests

            url = USER_TWEETS_URL.format(user_id=user_id)
            params = {
                "max_results": min(limit, 100),
                "tweet.fields": "public_metrics,created_at,text",
            }
            resp = requests.get(url, auth=self._auth, params=params, timeout=30)

            if resp.status_code == 200:
                return resp.json().get("data", [])

        except Exception as e:
            error_logger.log_error("social.twitter.recent_tweets", e)

        return []
