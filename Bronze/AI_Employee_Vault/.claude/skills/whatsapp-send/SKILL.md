# Skill: WhatsApp Send

## Description

Sends WhatsApp messages using Playwright browser automation via WhatsApp Web. Uses persistent browser state so you only need to scan the QR code once.

## Prerequisites

1. Install Playwright:
```bash
pip install playwright
playwright install chromium
```

2. A WhatsApp account linked to a phone.

## Usage

```bash
python scripts/send_whatsapp.py --phone "+923001234567" --message "Hello from automation!"
```

Optional flags:
- `--headless` — Run browser in headless mode (not recommended for first run)
- `--dry-run` — Type the message but do not send it

## First Run

On the first run, a browser window will open showing a QR code. Scan it with your phone:
1. Open WhatsApp on your phone
2. Go to Settings > Linked Devices > Link a Device
3. Scan the QR code

The session is saved — subsequent runs will skip the QR step.

## Inputs

| Parameter   | Required | Description                                      |
|-------------|----------|--------------------------------------------------|
| `--phone`   | Yes      | Recipient phone number with country code         |
| `--message` | Yes      | The message text to send                         |
| `--headless`| No       | Run browser without visible window               |
| `--dry-run` | No       | Preview mode — does everything except send       |

## Limitations

- Text messages only (no images, documents, or media).
- WhatsApp Web must stay linked to your phone.
- Do not run in headless mode on the first run (QR code needs to be visible).
