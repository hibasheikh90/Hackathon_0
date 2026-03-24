"""
Vault Synchronization System for Platinum Tier
==============================================

Manages synchronization between cloud and local vaults using Git.
Implements the required folder structure and claim-by-move rules.
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import shutil
import tempfile
from enum import Enum


class SyncDirection(Enum):
    CLOUD_TO_LOCAL = "cloud_to_local"
    LOCAL_TO_CLOUD = "local_to_cloud"
    BIDIRECTIONAL = "bidirectional"


class VaultSyncManager:
    def __init__(self, vault_path: str = "./vault", remote_repo: Optional[str] = None):
        self.vault_path = Path(vault_path).resolve()
        self.remote_repo = remote_repo
        self.sync_log_path = self.vault_path / ".sync_log.json"

        # Ensure required directories exist
        required_dirs = [
            "inbox",
            "needs_action",
            "needs_action/email_triage",
            "needs_action/social_drafts",
            "needs_action/accounting",
            "needs_action/other",
            "plans",
            "plans/email",
            "plans/social",
            "plans/accounting",
            "plans/other",
            "pending_approval",
            "pending_approval/email_drafts",
            "pending_approval/social_posts",
            "pending_approval/accounting",
            "pending_approval/other",
            "in_progress",
            "in_progress/cloud",
            "in_progress/local",
            "updates",
            "signals",
            "done"
        ]

        for dir_path in required_dirs:
            (self.vault_path / dir_path).mkdir(parents=True, exist_ok=True)

        # Load sync log or initialize
        self.sync_log = self._load_sync_log()

    def _load_sync_log(self) -> Dict[str, Any]:
        """Load the sync log from file or initialize it."""
        if self.sync_log_path.exists():
            try:
                with open(self.sync_log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # Initialize with default values
        return {
            "last_sync": None,
            "sync_history": [],
            "file_locks": {},
            "stats": {
                "sync_count": 0,
                "conflict_count": 0,
                "error_count": 0
            }
        }

    def _save_sync_log(self):
        """Save the sync log to file."""
        with open(self.sync_log_path, 'w', encoding='utf-8') as f:
            json.dump(self.sync_log, f, indent=2, default=str)

    def _is_safe_for_sync(self, file_path: Path) -> bool:
        """Check if a file is safe to sync (not containing sensitive info)."""
        file_str = str(file_path).lower()

        # Files that should never be synced
        unsafe_patterns = [
            '.env', '.secret', '.key', '.pem', '.p12', '.token',
            'password', 'credential', 'banking', 'payment', 'whatsapp'
        ]

        for pattern in unsafe_patterns:
            if pattern in file_str:
                return False

        return True

    def initialize_git_repo(self):
        """Initialize a Git repository for vault synchronization."""
        os.chdir(self.vault_path)

        # Initialize git repo if not already initialized
        if not (self.vault_path / ".git").exists():
            subprocess.run(["git", "init"], check=True, capture_output=True)

        # Create .gitignore to exclude sensitive files
        gitignore_path = self.vault_path / ".gitignore"
        gitignore_content = """
# Vault sync exclusions
.env
*.env
*.secret
*.key
*.pem
*.p12
*.token
tokens.json
credentials.json
passwords.txt
banking/
payment/
whatsapp/

# Temporary files
*.tmp
*.temp
.DS_Store
Thumbs.db
"""

        with open(gitignore_path, 'a') as f:
            f.write(gitignore_content)

        # Configure git user if not set
        try:
            subprocess.run(["git", "config", "user.email"], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            subprocess.run(["git", "config", "user.email", "ai-employee@example.com"], check=True)
            subprocess.run(["git", "config", "user.name", "AI Employee"], check=True)

    def add_remote(self, remote_url: str):
        """Add a remote repository for synchronization."""
        os.chdir(self.vault_path)
        try:
            subprocess.run(["git", "remote", "add", "origin", remote_url], check=True, capture_output=True)
            self.remote_repo = remote_url
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to add remote: {e}")

    def pull_changes(self) -> bool:
        """Pull changes from remote repository."""
        if not self.remote_repo:
            raise Exception("No remote repository configured")

        os.chdir(self.vault_path)

        try:
            # Fetch and merge changes
            result = subprocess.run([
                "git", "pull", "origin", "main", "--no-rebase"
            ], capture_output=True, text=True)

            if result.returncode == 0:
                print(f"Pulled changes successfully at {datetime.now()}")
                return True
            else:
                # Handle potential merge conflicts
                if "CONFLICT" in result.stdout or "conflict" in result.stderr:
                    print(f"Merge conflict detected: {result.stderr}")
                    self.sync_log["stats"]["conflict_count"] += 1
                    self._handle_merge_conflicts()
                else:
                    print(f"Pull failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error pulling changes: {e}")
            self.sync_log["stats"]["error_count"] += 1
            return False

    def push_changes(self) -> bool:
        """Push local changes to remote repository."""
        if not self.remote_repo:
            raise Exception("No remote repository configured")

        os.chdir(self.vault_path)

        # Add all changes
        subprocess.run(["git", "add", "."], check=True, capture_output=True)

        # Check if there are changes to commit
        status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status_result.stdout.strip():
            print("No changes to commit")
            return True

        try:
            # Create commit
            commit_msg = f"Vault sync at {datetime.now().isoformat()}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)

            # Push changes
            result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)

            if result.returncode == 0:
                print(f"Pushed changes successfully at {datetime.now()}")
                return True
            else:
                print(f"Push failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error pushing changes: {e}")
            self.sync_log["stats"]["error_count"] += 1
            return False

    def _handle_merge_conflicts(self):
        """Handle merge conflicts during sync."""
        os.chdir(self.vault_path)

        # Get list of conflicted files
        result = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                              capture_output=True, text=True)
        conflicted_files = result.stdout.strip().split('\n') if result.stdout.strip() else []

        for file_path in conflicted_files:
            if file_path:
                print(f"Resolving conflict in: {file_path}")
                # For now, we'll accept the incoming changes (cloud wins for non-sensitive files)
                # In a real system, you'd have more sophisticated conflict resolution
                subprocess.run(["git", "checkout", "--theirs", file_path], check=True)

        # Add resolved files
        subprocess.run(["git", "add", "."], check=True)

        # Commit the resolution
        subprocess.run(["git", "commit", "-m", f"Resolve conflicts at {datetime.now().isoformat()}"],
                      check=True, capture_output=True)

    def sync_vault(self, direction: SyncDirection = SyncDirection.BIDIRECTIONAL) -> bool:
        """Synchronize the vault with the remote repository."""
        print(f"Starting vault sync in direction: {direction.value}")

        success = True

        if direction in [SyncDirection.CLOUD_TO_LOCAL, SyncDirection.BIDIRECTIONAL]:
            success &= self.pull_changes()

        if direction in [SyncDirection.LOCAL_TO_CLOUD, SyncDirection.BIDIRECTIONAL]:
            success &= self.push_changes()

        if success:
            # Update sync log
            self.sync_log["last_sync"] = datetime.now().isoformat()
            self.sync_log["stats"]["sync_count"] += 1
            self._save_sync_log()

        return success

    def claim_file(self, file_path: str, agent_name: str) -> bool:
        """Implement the claim-by-move rule: move file from needs_action to in_progress/<agent>."""
        source_path = self.vault_path / "needs_action" / file_path
        dest_path = self.vault_path / "in_progress" / agent_name / file_path

        if not source_path.exists():
            print(f"File not found: {source_path}")
            return False

        if not self._is_safe_for_sync(source_path):
            print(f"File is not safe for sync operations: {source_path}")
            return False

        try:
            # Create destination directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file (implementing the claim-by-move rule)
            shutil.move(str(source_path), str(dest_path))

            print(f"File claimed by {agent_name}: {file_path}")
            return True
        except Exception as e:
            print(f"Error claiming file: {e}")
            return False

    def release_claim(self, file_path: str, agent_name: str, status: str = "needs_action") -> bool:
        """Release a claimed file back to needs_action or move to done/pending_approval."""
        source_path = self.vault_path / "in_progress" / agent_name / file_path

        if not source_path.exists():
            print(f"Claimed file not found: {source_path}")
            return False

        if status == "needs_action":
            dest_path = self.vault_path / "needs_action" / file_path
        elif status == "done":
            dest_path = self.vault_path / "done" / file_path
        elif status == "pending_approval":
            dest_path = self.vault_path / "pending_approval" / file_path
        else:
            dest_path = self.vault_path / status / file_path

        try:
            # Create destination directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            shutil.move(str(source_path), str(dest_path))

            print(f"File released from {agent_name} to {status}: {file_path}")
            return True
        except Exception as e:
            print(f"Error releasing file: {e}")
            return False

    def get_available_tasks(self, agent_name: str) -> List[str]:
        """Get list of available tasks in needs_action that aren't claimed."""
        available_tasks = []

        needs_action_dir = self.vault_path / "needs_action"

        if needs_action_dir.exists():
            for item in needs_action_dir.rglob("*"):
                if item.is_file() and item.suffix == '.md':
                    # Check if this file is already claimed by checking in_progress directories
                    relative_path = item.relative_to(needs_action_dir)

                    claimed = False
                    for in_progress_agent_dir in (self.vault_path / "in_progress").iterdir():
                        if in_progress_agent_dir.is_dir():
                            claimed_file = in_progress_agent_dir / relative_path
                            if claimed_file.exists():
                                claimed = True
                                break

                    if not claimed:
                        available_tasks.append(str(relative_path))

        return available_tasks

    def get_pending_approvals(self) -> List[str]:
        """Get list of items pending approval."""
        pending_approvals = []

        pending_dir = self.vault_path / "pending_approval"

        if pending_dir.exists():
            for item in pending_dir.rglob("*.md"):
                if item.is_file():
                    relative_path = item.relative_to(self.vault_path)
                    pending_approvals.append(str(relative_path))

        return pending_approvals

    def get_updates_for_local(self) -> List[str]:
        """Get list of updates from cloud that need to be merged into local dashboard."""
        updates = []

        updates_dir = self.vault_path / "updates"

        if updates_dir.exists():
            for item in updates_dir.rglob("*.md"):
                if item.is_file():
                    relative_path = item.relative_to(self.vault_path)
                    updates.append(str(relative_path))

        return updates

    def cleanup_old_files(self, days: int = 30) -> int:
        """Clean up old files that have been processed."""
        import time

        cutoff_time = time.time() - (days * 24 * 60 * 60)
        cleaned_count = 0

        # Clean up done directory
        done_dir = self.vault_path / "done"
        if done_dir.exists():
            for item in done_dir.rglob("*"):
                if item.is_file():
                    if item.stat().st_mtime < cutoff_time:
                        try:
                            item.unlink()
                            cleaned_count += 1
                        except:
                            pass  # Skip files that can't be deleted

        return cleaned_count


def main():
    """Example usage of the vault sync manager."""
    print("Initializing Vault Sync Manager...")

    # Initialize the sync manager
    sync_manager = VaultSyncManager()

    # Initialize git repo
    sync_manager.initialize_git_repo()

    print("Vault sync manager initialized successfully!")
    print("Directories created and .gitignore configured.")

    # Example: Show available tasks
    cloud_tasks = sync_manager.get_available_tasks("cloud")
    local_tasks = sync_manager.get_available_tasks("local")

    print(f"Available tasks for cloud: {len(cloud_tasks)}")
    print(f"Available tasks for local: {len(local_tasks)}")


if __name__ == "__main__":
    main()