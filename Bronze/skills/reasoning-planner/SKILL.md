# Skill: Reasoning Planner

## Purpose

This skill enables the AI agent to analyze incoming task files from the vault Inbox and produce detailed, structured **plan files** in `vault/Needs_Action/`. The agent reasons about the task but **never executes it** — it only outputs a plan for human review.

---

## Step 1 — Read the Inbox Task

1. Open the `.md` file from `vault/Inbox/`.
2. Read the full contents into memory.
3. Extract the **title** (first markdown heading, or derive from filename).
4. Extract the **body** (everything below the title).

If the file is empty or whitespace-only, create a plan noting the task is unclear and requires human clarification.

---

## Step 2 — Analyze and Reason

Determine the following by analyzing the task content:

### Objective
Write a single clear sentence describing what the task aims to achieve.

### Step-by-Step Plan
Break the task into 3–8 concrete, ordered steps. Each step should be:
- Actionable (starts with a verb)
- Specific (no vague language)
- Scoped (one action per step)

### Priority
Assign one of:
| Priority | Criteria |
|----------|----------|
| **High** | Contains urgency words ("urgent", "ASAP", "critical", "overdue", "immediately", "deadline"), or involves payments/security/outages. |
| **Medium** | Contains standard action verbs ("fix", "update", "add", "review") with no urgency signals. |
| **Low** | Informational, exploratory, or contains only questions with no deadline. |

### Requires Human Approval
Answer **Yes** if any of these are true:
- The task involves spending money or finances
- The task modifies public-facing content (website, emails to clients)
- The task deletes or removes data
- The task involves access permissions or security changes
- The task is ambiguous or missing details

Otherwise answer **No**.

### Suggested Output
Describe in 1–2 sentences what the completed task should produce (e.g., "Updated homepage with new banner image and working footer link").

---

## Step 3 — Write the Plan File

Create a new file at:
```
vault/Needs_Action/Plan_<YYYYMMDD_HHMMSS>.md
```

Use this template:

```
# Task Plan

## Original Task
**Source:** Inbox/{original filename}
**Received:** {current date and time, YYYY-MM-DD HH:MM:SS}

{Full original file content, unmodified}

## Objective
{Single sentence from Step 2}

## Step-by-Step Plan
1. {Step 1}
2. {Step 2}
...

## Priority
{High / Medium / Low} — {brief justification}

## Requires Human Approval?
{Yes / No} — {brief justification}

## Suggested Output
{1–2 sentence description of expected deliverable}
```

---

## Step 4 — Handle Edge Cases

| Situation | Action |
|-----------|--------|
| File is empty or whitespace-only | Create plan with objective "Clarify task requirements" and single step "Request task details from the sender." Priority: Low. Requires Human Approval: Yes. |
| File cannot be read | Log error. Do not create a plan file. |
| Plan file with same timestamp exists | Append `_2`, `_3`, etc. before `.md`. |

---

## Principles

- **Never execute.** This skill only plans. It never modifies, deploys, or acts on the task.
- **Be specific.** Vague plans are useless. Every step must be concrete.
- **Be honest about unknowns.** If information is missing, say so in the plan and flag for human approval.
- **Be traceable.** Every plan links back to its source file and timestamp.
