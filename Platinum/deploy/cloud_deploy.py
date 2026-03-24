"""
Cloud Deployment Scripts for Platinum Tier
========================================

Deployment scripts for running the AI Employee on a cloud VM with 24/7 operation,
health monitoring, and automatic restarts.
"""
import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import time
import signal
import psutil
import docker
from docker.errors import ImageNotFound, ContainerError


class CloudDeploymentManager:
    def __init__(self, project_path: str = "./", config_path: str = "./cloud_config.json"):
        self.project_path = Path(project_path).resolve()
        self.config_path = Path(config_path)
        self.client = docker.from_env()

        # Load configuration
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load deployment configuration."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Create default configuration
            default_config = {
                "project_name": "ai-employee-cloud",
                "image_name": "ai-employee-cloud:latest",
                "container_name": "ai-employee-cloud-container",
                "vault_volume": "./vault:/app/vault",
                "port_mappings": {
                    "mcp_servers": "8080:8080"
                },
                "environment": {
                    "VAULT_PATH": "/app/vault",
                    "ENVIRONMENT": "cloud",
                    "SYNC_INTERVAL_MINUTES": "10",
                    "HEALTH_CHECK_INTERVAL_SECONDS": "60"
                },
                "resources": {
                    "memory": "2g",
                    "cpu_count": 1
                },
                "restart_policy": "unless-stopped",
                "health_check_endpoint": "/health"
            }

            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=2)

            return default_config

    def create_dockerfile(self):
        """Create Dockerfile for cloud deployment."""
        dockerfile_content = """# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create vault directory
RUN mkdir -p ./vault

# Expose ports for MCP servers
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the cloud AI employee
CMD ["python", "run_cloud.py"]
"""

        dockerfile_path = self.project_path / "Dockerfile.cloud"
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)

        print(f"Dockerfile created: {dockerfile_path}")

    def create_cloud_startup_script(self):
        """Create startup script for cloud operations."""
        startup_script = '''#!/usr/bin/env python3
"""
Cloud Startup Script for AI Employee
===================================

Entry point for the cloud component of the AI Employee.
"""
import os
import sys
import time
import signal
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("cloud_runtime.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cloud-ai-employee")

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received. Cleaning up...")
    # Perform cleanup operations here
    sys.exit(0)

def main():
    """Main entry point for cloud AI employee."""
    logger.info("Starting Cloud AI Employee...")

    # Set environment variables specific to cloud
    os.environ["ENVIRONMENT"] = "cloud"
    os.environ["AGENT_TYPE"] = "cloud"

    # Initialize vault sync
    from Platinum.sync.vault_sync import VaultSyncManager
    from Platinum.sync.claim_by_move import ClaimByMoveSystem

    vault_path = os.getenv("VAULT_PATH", "./vault")
    remote_repo = os.getenv("VAULT_REMOTE_REPO")

    if not remote_repo:
        logger.error("VAULT_REMOTE_REPO environment variable not set")
        sys.exit(1)

    logger.info(f"Initializing vault sync with remote: {remote_repo}")
    sync_manager = VaultSyncManager(vault_path=vault_path, remote_repo=remote_repo)
    sync_manager.initialize_git_repo()

    # Initialize claim-by-move system
    claim_system = ClaimByMoveSystem(vault_path=vault_path)

    # Initialize MCP servers
    from Platinum.cloud.cloud_vault_server import CloudVaultServer
    from Platinum.cloud.cloud_email_server import CloudEmailServer

    vault_server = CloudVaultServer(vault_path=vault_path)
    email_server = CloudEmailServer(vault_path=vault_path)

    # Start MCP servers in background threads
    import threading

    def start_vault_server():
        logger.info("Starting Cloud Vault Server...")
        try:
            vault_server.run()
        except Exception as e:
            logger.error(f"Cloud Vault Server error: {e}")

    def start_email_server():
        logger.info("Starting Cloud Email Server...")
        try:
            email_server.run()
        except Exception as e:
            logger.error(f"Cloud Email Server error: {e}")

    # Start servers in background
    vault_thread = threading.Thread(target=start_vault_server, daemon=True)
    email_thread = threading.Thread(target=start_email_server, daemon=True)

    vault_thread.start()
    email_thread.start()

    # Main loop for cloud operations
    sync_interval = int(os.getenv("SYNC_INTERVAL_MINUTES", "10")) * 60  # Convert to seconds
    last_sync = 0

    logger.info(f"Cloud AI Employee started. Sync interval: {sync_interval}s")

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while True:
        current_time = time.time()

        # Periodic vault sync
        if current_time - last_sync >= sync_interval:
            logger.info("Performing periodic vault sync...")
            try:
                success = sync_manager.sync_vault()
                if success:
                    logger.info("Vault sync completed successfully")

                    # Process available tasks
                    available_tasks = claim_system.get_available_items("cloud")
                    logger.info(f"Found {len(available_tasks)} available tasks for cloud processing")

                    # Process each available task
                    for task in available_tasks:
                        success, msg = claim_system.claim_item(task, "cloud")
                        if success:
                            logger.info(f"Claimed task: {msg}")

                            # Process the task (this is where you'd add specific task processing logic)
                            # For now, we'll just mark it as done after processing
                            claim_system.release_claim(task, "cloud", "done")
                        else:
                            logger.warning(f"Failed to claim task: {msg}")

                last_sync = current_time
            except Exception as e:
                logger.error(f"Error during vault sync: {e}")

        # Sleep before next iteration
        time.sleep(min(60, sync_interval))  # Check every minute or at sync interval, whichever is smaller

if __name__ == "__main__":
    main()
'''

        script_path = self.project_path / "run_cloud.py"
        with open(script_path, 'w') as f:
            f.write(startup_script)

        # Make executable
        script_path.chmod(0o755)
        print(f"Cloud startup script created: {script_path}")

    def create_systemd_service(self):
        """Create systemd service file for Linux deployment."""
        service_content = f"""[Unit]
Description=AI Employee Cloud Service
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'ai-employee')}
WorkingDirectory={self.project_path}
Environment=VAULT_REMOTE_REPO={self.config.get('vault_remote_repo', 'https://github.com/user/vault.git')}
Environment=ENVIRONMENT=cloud
ExecStart=/usr/bin/python3 {self.project_path}/run_cloud.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

        service_path = "/etc/systemd/system/ai-employee-cloud.service"  # This would be created in deployment
        print(f"SystemD service content for: {service_path}")
        print(service_content)

        return service_content

    def create_health_monitor(self):
        """Create health monitoring script."""
        monitor_script = '''#!/usr/bin/env python3
"""
Health Monitor for Cloud AI Employee
===================================

Monitors the health of the cloud AI employee and performs automated actions
if issues are detected.
"""
import os
import sys
import time
import requests
import logging
import subprocess
from datetime import datetime
import psutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("health_monitor.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("health-monitor")

class HealthMonitor:
    def __init__(self, health_endpoint="http://localhost:8080/health",
                 check_interval=60, max_failures=3):
        self.health_endpoint = health_endpoint
        self.check_interval = check_interval
        self.max_failures = max_failures
        self.failure_count = 0

    def check_health(self):
        """Check the health of the AI employee service."""
        try:
            response = requests.get(self.health_endpoint, timeout=10)
            return response.status_code == 200
        except:
            return False

    def check_process_health(self):
        """Check if the main process is running."""
        # Look for Python processes running our main script
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'])
                    if 'run_cloud.py' in cmdline:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def restart_service(self):
        """Attempt to restart the service."""
        logger.info("Attempting to restart the AI employee service...")
        try:
            # This would vary depending on deployment method
            # For systemd:
            # result = subprocess.run(['sudo', 'systemctl', 'restart', 'ai-employee-cloud'],
            #                       capture_output=True, text=True)

            # For Docker:
            result = subprocess.run(['docker', 'restart', 'ai-employee-cloud-container'],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Service restarted successfully")
                self.failure_count = 0
                return True
            else:
                logger.error(f"Failed to restart service: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error restarting service: {e}")
            return False

    def run(self):
        """Main monitoring loop."""
        logger.info(f"Starting health monitor. Checking every {self.check_interval}s")

        while True:
            # Check if main process is running
            if not self.check_process_health():
                logger.error("Main process not running, attempting restart...")
                self.restart_service()
                time.sleep(self.check_interval)
                continue

            # Check health endpoint
            is_healthy = self.check_health()

            if is_healthy:
                if self.failure_count > 0:
                    logger.info("Service recovered from previous failures")
                self.failure_count = 0
            else:
                self.failure_count += 1
                logger.warning(f"Health check failed ({self.failure_count}/{self.max_failures})")

                if self.failure_count >= self.max_failures:
                    logger.error("Max failures reached, attempting restart...")
                    self.restart_service()

            time.sleep(self.check_interval)

if __name__ == "__main__":
    # Get configuration from environment
    endpoint = os.getenv("HEALTH_ENDPOINT", "http://localhost:8080/health")
    interval = int(os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "60"))
    max_failures = int(os.getenv("HEALTH_MAX_FAILURES", "3"))

    monitor = HealthMonitor(health_endpoint=endpoint,
                          check_interval=interval,
                          max_failures=max_failures)
    monitor.run()
'''

        monitor_path = self.project_path / "health_monitor.py"
        with open(monitor_path, 'w') as f:
            f.write(monitor_script)

        # Make executable
        monitor_path.chmod(0o755)
        print(f"Health monitor script created: {monitor_path}")

    def build_docker_image(self):
        """Build the Docker image for cloud deployment."""
        try:
            # Create Dockerfile if it doesn't exist
            if not (self.project_path / "Dockerfile.cloud").exists():
                self.create_dockerfile()

            # Build the image
            logger = logging.getLogger("build")
            logger.info(f"Building Docker image: {self.config['image_name']}")

            image, build_logs = self.client.images.build(
                path=str(self.project_path),
                dockerfile="Dockerfile.cloud",
                tag=self.config['image_name'],
                rm=True
            )

            # Print build logs
            for chunk in build_logs:
                if 'stream' in chunk:
                    logger.info(chunk['stream'].strip())

            logger.info(f"Image built successfully: {self.config['image_name']}")
            return True

        except ImageNotFound as e:
            logger.error(f"Base image not found: {e}")
            return False
        except Exception as e:
            logger.error(f"Error building image: {e}")
            return False

    def deploy_container(self):
        """Deploy the container with the specified configuration."""
        try:
            # Stop and remove existing container if it exists
            try:
                existing_container = self.client.containers.get(self.config['container_name'])
                existing_container.stop()
                existing_container.remove()
                print(f"Removed existing container: {self.config['container_name']}")
            except:
                pass  # Container doesn't exist, which is fine

            # Prepare port mappings
            ports = {}
            for service, mapping in self.config['port_mappings'].items():
                host_port, container_port = mapping.split(':')
                ports[f"{container_port}/tcp"] = int(host_port)

            # Prepare environment variables
            environment = self.config['environment'].copy()
            if 'VAULT_REMOTE_REPO' in os.environ:
                environment['VAULT_REMOTE_REPO'] = os.environ['VAULT_REMOTE_REPO']

            # Run the container
            container = self.client.containers.run(
                image=self.config['image_name'],
                name=self.config['container_name'],
                volumes={
                    str(Path(self.config['vault_volume']).parent.absolute()): {
                        'bind': '/app/vault',
                        'mode': 'rw'
                    }
                },
                ports=ports,
                environment=environment,
                detach=True,
                restart_policy={"Name": self.config['restart_policy']},
                mem_limit=self.config['resources']['memory'],
                cpu_count=self.config['resources']['cpu_count'],
                auto_remove=False
            )

            print(f"Container deployed successfully: {self.config['container_name']}")
            print(f"Container ID: {container.id[:12]}")

            # Print container logs for verification
            print("Container logs:")
            print(container.logs().decode('utf-8'))

            return True

        except ContainerError as e:
            print(f"Container error: {e}")
            return False
        except Exception as e:
            print(f"Error deploying container: {e}")
            return False

    def setup_deployment(self):
        """Complete setup for cloud deployment."""
        print("Setting up cloud deployment...")

        # Create necessary files
        self.create_dockerfile()
        self.create_cloud_startup_script()
        self.create_health_monitor()

        # Build Docker image
        if not self.build_docker_image():
            print("Failed to build Docker image")
            return False

        # Deploy container
        if not self.deploy_container():
            print("Failed to deploy container")
            return False

        print("Cloud deployment setup complete!")
        print("Configuration saved to:", self.config_path)
        return True


def main():
    """Main function to run the deployment setup."""
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        deployer = CloudDeploymentManager()
        success = deployer.setup_deployment()

        if success:
            print("\\nCloud deployment setup completed successfully!")
            print("The AI Employee is now ready for 24/7 operation on the cloud.")
        else:
            print("\\nCloud deployment setup failed.")
            sys.exit(1)
    else:
        print("Usage: python cloud_deploy.py setup")
        print("This will create all necessary files for cloud deployment.")


if __name__ == "__main__":
    main()
'''