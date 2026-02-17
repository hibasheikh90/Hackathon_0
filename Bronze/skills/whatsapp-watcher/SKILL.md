# Skill: WhatsApp Watcher

## Description

Polls WhatsApp Web using Playwright browser automation for unread messages and creates structured `.md` files in `vault/Inbox/` for the AI Employee pipeline to process.

Reuses the persistent browser session from the `whatsapp-send` skill — no second QR code scan required.

## Prerequisites

1. Playwright installed:
   ```bash
   pip install playwright
   playwright install chromium
   ```
2. WhatsApp Web already authenticated via the `whatsapp-send` skill (browser data in `AI_Employee_Vault/.claude/skills/whatsapp-send/scripts/.browser_data/`).

## Usage

```bash
# Single check — scan for unread messages, then exit
python scripts/whatsapp_watcher.py --once

# Continuous polling every 2 minutes
python scripts/whatsapp_watcher.py --daemon --interval 120

# Headless mode (no visible browser window)
python scripts/whatsapp_watcher.py --once --headless
```

## Inputs

| Parameter    | Required | Description                                           |
|--------------|----------|-------------------------------------------------------|
| `--once`     | Yes*     | Check once and exit                                   |
| `--daemon`   | Yes*     | Poll continuously                                     |
| `--interval` | No       | Seconds between polls in daemon mode (default: 120)   |
| `--headless` | No       | Run browser without visible window                    |

*One of `--once` or `--daemon` is required.

## Output

For each unread conversation, creates a markdown file in `vault/Inbox/` named `wa_{contact}_{keyword}.md` containing:

- **Metadata:** From (contact name), Date, Source, Type
- **Message:** Last message preview text

## Workflow

1. Launch Chromium with persistent browser context (reusing whatsapp-send session).
2. Navigate to WhatsApp Web and verify login status.
3. Scan sidebar for unread message badges.
4. For each unread chat (up to 10 per poll):
   - Extract contact name from the chat row.
   - Extract last message preview text.
   - Deduplicate against previously processed messages.
   - Write structured `.md` file to `vault/Inbox/`.
5. Track processed messages in `scripts/.whatsapp_watcher_state.json`.
6. In daemon mode, repeat at the configured interval.

## Limitations

- Text messages only — media messages show as preview text.
- Processes up to 10 unread chats per poll to avoid timeouts.
- Requires prior authentication via the `whatsapp-send` skill.
- WhatsApp Web session may expire if the phone is offline for extended periods.
