"""
Health Monitoring System for Platinum Tier

Monitors the health of both cloud and local components,
tracks system status, and manages failover mechanisms.
"""

import os
import time
import logging
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import psutil
import requests
from dataclasses import dataclass, asdict
from enum import Enum

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComponentStatus(Enum):
    HEALTHY = "healthy"
    UNSTABLE = "unstable"
    FAILED = "failed"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    status: ComponentStatus
    timestamp: str
    details: Dict[str, Any]
    message: str

class HealthMonitor:
    """Monitors the health of the Platinum Tier system."""

    def __init__(self, vault_path: str = "./vault", is_cloud: bool = False):
        self.vault_path = Path(vault_path).resolve()
        self.is_cloud = is_cloud
        self.component_name = "cloud" if is_cloud else "local"
        self.monitoring = False
        self.check_results: List[HealthCheckResult] = []
        self.health_log_path = self.vault_path / f"health_{self.component_name}.log"
        self.status_file = self.vault_path / f"status_{self.component_name}.json"

        # Create necessary directories
        (self.vault_path / "health_checks").mkdir(parents=True, exist_ok=True)

        # Initialize status
        self.system_status = {
            "overall": ComponentStatus.UNKNOWN.value,
            "last_check": None,
            "components": {},
            "metrics": {}
        }

        # Load existing status if available
        self.load_status()

    def load_status(self):
        """Load system status from file."""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    self.system_status = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load status file: {e}")

    def save_status(self):
        """Save system status to file."""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self.system_status, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save status file: {e}")

    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_available_gb": round(disk.free / (1024**3), 2),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return {"error": str(e)}

    def check_vault_integrity(self) -> Dict[str, Any]:
        """Check the integrity of the vault structure."""
        try:
            vault_dirs = [
                "inbox", "needs_action", "pending_approval",
                "in_progress", "done", "plans", "updates"
            ]

            if self.is_cloud:
                # Cloud has cloud-specific dirs
                vault_dirs.extend(["in_progress/cloud"])
            else:
                # Local has local-specific dirs
                vault_dirs.extend(["in_progress/local", "approved", "rejected"])

            results = {}
            for directory in vault_dirs:
                dir_path = self.vault_path / directory
                results[directory] = {
                    "exists": dir_path.exists(),
                    "writable": dir_path.exists() and os.access(dir_path, os.W_OK),
                    "item_count": len(list(dir_path.glob("*"))) if dir_path.exists() else 0
                }

            return {
                "directories": results,
                "all_ok": all(info["exists"] and info["writable"] for info in results.values()),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking vault integrity: {e}")
            return {"error": str(e)}

    def check_sync_status(self) -> Dict[str, Any]:
        """Check the status of vault synchronization."""
        try:
            # Check if git repo exists and is accessible
            git_path = self.vault_path / ".git"
            sync_status = {
                "git_exists": git_path.exists(),
                "has_remote": False,
                "last_sync": None,
                "uncommitted_changes": 0
            }

            if git_path.exists():
                # Check git status
                try:
                    result = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=self.vault_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    sync_status["uncommitted_changes"] = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

                    # Check for remote
                    remote_result = subprocess.run(
                        ["git", "remote", "-v"],
                        cwd=self.vault_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    sync_status["has_remote"] = bool(remote_result.stdout.strip())

                    # Get last commit time
                    last_commit_result = subprocess.run(
                        ["git", "log", "-1", "--format=%ct"],
                        cwd=self.vault_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if last_commit_result.returncode == 0 and last_commit_result.stdout.strip():
                        import datetime as dt
                        timestamp = int(last_commit_result.stdout.strip())
                        sync_status["last_sync"] = dt.datetime.fromtimestamp(timestamp).isoformat()

                except subprocess.TimeoutExpired:
                    logger.warning("Git operations timed out")
                    sync_status["error"] = "timeout"
                except Exception as e:
                    logger.error(f"Git check error: {e}")
                    sync_status["error"] = str(e)

            sync_status["timestamp"] = datetime.now().isoformat()
            return sync_status
        except Exception as e:
            logger.error(f"Error checking sync status: {e}")
            return {"error": str(e)}

    def check_component_processes(self) -> Dict[str, Any]:
        """Check if critical processes are running."""
        try:
            # Look for processes related to our system
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'platinum' in cmdline.lower() or 'claude' in cmdline.lower():
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:100]  # Truncate long command lines
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return {
                "processes": processes,
                "count": len(processes),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking component processes: {e}")
            return {"error": str(e)}

    def check_health(self) -> HealthCheckResult:
        """Perform a comprehensive health check."""
        timestamp = datetime.now().isoformat()

        # Perform individual checks
        resource_check = self.check_system_resources()
        vault_check = self.check_vault_integrity()
        sync_check = self.check_sync_status()
        process_check = self.check_component_processes()

        # Determine overall status based on checks
        status = ComponentStatus.HEALTHY

        # Check for critical issues
        if resource_check.get("error") or vault_check.get("error"):
            status = ComponentStatus.FAILED
        elif (resource_check.get("cpu_percent", 100) > 90 or
              resource_check.get("memory_percent", 100) > 90 or
              resource_check.get("disk_percent", 100) > 95):
            status = ComponentStatus.UNSTABLE
        elif not vault_check.get("all_ok", True):
            status = ComponentStatus.UNSTABLE

        # Compile check results
        details = {
            "resources": resource_check,
            "vault": vault_check,
            "sync": sync_check,
            "processes": process_check
        }

        # Update system status
        self.system_status["overall"] = status.value
        self.system_status["last_check"] = timestamp
        self.system_status["components"][self.component_name] = status.value
        self.system_status["metrics"] = resource_check

        # Save status
        self.save_status()

        # Create result object
        result = HealthCheckResult(
            component=self.component_name,
            status=status,
            timestamp=timestamp,
            details=details,
            message=f"Health check completed for {self.component_name} component"
        )

        # Log the result
        self.log_check_result(result)

        return result

    def log_check_result(self, result: HealthCheckResult):
        """Log the health check result."""
        try:
            log_entry = {
                "component": result.component,
                "status": result.status.value,
                "timestamp": result.timestamp,
                "message": result.message,
                "details": result.details
            }

            with open(self.health_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')

            self.check_results.append(result)

            # Keep only last 100 results
            if len(self.check_results) > 100:
                self.check_results = self.check_results[-100:]

        except Exception as e:
            logger.error(f"Error logging health check result: {e}")

    def get_latest_health_status(self) -> Dict[str, Any]:
        """Get the latest health status."""
        return {
            "system_status": self.system_status,
            "last_result": asdict(self.check_results[-1]) if self.check_results else None,
            "component": self.component_name,
            "is_cloud": self.is_cloud
        }

    def start_monitoring(self, interval: int = 300):  # Default to 5 minutes
        """Start continuous health monitoring."""
        self.monitoring = True

        def monitor_loop():
            while self.monitoring:
                try:
                    self.check_health()

                    # Wait for the specified interval
                    for _ in range(interval):
                        if not self.monitoring:
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Error in health monitoring loop: {e}")
                    time.sleep(60)  # Wait a minute before retrying

        # Start monitoring in a separate thread
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()

        logger.info(f"Started health monitoring for {self.component_name} component (interval: {interval}s)")

    def stop_monitoring(self):
        """Stop health monitoring."""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=5)
        logger.info(f"Stopped health monitoring for {self.component_name} component")

    def get_health_report(self) -> str:
        """Generate a health report."""
        if not self.check_results:
            return "No health checks performed yet."

        latest = self.check_results[-1]

        report = f"""
Platinum Tier Health Report - {self.component_name} Component
{'='*60}

Timestamp: {latest.timestamp}
Status: {latest.status.value}
Message: {latest.message}

Resource Usage:
- CPU: {latest.details['resources'].get('cpu_percent', 'N/A')}%
- Memory: {latest.details['resources'].get('memory_percent', 'N/A')}%
- Disk: {latest.details['resources'].get('disk_percent', 'N/A')}%

Vault Status: {'OK' if latest.details['vault'].get('all_ok', False) else 'Issues found'}
Sync Status: {'Remote available' if latest.details['sync'].get('has_remote', False) else 'No remote'}

Last {min(5, len(self.check_results))} Checks:
"""

        for result in self.check_results[-5:]:
            report += f"- {result.timestamp}: {result.status.value}\n"

        return report

    def notify_if_unhealthy(self, webhook_url: Optional[str] = None):
        """Notify if the system is unhealthy."""
        if not self.check_results:
            return

        latest = self.check_results[-1]
        if latest.status in [ComponentStatus.FAILED, ComponentStatus.UNSTABLE]:
            message = f"⚠️ {self.component_name} component health issue detected!\nStatus: {latest.status.value}\nTime: {latest.timestamp}"

            logger.warning(f"Heath issue detected: {message}")

            # If webhook provided, send notification
            if webhook_url:
                try:
                    response = requests.post(webhook_url, json={"text": message})
                    if response.status_code != 200:
                        logger.error(f"Failed to send notification: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error sending notification: {e}")


def main():
    """Example usage of the health monitor."""
    import argparse

    parser = argparse.ArgumentParser(description="Platinum Tier Health Monitor")
    parser.add_argument("--vault-path", type=str, default="./vault",
                       help="Path to the vault directory")
    parser.add_argument("--cloud", action="store_true",
                       help="Run as cloud component")
    parser.add_argument("--interval", type=int, default=300,
                       help="Health check interval in seconds")

    args = parser.parse_args()

    # Initialize the health monitor
    monitor = HealthMonitor(vault_path=args.vault_path, is_cloud=args.cloud)

    print(f"Starting health monitoring for {'cloud' if args.cloud else 'local'} component...")
    print(f"Vault path: {args.vault_path}")
    print(f"Check interval: {args.interval}s")

    # Perform initial health check
    result = monitor.check_health()
    print(f"Initial health check: {result.status.value}")

    # Print initial report
    print(monitor.get_health_report())

    # Start continuous monitoring
    monitor.start_monitoring(interval=args.interval)

    try:
        # Keep running
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping health monitor...")
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()