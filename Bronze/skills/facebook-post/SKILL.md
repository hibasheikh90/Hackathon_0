# Skill: Facebook Post

## Description

Posts content to Facebook Pages and Profiles via Playwright browser automation using a persistent session. Supports text posts and image attachments on both personal profiles and managed Pages.

## Prerequisites

1. Facebook account credentials.
2. `.env` file with:
   ```
   FACEBOOK_EMAIL="your_email@example.com"
   FACEBOOK_PASSWORD="your_password"
   ```
3. Dependencies: `pip install playwright python-dotenv && playwright install chromium`
4. First run requires interactive browser (non-headless) for any login challenges or 2FA.

## Usage

```bash
# Post a text update
python -c "
from integrations.social.facebook import FacebookPlatform
fb = FacebookPlatform()
result = fb.post('Exciting news from our team!')
print(result.success, result.url)
"

# Post with image
python -c "
from pathlib import Path
from integrations.social.facebook import FacebookPlatform
fb = FacebookPlatform()
result = fb.post('New product launch!', media=[Path('product.jpg')])
"

# Schedule via social queue (recommended)
python -c "
from integrations.social.content_queue import ContentQueue
q = ContentQueue()
q.add_draft('Our weekly update!', platforms=['facebook'], scheduled_time='2026-02-24 09:00')
"

# Run scheduler to post queued content
python -c "from integrations.social.scheduler import SocialScheduler; SocialScheduler().run_once()"
```

## Inputs

| Parameter | Required | Description |
|-----------|----------|-------------|
| `text` | Yes | Post caption / status text |
| `media` | No | List of image file Paths to attach |

## Output

| Return | Type | Description |
|--------|------|-------------|
| `PostResult.success` | bool | Whether the post succeeded |
| `PostResult.post_id` | str | Facebook post ID (if extracted) |
| `PostResult.url` | str | Direct link to the post |

## Workflow

1. Launch Chromium with persistent context from `.facebook_browser_data/` (login cached).
2. Navigate to `https://www.facebook.com/` (or `https://m.facebook.com/` as fallback).
3. If session expired, authenticate with `FACEBOOK_EMAIL` and `FACEBOOK_PASSWORD`.
4. Locate the "What's on your mind?" composer and enter the post text.
5. Attach images if provided.
6. Click Post and wait for confirmation.
7. On success: fires `social.post.success` event with platform `facebook` and post ID.
8. On failure: fires `social.post.failed`; retries up to 2 times; logs to `logs/error.log`.

## Rate Limits

| Default | Configured |
|---------|------------|
| Facebook allows many posts/day | 3 posts/day (conservative) |

Optimal posting hours: **09:00, 12:00, 18:00**. The content queue enforces this automatically.

## MCP Integration

The `mcp_servers/social_server.py` exposes Facebook posting as Claude-callable tools:

| Tool | Description |
|------|-------------|
| `create_draft` | Add a Facebook post to the content queue |
| `schedule_post` | Schedule a draft for a specific time |
| `get_metrics` | Retrieve engagement stats for a post |

## Important Notes

- Facebook's web automation may break when Facebook updates their UI. Monitor `logs/error.log`.
- Never run two Facebook browser sessions simultaneously.
- For business Pages, ensure the logged-in account has Page admin access.
- Image files must exist at the specified path before posting.
