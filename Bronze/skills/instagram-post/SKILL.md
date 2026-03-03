# Skill: Instagram Post

## Description

Posts content to Instagram via Playwright browser automation (persistent session). Supports image posts and caption text. Reuses a saved browser session to avoid repeated login.

## Prerequisites

1. Instagram account credentials.
2. `.env` file with:
   ```
   INSTAGRAM_USERNAME="your_username"
   INSTAGRAM_PASSWORD="your_password"
   ```
3. Dependencies: `pip install playwright python-dotenv && playwright install chromium`
4. First run requires interactive browser (non-headless) to complete any login challenges.

## Usage

```bash
# Post with caption
python -c "
from integrations.social.instagram import InstagramPlatform
ig = InstagramPlatform()
result = ig.post('New product launch! Check it out. #business #startup')
print(result.success, result.post_id)
"

# Post with image
python -c "
from pathlib import Path
from integrations.social.instagram import InstagramPlatform
ig = InstagramPlatform()
result = ig.post('Behind the scenes at the office!', media=[Path('photo.jpg')])
"

# Schedule via social queue (recommended)
python -c "
from integrations.social.content_queue import ContentQueue
q = ContentQueue()
q.add_draft('Our latest update!', platforms=['instagram'], scheduled_time='2026-02-24 11:00')
"

# Run social scheduler (posts queued content at scheduled times)
python -c "from integrations.social.scheduler import SocialScheduler; SocialScheduler().run_once()"
```

## Inputs

| Parameter | Required | Description |
|-----------|----------|-------------|
| `text` | Yes | Caption text for the post |
| `media` | No | List of image file Paths to attach |

## Output

| Return | Type | Description |
|--------|------|-------------|
| `PostResult.success` | bool | Whether the post succeeded |
| `PostResult.post_id` | str | Instagram post identifier (if available) |
| `PostResult.url` | str | URL to the posted content |

## Workflow

1. Launch Chromium with persistent context from `.instagram_browser_data/` (no QR re-scan).
2. Navigate to `https://www.instagram.com/`.
3. If not logged in, authenticate using `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD`.
4. Use the Instagram web interface to compose and submit the post.
5. On success: fires `social.post.success` event.
6. On failure: fires `social.post.failed`; retries up to 2 times before logging to `logs/error.log`.
7. Session data is saved to persist login across restarts.

## Rate Limits

| Default | Configured |
|---------|------------|
| Instagram allows ~50 posts/day | 2 posts/day (conservative) |

Optimal posting hours: **11:00, 19:00**. The content queue enforces this automatically.

## MCP Integration

The `mcp_servers/social_server.py` exposes Instagram posting as Claude-callable tools:

| Tool | Description |
|------|-------------|
| `create_draft` | Add an Instagram post to the content queue |
| `schedule_post` | Schedule for a specific time |
| `get_metrics` | Retrieve post engagement data |

## Important Notes

- Instagram's web automation may break if Instagram updates their UI. Check `logs/error.log` if posts start failing.
- Never run two Instagram sessions simultaneously — the persistent browser data prevents this.
- Image files must exist at the specified path before posting.
