# Skill: MCP Server

## Description

Model Context Protocol (MCP) server that wraps all AI Employee skills as tools accessible via stdio transport. Allows Claude Code and other MCP-compatible clients to invoke skills programmatically.

## Prerequisites

1. Install the MCP SDK:
   ```bash
   pip install mcp
   ```
2. All underlying skill scripts must be present in their expected locations.

## Usage

```bash
# Start the MCP server (stdio transport)
python scripts/mcp_server.py
```

### Claude Code Integration

Register in `.claude/settings.json`:
```json
{
  "mcpServers": {
    "ai-employee": {
      "command": "python",
      "args": ["scripts/mcp_server.py"]
    }
  }
}
```

## Available Tools

| Tool              | Description                                          | Underlying Script                      |
|-------------------|------------------------------------------------------|----------------------------------------|
| `send_email`      | Send email via Gmail SMTP                            | `gmail-send/scripts/send_email.py`     |
| `post_linkedin`   | Create a LinkedIn text post                          | `linkedin-post/scripts/post_linkedin.py` |
| `send_whatsapp`   | Send a WhatsApp message                              | `whatsapp-send/scripts/send_whatsapp.py` |
| `manage_vault`    | List, move, archive, search vault files              | `vault-file-manager/scripts/manage_files.py` |
| `check_gmail`     | Poll Gmail for unread emails                         | `scripts/gmail_watcher.py`             |
| `check_whatsapp`  | Check WhatsApp for unread messages                   | `scripts/whatsapp_watcher.py`          |

## Inputs (per tool)

### send_email
| Parameter | Required | Type    | Description                     |
|-----------|----------|---------|---------------------------------|
| `to`      | Yes      | string  | Recipient email address         |
| `subject` | Yes      | string  | Email subject line              |
| `body`    | Yes      | string  | Email body text                 |
| `cc`      | No       | string  | CC recipients (comma-separated) |
| `html`    | No       | boolean | Send body as HTML               |

### post_linkedin
| Parameter  | Required | Type    | Description                      |
|------------|----------|---------|----------------------------------|
| `content`  | Yes      | string  | Post text (max 3000 chars)       |
| `headless` | No       | boolean | Run browser in headless mode     |
| `dry_run`  | No       | boolean | Compose without publishing       |

### send_whatsapp
| Parameter  | Required | Type    | Description                              |
|------------|----------|---------|------------------------------------------|
| `phone`    | Yes      | string  | Phone number with country code           |
| `message`  | Yes      | string  | Message text                             |
| `headless` | No       | boolean | Run browser in headless mode             |
| `dry_run`  | No       | boolean | Compose without sending                  |

### manage_vault
| Parameter | Required | Type   | Description                                |
|-----------|----------|--------|--------------------------------------------|
| `command` | Yes      | string | list, move, archive, search, status        |
| `stage`   | No       | string | Vault stage (for list): inbox, needs_action, done |
| `file`    | No       | string | Filename (for move/archive)                |
| `to`      | No       | string | Target stage (for move)                    |
| `query`   | No       | string | Search keyword (for search)                |

### check_gmail / check_whatsapp
No required parameters. Runs a single poll (`--once` mode).

## Workflow

1. Client connects via stdio transport.
2. Client calls `list_tools` to discover available tools.
3. Client calls a tool with JSON arguments.
4. MCP server maps the tool call to the correct Python script.
5. Script runs as a subprocess with a 120-second timeout.
6. Output is returned as text content.
