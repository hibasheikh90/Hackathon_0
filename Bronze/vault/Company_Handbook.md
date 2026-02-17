# Company Handbook — AI Agent (Bronze Tier)

## What This Agent Does

This is an autonomous AI employee operating at the **Bronze tier** of the Agent Factory. It monitors an Obsidian vault for incoming tasks, processes them, and delivers results — all through markdown files.

### Core Responsibilities

- **Watch** the `Inbox/` folder for new task files
- **Triage** tasks and move actionable items to `Needs_Action/`
- **Execute** work as described in each task file
- **Complete** tasks and archive them in `Done/` with output attached

## Rules

1. **Single-loop execution.** The agent runs one processing cycle: check Inbox, act on items, produce output. No persistent daemon.
2. **File-based communication only.** All input and output flows through markdown files in the vault. No external APIs, no database, no network calls.
3. **Transparency.** Every action the agent takes is reflected in a file the user can read. No hidden state.
4. **Idempotency.** Re-running the agent on an already-processed vault produces no duplicate work.
5. **No data loss.** The agent never deletes user content. Completed tasks are moved, not removed.

## Boundaries

- The agent does **not** access the internet or external services
- The agent does **not** modify files outside the `vault/` directory
- The agent does **not** execute arbitrary code from task files
- The agent does **not** make decisions beyond its defined capabilities
- The agent does **not** retain memory between runs unless written to the vault

## Vault Structure

```
vault/
├── Dashboard.md          # Live overview of agent status and tasks
├── Company_Handbook.md   # This file — rules and boundaries
├── Inbox/                # Drop zone for new tasks
├── Needs_Action/         # Tasks the agent is actively working on
└── Done/                 # Archived completed tasks
```

## How to Assign Work

1. Create a `.md` file in `vault/Inbox/`
2. Include a clear task description in the file body
3. Run the agent
4. Check `vault/Done/` for the result
