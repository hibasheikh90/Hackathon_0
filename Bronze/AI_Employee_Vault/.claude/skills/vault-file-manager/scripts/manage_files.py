"""
Skill: vault-file-manager
Manages task files across the Inbox → Needs_Action → Done pipeline.
"""

import argparse
import os
import re
import shutil
import sys
from datetime import datetime

# Resolve vault path relative to this script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
VAULT_DIR = os.path.join(PROJECT_ROOT, "vault")

STAGES = {
    "inbox": "Inbox",
    "needs_action": "Needs_Action",
    "done": "Done",
}


def stage_path(stage: str) -> str:
    folder = STAGES.get(stage.lower())
    if not folder:
        print(f"[ERROR] Unknown stage: '{stage}'")
        print(f"        Valid stages: {', '.join(STAGES.keys())}")
        sys.exit(1)
    path = os.path.join(VAULT_DIR, folder)
    os.makedirs(path, exist_ok=True)
    return path


def find_file(filename: str) -> tuple[str, str] | None:
    """Find a file across all stages. Returns (full_path, stage_key) or None."""
    for key, folder in STAGES.items():
        candidate = os.path.join(VAULT_DIR, folder, filename)
        if os.path.isfile(candidate):
            return candidate, key
    return None


def unique_dest(dest_dir: str, filename: str) -> str:
    candidate = os.path.join(dest_dir, filename)
    if not os.path.exists(candidate):
        return candidate
    name, ext = os.path.splitext(filename)
    counter = 2
    while True:
        candidate = os.path.join(dest_dir, f"{name}_{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


# ---- Commands ---------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> None:
    path = stage_path(args.stage)
    files = sorted(f for f in os.listdir(path) if f.endswith(".md"))

    if not files:
        print(f"[LIST] {STAGES[args.stage.lower()]}/ — empty")
        return

    print(f"[LIST] {STAGES[args.stage.lower()]}/ — {len(files)} file(s)")
    for f in files:
        size = os.path.getsize(os.path.join(path, f))
        print(f"  - {f}  ({size} bytes)")


def cmd_move(args: argparse.Namespace) -> None:
    result = find_file(args.file)
    if not result:
        print(f"[ERROR] File not found in any stage: {args.file}")
        sys.exit(1)

    src_path, src_stage = result
    dest_dir = stage_path(args.to)
    dest_path = unique_dest(dest_dir, args.file)

    if os.path.dirname(src_path) == dest_dir:
        print(f"[SKIP] {args.file} is already in {STAGES[args.to.lower()]}/")
        return

    shutil.move(src_path, dest_path)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    src_label = STAGES[src_stage]
    dest_label = STAGES[args.to.lower()]
    print(f"[MOVED] {args.file}: {src_label} -> {dest_label}")
    print(f"  Timestamp: {timestamp}")


def cmd_archive(args: argparse.Namespace) -> None:
    result = find_file(args.file)
    if not result:
        print(f"[ERROR] File not found in any stage: {args.file}")
        sys.exit(1)

    src_path, src_stage = result
    done_dir = stage_path("done")

    if src_stage == "done":
        print(f"[SKIP] {args.file} is already in Done/")
        return

    # Prepend completion metadata
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"[ERROR] Cannot read {args.file}: {e}")
        sys.exit(1)

    header = (
        f"---\n"
        f"completed: {timestamp}\n"
        f"archived_from: {STAGES[src_stage]}/\n"
        f"---\n\n"
    )

    dest_path = unique_dest(done_dir, args.file)

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(header + content)

    os.remove(src_path)

    print(f"[ARCHIVED] {args.file}: {STAGES[src_stage]} -> Done")
    print(f"  Timestamp: {timestamp}")


def cmd_search(args: argparse.Namespace) -> None:
    query = args.query.lower()
    matches = []

    for key, folder in STAGES.items():
        dir_path = os.path.join(VAULT_DIR, folder)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith(".md"):
                continue
            full_path = os.path.join(dir_path, fname)
            # Check filename
            if query in fname.lower():
                matches.append((folder, fname, "filename"))
                continue
            # Check content
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if query in content.lower():
                    matches.append((folder, fname, "content"))
            except (OSError, UnicodeDecodeError):
                pass

    if not matches:
        print(f"[SEARCH] No results for \"{args.query}\"")
        return

    print(f"[SEARCH] {len(matches)} result(s) for \"{args.query}\"")
    for folder, fname, match_type in matches:
        print(f"  - {folder}/{fname}  (matched in {match_type})")


def cmd_status(args: argparse.Namespace) -> None:
    counts = {}
    total = 0
    for key, folder in STAGES.items():
        dir_path = os.path.join(VAULT_DIR, folder)
        if os.path.isdir(dir_path):
            count = len([f for f in os.listdir(dir_path) if f.endswith(".md")])
        else:
            count = 0
        counts[folder] = count
        total += count

    print("[STATUS] Vault Summary")
    for folder, count in counts.items():
        print(f"  {folder + ':':16s} {count} file(s)")
    print(f"  {'Total:':16s} {total} file(s)")


# ---- Main -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Vault File Manager — manage task pipeline files.")
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List files in a vault stage")
    p_list.add_argument("--stage", required=True, help="Stage: inbox, needs_action, done")

    # move
    p_move = sub.add_parser("move", help="Move a file to a different stage")
    p_move.add_argument("--file", required=True, help="Filename to move")
    p_move.add_argument("--to", required=True, help="Target stage: inbox, needs_action, done")

    # archive
    p_archive = sub.add_parser("archive", help="Archive a file to Done/")
    p_archive.add_argument("--file", required=True, help="Filename to archive")

    # search
    p_search = sub.add_parser("search", help="Search files by keyword")
    p_search.add_argument("--query", required=True, help="Search keyword")

    # status
    sub.add_parser("status", help="Show vault status summary")

    args = parser.parse_args()

    # Ensure vault exists
    os.makedirs(VAULT_DIR, exist_ok=True)

    commands = {
        "list": cmd_list,
        "move": cmd_move,
        "archive": cmd_archive,
        "search": cmd_search,
        "status": cmd_status,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
