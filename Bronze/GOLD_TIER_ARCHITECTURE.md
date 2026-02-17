# Gold Tier Architecture — Personal AI Employee

## Tier Progression

```
Bronze (Done)          Silver (Done)              Gold (This Document)
─────────────         ─────────────              ─────────────────────
Inbox watcher          Gmail send skill           Odoo accounting integration
File triage            LinkedIn automation         Multi-social media (X, IG, LinkedIn)
Plan generator         Daily report               Weekly CEO briefing
Vault pipeline         Vault file manager          Multiple MCP servers
                       Scheduler (once/daemon)     Centralized error logging
                                                   Event bus architecture
```

---

## Folder Structure

```
Bronze/
├── .env                              # All credentials (Odoo, SMTP, socials, MCP keys)
├── config/
│   ├── gold.yaml                     # Master config — feature flags, schedules, thresholds
│   ├── social_accounts.yaml          # Platform credentials & posting rules
│   └── odoo_connection.yaml          # Odoo host, DB, API key
│
├── core/
│   ├── __init__.py
│   ├── event_bus.py                  # Pub/sub event system connecting all modules
│   ├── error_logger.py              # Centralized error capture, rotation, alerts
│   ├── scheduler.py                  # Gold scheduler — replaces scripts/run_ai_employee.py
│   └── config_loader.py             # Loads YAML configs, validates, merges with .env
│
├── integrations/
│   ├── __init__.py
│   ├── odoo/
│   │   ├── __init__.py
│   │   ├── client.py                # XML-RPC / JSON-RPC client for Odoo
│   │   ├── invoices.py              # Create, read, track invoices
│   │   ├── expenses.py              # Log and categorize expenses
│   │   ├── reports.py               # Pull P&L, balance sheet, cash flow
│   │   └── sync.py                  # Bidirectional vault <-> Odoo sync
│   │
│   ├── social/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract base class for all social platforms
│   │   ├── linkedin.py              # Upgraded from Silver skill (Playwright)
│   │   ├── twitter.py               # X/Twitter posting via API v2
│   │   ├── instagram.py             # Instagram posting via unofficial API / Playwright
│   │   ├── scheduler.py             # Cross-platform posting calendar
│   │   └── content_queue.py         # Queue with drafts, approvals, scheduled times
│   │
│   └── gmail/
│       ├── __init__.py
│       ├── sender.py                # Upgraded from Silver skill
│       └── watcher.py               # IMAP listener for incoming mail (new)
│
├── mcp_servers/
│   ├── __init__.py
│   ├── vault_server.py              # MCP server: vault file operations
│   ├── email_server.py              # MCP server: send/read email
│   ├── accounting_server.py         # MCP server: Odoo queries & actions
│   ├── social_server.py             # MCP server: post/schedule to any platform
│   └── briefing_server.py           # MCP server: generate/fetch briefings
│
├── briefings/
│   ├── __init__.py
│   ├── weekly_ceo.py                # Weekly CEO briefing generator
│   ├── data_collectors/
│   │   ├── __init__.py
│   │   ├── vault_stats.py           # Task throughput, SLA, backlog trends
│   │   ├── financial_summary.py     # Pulls from Odoo: revenue, expenses, cash
│   │   ├── social_metrics.py        # Engagement stats from all platforms
│   │   └── email_digest.py          # Key email threads, response rates
│   └── templates/
│       └── ceo_briefing.md.j2       # Jinja2 template for the weekly briefing
│
├── logs/
│   ├── error.log                    # Structured error log (JSON lines)
│   ├── audit.log                    # All actions taken by the system
│   └── archive/                     # Rotated logs (weekly rotation)
│
├── scripts/                          # (Silver — kept for backwards compat)
│   ├── run_ai_employee.py
│   ├── setup_task_scheduler.bat
│   └── SCHEDULER.md
│
├── AI_Employee_Vault/                # (Silver — untouched, still works)
│   ├── .claude/skills/...
│   └── vault/
│       ├── Inbox/
│       ├── Needs_Action/
│       └── Done/
│
├── vault/                            # (Bronze — untouched)
│   ├── Inbox/
│   ├── Needs_Action/
│   ├── Done/
│   ├── Dashboard.md
│   └── Company_Handbook.md
│
├── watcher.py                        # (Bronze — still works)
├── planner.py                        # (Bronze — still works)
└── skills/                           # (Bronze skills — still work)
```

---

## System Flow

```
                         ┌──────────────────────────────────┐
                         │         EVENT BUS (core)          │
                         │   pub/sub backbone for all modules│
                         └──┬───┬───┬───┬───┬───┬───┬───┬──┘
                            │   │   │   │   │   │   │   │
          ┌─────────────────┘   │   │   │   │   │   │   └──────────────────┐
          │                     │   │   │   │   │   │                      │
          ▼                     ▼   │   ▼   │   ▼   │                      ▼
    ┌───────────┐     ┌──────────┐ │ ┌────────┐ │ ┌──────────┐    ┌──────────────┐
    │  GMAIL    │     │  SOCIAL  │ │ │  ODOO  │ │ │  VAULT   │    │   ERROR      │
    │ Watcher   │     │  Multi-  │ │ │Accounting│ │ │ Pipeline │    │  LOGGER      │
    │ (IMAP)    │     │ Platform │ │ │ Sync   │ │ │ (triage  │    │  (all errors │
    │           │     │ Poster   │ │ │        │ │ │  + plan)  │    │   flow here) │
    └─────┬─────┘     └────┬─────┘ │ └───┬────┘ │ └────┬─────┘    └──────┬───────┘
          │                │       │     │      │      │                  │
          │ new email      │ post  │     │query │      │ task             │ log
          │ arrived        │ made  │     │      │      │ triaged          │ rotate
          ▼                ▼       │     ▼      │      ▼                  ▼
    ┌──────────┐   ┌──────────┐   │  ┌──────┐  │  ┌──────────┐    ┌──────────┐
    │vault/    │   │content   │   │  │Odoo  │  │  │Needs_    │    │logs/     │
    │Inbox/    │   │queue     │   │  │ERP   │  │  │Action/   │    │error.log │
    └──────────┘   └──────────┘   │  └──────┘  │  └──────────┘    │audit.log │
                                  │            │                   └──────────┘
                                  │            │
                         ┌────────┘            └────────┐
                         ▼                              ▼
                   ┌───────────┐                 ┌─────────────┐
                   │  WEEKLY   │                 │ MCP SERVERS │
                   │  CEO      │◄────collects────│ (5 servers) │
                   │ BRIEFING  │    data from    │             │
                   │           │    all modules  │ vault_server│
                   └─────┬─────┘                 │ email_server│
                         │                       │ acct_server │
                         ▼                       │social_server│
                   ┌───────────┐                 │brief_server │
                   │vault/Done/│                 └─────────────┘
                   │WeeklyBrief│                        ▲
                   │_YYYYWW.md │                        │
                   └───────────┘                  Claude / LLM
                                                  connects via
                                                  MCP protocol
```

---

## Component Details

### 1. Odoo Accounting Integration (`integrations/odoo/`)

**Purpose:** Connect your AI Employee to Odoo ERP for financial visibility and automation.

```
Event Bus ←──── odoo.sync ────→ Odoo Server (XML-RPC)
                   │
         ┌─────────┼──────────┐
         ▼         ▼          ▼
    invoices.py  expenses.py  reports.py
```

**`client.py`** — Low-level Odoo connection:
- XML-RPC authentication via `xmlrpc.client`
- Connection pooling and retry logic
- Methods: `authenticate()`, `search_read()`, `create()`, `write()`
- Config loaded from `config/odoo_connection.yaml` + `.env`

**`invoices.py`** — Invoice operations:
- `list_unpaid()` → returns overdue invoices for briefing
- `create_invoice(partner, lines)` → creates draft invoice in Odoo
- `mark_paid(invoice_id)` → reconciles payment
- Emits event: `odoo.invoice.overdue` when unpaid > 30 days

**`expenses.py`** — Expense tracking:
- `log_expense(amount, category, description)` → creates expense record
- `get_weekly_expenses()` → aggregated for CEO briefing

**`reports.py`** — Financial reports:
- `get_profit_loss(date_from, date_to)` → P&L summary
- `get_cash_position()` → current bank balance
- `get_ar_aging()` → accounts receivable aging

**`sync.py`** — Vault-Odoo bidirectional sync:
- Watches `vault/Needs_Action/` for files tagged `#accounting`
- Pushes relevant data to Odoo (e.g., new invoice request)
- Pulls Odoo alerts into `vault/Inbox/` (e.g., overdue invoice notifications)

### 2. Multi-Social Media Automation (`integrations/social/`)

**Purpose:** Expand from LinkedIn-only to cross-platform posting with a content queue.

```
content_queue.py
    │
    ├── Drafts ready? ──→ scheduler.py (checks posting calendar)
    │                          │
    │                    ┌─────┼──────┐
    │                    ▼     ▼      ▼
    │              linkedin  twitter  instagram
    │                .py      .py      .py
    │
    └── All implement base.py (abstract interface)
```

**`base.py`** — Abstract interface every platform implements:
```python
class SocialPlatform(ABC):
    @abstractmethod
    def authenticate(self) -> bool: ...

    @abstractmethod
    def post(self, content: str, media: list[Path] | None) -> PostResult: ...

    @abstractmethod
    def get_metrics(self, post_id: str) -> dict: ...
```

**`content_queue.py`** — Draft management:
- Reads drafts from `vault/Needs_Action/social_*.md`
- Schema: each file has frontmatter with `platforms`, `scheduled_time`, `status`
- States: `draft` → `approved` → `scheduled` → `posted` → `archived`
- Emits event: `social.post.ready` when approved content hits its scheduled time

**`scheduler.py`** — Cross-platform calendar:
- Enforces per-platform rate limits (LinkedIn: 1/day, X: 5/day, IG: 2/day)
- Distributes posts across optimal time windows
- Calls the correct platform `.post()` method

**`twitter.py`** — X/Twitter via API v2:
- OAuth 2.0 Bearer token auth
- `post(content)` → creates tweet
- `get_metrics(tweet_id)` → impressions, likes, retweets

**`instagram.py`** — Instagram via Playwright:
- Same pattern as LinkedIn skill (browser automation)
- Supports image + caption posting
- `post(content, media)` → publishes to feed

### 3. Weekly CEO Briefing (`briefings/`)

**Purpose:** Auto-generate a structured executive summary every Monday.

```
weekly_ceo.py (orchestrator)
    │
    ├── vault_stats.py ──────→ Task throughput, backlog, SLA compliance
    ├── financial_summary.py ─→ Calls integrations/odoo/reports.py
    ├── social_metrics.py ────→ Calls integrations/social/*.get_metrics()
    └── email_digest.py ──────→ Key threads, response time averages
          │
          ▼
    templates/ceo_briefing.md.j2 ──→ Rendered to vault/Done/WeeklyBrief_2026W07.md
```

**Output format** (rendered from Jinja2 template):
```markdown
# Weekly CEO Briefing — Week 07, 2026

## Executive Summary
AI Employee processed 34 tasks this week. Revenue up 12%.
3 items require your decision.

## Financial Snapshot
| Metric              | This Week | Last Week | Change |
|---------------------|-----------|-----------|--------|
| Revenue             | $12,400   | $11,071   | +12%   |
| Expenses            | $3,200    | $2,980    | +7%    |
| Outstanding AR      | $8,500    | $9,100    | -7%    |
| Cash Position       | $45,200   | $41,000   | +10%   |

## Task Pipeline
- New tasks received: 12
- Tasks completed: 9
- Backlog (Needs Action): 7
- Avg time to completion: 1.4 days

## Social Media Performance
| Platform  | Posts | Impressions | Engagement |
|-----------|-------|-------------|------------|
| LinkedIn  | 3     | 2,400       | 4.2%       |
| X/Twitter | 8     | 5,100       | 2.1%       |
| Instagram | 2     | 1,800       | 6.7%       |

## Email Activity
- Sent: 18 | Received: 42 | Avg response: 2.3 hrs
- Key thread: "Q1 Contract Renewal" — awaiting client reply

## Action Items Requiring Your Decision
1. [HIGH] Invoice #4821 — $2,400 overdue 45 days → Approve escalation?
2. [MEDIUM] New vendor onboarding — Approve budget $500/mo?
3. [MEDIUM] Social campaign Q2 — Approve content calendar?

---
Generated 2026-02-16 08:00 by AI Employee (Gold Tier)
```

**Scheduling:** Triggered by `core/scheduler.py` every Monday at 08:00.

### 4. Multiple MCP Servers (`mcp_servers/`)

**Purpose:** Expose every Gold Tier capability to Claude via the Model Context Protocol.

```
Claude Code / Claude Desktop
    │
    │  MCP (stdio / SSE)
    │
    ├── vault_server.py ─────── Tools: list_tasks, move_task, search_vault, get_dashboard
    ├── email_server.py ─────── Tools: send_email, search_inbox, get_thread
    ├── accounting_server.py ── Tools: get_invoices, create_invoice, get_pnl, get_cash
    ├── social_server.py ────── Tools: create_draft, schedule_post, get_metrics
    └── briefing_server.py ──── Tools: generate_briefing, get_last_briefing
```

**Each server** follows this pattern:
```python
# Example: accounting_server.py
from mcp.server import Server
from integrations.odoo import invoices, reports

server = Server("accounting")

@server.tool("get_unpaid_invoices")
async def get_unpaid():
    """List all unpaid invoices from Odoo."""
    return invoices.list_unpaid()

@server.tool("get_profit_loss")
async def get_pnl(date_from: str, date_to: str):
    """Get P&L report for a date range."""
    return reports.get_profit_loss(date_from, date_to)

@server.tool("get_cash_position")
async def get_cash():
    """Get current bank balance and cash position."""
    return reports.get_cash_position()
```

**MCP config** (`claude_desktop_config.json` or `.mcp.json`):
```json
{
  "mcpServers": {
    "vault":      { "command": "python", "args": ["mcp_servers/vault_server.py"] },
    "email":      { "command": "python", "args": ["mcp_servers/email_server.py"] },
    "accounting": { "command": "python", "args": ["mcp_servers/accounting_server.py"] },
    "social":     { "command": "python", "args": ["mcp_servers/social_server.py"] },
    "briefing":   { "command": "python", "args": ["mcp_servers/briefing_server.py"] }
  }
}
```

### 5. Error Logging System (`core/error_logger.py`)

**Purpose:** Every module logs errors to one place. No silent failures.

```
Any module
    │
    │  error_logger.log_error(source, error, context)
    ▼
┌──────────────────────────────────────────┐
│            error_logger.py               │
│                                          │
│  ┌─ logs/error.log (JSON Lines) ──────┐  │
│  │ {"ts":"...","source":"odoo",       │  │
│  │  "error":"ConnectionTimeout",      │  │
│  │  "context":{"host":"..."},         │  │
│  │  "severity":"ERROR",               │  │
│  │  "retry_count": 2}                 │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ logs/audit.log ──────────────────┐   │
│  │ Every successful action logged    │   │
│  │ (who, what, when, result)         │   │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ Alert escalation ───────────────┐    │
│  │ 3+ errors from same source in    │    │
│  │ 1 hour → email alert to CEO      │    │
│  │ via integrations/gmail/sender.py  │    │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ Weekly rotation ────────────────┐    │
│  │ Rotate to logs/archive/ every    │    │
│  │ Sunday at midnight               │    │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Error log format** (JSON Lines — one object per line):
```json
{"ts": "2026-02-16T10:30:00", "severity": "ERROR", "source": "odoo.invoices", "error": "ConnectionTimeout", "message": "Failed to connect to Odoo server after 3 retries", "context": {"host": "odoo.example.com", "timeout": 30}, "retry_count": 3, "resolved": false}
```

**Audit log format:**
```json
{"ts": "2026-02-16T10:30:00", "action": "social.post", "platform": "linkedin", "status": "success", "details": {"content_length": 142, "post_id": "urn:li:share:123"}}
```

---

## Event Bus Design (`core/event_bus.py`)

The event bus is the nervous system connecting all Gold Tier modules.

```python
# Events emitted by each module:

# Gmail
"email.received"          # New email landed in inbox
"email.sent"              # Email sent successfully
"email.send_failed"       # Email send failed

# Social
"social.draft.created"    # New draft added to queue
"social.post.ready"       # Approved content hit scheduled time
"social.post.success"     # Post published
"social.post.failed"      # Post failed

# Odoo
"odoo.invoice.created"    # New invoice created
"odoo.invoice.overdue"    # Invoice past due date
"odoo.sync.complete"      # Vault-Odoo sync finished
"odoo.connection.failed"  # Cannot reach Odoo

# Vault
"vault.task.new"          # New file in Inbox
"vault.task.triaged"      # File moved to Needs_Action
"vault.task.completed"    # File moved to Done

# Briefing
"briefing.generated"      # Weekly briefing created
"briefing.failed"         # Briefing generation failed

# System
"error.logged"            # Error captured by logger
"error.alert_triggered"   # Error threshold exceeded → email alert
```

**Implementation:** Simple in-process pub/sub (no external dependencies):
```python
class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable):
        self._handlers[event].append(handler)

    def emit(self, event: str, data: dict):
        for handler in self._handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                error_logger.log_error("event_bus", e, {"event": event})
```

---

## Gold Scheduler (`core/scheduler.py`)

Replaces `scripts/run_ai_employee.py` as the master orchestrator.

```
┌─────────────────────────────────────────────────┐
│               Gold Scheduler                     │
│                                                  │
│  Every 5 min:                                    │
│    ├── Scan vault/Inbox/ → triage + plan         │
│    ├── Check content_queue → post if scheduled   │
│    └── Odoo sync → pull alerts, push updates     │
│                                                  │
│  Every 1 hour:                                   │
│    └── Rotate error logs if needed               │
│                                                  │
│  Every Monday 08:00:                             │
│    └── Generate weekly CEO briefing              │
│                                                  │
│  Every day 18:00:                                │
│    └── Generate daily report (Silver, kept)      │
│                                                  │
│  On event "error.alert_triggered":               │
│    └── Send alert email to CEO                   │
└─────────────────────────────────────────────────┘
```

---

## Config Files

**`config/gold.yaml`:**
```yaml
scheduler:
  vault_scan_interval_min: 5
  social_check_interval_min: 5
  odoo_sync_interval_min: 5
  daily_report_time: "18:00"
  weekly_briefing_day: "monday"
  weekly_briefing_time: "08:00"

error_logging:
  max_file_size_mb: 50
  rotation: "weekly"
  alert_threshold: 3          # errors from same source in 1 hour
  alert_email: "ceo@company.com"

briefing:
  include_financials: true
  include_social_metrics: true
  include_email_digest: true
  include_task_stats: true
```

**`config/social_accounts.yaml`:**
```yaml
linkedin:
  method: "playwright"        # browser automation
  rate_limit_per_day: 1
  optimal_hours: [9, 12, 17]

twitter:
  method: "api_v2"            # official API
  rate_limit_per_day: 5
  optimal_hours: [8, 12, 15, 18, 21]

instagram:
  method: "playwright"
  rate_limit_per_day: 2
  optimal_hours: [11, 19]
```

**`config/odoo_connection.yaml`:**
```yaml
host: "https://your-company.odoo.com"
database: "your-company-db"
# API key loaded from .env: ODOO_API_KEY
timeout_seconds: 30
max_retries: 3
```

---

## `.env` Additions for Gold Tier

```bash
# --- Silver (existing) ---
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_PASSWORD=your-app-password
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=your-password

# --- Gold (new) ---
ODOO_URL=https://your-company.odoo.com
ODOO_DB=your-company-db
ODOO_API_KEY=your-odoo-api-key
ODOO_USERNAME=admin

TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...

INSTAGRAM_USERNAME=...
INSTAGRAM_PASSWORD=...

CEO_ALERT_EMAIL=ceo@company.com
```

---

## Build Order (Implementation Phases)

```
Phase 1: Foundation              Phase 2: Integrations       Phase 3: Intelligence
──────────────────               ──────────────────────      ──────────────────────
1. core/event_bus.py             4. integrations/odoo/*      7. briefings/weekly_ceo.py
2. core/error_logger.py          5. integrations/social/*    8. briefings/data_collectors/*
3. core/config_loader.py         6. integrations/gmail/*     9. briefings/templates/*
   core/scheduler.py                (IMAP watcher)

Phase 4: MCP Servers             Phase 5: Polish
──────────────────               ──────────────────
10. mcp_servers/vault_server.py  14. End-to-end testing
11. mcp_servers/email_server.py  15. Config validation
12. mcp_servers/accounting_server 16. Documentation
13. mcp_servers/social_server.py 17. Windows Task Scheduler
    mcp_servers/briefing_server     setup for Gold
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Event bus over direct calls** | Modules stay decoupled. Adding a new integration = subscribe to events, no changes to existing code. |
| **JSON Lines for logs** | Parseable, greppable, appendable. No database dependency. |
| **YAML config over hardcoded values** | Change schedules, thresholds, and accounts without touching code. |
| **One MCP server per domain** | Each server is small, restartable, independently testable. Claude sees clean tool boundaries. |
| **Playwright for IG (same as LinkedIn)** | Reuses the browser automation pattern already proven in Silver. No API approval delays. |
| **Jinja2 for briefing templates** | CEO briefing format can be customized without modifying Python logic. |
| **Silver modules untouched** | `scripts/run_ai_employee.py` still works. Gold wraps and extends, never breaks Silver. |
