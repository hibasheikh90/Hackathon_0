"""
Claim-by-Move Rule System for Platinum Tier
==========================================

Implements the claim-by-move rule where the first agent to move an item from
/Needs_Action to /In_Progress/<agent> owns it; other agents must ignore it.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import shutil
import threading
import time
from dataclasses import dataclass, asdict


@dataclass
class ClaimRecord:
    """Record of a claimed file."""
    file_path: str
    agent_name: str
    claimed_at: str
    original_path: str


class ClaimByMoveSystem:
    def __init__(self, vault_path: str = "./vault"):
        self.vault_path = Path(vault_path).resolve()
        self.claim_log_path = self.vault_path / ".claims_log.json"
        self.lock = threading.Lock()  # Thread safety for claim operations

        # Ensure required directories exist
        required_dirs = [
            "inbox",
            "needs_action",
            "needs_action/email",
            "needs_action/social",
            "needs_action/accounting",
            "needs_action/business",
            "needs_action/personal",
            "in_progress",
            "in_progress/cloud",
            "in_progress/local",
            "pending_approval",
            "pending_approval/email",
            "pending_approval/social",
            "pending_approval/accounting",
            "done"
        ]

        for dir_path in required_dirs:
            (self.vault_path / dir_path).mkdir(parents=True, exist_ok=True)

        # Load claims log or initialize
        self.claims_log = self._load_claims_log()

    def _load_claims_log(self) -> Dict[str, Any]:
        """Load the claims log from file or initialize it."""
        if self.claim_log_path.exists():
            try:
                with open(self.claim_log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # Initialize with default values
        return {
            "active_claims": [],
            "completed_claims": [],
            "stats": {
                "total_claims": 0,
                "active_claims": 0,
                "completed_claims": 0,
                "failed_claims": 0
            }
        }

    def _save_claims_log(self):
        """Save the claims log to file."""
        with open(self.claim_log_path, 'w', encoding='utf-8') as f:
            json.dump(self.claims_log, f, indent=2, default=str)

    def _is_file_claimed(self, relative_file_path: str) -> bool:
        """Check if a file is already claimed by any agent."""
        for claim in self.claims_log["active_claims"]:
            if claim["file_path"] == relative_file_path:
                return True
        return False

    def _get_original_needs_action_path(self, relative_file_path: str) -> Optional[Path]:
        """Get the original path in needs_action for a claimed file."""
        # Try to reconstruct the original path by checking if the file exists in needs_action
        needs_action_file = self.vault_path / "needs_action" / relative_file_path
        if needs_action_file.exists():
            return needs_action_file

        # If not directly in needs_action, try to find it in subdirectories
        for subdir in (self.vault_path / "needs_action").iterdir():
            if subdir.is_dir():
                file_path = subdir / relative_file_path
                if file_path.exists():
                    return file_path

        return None

    def claim_item(self, file_path: str, agent_name: str) -> Tuple[bool, str]:
        """
        Claim an item by moving it from needs_action to in_progress/<agent>.

        Returns: (success: bool, message: str)
        """
        with self.lock:  # Ensure thread safety
            # Normalize the file path to be relative to needs_action
            if file_path.startswith("needs_action/"):
                relative_path = file_path[len("needs_action/"):]
            else:
                relative_path = file_path

            # Check if file exists in needs_action
            original_file = self._get_original_needs_action_path(relative_path)
            if not original_file:
                return False, f"File does not exist in needs_action: {file_path}"

            # Check if already claimed
            if self._is_file_claimed(relative_path):
                return False, f"File already claimed: {relative_path}"

            # Create destination path
            destination_path = self.vault_path / "in_progress" / agent_name / relative_path

            try:
                # Create destination directory
                destination_path.parent.mkdir(parents=True, exist_ok=True)

                # Move the file (implementing the claim-by-move rule)
                shutil.move(str(original_file), str(destination_path))

                # Record the claim
                claim_record = ClaimRecord(
                    file_path=str(destination_path.relative_to(self.vault_path)),
                    agent_name=agent_name,
                    claimed_at=datetime.now().isoformat(),
                    original_path=str(original_file.relative_to(self.vault_path))
                )

                self.claims_log["active_claims"].append(asdict(claim_record))
                self.claims_log["stats"]["total_claims"] += 1
                self.claims_log["stats"]["active_claims"] += 1

                self._save_claims_log()

                return True, f"Successfully claimed by {agent_name}: {relative_path}"
            except Exception as e:
                return False, f"Error claiming file: {str(e)}"

    def release_claim(self, file_path: str, agent_name: str, new_status: str = "done") -> Tuple[bool, str]:
        """
        Release a claimed item by moving it to a new status directory.

        Returns: (success: bool, message: str)
        """
        with self.lock:  # Ensure thread safety
            # Normalize the file path to be relative to in_progress/agent
            if not file_path.startswith(f"in_progress/{agent_name}/"):
                # Prepend the expected path
                file_path = f"in_progress/{agent_name}/{file_path}"

            source_path = self.vault_path / file_path

            if not source_path.exists():
                return False, f"Claimed file does not exist: {file_path}"

            # Determine destination based on new status
            if new_status == "needs_action":
                dest_path = self.vault_path / "needs_action" / source_path.name
            elif new_status == "pending_approval":
                dest_path = self.vault_path / "pending_approval" / source_path.name
            elif new_status == "done":
                dest_path = self.vault_path / "done" / source_path.name
            else:
                # Assume it's a specific subdirectory
                dest_path = self.vault_path / new_status / source_path.name

            try:
                # Create destination directory
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Move the file to new status
                shutil.move(str(source_path), str(dest_path))

                # Remove from active claims
                original_relative_path = str(Path(file_path).relative_to(Path(f"in_progress/{agent_name}")))
                self.claims_log["active_claims"] = [
                    claim for claim in self.claims_log["active_claims"]
                    if claim["original_path"] != original_relative_path
                ]

                # Add to completed claims
                completed_claim = {
                    "file_path": str(dest_path.relative_to(self.vault_path)),
                    "agent_name": agent_name,
                    "claimed_at": datetime.now().isoformat(),
                    "released_at": datetime.now().isoformat(),
                    "original_path": original_relative_path,
                    "final_status": new_status
                }
                self.claims_log["completed_claims"].append(completed_claim)

                self.claims_log["stats"]["active_claims"] -= 1
                self.claims_log["stats"]["completed_claims"] += 1

                self._save_claims_log()

                return True, f"Successfully released from {agent_name} to {new_status}: {dest_path.name}"
            except Exception as e:
                return False, f"Error releasing file: {str(e)}"

    def get_available_items(self, agent_name: str) -> List[str]:
        """Get list of items in needs_action that are not currently claimed."""
        available_items = []

        needs_action_dir = self.vault_path / "needs_action"

        if needs_action_dir.exists():
            for item in needs_action_dir.rglob("*"):
                if item.is_file() and item.suffix == '.md':
                    # Get relative path from needs_action
                    relative_path = str(item.relative_to(needs_action_dir))

                    # Check if this file is already claimed
                    if not self._is_file_claimed(relative_path):
                        available_items.append(relative_path)

        return available_items

    def get_claimed_by_agent(self, agent_name: str) -> List[str]:
        """Get list of items currently claimed by a specific agent."""
        claimed_items = []

        agent_in_progress_dir = self.vault_path / "in_progress" / agent_name

        if agent_in_progress_dir.exists():
            for item in agent_in_progress_dir.rglob("*.md"):
                if item.is_file():
                    relative_path = str(item.relative_to(agent_in_progress_dir))
                    claimed_items.append(relative_path)

        return claimed_items

    def get_claim_details(self, relative_file_path: str) -> Optional[Dict[str, Any]]:
        """Get details about a specific claimed file."""
        for claim in self.claims_log["active_claims"]:
            if claim["original_path"] == relative_file_path:
                return claim
        return None

    def check_claim_conflicts(self) -> List[Dict[str, Any]]:
        """Check for any potential claim conflicts."""
        conflicts = []

        # In this implementation, a conflict would be if two agents somehow
        # have the same file in their in_progress directories
        for agent_dir in (self.vault_path / "in_progress").iterdir():
            if agent_dir.is_dir():
                for item in agent_dir.rglob("*.md"):
                    if item.is_file():
                        # Check if any other agent also has this file
                        filename = item.name
                        other_agents_with_file = []

                        for other_agent_dir in (self.vault_path / "in_progress").iterdir():
                            if other_agent_dir.is_dir() and other_agent_dir.name != agent_dir.name:
                                for other_item in other_agent_dir.rglob(filename):
                                    if other_item.is_file():
                                        other_agents_with_file.append(other_agent_dir.name)

                        if other_agents_with_file:
                            conflicts.append({
                                "file": filename,
                                "agents": [agent_dir.name] + other_agents_with_file
                            })

        return conflicts

    def cleanup_stale_claims(self, hours: int = 24) -> int:
        """
        Cleanup claims that have been active for too long (stale claims).
        Moves them back to needs_action.

        Returns: number of cleaned claims
        """
        import time
        from datetime import timedelta

        cleaned_count = 0
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=hours)

        # Find stale claims
        stale_claims = []
        for claim in self.claims_log["active_claims"]:
            claimed_at = datetime.fromisoformat(claim["claimed_at"])
            if claimed_at < cutoff_time:
                stale_claims.append(claim)

        # Move stale claims back to needs_action
        for claim in stale_claims:
            original_file = self.vault_path / claim["original_path"]
            claimed_file = self.vault_path / claim["file_path"]

            if claimed_file.exists():
                # Move back to needs_action
                destination = self.vault_path / "needs_action" / claimed_file.name
                destination.parent.mkdir(parents=True, exist_ok=True)

                try:
                    shutil.move(str(claimed_file), str(destination))
                    cleaned_count += 1

                    # Remove from active claims
                    self.claims_log["active_claims"] = [
                        c for c in self.claims_log["active_claims"]
                        if c["original_path"] != claim["original_path"]
                    ]

                    print(f"Moved stale claim back to needs_action: {destination.name}")
                except Exception as e:
                    print(f"Error moving stale claim: {e}")

        self.claims_log["stats"]["active_claims"] = len(self.claims_log["active_claims"])
        self._save_claims_log()

        return cleaned_count


def main():
    """Example usage of the claim-by-move system."""
    print("Initializing Claim-by-Move System...")

    # Initialize the system
    claim_system = ClaimByMoveSystem()

    print("Claim-by-Move system initialized successfully!")

    # Example: Show available items for cloud agent
    cloud_available = claim_system.get_available_items("cloud")
    local_available = claim_system.get_available_items("local")

    print(f"Available items for cloud: {len(cloud_available)}")
    print(f"Available items for local: {len(local_available)}")

    # Example claim attempt
    if cloud_available:
        file_to_claim = cloud_available[0]
        success, message = claim_system.claim_item(file_to_claim, "cloud")
        print(f"Claim attempt: {message}")

    # Show claimed items
    cloud_claimed = claim_system.get_claimed_by_agent("cloud")
    local_claimed = claim_system.get_claimed_by_agent("local")

    print(f"Items claimed by cloud: {len(cloud_claimed)}")
    print(f"Items claimed by local: {len(local_claimed)}")


if __name__ == "__main__":
    main()