# Skill: Gmail Send

## Description

Sends real emails through Gmail SMTP. This skill is a production replacement for email-sending MCP servers. It authenticates using environment variables, constructs a MIME message, and delivers it via TLS.

## Prerequisites

Set these environment variables before use:

```
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_PASSWORD=your-app-password
```

**Important:** Use a Gmail App Password, not your account password. Generate one at https://myaccount.google.com/apppasswords (requires 2FA enabled).

## Usage

```bash
python scripts/send_email.py --to "recipient@example.com" --subject "Meeting Tomorrow" --body "Hi, confirming our 2pm meeting."
```

**All three flags are required.**

Optional flags:
- `--cc "person@example.com"` — Add CC recipients (comma-separated)
- `--html` — Treat the body as HTML instead of plain text

## Inputs

| Parameter   | Required | Description                          |
|-------------|----------|--------------------------------------|
| `--to`      | Yes      | Recipient email address              |
| `--subject` | Yes      | Email subject line                   |
| `--body`    | Yes      | Email body (plain text or HTML)      |
| `--cc`      | No       | CC recipients, comma-separated       |
| `--html`    | No       | Flag to send body as HTML            |

## Output

On success:
```
[OK] Email sent to recipient@example.com
  Subject: Meeting Tomorrow
  Timestamp: 2026-02-15 14:30:22
```

On failure:
```
[ERROR] Failed to send email: <error detail>
```

## Workflow

1. Validate that `EMAIL_ADDRESS` and `EMAIL_PASSWORD` are set in environment.
2. Validate all required inputs (`--to`, `--subject`, `--body`).
3. Construct MIME message with proper headers.
4. Connect to `smtp.gmail.com:587` over TLS.
5. Authenticate with credentials.
6. Send the message.
7. Print confirmation or error.

## Security Notes

- Credentials are never logged or written to files.
- The script exits with code 1 on any failure.
- TLS is mandatory — the script never sends over plain SMTP.
