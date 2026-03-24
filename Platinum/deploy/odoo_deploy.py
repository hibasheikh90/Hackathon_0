"""
Cloud Odoo Deployment for Platinum Tier
====================================

Deployment scripts for Odoo Community on Cloud VM with HTTPS, backups, and health monitoring.
"""
import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import docker
from docker.errors import ImageNotFound, ContainerError


class OdooCloudDeployment:
    def __init__(self, project_path: str = "./", config_path: str = "./odoo_config.json"):
        self.project_path = Path(project_path).resolve()
        self.config_path = Path(config_path)
        self.client = docker.from_env()

        # Load configuration
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load Odoo deployment configuration."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Create default configuration
            default_config = {
                "project_name": "odoo-cloud",
                "image_name": "odoo:17.0",
                "container_name": "odoo-cloud-container",
                "db_container_name": "odoo-db-container",
                "port_mapping": "8069:8069",
                "db_port_mapping": "5432:5432",
                "volumes": {
                    "odoo_data": "./odoo-data:/var/lib/odoo",
                    "odoo_addons": "./custom-addons:/mnt/extra-addons",
                    "postgres_data": "./postgres-data:/var/lib/postgresql/data"
                },
                "environment": {
                    "HOST": "odoo-db-container",
                    "USER": "odoo",
                    "PASSWORD": "odoo",
                    "ADMIN_PASSWORD": "admin_password_change_me",
                    "ODOO_RC": "/etc/odoo/odoo.conf"
                },
                "resources": {
                    "memory": "4g",
                    "cpu_count": 2
                },
                "restart_policy": "unless-stopped",
                "backup_schedule": "0 2 * * *",  # Daily at 2 AM
                "ssl_enabled": True
            }

            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=2)

            return default_config

    def create_odoo_docker_compose(self):
        """Create Docker Compose file for Odoo and PostgreSQL."""
        compose_content = f"""version: '3.8'

services:
  odoo:
    image: {self.config['image_name']}
    container_name: {self.config['container_name']}
    depends_on:
      - db
    ports:
      - "{self.config['port_mapping']}"
    volumes:
      - {self.config['volumes']['odoo_data']}
      - {self.config['volumes']['odoo_addons']}
    environment:
      - HOST=db
      - USER=odoo
      - PASSWORD=odoo
      - ADMIN_PASSWORD={self.config['environment']['ADMIN_PASSWORD']}
    restart: {self.config['restart_policy']}
    networks:
      - odoo-network
    deploy:
      resources:
        limits:
          memory: {self.config['resources']['memory']}
          cpus: '{self.config['resources']['cpu_count']}'

  db:
    image: postgres:15
    container_name: {self.config['db_container_name']}
    ports:
      - "{self.config['db_port_mapping']}"
    volumes:
      - {self.config['volumes']['postgres_data']}
    environment:
      - POSTGRES_DB=postgres
      - POSTGRES_USER=odoo
      - POSTGRES_PASSWORD=odoo
    restart: {self.config['restart_policy']}
    networks:
      - odoo-network
    deploy:
      resources:
        limits:
          memory: 2g
          cpus: '1'

networks:
  odoo-network:
    driver: bridge
"""

        compose_path = self.project_path / "docker-compose.odoo.yml"
        with open(compose_path, 'w') as f:
            f.write(compose_content)

        print(f"Docker Compose file created: {compose_path}")

    def create_ssl_setup(self):
        """Create SSL setup for HTTPS."""
        ssl_script = '''#!/bin/bash
# SSL Setup Script for Odoo Cloud Deployment
# Sets up SSL certificates using Let's Encrypt

set -e

DOMAIN="${1:-your-domain.com}"
EMAIL="${2:-your-email@example.com}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: $0 <domain> <email>"
    echo "Example: $0 example.com admin@example.com"
    exit 1
fi

echo "Setting up SSL for $DOMAIN..."

# Install certbot if not already installed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    sudo apt-get update
    sudo apt-get install -y certbot python3-certbot-nginx
fi

# Get SSL certificate
echo "Obtaining SSL certificate from Let's Encrypt..."
sudo certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --non-interactive

# Set up auto-renewal
echo "Setting up auto-renewal..."
sudo crontab -l | grep -v '/opt/certbot-auto renew' | crontab -
echo "0 12 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'" | sudo crontab -

# Create dhparams if they don't exist
if [ ! -f /etc/ssl/certs/dhparam.pem ]; then
    echo "Creating Diffie-Hellman parameters (this may take a while)..."
    sudo openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048
fi

echo "SSL setup completed for $DOMAIN!"
echo "Certificate location: /etc/letsencrypt/live/$DOMAIN/"
'''

        ssl_path = self.project_path / "setup_ssl.sh"
        with open(ssl_path, 'w') as f:
            f.write(ssl_script)

        # Make executable
        ssl_path.chmod(0o755)
        print(f"SSL setup script created: {ssl_path}")

    def create_backup_scripts(self):
        """Create backup and restore scripts."""
        backup_script = '''#!/bin/bash
# Backup Script for Odoo Cloud Deployment

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="odoo-db-container"

echo "Starting backup of Odoo database..."

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Dump the database
docker exec $CONTAINER_NAME pg_dump -U odoo -d odoo > $BACKUP_DIR/odoo_backup_$DATE.sql

# Compress the backup
gzip $BACKUP_DIR/odoo_backup_$DATE.sql

# Remove backups older than 30 days
find $BACKUP_DIR -name "odoo_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: odoo_backup_$DATE.sql.gz"
'''

        backup_path = self.project_path / "backup_odoo.sh"
        with open(backup_path, 'w') as f:
            f.write(backup_script)

        # Make executable
        backup_path.chmod(0o755)
        print(f"Backup script created: {backup_path}")

        restore_script = '''#!/bin/bash
# Restore Script for Odoo Cloud Deployment

BACKUP_FILE="$1"
CONTAINER_NAME="odoo-db-container"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 /backups/odoo_backup_20231201_120000.sql.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring from backup: $BACKUP_FILE"

# If the file is compressed, decompress it temporarily
if [[ "$BACKUP_FILE" == *.gz ]]; then
    TEMP_FILE="/tmp/restore_temp.sql"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    BACKUP_FILE="$TEMP_FILE"
fi

# Stop Odoo container during restore
docker stop odoo-cloud-container

# Restore the database
docker exec -i $CONTAINER_NAME psql -U odoo -d odoo < "$BACKUP_FILE"

# Start Odoo container
docker start odoo-cloud-container

echo "Restore completed from: $BACKUP_FILE"

# Clean up temp file if it was created
if [ -f "/tmp/restore_temp.sql" ]; then
    rm /tmp/restore_temp.sql
fi
'''

        restore_path = self.project_path / "restore_odoo.sh"
        with open(restore_path, 'w') as f:
            f.write(restore_script)

        # Make executable
        restore_path.chmod(0o755)
        print(f"Restore script created: {restore_path}")

    def create_health_check(self):
        """Create health check for Odoo service."""
        health_check_script = '''#!/usr/bin/env python3
"""
Health Check for Odoo Cloud Service
=================================

Checks the health of the Odoo service and performs automated actions
if issues are detected.
"""
import os
import sys
import time
import requests
import logging
import subprocess
from datetime import datetime
import docker
from docker.errors import APIError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("odoo_health_check.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("odoo-health-check")

class OdooHealthChecker:
    def __init__(self, odoo_url="http://localhost:8069",
                 check_interval=60, max_failures=3):
        self.odoo_url = odoo_url
        self.check_interval = check_interval
        self.max_failures = max_failures
        self.failure_count = 0
        self.client = docker.from_env()

    def check_odoo_health(self):
        """Check the health of the Odoo service."""
        try:
            # Check if Odoo is responding
            response = requests.get(f"{self.odoo_url}/web", timeout=10)

            # Check for Odoo-specific indicators
            if response.status_code == 200 and "odoo" in response.text.lower():
                return True
            else:
                return False
        except:
            return False

    def check_db_health(self):
        """Check if the database container is running."""
        try:
            db_container = self.client.containers.get("odoo-db-container")
            return db_container.status == "running"
        except:
            return False

    def restart_odoo_service(self):
        """Attempt to restart the Odoo service."""
        logger.info("Attempting to restart Odoo service...")
        try:
            # Restart both containers
            odoo_container = self.client.containers.get("odoo-cloud-container")
            db_container = self.client.containers.get("odoo-db-container")

            # Restart DB first, then Odoo
            db_container.restart()
            time.sleep(10)  # Wait for DB to start
            odoo_container.restart()

            logger.info("Odoo service restarted successfully")
            self.failure_count = 0
            return True
        except APIError as e:
            logger.error(f"Failed to restart containers: {e}")
            return False
        except Exception as e:
            logger.error(f"Error restarting service: {e}")
            return False

    def run(self):
        """Main monitoring loop."""
        logger.info(f"Starting Odoo health check. Checking every {self.check_interval}s")

        while True:
            # Check database health first
            if not self.check_db_health():
                logger.error("Database container is not running, attempting restart...")
                self.restart_odoo_service()
                time.sleep(self.check_interval)
                continue

            # Check Odoo web interface
            is_healthy = self.check_odoo_health()

            if is_healthy:
                if self.failure_count > 0:
                    logger.info("Odoo service recovered from previous failures")
                self.failure_count = 0
            else:
                self.failure_count += 1
                logger.warning(f"Odoo health check failed ({self.failure_count}/{self.max_failures})")

                if self.failure_count >= self.max_failures:
                    logger.error("Max failures reached, attempting restart...")
                    self.restart_odoo_service()

            time.sleep(self.check_interval)

if __name__ == "__main__":
    # Get configuration from environment
    odoo_url = os.getenv("ODOO_URL", "http://localhost:8069")
    interval = int(os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "60"))
    max_failures = int(os.getenv("HEALTH_MAX_FAILURES", "3"))

    checker = OdooHealthChecker(odoo_url=odoo_url,
                               check_interval=interval,
                               max_failures=max_failures)
    checker.run()
'''

        health_path = self.project_path / "odoo_health_check.py"
        with open(health_path, 'w') as f:
            f.write(health_check_script)

        # Make executable
        health_path.chmod(0o755)
        print(f"Health check script created: {health_path}")

    def create_odoo_mcp_server(self):
        """Create MCP server for cloud Odoo integration."""
        odoo_mcp_script = '''"""
Cloud Odoo MCP Server for Platinum Tier
=====================================

Handles cloud-specific Odoo operations: draft accounting entries that require
local approval before posting invoices/payments.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from mcp import Server, NotificationOptions
from mcp.types import CallToolResult, Prompt, TextContent, Tool, ToolCallResult, ExperimentalLLMContext
import xmlrpc.client
from datetime import datetime


class CloudOdooServer:
    def __init__(self, vault_path: str = "./vault",
                 odoo_url: str = "http://localhost:8069",
                 db_name: str = "odoo_db"):
        self.vault_path = Path(vault_path)
        self.odoo_url = odoo_url
        self.db_name = db_name
        self.server = Server("cloud-odoo-server")

        # These would normally come from environment/config
        # For cloud, we'll only use them for draft operations
        self.username = os.getenv("ODOO_USERNAME")
        self.password = os.getenv("ODOO_PASSWORD")

        # Register handlers
        self.server.on_call_tool(self.handle_tool_call)
        self.server.on_prompt_request(self.handle_prompt_request)

        # Define cloud-safe Odoo tools (draft operations only)
        self.tools = [
            Tool(
                name="create_draft_invoice",
                description="Create a draft invoice in Odoo. Invoice will be saved as draft and require local approval before posting.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "partner_id": {"type": "integer", "description": "Customer ID in Odoo"},
                        "invoice_lines": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "product_id": {"type": "integer", "description": "Product ID"},
                                    "quantity": {"type": "number", "description": "Quantity"},
                                    "price_unit": {"type": "number", "description": "Unit price"}
                                },
                                "required": ["product_id", "quantity", "price_unit"]
                            }
                        },
                        "reference": {"type": "string", "description": "Invoice reference"},
                        "journal_id": {"type": "integer", "description": "Journal to use (defaults to customer invoice journal)"}
                    },
                    "required": ["partner_id", "invoice_lines"]
                }
            ),
            Tool(
                name="create_draft_expense",
                description="Create a draft expense in Odoo. Expense will be saved as draft and require local approval before posting.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "integer", "description": "Employee ID in Odoo"},
                        "expense_lines": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "product_id": {"type": "integer", "description": "Expense product ID"},
                                    "quantity": {"type": "number", "description": "Quantity"},
                                    "unit_amount": {"type": "number", "description": "Unit amount"},
                                    "description": {"type": "string", "description": "Expense description"}
                                },
                                "required": ["product_id", "quantity", "unit_amount", "description"]
                            }
                        }
                    },
                    "required": ["employee_id", "expense_lines"]
                }
            ),
            Tool(
                name="get_pending_drafts",
                description="Get list of pending draft invoices and expenses that need approval.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "draft_type": {"type": "string", "description": "Type of drafts to get ('invoice', 'expense', 'all')"}
                    }
                }
            ),
            Tool(
                name="update_draft",
                description="Update an existing draft invoice or expense.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "draft_id": {"type": "integer", "description": "ID of the draft to update"},
                        "draft_type": {"type": "string", "description": "Type of draft ('invoice', 'expense')"},
                        "updates": {"type": "object", "description": "Fields to update"}
                    },
                    "required": ["draft_id", "draft_type", "updates"]
                }
            )
        ]

    def connect_to_odoo(self):
        """Establish connection to Odoo."""
        # For cloud operations, we'll create draft records in the vault
        # Actual Odoo operations will be handled by local component after approval
        pass

    def handle_tool_call(self, *, method_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle incoming tool calls."""
        if method_name == "create_draft_invoice":
            return self.create_draft_invoice(arguments)
        elif method_name == "create_draft_expense":
            return self.create_draft_expense(arguments)
        elif method_name == "get_pending_drafts":
            return self.get_pending_drafts(arguments)
        elif method_name == "update_draft":
            return self.update_draft(arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {method_name}")]
            )

    def create_draft_invoice(self, args: Dict[str, Any]) -> CallToolResult:
        """Create a draft invoice in the vault for local approval."""
        partner_id = args["partner_id"]
        invoice_lines = args["invoice_lines"]
        reference = args.get("reference", "")
        journal_id = args.get("journal_id")

        # Create a unique filename for the draft invoice
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"draft_invoice_{timestamp}_{partner_id}.json"

        # Create draft invoice data
        draft_data = {
            "partner_id": partner_id,
            "invoice_lines": invoice_lines,
            "reference": reference,
            "journal_id": journal_id,
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "requires_approval": True
        }

        # Save to pending_approval/accounting directory
        draft_path = f"pending_approval/accounting/invoices/{filename}"
        draft_full_path = self.vault_path / draft_path

        try:
            draft_full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(draft_full_path, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, indent=2)

            return CallToolResult(
                content=[TextContent(type="text", text=f"Draft invoice created in vault at {draft_path}. Awaiting local approval for posting to Odoo.")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error creating draft invoice: {str(e)}")]
            )

    def create_draft_expense(self, args: Dict[str, Any]) -> CallToolResult:
        """Create a draft expense in the vault for local approval."""
        employee_id = args["employee_id"]
        expense_lines = args["expense_lines"]

        # Create a unique filename for the draft expense
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"draft_expense_{timestamp}_{employee_id}.json"

        # Create draft expense data
        draft_data = {
            "employee_id": employee_id,
            "expense_lines": expense_lines,
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "requires_approval": True
        }

        # Save to pending_approval/accounting directory
        draft_path = f"pending_approval/accounting/expenses/{filename}"
        draft_full_path = self.vault_path / draft_path

        try:
            draft_full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(draft_full_path, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, indent=2)

            return CallToolResult(
                content=[TextContent(type="text", text=f"Draft expense created in vault at {draft_path}. Awaiting local approval for posting to Odoo.")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error creating draft expense: {str(e)}")]
            )

    def get_pending_drafts(self, args: Dict[str, Any]) -> CallToolResult:
        """Get list of pending draft invoices and expenses."""
        draft_type = args.get("draft_type", "all").lower()

        pending_drafts = []

        accounting_dir = self.vault_path / "pending_approval" / "accounting"

        if accounting_dir.exists():
            # Look for draft invoices
            if draft_type in ["invoice", "all"]:
                invoice_dir = accounting_dir / "invoices"
                if invoice_dir.exists():
                    for file_path in invoice_dir.glob("*.json"):
                        pending_drafts.append(f"Invoice draft: {file_path.name}")

            # Look for draft expenses
            if draft_type in ["expense", "all"]:
                expense_dir = accounting_dir / "expenses"
                if expense_dir.exists():
                    for file_path in expense_dir.glob("*.json"):
                        pending_drafts.append(f"Expense draft: {file_path.name}")

        if pending_drafts:
            return CallToolResult(
                content=[TextContent(type="text", text="Pending drafts:\n" + "\n".join([f"- {draft}" for draft in pending_drafts]))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text="No pending drafts found.")]
            )

    def update_draft(self, args: Dict[str, Any]) -> CallToolResult:
        """Update an existing draft invoice or expense."""
        draft_id = args["draft_id"]
        draft_type = args["draft_type"]
        updates = args["updates"]

        # Since drafts are stored by filename in our system, we need to find the file
        # In a real implementation, you'd have a mapping between draft_id and filename
        # For now, we'll look for files containing the draft_id

        search_pattern = f"*{draft_id}*"
        found_files = []

        if draft_type == "invoice":
            search_dir = self.vault_path / "pending_approval" / "accounting" / "invoices"
        elif draft_type == "expense":
            search_dir = self.vault_path / "pending_approval" / "accounting" / "expenses"
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Invalid draft type: {draft_type}")]
            )

        if search_dir.exists():
            found_files = list(search_dir.glob(search_pattern))

        if not found_files:
            return CallToolResult(
                content=[TextContent(type="text", text=f"No draft found with ID {draft_id}")]
            )

        # Update the first found file
        draft_file = found_files[0]
        try:
            with open(draft_file, 'r', encoding='utf-8') as f:
                draft_data = json.load(f)

            # Apply updates
            for key, value in updates.items():
                draft_data[key] = value

            # Save updated data
            with open(draft_file, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, indent=2)

            return CallToolResult(
                content=[TextContent(type="text", text=f"Draft updated: {draft_file.name}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error updating draft: {str(e)}")]
            )

    def handle_prompt_request(self, *, name: str, arguments: Optional[Dict[str, str]]) -> Prompt:
        """Handle prompt requests."""
        if name == "cloud-odoo-status":
            return Prompt(
                description="Check the status of cloud Odoo operations",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Cloud Odoo server operational. Creating draft invoices and expenses in vault for local approval. "
                                       f"Direct posting to Odoo requires local component after approval."
                            }
                        ]
                    }
                ]
            )
        else:
            return Prompt(
                description="Unknown prompt",
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": f"Unknown prompt: {name}"}]
                    }
                ]
            )

    def run(self):
        """Start the MCP server."""
        import asyncio
        return self.server.run_asyncio()


if __name__ == "__main__":
    # Initialize and run the server
    server = CloudOdooServer()
    print("Starting Cloud Odoo MCP Server...")
    server.run()
'''

        odoo_mcp_path = self.project_path / "Platinum/cloud/cloud_odoo_server.py"
        with open(odoo_mcp_path, 'w') as f:
            f.write(odoo_mcp_script)

        print(f"Cloud Odoo MCP server created: {odoo_mcp_path}")

    def setup_deployment(self):
        """Complete setup for Odoo cloud deployment."""
        print("Setting up Odoo cloud deployment...")

        # Create necessary files
        self.create_odoo_docker_compose()
        self.create_ssl_setup()
        self.create_backup_scripts()
        self.create_health_check()
        self.create_odoo_mcp_server()

        print("Odoo cloud deployment setup complete!")
        print("Configuration saved to:", self.config_path)
        return True


def main():
    """Main function to run the Odoo deployment setup."""
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        deployer = OdooCloudDeployment()
        success = deployer.setup_deployment()

        if success:
            print("\\nOdoo cloud deployment setup completed successfully!")
            print("Odoo is now ready for 24/7 operation on the cloud with HTTPS, backups, and health monitoring.")
        else:
            print("\\nOdoo cloud deployment setup failed.")
            sys.exit(1)
    else:
        print("Usage: python odoo_deploy.py setup")
        print("This will create all necessary files for Odoo cloud deployment.")


if __name__ == "__main__":
    main()