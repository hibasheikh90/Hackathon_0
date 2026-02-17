# Skill: Daily Report

## Description

Scans the entire vault and generates a structured daily activity report. The report summarizes pending tasks, active work, completed items, and highlights items that need attention. Designed to give the user a single-glance overview of their AI Employee's state.

## Prerequisites

The vault directory must exist at `AI_Employee_Vault/vault/` with the standard `Inbox/`, `Needs_Action/`, and `Done/` subdirectories.

## Usage

```bash
# Generate today's report
python scripts/generate_report.py

# Generate report for a specific date
python scripts/generate_report.py --date 2026-02-14

# Print to stdout only (do not save to file)
python scripts/generate_report.py --stdout
```

## Inputs

| Parameter  | Required | Description                                              |
|------------|----------|----------------------------------------------------------|
| `--date`   | No       | Date to report on (YYYY-MM-DD). Defaults to today.      |
| `--stdout` | No       | Print report to terminal only, do not write a file.      |

## Output

By default, the report is saved to:
```
AI_Employee_Vault/vault/Done/DailyReport_YYYYMMDD.md
```

Report format:

```markdown
# Daily Report — 2026-02-15

## Summary
- Inbox: 2 new tasks
- Needs Action: 4 tasks pending
- Completed: 3 tasks done today
- Attention: 1 high-priority item

## Inbox (New)
| File | Title | Received |
| ...  | ...   | ...      |

## Needs Action (Pending)
| File | Title | Priority | Approval Needed |
| ...  | ...   | ...      | ...             |

## Completed Today
| File | Title | Completed |
| ...  | ...   | ...       |

## Attention Required
- [HIGH] Invoice_4821.md — Payment overdue, requires human approval

## Generated
2026-02-15 18:00:00 by AI Employee (Silver Tier)
```

## Workflow

1. Scan `vault/Inbox/` — count and list all `.md` files.
2. Scan `vault/Needs_Action/` — count, list, and extract priority/approval metadata from plan files.
3. Scan `vault/Done/` — count and list files modified today (or on the `--date` target).
4. Identify attention items: any file with **High** priority or **Requires Human Approval: Yes**.
5. Assemble the report using the template above.
6. Write the report to `vault/Done/DailyReport_YYYYMMDD.md` (unless `--stdout`).
7. Print confirmation.

## Output Messages

On success:
```
[OK] Daily report generated: DailyReport_20260215.md
  Inbox: 2 | Pending: 4 | Done: 3 | Attention: 1
```

On failure:
```
[ERROR] Report generation failed: <error detail>
```
