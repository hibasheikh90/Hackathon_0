# Skill: File Triage

## Purpose

This skill enables the AI agent to process incoming task files from the vault Inbox, understand their intent, and route them to the correct destination folder with a structured response attached.

---

## Step 1 — Read the Inbox File

1. Open the `.md` file from `vault/Inbox/`.
2. Read the full contents into memory.
3. Identify three components:
   - **Title**: The first markdown heading (`# ...`). If no heading exists, derive a title from the filename by replacing underscores and hyphens with spaces.
   - **Body**: All text below the title heading.
   - **Metadata** (optional): Any YAML front-matter block between `---` fences at the top of the file.

If the file is empty or contains only whitespace, mark it as **invalid** and skip to Step 5.

---

## Step 2 — Summarize the Task

Produce a summary by following these rules in order:

1. Strip all markdown formatting (headings, bold, links, images) to get plain text.
2. Discard blank lines.
3. Take the first five non-empty lines of the body as the summary block.
4. If the body contains a line starting with `TL;DR` or `Summary:`, prefer that line as the summary instead.
5. The final summary must be no longer than five lines and no longer than 300 characters total. Truncate with `...` if necessary.

---

## Step 3 — Decide the Destination

Evaluate the content against the following decision table, checked from top to bottom. Use the **first matching rule**.

| # | Condition | Destination | Rationale |
|---|-----------|-------------|-----------|
| 1 | Body contains the word "DONE" or "COMPLETED" (case-insensitive) anywhere | `vault/Done/` | The task is already finished; archive it. |
| 2 | Body contains a question mark on any line | `vault/Needs_Action/` | Open questions require a response or decision. |
| 3 | Body contains action verbs: "fix", "add", "remove", "update", "create", "delete", "change", "implement", "deploy", "review" | `vault/Needs_Action/` | Explicit action requested. |
| 4 | Body contains a checklist (`- [ ]`) with at least one unchecked item | `vault/Needs_Action/` | Outstanding to-do items remain. |
| 5 | Body contains only a checklist where every item is checked (`- [x]`) | `vault/Done/` | All items completed. |
| 6 | None of the above match | `vault/Needs_Action/` | When uncertain, default to action. Never discard work. |

Record the **rule number** that matched. This is included in the output for traceability.

---

## Step 4 — Write the Output File

Create a new `.md` file in the destination folder determined by Step 3. The filename must match the original Inbox filename exactly.

Use the following template:

```
# {Title from Step 1}

## Metadata
- **Source:** Inbox/{original filename}
- **Received:** {current date and time, YYYY-MM-DD HH:MM:SS}
- **Routed to:** {destination folder name}
- **Triage rule:** #{rule number from Step 3}
- **Status:** {Needs Action | Done}

## Summary
{Summary from Step 2}

## Original Task
{Full original file content, unmodified}

## Agent Notes
- Triage complete. File routed by rule #{rule number}.
```

Formatting rules for the output:
- Preserve the original content exactly as-is under "Original Task". Do not reformat, truncate, or edit it.
- Use a blank line between every section.
- Do not add content beyond what the template specifies.

---

## Step 5 — Handle Edge Cases

| Situation | Action |
|-----------|--------|
| File is empty or whitespace-only | Write output to `vault/Needs_Action/` with summary set to `(empty file — manual review required)` and status `Needs Action`. |
| File cannot be read (encoding error, permissions) | Log the error to the console. Do not move or create any file. |
| A file with the same name already exists in the destination | Append a numeric suffix before the extension: `task.md` becomes `task_2.md`, then `task_3.md`, and so on. Never overwrite. |
| Filename has no `.md` extension | Ignore the file entirely. This skill only processes markdown. |

---

## Principles

- **Never delete the original.** The Inbox file remains untouched until an external process or the user removes it.
- **Never guess.** If the content is ambiguous, route to `Needs_Action/` and let a human decide.
- **Be traceable.** Every output file records the source, timestamp, and rule used so decisions can be audited.
- **Be idempotent.** Processing the same file twice must not create duplicate outputs (check for existing files first).
