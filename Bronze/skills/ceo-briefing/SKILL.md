# Skill: CEO Briefing

## Description

Generates automated executive summary reports combining task pipeline metrics, financial data from Odoo, social media engagement, and email activity. Two report types are supported:

- **Weekly CEO Briefing** — comprehensive Monday morning summary (generated every Monday at 08:00 by the Gold scheduler).
- **Daily Error Summary** — concise daily health report on system errors and alerts (generated at 18:00).

## Prerequisites

1. Gold scheduler running or manual invocation.
2. Odoo connection configured in `config/odoo_connection.yaml` (financial section is skipped gracefully if Odoo is unreachable).
3. Dependencies: `pip install jinja2 pyyaml python-dotenv requests`

## Usage

```bash
# Generate weekly briefing and write to vault/Done/
python -m briefings.weekly_ceo

# Generate and print to stdout (no file written)
python -m briefings.weekly_ceo --stdout

# Generate for a specific week
python -m briefings.weekly_ceo --week 2026-W07

# Generate daily error summary
python -m briefings.daily_error_summary

# Via the Gold entry point (same as scheduler runs)
python run_gold.py --briefing

# MCP tool (called by Claude)
python mcp_servers/briefing_server.py
```

## Inputs

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--stdout` | No | Print to console instead of writing file |
| `--week` | No | ISO week string, e.g. `2026-W07` (default: current week) |

## Output

**Weekly CEO Briefing** written to `vault/Done/WeeklyBrief_YYYYWNN.md`:

```markdown
# Weekly CEO Briefing — Week 07, 2026

## Executive Summary
AI Employee processed 15 tasks this week. 4 items require your decision.

## Financial Snapshot
| Metric     | This Week | Last Week | Change  |
|------------|-----------|-----------|---------|
| Revenue    | $12,400   | $11,800   | +5.1%   |
| AR Overdue | $3,200    | $4,100    | -22.0%  |

## Task Pipeline
| Metric    | Value |
|-----------|-------|
| New tasks | 15    |
| Completed | 11    |
| Stuck     | 0     |
| Backlog   | 4     |

## Social Media Performance
| Platform | Posts | Impressions | Engagements |
|----------|-------|-------------|-------------|
| LinkedIn | 5     | 1,240       | 87          |
| Twitter  | 7     | 3,100       | 210         |

## Action Items Requiring Your Decision
1. [HIGH] Invoice #4821 — Payment 30 days overdue
2. [MEDIUM] LinkedIn post draft awaiting approval
```

**Daily Error Summary** written to `logs/DailyErrorSummary_YYYYMMDD.md`.

## Data Collectors

Each section is populated by a dedicated module in `briefings/data_collectors/`:

| Module | Data Source | Provides |
|--------|-------------|----------|
| `vault_stats.py` | `vault/Needs_Action/`, `vault/Done/` | Task volume, completion rate, backlog, stuck count |
| `financial_summary.py` | Odoo (via `InvoiceManager`, `ReportManager`) | Revenue, expenses, overdue AR, cash position |
| `social_metrics.py` | `integrations/social/` platform APIs | Posts published, impressions, engagement per platform |
| `email_digest.py` | Gmail IMAP + vault email files | Email volume, key threads, avg response time |

Each collector degrades gracefully — if its data source is unreachable, the section is omitted with a note rather than crashing the entire briefing.

## Workflow

1. **Collect** — each data collector runs and returns a dict.
2. **Render** — Jinja2 template is populated with collected data.
3. **Write** — output saved to `vault/Done/WeeklyBrief_YYYYWNN.md`.
4. **Event** — fires `briefing.weekly.generated` with the file path.
5. **Alert** — if `CEO_ALERT_EMAIL` is set in `.env`, the briefing is emailed automatically.

## MCP Integration

The `mcp_servers/briefing_server.py` exposes briefing generation as Claude-callable tools:

| Tool | Description |
|------|-------------|
| `generate_briefing` | Trigger an on-demand briefing for the current or specified week |
| `get_latest_briefing` | Read and return the most recent briefing file |

## Schedule (Gold Tier)

| Report | Trigger | Output location |
|--------|---------|-----------------|
| Weekly CEO Briefing | Every Monday at 08:00 | `vault/Done/WeeklyBrief_YYYYWNN.md` |
| Daily Error Summary | Every day at 18:00 | `logs/DailyErrorSummary_YYYYMMDD.md` |
