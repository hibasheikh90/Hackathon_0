# Skill: Approval Gate

## Description

Human-in-the-loop approval workflow for the AI Employee pipeline. Scans plans in `vault/Needs_Action/` that require human approval, creates approval request files in `vault/Approvals/`, and monitors for human decisions (APPROVED / REJECTED / TIMEOUT).

## Prerequisites

No additional dependencies — uses only Python standard library.

## Usage

```bash
# Single scan — check for new approvals and resolutions, then exit
python scripts/approval_gate.py --once

# Continuous monitoring every 30 seconds
python scripts/approval_gate.py --daemon --interval 30

# Custom timeout (48 hours instead of default 24)
python scripts/approval_gate.py --once --timeout 48
```

## Inputs

| Parameter    | Required | Description                                              |
|--------------|----------|----------------------------------------------------------|
| `--once`     | Yes*     | Scan once and exit                                       |
| `--daemon`   | Yes*     | Poll continuously                                        |
| `--interval` | No       | Seconds between polls in daemon mode (default: 30)       |
| `--timeout`  | No       | Hours before unanswered approval times out (default: 24) |

*One of `--once` or `--daemon` is required.

## Output

Creates approval request files in `vault/Approvals/` named `Approval_Plan_TIMESTAMP.md` containing:

- **Task:** Plan filename, title, priority, creation time, timeout deadline
- **Objective:** Extracted from the plan
- **Reason:** Why approval is needed
- **Decision:** `PENDING` (to be changed by human to `APPROVED` or `REJECTED`)
- **Notes:** Space for human comments

## Workflow

1. **Scan** `vault/Needs_Action/Plan_*.md` for plans containing `**Yes**` in the "Requires Human Approval?" section.
2. **Create** approval request file in `vault/Approvals/` with task summary and decision section.
3. **Poll** existing approval files for human decisions:
   - **APPROVED** — Plan stays in Needs_Action for normal execution; approval file moves to Done/.
   - **REJECTED** — Plan moves to Done/ with rejection note; approval file moves to Done/.
   - **TIMEOUT** — Both files move to Done/ with timeout note after the configured timeout period.
4. Track state in `scripts/.approval_gate_state.json`.

## How to Approve or Reject

1. Open the approval file in `vault/Approvals/` (e.g., `Approval_Plan_20250216_143000.md`).
2. Find the `## Decision` section.
3. Change `**PENDING**` to `**APPROVED**` or `**REJECTED**`.
4. Optionally add notes in the `## Notes` section.
5. Save the file.
6. The next approval gate scan will detect and process the decision.
