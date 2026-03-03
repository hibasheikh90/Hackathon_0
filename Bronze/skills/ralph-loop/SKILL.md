# Skill: Ralph Loop (Autonomous Execution)

## Description

Ralph is the AI Employee's autonomous execution engine — named for the character who just keeps going. It continuously scans `vault/Needs_Action/` for incomplete tasks, classifies and processes them, marks steps complete, and moves finished tasks to `vault/Done/`. Ralph keeps running until the task queue is empty or the maximum cycle count is reached.

This is the Gold-tier implementation of the "Ralph Wiggum" Stop-hook pattern described in the hackathon spec.

## Prerequisites

No additional dependencies beyond the project core. Ralph uses only the built-in vault file system and the event bus.

## Usage

```bash
# Single pass — process all tasks once and exit
python -m core.ralph --once

# Run until queue is empty (default max 10 cycles)
python -m core.ralph

# Run with custom cycle limit
python -m core.ralph --cycles 20

# Continuous daemon — re-scan every 2 minutes
python -m core.ralph --daemon --interval 2

# Via the Gold entry point
python run_gold.py --ralph
python run_gold.py --ralph --cycles 20
```

## Inputs

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--once` | No | Single scan pass, then exit |
| `--cycles` | No | Max number of full scan cycles (default: 10) |
| `--daemon` | No | Run continuously, repeating every `--interval` minutes |
| `--interval` | No | Minutes between cycles in daemon mode (default: 2) |

## Output

For each processed task, Ralph:

1. Appends completion metadata to the task file:
   ```markdown
   ## Completion
   - **Completed:** 2026-02-24 09:15:00
   - **Cycles taken:** 2
   - **Status:** Done
   ```
2. Moves the file from `vault/Needs_Action/` → `vault/Done/`.
3. Updates `vault/Dashboard.md` with:
   ```
   | Completed | 5 |
   | Pending   | 2 |
   | Stuck     | 0 |
   ```
4. Logs every action to `logs/audit.log`.

## Workflow

```
Cycle start
│
├── Scan vault/Needs_Action/ for .md files
│
├── For each file:
│   ├── Classify task type (plan / email / social / general)
│   ├── Extract objectives (checklist items, headings)
│   ├── Check completion:
│   │   ├── All checkboxes checked? → Move to Done/
│   │   ├── No unchecked items and no objectives? → Move to Done/
│   │   └── Still work remaining? → Mark attempt, increment retry counter
│   └── Fire event: vault.task.completed OR vault.task.stuck
│
├── Update Dashboard.md
│
├── Check stopping condition:
│   ├── Queue empty → exit
│   ├── Max cycles reached → exit
│   └── All remaining tasks stuck (max_retries exceeded) → exit
│
└── Next cycle
```

## Task Classification

Ralph classifies each task to route execution:

| Type | Detection | Action |
|------|-----------|--------|
| `plan` | Filename starts with `Plan_` | Reads plan steps, checks off each |
| `email` | Contains `send email` / `reply` / `@` | Delegates to Gmail MCP |
| `social` | Contains `post`, `tweet`, `linkedin` | Delegates to Social MCP |
| `general` | Default | Marks checkboxes, appends completion |

## Stuck Task Handling

If a task is retried more than `max_retries` times (default: 3) without completion:
- The task is flagged as `STUCK` in its metadata.
- A `vault.task.stuck` event is fired.
- The task is **not** moved to `Done/` — it remains for human review.
- The error is logged and an alert escalation email is sent if configured.

## Events Fired

| Event | When |
|-------|------|
| `vault.task.triaged` | Task classified and queued |
| `vault.task.completed` | Task moved to Done/ |
| `vault.task.stuck` | Task exceeded max retries |
| `ralph.cycle.start` | Each scan cycle begins |
| `ralph.cycle.end` | Each scan cycle completes |
