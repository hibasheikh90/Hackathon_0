# Skill: Task Planner

## Description

This skill reads tasks from `vault/Inbox/` and creates structured execution plans. The agent analyzes the intent behind each task, decomposes it into actionable steps, assigns a priority level, and determines whether human approval is required before execution. The resulting plan is saved as a `.md` file in `vault/Needs_Action/`.

**This skill produces plans only. It never executes tasks.**

---

## Trigger

This skill activates when a new `.md` file appears in `vault/Inbox/`.

---

## Workflow

### Step 1 — Read Task

1. Open the `.md` file from `vault/Inbox/`.
2. Read the full contents into memory.
3. Extract the **title** from the first markdown heading (`# ...`). If no heading exists, derive a title from the filename by replacing underscores and hyphens with spaces.
4. Extract the **body** — all content below the title line.
5. If the file is empty or whitespace-only, flag it as `incomplete` and proceed to Step 6 (Edge Cases).

---

### Step 2 — Analyze Intent

Determine the core purpose of the task by evaluating:

| Signal | What to look for |
|--------|-----------------|
| **Explicit actions** | Action verbs: fix, add, remove, update, create, delete, change, implement, deploy, review. |
| **Open questions** | Lines containing `?` indicate decisions or information are needed. |
| **Checklists** | `- [ ]` items represent outstanding work. `- [x]` items represent completed work. |
| **Delegations** | Phrases like "please handle", "can you", "need someone to" indicate a request directed at the agent. |
| **References** | Mentions of files, URLs, people, or systems that scope the work. |

Produce a single-sentence **objective** that captures what the task aims to achieve.

---

### Step 3 — Break into Steps

Decompose the task into **3–8 ordered steps**. Each step must be:

- **Actionable** — Begins with an imperative verb (e.g., "Replace", "Identify", "Verify").
- **Specific** — References concrete artifacts, locations, or criteria. No vague language.
- **Scoped** — Contains exactly one action. If a step has "and", split it.
- **Sequential** — Steps are ordered by dependency. A step should not depend on a later step.

**Rules for generating steps:**

1. If the task contains a checklist (`- [ ]` items), convert each unchecked item into a step.
2. If the task is a paragraph, extract each distinct action as a separate step.
3. Always include a final verification step (e.g., "Verify all requirements are met").
4. Always include a closing step: "Mark task as complete and archive to `vault/Done/`".

---

### Step 4 — Assign Priority

Evaluate the task content and assign exactly one priority level.

| Priority | Criteria | Examples |
|----------|----------|----------|
| **High** | Contains urgency indicators: "urgent", "ASAP", "critical", "overdue", "immediately", "deadline", "blocker", "emergency", "P0", "P1". Also applies to tasks involving payments, security incidents, or service outages. | "URGENT: Fix login page", "Invoice #4821 — Payment Overdue" |
| **Medium** | Contains standard action verbs with no urgency signals. The task is clear and actionable but not time-sensitive. | "Update homepage banner", "Add dark mode toggle" |
| **Low** | Informational, exploratory, or contains only questions with no stated deadline. No action verbs present. | "What's the status of the redesign?", "Notes from Monday standup" |

Apply the **first matching** priority from top to bottom. If no criteria match, default to **Medium**.

---

### Step 5 — Check if Human Approval Needed

Determine whether the plan requires human sign-off before execution.

**Answer YES if any condition is true:**

| Condition | Rationale |
|-----------|-----------|
| Task involves money, payments, or budgets | Financial decisions require authorization. |
| Task modifies public-facing content (website, client emails, social media) | External visibility demands review. |
| Task deletes, removes, or archives data | Destructive actions are irreversible. |
| Task changes access permissions, credentials, or security settings | Security modifications carry elevated risk. |
| Task is ambiguous, incomplete, or missing key details | Unclear tasks should not be acted on without clarification. |
| Task body is fewer than two non-empty lines | Insufficient context to plan reliably. |

**Answer NO** if none of the above conditions are met and the task is clear, self-contained, and low-risk.

Always include a brief justification with the answer.

---

### Step 6 — Save Plan to Needs_Action

Generate the plan file at:

```
vault/Needs_Action/Plan_<YYYYMMDD_HHMMSS>.md
```

Use the following template exactly:

```markdown
# Task Plan

## Original Task
**Source:** Inbox/{original filename}
**Received:** {YYYY-MM-DD HH:MM:SS}

{Full original file content, unmodified}

## Objective
{Single sentence describing what the task aims to achieve}

## Step-by-Step Plan
1. {Step}
2. {Step}
3. {Step}
...

## Priority
**{High / Medium / Low}** — {one-line justification}

## Requires Human Approval?
**{Yes / No}** — {one-line justification}

## Suggested Output
{1–2 sentences describing the expected deliverable when the task is complete}
```

**Formatting rules:**
- Preserve the original task content exactly as-is under "Original Task". Never reformat, truncate, or edit it.
- Use a blank line between every section.
- Do not add sections beyond what the template specifies.
- Filename uses underscores, not hyphens, in the timestamp.

---

## Edge Cases

| Situation | Action |
|-----------|--------|
| File is empty or whitespace-only | Create a plan with objective: "Clarify task requirements." Single step: "Request details from the task sender." Priority: **Low**. Requires Human Approval: **Yes** — "Task is empty and cannot be planned without clarification." |
| File cannot be read (encoding error, permissions) | Log the error to the console. Do not create a plan file. |
| Plan file with the same timestamp already exists | Append a numeric suffix: `Plan_20260215_143022_2.md`, then `_3.md`, and so on. Never overwrite. |
| File does not have a `.md` extension | Ignore the file. This skill only processes markdown. |
| File has already been planned (duplicate detection) | Check if a `Plan_*.md` referencing the same `Source: Inbox/{filename}` already exists in `vault/Needs_Action/`. If so, skip to avoid duplicate plans. |

---

## Output Contract

Every successful execution of this skill produces exactly **one** file:

```
vault/Needs_Action/Plan_<timestamp>.md
```

The file contains all six sections from the template. No task is executed. No files outside `vault/Needs_Action/` are created or modified.

---

## Principles

- **Plan, never execute.** This skill reasons about work. It never performs it.
- **Be specific.** Every step in the plan must be concrete and actionable. Vague plans waste time.
- **Be honest about unknowns.** If information is missing, state it explicitly and flag for human approval.
- **Be traceable.** Every plan records its source file, timestamp, and reasoning so decisions can be audited.
- **Be idempotent.** Running the skill twice on the same input must not produce duplicate plans.
- **Never destroy.** The original Inbox file is never modified, moved, or deleted by this skill.
