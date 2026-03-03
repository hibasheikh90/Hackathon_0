# Personal AI Employee — Autonomous AI Workforce System

> A modular, event-driven AI automation framework that manages tasks, emails, social media, accounting, and executive reporting — autonomously.

Built as a three-tier system (**Bronze → Silver → Gold**), this project transforms Claude into a fully autonomous digital employee capable of triaging work, executing multi-step plans, syncing with enterprise tools, and delivering weekly CEO briefings — all without human intervention.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Bronze Tier — Foundation](#bronze-tier--foundation)
- [Silver Tier — Communication](#silver-tier--communication)
- [Gold Tier — Enterprise Autonomy](#gold-tier--enterprise-autonomy)
- [Folder Structure](#folder-structure)
- [Getting Started](#getting-started)
- [Demo Workflow](#demo-workflow)
- [Tech Stack](#tech-stack)
- [Hackathon Completion Summary](#hackathon-completion-summary)

---

## Project Overview

**Personal AI Employee** is an autonomous workforce system that operates through a file-based vault (Obsidian-style markdown files) and an event-driven architecture. Tasks flow through a structured pipeline:

```
Inbox/  →  Needs_Action/  →  Done/
 (new)     (processing)     (archived)
```

The system watches for new tasks, triages them using a rule-based decision engine, generates execution plans, processes work autonomously, and archives completed items — all while logging every action for auditability.

### Key Capabilities

- **Task Automation** — Inbox monitoring, intelligent triage, plan generation, autonomous execution
- **Email Integration** — Gmail watching and sending via IMAP/SMTP
- **Social Media Management** — Multi-platform posting with rate limiting and scheduling (LinkedIn, Twitter/X, Instagram, Facebook)
- **ERP Accounting** — Odoo integration for invoices, expenses, P&L reports, and AR aging
- **Executive Reporting** — Automated weekly CEO briefings with financial, task, and social metrics
- **Error Recovery** — Centralized logging, retry queues, and alert escalation
- **Claude Integration** — MCP (Model Context Protocol) servers expose all capabilities as AI-callable tools

---

## Architecture

### System Overview

```
                    ┌─────────────────────────┐
                    │    Claude / Claude Code  │
                    │       (MCP Client)       │
                    └────────────┬────────────┘
                                 │
                            MCP Protocol
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
   ┌──────▼──────┐       ┌──────▼──────┐       ┌───────▼──────┐
   │    Vault    │       │ Accounting  │       │    Social    │
   │   Server    │       │   Server    │       │   Server     │
   └──────┬──────┘       └──────┬──────┘       └───────┬──────┘
          │                     │                      │
          └─────────────────────┼──────────────────────┘
                                │
                     ┌──────────▼──────────┐
                     │     EVENT BUS       │
                     │  (Pub/Sub Engine)   │
                     └──────────┬──────────┘
                                │
         ┌──────────┬───────────┼───────────┬──────────┐
         │          │           │           │          │
   ┌─────▼──┐ ┌────▼───┐ ┌────▼───┐ ┌─────▼──┐ ┌────▼─────┐
   │ Vault  │ │  Odoo  │ │ Social │ │ Email  │ │ Briefing │
   │Watcher │ │  Sync  │ │ Queue  │ │ Watch  │ │Generator │
   └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘
         │          │           │           │          │
         └──────────┴───────────┴───────────┴──────────┘
                                │
                  ┌─────────────▼─────────────┐
                  │    MASTER SCHEDULER       │
                  │                           │
                  │  Every 5 min  → Vault,    │
                  │                Social,    │
                  │                Odoo       │
                  │  Every 1 hr  → Log rotate │
                  │  18:00 daily → Report     │
                  │  Mon 08:00   → CEO brief  │
                  └───────────────────────────┘
```

### Event Bus — The Nervous System

All modules communicate through a synchronous pub/sub event bus (`core/event_bus.py`), enabling loose coupling and extensibility:

```
vault.task.new  →  vault.task.triaged  →  vault.task.completed
email.received  →  email.sent / email.send_failed
social.draft.created  →  social.post.ready  →  social.post.success
odoo.invoice.created  →  odoo.invoice.overdue
error.logged  →  error.alert_triggered
```

Handler exceptions are caught and logged — they never crash the bus.

### Vault Workflow

The vault is a file-based task management system using markdown files:

1. **Watcher** monitors `vault/Inbox/` for new `.md` files
2. **Triager** applies a 6-rule decision table to classify each task
3. **Planner** generates step-by-step execution plans
4. **Ralph** (autonomous loop) processes tasks in `vault/Needs_Action/`
5. **Archiver** moves completed work to `vault/Done/` with metadata

---

## Bronze Tier — Foundation

The Bronze tier establishes the core task management pipeline.

### Watcher (`watcher.py`)

Monitors the `vault/Inbox/` directory for new markdown files and applies intelligent triage.

**6-Rule Triage Decision Table:**

| Rule | Condition | Destination |
|------|-----------|-------------|
| 1 | Contains "DONE" or "COMPLETED" | `Done/` |
| 2 | Contains a question mark `?` | `Needs_Action/` |
| 3 | Contains action verbs (send, create, update, etc.) | `Needs_Action/` |
| 4 | Has unchecked checkboxes `- [ ]` | `Needs_Action/` |
| 5 | All checkboxes are checked `- [x]` | `Done/` |
| 6 | Default fallback | `Needs_Action/` |

### Vault Structure

```
vault/
├── Dashboard.md        # Live system status overview
├── Company_Handbook.md # Reference documentation
├── Inbox/              # Drop zone for new tasks
├── Needs_Action/       # Tasks queued for processing
└── Done/               # Completed work archive
```

### Planner (`planner.py`)

Reads triaged tasks and generates structured execution plans with metadata:

```markdown
# Task Title

## Metadata
- Source: Inbox/filename.md
- Received: 2026-02-17 10:30:00
- Routed to: Needs_Action/
- Triage rule: #3
- Status: Needs Action

## Agent Notes
Triage complete. Task queued for execution.
```

---

## Silver Tier — Communication

The Silver tier adds external communication channels and scheduling.

### Gmail Integration (`integrations/gmail/`)

- **Watcher** — IMAP-based inbox monitoring for incoming emails
- **Sender** — SMTP email dispatch with retry logic
- Events: `email.received`, `email.sent`, `email.send_failed`

### Social Media Automation (`integrations/social/`)

Multi-platform posting engine with per-platform strategies:

| Platform | Method | Rate Limit | Optimal Hours |
|----------|--------|------------|---------------|
| LinkedIn | Playwright | 1/day | 9, 12, 17 |
| Twitter/X | API v2 (OAuth 1.0a) | 5/day | 8, 12, 15, 18, 21 |
| Instagram | Playwright | 2/day | 11, 19 |
| Facebook | Playwright | 3/day | 9, 12, 18 |

**Content Queue Lifecycle:**

```
Draft  →  Approved  →  Scheduled  →  Posted
```

Content is managed as markdown files with YAML frontmatter:

```markdown
---
platforms: linkedin, twitter
scheduled_time: 2026-02-17 09:00
status: approved
---
Your post content goes here. #hashtag
```

### Planner & Scheduler

- **Planner** generates multi-step plans for complex tasks
- **Scheduler** (`scripts/run_ai_employee.py`) orchestrates periodic execution via cron or Task Scheduler

---

## Gold Tier — Enterprise Autonomy

The Gold tier adds enterprise integrations, executive reporting, and fully autonomous operation.

### Odoo ERP Integration (`integrations/odoo/`)

Full accounting integration via XML-RPC / JSON-RPC:

- **Invoices** — Create, search, mark paid, list overdue
- **Expenses** — Log and categorize expenses
- **Reports** — Profit & loss, cash position, AR aging
- **Sync** — Bidirectional vault ↔ Odoo synchronization

### CEO Briefing (`briefings/weekly_ceo.py`)

Automated weekly executive summary generated every Monday at 08:00:

```markdown
# Weekly CEO Briefing — Week 07, 2026

## Executive Summary
AI Employee processed 7 tasks this week. 4 items require decision.

## Financial Snapshot
| Metric       | This Week | Last Week | Change |
|--------------|-----------|-----------|--------|
| Revenue      | $12,400   | $11,800   | +5.1%  |
| AR Overdue   | $3,200    | $4,100    | -22.0% |

## Task Pipeline
| Metric     | Value |
|------------|-------|
| New tasks  | 15    |
| Completed  | 7     |
| Backlog    | 13    |

## Action Items Requiring Your Decision
1. [HIGH] Invoice #4821 — Payment 30 days overdue
2. [MEDIUM] LinkedIn content approval pending
```

**Data Collectors:**
- `vault_stats.py` — Task volume, completion rate, SLA metrics
- `financial_summary.py` — Revenue, expenses, cash position (from Odoo)
- `social_metrics.py` — Posts published, impressions, engagement
- `email_digest.py` — Email volume, key threads, response times

### Ralph — Autonomous Loop (`core/ralph.py`)

The autonomous execution engine that continuously processes tasks:

1. Scans `Needs_Action/` for incomplete tasks
2. Classifies each task (plan, email, social, general)
3. Extracts step-by-step objectives
4. Detects completion (all checkboxes checked or no work remaining)
5. Moves completed tasks → `Done/`
6. Updates `Dashboard.md` with live status
7. Repeats until queue is empty or max cycles reached

### Error Recovery (`core/retry.py`, `core/recovery.py`)

- **Retry decorator** with exponential backoff
- **Failed task queue** persisted to `logs/failed_tasks.json`
- **Alert escalation** — 3+ errors from the same source within 1 hour triggers `error.alert_triggered`
- **Log rotation** — Size-based (50 MB default) with archival

### MCP Servers (`mcp_servers/`)

All Gold tier capabilities are exposed to Claude via the Model Context Protocol:

| Server | Tools Exposed |
|--------|---------------|
| `vault_server.py` | `vault_status`, `list_tasks`, `read_task`, `move_task`, `search_vault` |
| `accounting_server.py` | `get_unpaid_invoices`, `create_invoice`, `get_profit_loss`, `get_ar_aging` |
| `email_server.py` | `send_email`, `read_inbox`, `search_emails` |
| `social_server.py` | `create_draft`, `schedule_post`, `get_metrics` |
| `briefing_server.py` | `generate_briefing`, `get_latest_briefing` |

---

## Folder Structure

```
Bronze/
├── run_gold.py                    # Main entry point (Gold tier)
├── watcher.py                     # Inbox watcher (Bronze tier)
├── planner.py                     # Plan generator (Bronze tier)
├── .env                           # Credentials (not committed)
├── .mcp.json                      # MCP server configuration
│
├── core/                          # Gold tier core modules
│   ├── event_bus.py               # Pub/sub event system
│   ├── error_logger.py            # Centralized JSON logging
│   ├── config_loader.py           # YAML config + .env loader
│   ├── scheduler.py               # Master task scheduler
│   ├── ralph.py                   # Autonomous execution loop
│   ├── retry.py                   # Retry decorator + failed queue
│   ├── recovery.py                # Recovery manager
│   └── validator.py               # Configuration validator
│
├── config/                        # YAML configuration
│   ├── gold.yaml                  # Scheduler timings, thresholds
│   ├── social_accounts.yaml       # Platform rate limits, hours
│   └── odoo_connection.yaml       # Odoo ERP connection settings
│
├── integrations/                  # External service integrations
│   ├── odoo/                      # Odoo ERP (invoices, expenses, reports)
│   ├── social/                    # Social media (LinkedIn, Twitter, IG, FB)
│   └── gmail/                     # Email (IMAP watcher, SMTP sender)
│
├── mcp_servers/                   # MCP servers for Claude integration
│   ├── vault_server.py            # Task management tools
│   ├── accounting_server.py       # Financial query tools
│   ├── email_server.py            # Email tools
│   ├── social_server.py           # Social media tools
│   └── briefing_server.py         # Briefing generation tools
│
├── briefings/                     # Executive reporting
│   ├── weekly_ceo.py              # Weekly briefing orchestrator
│   ├── daily_error_summary.py     # Daily error report
│   └── data_collectors/           # Metric collection modules
│
├── skills/                        # Claude Agent Skills (all AI functionality)
│   ├── file-triage/               # Inbox triage decision engine
│   ├── reasoning-planner/         # Task planning and prioritization
│   ├── task-planner/              # Plan file generation
│   ├── gmail-watcher/             # Gmail IMAP polling
│   ├── whatsapp-watcher/          # WhatsApp Web automation
│   ├── approval-gate/             # Human-in-the-loop approval workflow
│   ├── mcp-server/                # MCP server management
│   ├── odoo-accounting/           # Odoo ERP: invoices, expenses, reports
│   ├── twitter-post/              # X/Twitter API v2 posting
│   ├── instagram-post/            # Instagram Playwright automation
│   ├── facebook-post/             # Facebook Playwright automation
│   ├── ralph-loop/                # Autonomous execution engine
│   └── ceo-briefing/              # Weekly + daily executive reports
│
├── vault/                         # Task vault (Obsidian-style)
│   ├── Dashboard.md               # System status
│   ├── Company_Handbook.md        # Reference docs
│   ├── Inbox/                     # New tasks land here
│   ├── Needs_Action/              # Tasks being processed
│   ├── Pending_Approval/          # Awaiting human approval (HITL)
│   ├── Approved/                  # Human-approved actions ready to execute
│   ├── Rejected/                  # Human-rejected actions (archived)
│   └── Done/                      # Completed work archive
│
├── logs/                          # Logging & audit trail
│   ├── error.log                  # JSON Lines error records
│   ├── audit.log                  # Action audit trail
│   └── archive/                   # Rotated log files
│
├── scripts/                       # Setup & scheduling scripts
│   ├── run_ai_employee.py         # Silver tier scheduler
│   └── setup_task_scheduler.bat   # Windows Task Scheduler setup
│
└── tests/                         # Test suite
    └── test_gold.py               # End-to-end tests
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/ai-employee.git
cd ai-employee

# Install dependencies
pip install watchdog requests playwright pyyaml jinja2 requests-oauthlib

# Install Playwright browsers (for social media automation)
playwright install chromium

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

1. **`.env`** — Add your credentials (Gmail, LinkedIn, Odoo, Twitter, etc.)
2. **`config/gold.yaml`** — Adjust scheduler timings and alert thresholds
3. **`config/social_accounts.yaml`** — Configure platform rate limits
4. **`config/odoo_connection.yaml`** — Set Odoo ERP connection details

### Run Commands

```bash
# Validate configuration
python run_gold.py --validate

# Single pass — process inbox once and exit
python run_gold.py --once

# Daemon mode — continuous processing (every 5 minutes)
python run_gold.py --daemon

# Daemon mode with custom interval (every 10 minutes)
python run_gold.py --daemon -i 10

# Run Ralph autonomous loop
python run_gold.py --ralph
python run_gold.py --ralph --cycles 20

# Generate CEO briefing on demand
python run_gold.py --briefing

# Run tests
python run_gold.py --test
```

### Bronze Tier Only

```bash
# Watch inbox and triage tasks
python watcher.py

# Generate plans for triaged tasks
python planner.py
```

### Scheduled Execution

**Windows (Task Scheduler):**
```bash
# Run as Administrator
scripts\setup_task_scheduler.bat
```

**Linux/macOS (Cron):**
```bash
crontab -e
# Add: */5 * * * * cd /path/to/Bronze && python3 run_gold.py --once >> logs/scheduler.log 2>&1
```

---

## Demo Workflow

Here's a complete walkthrough of a task moving through the system:

### 1. Drop a Task into the Inbox

Create a file `vault/Inbox/send_invoice.md`:

```markdown
# Send Invoice to Acme Corp

- [ ] Create invoice for $5,000 (consulting services)
- [ ] Email invoice to billing@acme.com
- [ ] Log expense in Odoo
- [ ] Post update on LinkedIn
```

### 2. Watcher Triages the Task

The watcher detects the new file, applies **Rule #4** (unchecked checkboxes), and moves it:

```
vault/Inbox/send_invoice.md  →  vault/Needs_Action/send_invoice.md
```

Metadata is appended:

```markdown
## Metadata
- Source: Inbox/send_invoice.md
- Received: 2026-02-17 10:30:00
- Triage rule: #4 (unchecked checkboxes)
- Status: Needs Action
```

### 3. Ralph Processes the Task

The autonomous loop picks up the task and executes each step:

- Creates invoice in Odoo → `odoo.invoice.created` event
- Sends email via Gmail → `email.sent` event
- Logs expense → `odoo.expense.logged` event
- Posts to LinkedIn → `social.post.success` event

Each checkbox is marked as complete:

```markdown
- [x] Create invoice for $5,000 (consulting services)
- [x] Email invoice to billing@acme.com
- [x] Log expense in Odoo
- [x] Post update on LinkedIn
```

### 4. Task Moves to Done

Ralph detects all checkboxes are complete (**Rule #5**) and archives the task:

```
vault/Needs_Action/send_invoice.md  →  vault/Done/send_invoice.md
```

### 5. CEO Briefing Captures the Work

The next weekly briefing includes:

```markdown
## Task Pipeline
| Metric    | Value |
|-----------|-------|
| Completed | 1     |

## Financial Snapshot
| Metric  | This Week |
|---------|-----------|
| Revenue | +$5,000   |
```

---

## Tech Stack

| Category | Technology |
|----------|------------|
| **Language** | Python 3.11+ |
| **Task Management** | File-based vault (Obsidian-style markdown) |
| **Event System** | Custom synchronous pub/sub event bus |
| **File Watching** | `watchdog` |
| **Email** | IMAP (watching) / SMTP (sending) |
| **Social Media** | Twitter API v2, Playwright (LinkedIn, Instagram, Facebook) |
| **ERP** | Odoo via XML-RPC / JSON-RPC |
| **Templating** | Jinja2 (CEO briefings) |
| **Configuration** | YAML + `.env` |
| **Logging** | JSON Lines (RFC 7464) with rotation |
| **AI Integration** | Claude via MCP (Model Context Protocol) |
| **Testing** | unittest |
| **Scheduling** | Windows Task Scheduler / cron |

---

## Hackathon Completion Summary

### Bronze Tier — Task Foundation

| Feature | Status |
|---------|--------|
| Vault file structure (Inbox, Needs_Action, Done) | Done |
| Inbox watcher with file system monitoring | Done |
| 6-rule triage decision table | Done |
| Plan generator with metadata | Done |
| Dashboard.md live status | Done |

### Silver Tier — Communication Layer

| Feature | Status |
|---------|--------|
| Gmail watcher (IMAP) | Done |
| Gmail sender (SMTP) | Done |
| LinkedIn automation (Playwright) | Done |
| Twitter/X posting (API v2) | Done |
| Instagram automation (Playwright) | Done |
| Facebook automation (Playwright) | Done |
| Social content queue with scheduling | Done |
| Per-platform rate limiting | Done |
| Silver scheduler (`run_ai_employee.py`) | Done |

### Gold Tier — Enterprise Autonomy

| Feature | Status |
|---------|--------|
| Event bus (pub/sub) | Done |
| Centralized error logger (JSON Lines) | Done |
| YAML configuration system | Done |
| Odoo ERP integration (invoices, expenses, reports) | Done |
| Bidirectional vault ↔ Odoo sync | Done |
| Weekly CEO briefing with Jinja2 templates | Done |
| Daily error summary reports | Done |
| Ralph autonomous execution loop | Done |
| Retry decorator + failed task queue | Done |
| Recovery manager with alert escalation | Done |
| Master scheduler (5-min, hourly, daily, weekly jobs) | Done |
| MCP servers (vault, accounting, email, social, briefing) | Done |
| Configuration validator | Done |
| End-to-end test suite | Done |
| HITL vault folders (Pending_Approval, Approved, Rejected) | Done |
| Agent Skills — Odoo accounting | Done |
| Agent Skills — Twitter/X post | Done |
| Agent Skills — Instagram post | Done |
| Agent Skills — Facebook post | Done |
| Agent Skills — Ralph autonomous loop | Done |
| Agent Skills — CEO briefing | Done |

---


