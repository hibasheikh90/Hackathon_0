"""
Platinum Tier - Always-On Cloud + Local Executive
================================================

Main entry point for the Platinum Tier implementation featuring distributed AI employee
with cloud and local components working together through synchronized vaults.
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any
import threading
import time
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def cmd_cloud_daemon(vault_path: str, sync_interval: int) -> int:
    """Run the cloud component as a daemon."""
    print("Starting Cloud Component Daemon...")

    # Import here to avoid circular dependencies
    from Platinum.sync.vault_sync import VaultSyncManager
    from Platinum.sync.claim_by_move import ClaimByMoveSystem
    from Platinum.cloud.cloud_vault_server import CloudVaultServer
    from Platinum.cloud.cloud_email_server import CloudEmailServer
    from Platinum.cloud.cloud_accounting_integration import CloudAccountingIntegration

    # Initialize components
    sync_manager = VaultSyncManager(vault_path=vault_path)
    claim_system = ClaimByMoveSystem(vault_path=vault_path)
    vault_server = CloudVaultServer(vault_path=vault_path)
    email_server = CloudEmailServer(vault_path=vault_path)
    accounting_integration = CloudAccountingIntegration(vault_path=vault_path)

    # Start MCP servers in background threads
    def start_vault_server():
        print("Starting Cloud Vault Server...")
        try:
            vault_server.run()
        except Exception as e:
            print(f"Cloud Vault Server error: {e}")

    def start_email_server():
        print("Starting Cloud Email Server...")
        try:
            email_server.run()
        except Exception as e:
            print(f"Cloud Email Server error: {e}")

    vault_thread = threading.Thread(target=start_vault_server, daemon=True)
    email_thread = threading.Thread(target=start_email_server, daemon=True)

    vault_thread.start()
    email_thread.start()

    print("Cloud servers started in background.")

    # Main cloud loop
    last_sync = 0
    print(f"Cloud daemon running. Sync interval: {sync_interval} seconds")

    try:
        while True:
            current_time = time.time()

            # Periodic vault sync
            if current_time - last_sync >= sync_interval:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Performing vault sync...")

                try:
                    success = sync_manager.sync_vault()
                    if success:
                        print("Vault sync completed successfully")

                        # Process available tasks
                        available_tasks = claim_system.get_available_items("cloud")
                        print(f"Found {len(available_tasks)} available tasks for cloud processing")

                        # Process accounting requests
                        accounting_integration.process_accounting_requests()

                        # Process each available task
                        for task in available_tasks:
                            success, msg = claim_system.claim_item(task, "cloud")
                            if success:
                                print(f"Claimed task: {msg}")

                                # In a real implementation, you'd process the task here
                                # For now, we'll just mark it as done after processing
                                claim_system.release_claim(task, "cloud", "done")
                            else:
                                print(f"Failed to claim task: {msg}")

                    last_sync = current_time
                except Exception as e:
                    print(f"Error during vault sync: {e}")

            time.sleep(min(60, sync_interval))  # Check every minute or at sync interval, whichever is smaller

    except KeyboardInterrupt:
        print("\\nCloud daemon stopped by user.")
        return 0


def cmd_local_daemon(vault_path: str, sync_interval: int) -> int:
    """Run the local component as a daemon."""
    print("Starting Local Component Daemon...")

    # Import here to avoid circular dependencies
    from Platinum.sync.vault_sync import VaultSyncManager
    from Platinum.sync.claim_by_move import ClaimByMoveSystem
    from Platinum.local.local_approval_server import LocalApprovalServer

    # Initialize components
    sync_manager = VaultSyncManager(vault_path=vault_path)
    claim_system = ClaimByMoveSystem(vault_path=vault_path)
    approval_server = LocalApprovalServer(vault_path=vault_path)

    # Start MCP servers in background threads
    def start_approval_server():
        print("Starting Local Approval Server...")
        try:
            approval_server.run()
        except Exception as e:
            print(f"Local Approval Server error: {e}")

    approval_thread = threading.Thread(target=start_approval_server, daemon=True)
    approval_thread.start()

    print("Local approval server started in background.")

    # Main local loop
    last_sync = 0
    print(f"Local daemon running. Sync interval: {sync_interval} seconds")

    try:
        while True:
            current_time = time.time()

            # Periodic vault sync
            if current_time - last_sync >= sync_interval:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Performing vault sync...")

                try:
                    success = sync_manager.sync_vault()
                    if success:
                        print("Vault sync completed successfully")

                        # Check for pending approvals
                        pending_approvals = approval_server.get_pending_approvals({"category": "all"})
                        print(f"Found pending approvals: {pending_approvals}")

                        # Check for updates from cloud that need to be merged into dashboard
                        updates = sync_manager.get_updates_for_local()
                        for update_path in updates:
                            approval_server.update_dashboard({
                                "update_path": update_path,
                                "merge_strategy": "append"
                            })

                        # Process any approved items that need action
                        # (e.g., sending emails, posting to social media, executing payments)

                    last_sync = current_time
                except Exception as e:
                    print(f"Error during vault sync: {e}")

            time.sleep(min(60, sync_interval))  # Check every minute or at sync interval, whichever is smaller

    except KeyboardInterrupt:
        print("\\nLocal daemon stopped by user.")
        return 0


def cmd_validate() -> int:
    """Validate the Platinum Tier configuration."""
    print("Validating Platinum Tier configuration...")

    # Check required directories
    required_paths = [
        "vault/inbox",
        "vault/needs_action",
        "vault/pending_approval",
        "vault/in_progress/cloud",
        "vault/in_progress/local",
        "vault/done"
    ]

    all_valid = True
    for path in required_paths:
        full_path = Path(path)
        if not full_path.exists():
            print(f"Missing required path: {path}")
            all_valid = False
        else:
            print(f"✓ Found: {path}")

    # Check required files
    required_files = [
        "Platinum/cloud/cloud_vault_server.py",
        "Platinum/cloud/cloud_email_server.py",
        "Platinum/local/local_approval_server.py",
        "Platinum/sync/vault_sync.py",
        "Platinum/sync/claim_by_move.py"
    ]

    for file_path in required_files:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"Missing required file: {file_path}")
            all_valid = False
        else:
            print(f"✓ Found: {file_path}")

    if all_valid:
        print("\\n✓ Platinum Tier configuration is valid!")
        return 0
    else:
        print("\\n✗ Platinum Tier configuration has issues!")
        return 1


def main() -> None:
    """Main entry point for the Platinum Tier system."""
    parser = argparse.ArgumentParser(
        description="Platinum Tier - Always-On Cloud + Local Executive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  python run_platinum.py --validate     Validate configuration
  python run_platinum.py --cloud        Run cloud component daemon
  python run_platinum.py --local        Run local component daemon
  python run_platinum.py --sync         Run vault synchronization
  python run_platinum.py --status       Show system status
        """
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true", help="Validate configuration")
    group.add_argument("--cloud", action="store_true", help="Run cloud component daemon")
    group.add_argument("--local", action="store_true", help="Run local component daemon")
    group.add_argument("--sync", action="store_true", help="Run vault synchronization")
    group.add_argument("--status", action="store_true", help="Show system status")

    parser.add_argument("--vault-path", type=str, default="./vault",
                       help="Path to the vault directory (default: ./vault)")
    parser.add_argument("--sync-interval", type=int, default=300,
                       help="Sync interval in seconds (default: 300)")

    args = parser.parse_args()

    if args.validate:
        sys.exit(cmd_validate())
    elif args.cloud:
        sys.exit(cmd_cloud_daemon(args.vault_path, args.sync_interval))
    elif args.local:
        sys.exit(cmd_local_daemon(args.vault_path, args.sync_interval))
    elif args.sync:
        from Platinum.sync.vault_sync import VaultSyncManager
        sync_manager = VaultSyncManager(vault_path=args.vault_path)
        success = sync_manager.sync_vault()
        sys.exit(0 if success else 1)
    elif args.status:
        from Platinum.sync.vault_sync import VaultSyncManager
        from Platinum.sync.claim_by_move import ClaimByMoveSystem

        sync_manager = VaultSyncManager(vault_path=args.vault_path)
        claim_system = ClaimByMoveSystem(vault_path=args.vault_path)

        print("Platinum Tier System Status:")
        print(f"Vault Path: {args.vault_path}")
        print(f"Last Sync: {sync_manager.sync_log.get('last_sync', 'Never')}")
        print(f"Sync Stats: {sync_manager.sync_log['stats']}")

        cloud_tasks = claim_system.get_available_items("cloud")
        local_tasks = claim_system.get_available_items("local")
        cloud_claimed = claim_system.get_claimed_by_agent("cloud")
        local_claimed = claim_system.get_claimed_by_agent("local")

        print(f"\\nCloud Component:")
        print(f"  Available tasks: {len(cloud_tasks)}")
        print(f"  Currently processing: {len(cloud_claimed)}")

        print(f"\\nLocal Component:")
        print(f"  Available tasks: {len(local_tasks)}")
        print(f"  Currently processing: {len(local_claimed)}")

        pending_approvals = []
        for agent_dir in (Path(args.vault_path) / "pending_approval").iterdir():
            if agent_dir.is_dir():
                for item in agent_dir.rglob("*.md"):
                    if item.is_file():
                        pending_approvals.append(item.name)

        print(f"\\nPending Approvals: {len(pending_approvals)}")
        for approval in pending_approvals[:5]:  # Show first 5
            print(f"  - {approval}")
        if len(pending_approvals) > 5:
            print(f"  ... and {len(pending_approvals) - 5} more")

        sys.exit(0)


if __name__ == "__main__":
    main()