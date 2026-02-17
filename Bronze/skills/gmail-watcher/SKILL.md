# Skill: Gmail Watcher

## Description

Polls Gmail INBOX via IMAP for unread emails and creates structured `.md` files in `vault/Inbox/` for the AI Employee pipeline to triage and process.

## Prerequisites

1. Gmail account with IMAP enabled (Settings > See all settings > Forwarding and POP/IMAP > Enable IMAP).
2. Gmail App Password configured (https://myaccount.google.com/apppasswords).
3. `.env` file in the project root with:
   ```
   EMAIL_ADDRESS="your@gmail.com"
   EMAIL_PASSWORD="your-app-password"
   ```
4. `python-dotenv` installed (`pip install python-dotenv`).

## Usage

```bash
# Single poll — fetch unread emails, then exit
python scripts/gmail_watcher.py --once

# Continuous polling every 60 seconds
python scripts/gmail_watcher.py --daemon --interval 60
```

## Inputs

| Parameter    | Required | Description                                          |
|--------------|----------|------------------------------------------------------|
| `--once`     | Yes*     | Poll once and exit                                   |
| `--daemon`   | Yes*     | Poll continuously                                    |
| `--interval` | No       | Seconds between polls in daemon mode (default: 60)   |

*One of `--once` or `--daemon` is required.

## Output

For each unread email, creates a markdown file in `vault/Inbox/` named `gmail_{subject}.md` containing:

- **Metadata:** From, Date, Source, UID, Attachments (listed but not downloaded)
- **Body:** Plain text content of the email (truncated at 5000 chars)

## Workflow

1. Connect to `imap.gmail.com:993` using SSL.
2. Search for UNSEEN (unread) emails in INBOX.
3. For each new email:
   - Decode headers (From, Subject, Date) including RFC 2047 encoded values.
   - Extract plain text body (prefers text/plain, falls back to stripped text/html).
   - List attachment filenames without downloading.
   - Write structured `.md` file to `vault/Inbox/`.
   - Mark the email as read (SEEN flag).
4. Track processed UIDs in `scripts/.gmail_watcher_state.json` to avoid duplicates.
5. In daemon mode, repeat at the configured interval.

## Limitations

- Text extraction only — attachments are listed but not downloaded.
- Requires Gmail App Password (regular passwords will not work with IMAP).
- Very long email bodies are truncated at 5000 characters.
