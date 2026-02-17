"""
Approval Gate — Human-in-the-Loop approval workflow.

Scans vault/Needs_Action/ for plans requiring human approval and creates
approval request files in vault/Approvals/. Polls for human decisions
(APPROVED / REJECTED) and resolves plans accordingly.

Modes:
  --once     Single scan then exit
  --daemon   Continuous polling every N seconds

Usage:
  python scripts/approval_gate.py --once
  python scripts/approval_gate.py --daemon --interval 30
  python scripts/approval_gate.py --once --timeout 48  # 48-hour timeout
"""

import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Vault paths
_ai_vault = PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault

NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
DONE_DIR = VAULT_DIR / "Done"
APPROVALS_DIR = VAULT_DIR / "Approvals"

STATE_FILE = SCRIPT_DIR / ".approval_gate_state.json"


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"pending_approvals": {}, "last_scan": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_title(content: str) -> str:
    """Extract the first heading from markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return "(untitled)"


def extract_priority(content: str) -> str:
    """Extract priority from plan content."""
    m = re.search(r"## Priority\s*\n\*\*(\w+)\*\*", content, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r"\*\*Priority[:\s]*\*\*\s*(\w+)", content, re.IGNORECASE)
    if m:
        return m.group(1)
    return "Medium"


def extract_objective(content: str) -> str:
    """Extract objective from plan content."""
    m = re.search(r"## Objective\s*\n(.+?)(?:\n#|\Z)", content, re.DOTALL)
    if m:
        text = m.group(1).strip()
        # First non-empty line
        for line in text.splitlines():
            if line.strip():
                return line.strip()[:200]
    return "(no objective)"


def needs_approval(content: str) -> bool:
    """Check if a plan file requires human approval (contains **Yes**)."""
    # Look for the "Requires Human Approval?" section with **Yes**
    m = re.search(
        r"## Requires Human Approval\??\s*\n\*\*Yes\*\*",
        content,
        re.IGNORECASE,
    )
    return m is not None


# ---------------------------------------------------------------------------
# Stage 1: Scan for plans needing approval
# ---------------------------------------------------------------------------
def scan_for_new_approvals(state: dict, timeout_hours: int) -> int:
    """Scan Needs_Action for Plan_*.md needing approval. Returns count of new approvals."""
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    pending = state.get("pending_approvals", {})
    new_count = 0

    plan_files = sorted(NEEDS_ACTION_DIR.glob("Plan_*.md"))
    for plan_path in plan_files:
        plan_name = plan_path.name

        # Skip if already tracked
        if plan_name in pending:
            continue

        try:
            content = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if not needs_approval(content):
            continue

        # Create approval request file
        title = extract_title(content)
        priority = extract_priority(content)
        objective = extract_objective(content)
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        timeout_at = (now + timedelta(hours=timeout_hours)).strftime("%Y-%m-%d %H:%M:%S")

        approval_name = f"Approval_{plan_name}"
        approval_path = APPROVALS_DIR / approval_name

        # Avoid duplicates
        if approval_path.exists():
            continue

        approval_md = f"""# Approval Request

## Task
**Plan:** {plan_name}
**Title:** {title}
**Priority:** {priority}
**Created:** {now_str}
**Timeout:** {timeout_at}

## Objective
{objective}

## Reason for Approval
This plan was flagged for human review because it involves sensitive operations
(payments, public-facing changes, security, or destructive actions).

## Decision
**PENDING**

_To approve, replace PENDING above with APPROVED._
_To reject, replace PENDING above with REJECTED._
_Add optional notes below:_

## Notes

"""
        approval_path.write_text(approval_md, encoding="utf-8")
        print(f"  [APPROVAL] Created {approval_name}")

        pending[plan_name] = {
            "approval_file": approval_name,
            "created": now.isoformat(),
            "timeout_at": (now + timedelta(hours=timeout_hours)).isoformat(),
            "status": "PENDING",
        }
        new_count += 1

    state["pending_approvals"] = pending
    return new_count


# ---------------------------------------------------------------------------
# Stage 2: Check for resolved approvals
# ---------------------------------------------------------------------------
def check_resolutions(state: dict) -> dict:
    """Check approval files for human decisions. Returns resolution counts."""
    counts = {"approved": 0, "rejected": 0, "timed_out": 0}
    pending = state.get("pending_approvals", {})
    resolved_keys = []
    now = datetime.now()

    for plan_name, info in pending.items():
        if info.get("status") != "PENDING":
            continue

        approval_name = info["approval_file"]
        approval_path = APPROVALS_DIR / approval_name
        plan_path = NEEDS_ACTION_DIR / plan_name

        if not approval_path.is_file():
            continue

        try:
            content = approval_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Check for human decision in the Decision section
        decision = None
        decision_match = re.search(
            r"## Decision\s*\n\*\*(\w+)\*\*",
            content,
            re.IGNORECASE,
        )
        if decision_match:
            raw = decision_match.group(1).upper()
            if raw == "APPROVED":
                decision = "APPROVED"
            elif raw == "REJECTED":
                decision = "REJECTED"

        # Check timeout
        timeout_str = info.get("timeout_at")
        timed_out = False
        if timeout_str and not decision:
            try:
                timeout_at = datetime.fromisoformat(timeout_str)
                if now >= timeout_at:
                    timed_out = True
                    decision = "TIMEOUT"
            except ValueError:
                pass

        if not decision:
            continue

        # Resolve based on decision
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        DONE_DIR.mkdir(parents=True, exist_ok=True)

        if decision == "APPROVED":
            # Plan stays in Needs_Action (normal execution proceeds)
            # Move approval file to Done
            _append_to_file(approval_path, f"\n---\n_Resolved: APPROVED at {now_str}_\n")
            _move_to_done(approval_path)
            print(f"  [APPROVED] {plan_name}")
            counts["approved"] += 1

        elif decision == "REJECTED":
            # Move plan to Done with rejection note
            if plan_path.is_file():
                _append_to_file(plan_path, f"\n---\n_REJECTED at {now_str}. Plan will not be executed._\n")
                _move_to_done(plan_path)
            # Move approval file to Done
            _append_to_file(approval_path, f"\n---\n_Resolved: REJECTED at {now_str}_\n")
            _move_to_done(approval_path)
            print(f"  [REJECTED] {plan_name}")
            counts["rejected"] += 1

        elif decision == "TIMEOUT":
            # Move both to Done with timeout note
            if plan_path.is_file():
                _append_to_file(plan_path, f"\n---\n_TIMED OUT at {now_str}. Approval window expired._\n")
                _move_to_done(plan_path)
            _append_to_file(approval_path, f"\n---\n_Resolved: TIMED OUT at {now_str}_\n")
            _move_to_done(approval_path)
            print(f"  [TIMEOUT] {plan_name}")
            counts["timed_out"] += 1

        info["status"] = decision
        info["resolved_at"] = now.isoformat()
        resolved_keys.append(plan_name)

    return counts


def _append_to_file(filepath: Path, text: str) -> None:
    """Append text to a file."""
    try:
        content = filepath.read_text(encoding="utf-8")
        filepath.write_text(content + text, encoding="utf-8")
    except OSError:
        pass


def _move_to_done(filepath: Path) -> None:
    """Move a file to the Done directory."""
    dest = DONE_DIR / filepath.name
    if dest.exists():
        # Add counter suffix
        stem = filepath.stem
        ext = filepath.suffix
        counter = 2
        while True:
            dest = DONE_DIR / f"{stem}_{counter}{ext}"
            if not dest.exists():
                break
            counter += 1
    try:
        shutil.move(str(filepath), str(dest))
    except OSError as e:
        print(f"  [WARN] Could not move {filepath.name}: {e}")


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------
def run_once(state: dict, timeout_hours: int) -> dict:
    """Execute one full scan + resolution cycle. Returns counts."""
    for d in (NEEDS_ACTION_DIR, DONE_DIR, APPROVALS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    new = scan_for_new_approvals(state, timeout_hours)
    resolutions = check_resolutions(state)

    state["last_scan"] = datetime.now().isoformat()

    return {
        "new_approvals": new,
        **resolutions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Human-in-the-loop approval gate for plans.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Scan once and exit")
    mode.add_argument("--daemon", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between polls in daemon mode (default: 30)")
    parser.add_argument("--timeout", type=int, default=24, help="Hours before an unanswered approval times out (default: 24)")
    args = parser.parse_args()

    state = load_state()

    if args.once:
        counts = run_once(state, args.timeout)
        save_state(state)
        print(
            f"[OK] Approval gate: new={counts['new_approvals']} "
            f"approved={counts['approved']} rejected={counts['rejected']} "
            f"timed_out={counts['timed_out']}"
        )
    elif args.daemon:
        print(f"[INFO] Approval gate started (interval: {args.interval}s, timeout: {args.timeout}h). Ctrl+C to stop.")
        try:
            while True:
                counts = run_once(state, args.timeout)
                save_state(state)
                print(
                    f"[OK] Scan complete: new={counts['new_approvals']} "
                    f"approved={counts['approved']} rejected={counts['rejected']} "
                    f"timed_out={counts['timed_out']} | Next in {args.interval}s"
                )
                time.sleep(args.interval)
        except KeyboardInterrupt:
            save_state(state)
            print("\n[INFO] Approval gate stopped.")


if __name__ == "__main__":
    main()
