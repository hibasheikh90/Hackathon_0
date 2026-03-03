# Skill: Twitter/X Post

## Description

Posts content to X (Twitter) using the official v2 API with OAuth 1.0a authentication. Supports single tweets, threaded posts (multi-tweet chains), image media upload, and per-tweet engagement metrics retrieval.

## Prerequisites

1. X Developer account with an App created at [developer.twitter.com](https://developer.twitter.com).
2. OAuth 1.0a credentials (API Key + Secret, Access Token + Secret).
3. `.env` file with:
   ```
   TWITTER_API_KEY="your_api_key"
   TWITTER_API_SECRET="your_api_secret"
   TWITTER_ACCESS_TOKEN="your_access_token"
   TWITTER_ACCESS_SECRET="your_access_secret"
   ```
4. Dependencies: `pip install requests requests-oauthlib python-dotenv`

## Usage

```bash
# Post a single tweet
python -c "
from integrations.social.twitter import TwitterPlatform
tw = TwitterPlatform()
result = tw.post('Check out our latest product launch! #startup')
print(result.post_id, result.url)
"

# Post a thread
python -c "
from integrations.social.twitter import TwitterPlatform
tw = TwitterPlatform()
ids = tw.post_thread([
    'Thread 1/3: Here is our weekly update...',
    '2/3: This week we shipped a new feature...',
    '3/3: More details at the link below!'
])
"

# Get tweet metrics
python -c "
from integrations.social.twitter import TwitterPlatform
tw = TwitterPlatform()
metrics = tw.get_metrics('tweet_id_here')
print(metrics)
"

# Schedule via social queue (recommended)
python -c "
from integrations.social.content_queue import ContentQueue
q = ContentQueue()
q.add_draft('Our Monday update! #business', platforms=['twitter'], scheduled_time='2026-02-24 09:00')
"
```

## Inputs

| Parameter | Required | Description |
|-----------|----------|-------------|
| `text` | Yes | Tweet text (max 280 characters) |
| `media` | No | List of image file Paths to attach |
| `tweets` | Yes (thread) | List of strings, one per tweet in the chain |

## Output

| Return | Type | Description |
|--------|------|-------------|
| `PostResult.post_id` | str | Tweet ID from the X API |
| `PostResult.url` | str | Direct URL to the posted tweet |
| `PostResult.success` | bool | Whether the post succeeded |
| `MetricsResult` | dict | Impressions, likes, replies, retweets |

## Workflow

1. Authenticate with X API v2 using OAuth 1.0a (`requests-oauthlib`).
2. For single tweet: `POST /2/tweets` with `{"text": "..."}`.
3. For thread: post first tweet, then reply to each subsequent tweet using `reply.in_reply_to_tweet_id`.
4. For media: upload image to v1.1 `media/upload`, attach `media_ids` to tweet body.
5. On success: fires `social.post.success` event with platform and post ID.
6. On failure: fires `social.post.failed` event; error logged to `logs/error.log`.

## Rate Limits

| Tier | Limit |
|------|-------|
| Free | 17 posts / 24 hours |
| Basic | 100 posts / 24 hours |
| Default configured | 5 posts / day (conservative) |

The social content queue (`integrations/social/content_queue.py`) enforces per-platform rate limits automatically. Optimal posting hours: **08:00, 12:00, 15:00, 18:00, 21:00**.

## MCP Integration

The `mcp_servers/social_server.py` exposes Twitter posting as Claude-callable tools:

| Tool | Description |
|------|-------------|
| `create_draft` | Add a tweet to the content queue |
| `schedule_post` | Schedule a draft tweet for a specific time |
| `get_metrics` | Retrieve engagement metrics for a post |
