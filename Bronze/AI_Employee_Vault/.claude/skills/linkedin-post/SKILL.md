# Skill: LinkedIn Post

## Description

Creates real LinkedIn text posts using Playwright browser automation. This skill logs into LinkedIn, navigates to the post composer, types the content, and publishes it. Designed as a production replacement for LinkedIn API integrations that require OAuth app approval.

## Prerequisites

1. Set environment variables:
```
LINKEDIN_EMAIL=your.email@example.com
LINKEDIN_PASSWORD=your-password
```

2. Install Playwright:
```bash
pip install playwright
playwright install chromium
```

## Usage

```bash
python scripts/post_linkedin.py --content "Excited to share our latest project update! #AI #Automation"
```

Optional flags:
- `--headless` — Run browser in headless mode (default: visible browser)
- `--dry-run` — Navigate and type the post but do not click Publish

## Inputs

| Parameter    | Required | Description                                  |
|--------------|----------|----------------------------------------------|
| `--content`  | Yes      | The text content of the LinkedIn post        |
| `--headless` | No       | Run browser without visible window           |
| `--dry-run`  | No       | Preview mode — does everything except publish |

## Output

On success:
```
[OK] LinkedIn post published successfully
  Length: 142 characters
  Timestamp: 2026-02-15 14:30:22
```

On failure:
```
[ERROR] LinkedIn post failed: <error detail>
```

## Workflow

1. Validate that `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD` are set.
2. Validate that `--content` is provided and within LinkedIn's character limit.
3. Launch Chromium via Playwright.
4. Navigate to LinkedIn login page.
5. Enter credentials and submit.
6. Wait for the home feed to load.
7. Click the "Start a post" button to open the composer.
8. Type the post content.
9. Click "Post" to publish (skipped in `--dry-run` mode).
10. Confirm the post appeared in the feed.
11. Close the browser and print confirmation.

## Security Notes

- Credentials are never logged, screenshotted, or written to files.
- The browser session is ephemeral — no cookies or state are persisted between runs.
- LinkedIn may trigger security challenges (CAPTCHA, email verification) on new logins. Run in visible mode first to handle these manually.

## Limitations

- LinkedIn's DOM changes frequently. Selectors may need updates.
- Rate limiting: do not post more than 2–3 times per day.
- Does not support image or document attachments (text posts only).
