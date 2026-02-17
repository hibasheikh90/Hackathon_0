# Skill: Vault File Manager

## Description

Manages task files across the three-stage vault pipeline: `Inbox/` → `Needs_Action/` → `Done/`. Provides atomic file operations (move, list, archive, search) with full audit logging. This skill replaces manual file management and MCP filesystem servers.

## Prerequisites

The vault directory must exist with this structure:
```
AI_Employee_Vault/vault/
├── Inbox/
├── Needs_Action/
└── Done/
```

The script creates missing directories automatically.

## Usage

```bash
# List all files in a stage
python scripts/manage_files.py list --stage inbox

# Move a task to the next stage
python scripts/manage_files.py move --file "task_report.md" --to needs_action

# Archive a completed task
python scripts/manage_files.py archive --file "task_report.md"

# Search for a task by keyword
python scripts/manage_files.py search --query "invoice"

# Show vault status summary
python scripts/manage_files.py status
```

## Commands

| Command   | Description                                           |
|-----------|-------------------------------------------------------|
| `list`    | List all `.md` files in a vault stage                 |
| `move`    | Move a file from its current stage to a target stage  |
| `archive` | Move a file from `Needs_Action/` to `Done/` with a completion timestamp |
| `search`  | Search file names and contents across all stages      |
| `status`  | Print a summary of file counts in each stage          |

## Inputs

| Parameter  | Used By        | Description                                    |
|------------|----------------|------------------------------------------------|
| `--stage`  | `list`         | Stage to list: `inbox`, `needs_action`, `done` |
| `--file`   | `move`,`archive` | Filename to operate on                       |
| `--to`     | `move`         | Target stage: `inbox`, `needs_action`, `done`  |
| `--query`  | `search`       | Keyword to search for (case-insensitive)       |

## Output

All output is clean text. Example:

```
[STATUS] Vault Summary
  Inbox:        3 files
  Needs_Action: 5 files
  Done:         12 files
  Total:        20 files
```

```
[MOVED] task_report.md: Needs_Action → Done
  Timestamp: 2026-02-15 14:30:22
```

## Workflow

1. Resolve the vault base path relative to the project root.
2. Validate that the requested command and parameters are valid.
3. Execute the file operation atomically.
4. On `archive`: prepend a completion timestamp header to the file content.
5. Print the result.
6. Exit with code 0 on success, 1 on failure.

## Safety Rules

- Never delete files. `archive` moves to `Done/`, it does not remove.
- Never overwrite. If the target filename exists, append `_2`, `_3`, etc.
- Never modify file content except for the `archive` command (which prepends metadata only).
- All operations are logged to stdout for traceability.
