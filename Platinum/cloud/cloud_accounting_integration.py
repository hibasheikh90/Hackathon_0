"""
Cloud Agent Integration with Odoo for Platinum Tier
================================================

Integrates the cloud agent with Odoo via MCP for draft-only accounting actions
with Local approval for posting invoices/payments.
"""
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import time
import threading

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class CloudAccountingIntegration:
    """
    Manages the integration between the cloud agent and Odoo for accounting operations.
    Handles draft creation and approval workflows according to Platinum Tier requirements.
    """
    def __init__(self, vault_path: str = "./vault", odoo_url: str = "http://localhost:8069"):
        self.vault_path = Path(vault_path)
        self.odoo_url = odoo_url

        # Ensure required directories exist
        required_dirs = [
            "pending_approval/accounting/invoices",
            "pending_approval/accounting/expenses",
            "needs_action/accounting",
            "done/accounting"
        ]

        for dir_path in required_dirs:
            (self.vault_path / dir_path).mkdir(parents=True, exist_ok=True)

    def process_accounting_requests(self):
        """
        Process accounting requests that came in through the cloud component.
        Creates draft entries that require local approval.
        """
        # Look for accounting requests in needs_action
        accounting_requests_dir = self.vault_path / "needs_action" / "accounting"

        if not accounting_requests_dir.exists():
            return []

        processed_requests = []

        for request_file in accounting_requests_dir.glob("*.md"):
            try:
                content = request_file.read_text(encoding='utf-8')

                # Parse the request to determine type and details
                request_data = self._parse_accounting_request(content)

                if request_data:
                    # Create appropriate draft based on request type
                    if request_data['type'] == 'invoice':
                        result = self.create_draft_invoice(request_data)
                    elif request_data['type'] == 'expense':
                        result = self.create_draft_expense(request_data)
                    else:
                        result = {'success': False, 'message': f"Unknown request type: {request_data['type']}"}

                    if result['success']:
                        # Move processed request to done
                        done_path = self.vault_path / "done" / "accounting" / request_file.name
                        request_file.rename(done_path)

                        processed_requests.append({
                            'request': request_file.name,
                            'result': result
                        })
                    else:
                        print(f"Failed to process request {request_file.name}: {result['message']}")

            except Exception as e:
                print(f"Error processing accounting request {request_file.name}: {e}")

        return processed_requests

    def _parse_accounting_request(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Parse an accounting request from the vault to extract relevant information.
        """
        lines = content.split('\n')
        request_data = {
            'type': None,
            'details': {}
        }

        current_section = ''
        for line in lines:
            line = line.strip()

            if line.startswith('#'):
                # Header line - determine request type
                if 'invoice' in line.lower():
                    request_data['type'] = 'invoice'
                elif 'expense' in line.lower():
                    request_data['type'] = 'expense'
                elif 'payment' in line.lower():
                    request_data['type'] = 'payment'
            elif ':' in line and not line.startswith('*') and not line.startswith('-'):
                # Key-value pair
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower().replace(' ', '_')
                    value = parts[1].strip()

                    # Try to convert to appropriate type
                    if value.isdigit():
                        value = int(value)
                    elif self._is_float(value):
                        value = float(value)

                    request_data['details'][key] = value

        return request_data if request_data['type'] else None

    def _is_float(self, value: str) -> bool:
        """Check if a string represents a float value."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def create_draft_invoice(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a draft invoice in the vault that requires local approval.
        """
        details = request_data['details']

        # Validate required fields
        required_fields = ['customer', 'amount']
        missing_fields = [field for field in required_fields if field not in details]

        if missing_fields:
            return {
                'success': False,
                'message': f"Missing required fields: {', '.join(missing_fields)}"
            }

        # Create draft invoice data
        draft_invoice = {
            'type': 'invoice',
            'customer': details.get('customer'),
            'amount': details.get('amount'),
            'currency': details.get('currency', 'USD'),
            'description': details.get('description', ''),
            'due_date': details.get('due_date'),
            'reference': details.get('reference', ''),
            'status': 'draft',
            'created_at': datetime.now().isoformat(),
            'requires_local_approval': True,
            'cloud_created': True
        }

        # Add line items if provided
        if 'line_items' in details:
            draft_invoice['line_items'] = details['line_items']

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        customer_ref = str(details.get('customer', 'unknown')).replace(' ', '_').replace('/', '_')
        filename = f"draft_invoice_{timestamp}_{customer_ref}.json"

        # Save draft to pending approval directory
        draft_path = self.vault_path / "pending_approval" / "accounting" / "invoices" / filename

        try:
            with open(draft_path, 'w', encoding='utf-8') as f:
                json.dump(draft_invoice, f, indent=2)

            return {
                'success': True,
                'message': f'Draft invoice created at {draft_path}',
                'draft_id': filename
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error saving draft invoice: {str(e)}'
            }

    def create_draft_expense(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a draft expense in the vault that requires local approval.
        """
        details = request_data['details']

        # Validate required fields
        required_fields = ['employee', 'amount', 'category']
        missing_fields = [field for field in required_fields if field not in details]

        if missing_fields:
            return {
                'success': False,
                'message': f"Missing required fields: {', '.join(missing_fields)}"
            }

        # Create draft expense data
        draft_expense = {
            'type': 'expense',
            'employee': details.get('employee'),
            'amount': details.get('amount'),
            'currency': details.get('currency', 'USD'),
            'category': details.get('category'),
            'description': details.get('description', ''),
            'date_incurred': details.get('date', datetime.now().isoformat().split('T')[0]),
            'receipt_attached': details.get('receipt_attached', False),
            'status': 'draft',
            'created_at': datetime.now().isoformat(),
            'requires_local_approval': True,
            'cloud_created': True
        }

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        employee_ref = str(details.get('employee', 'unknown')).replace(' ', '_').replace('/', '_')
        filename = f"draft_expense_{timestamp}_{employee_ref}.json"

        # Save draft to pending approval directory
        draft_path = self.vault_path / "pending_approval" / "accounting" / "expenses" / filename

        try:
            with open(draft_path, 'w', encoding='utf-8') as f:
                json.dump(draft_expense, f, indent=2)

            return {
                'success': True,
                'message': f'Draft expense created at {draft_path}',
                'draft_id': filename
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error saving draft expense: {str(e)}'
            }

    def get_pending_accounting_drafts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all pending accounting drafts that need local approval.
        """
        pending_drafts = {
            'invoices': [],
            'expenses': []
        }

        # Get pending invoices
        invoice_dir = self.vault_path / "pending_approval" / "accounting" / "invoices"
        if invoice_dir.exists():
            for file_path in invoice_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        draft_data = json.load(f)
                        draft_data['file_path'] = str(file_path.relative_to(self.vault_path))
                        pending_drafts['invoices'].append(draft_data)
                except Exception as e:
                    print(f"Error reading invoice draft {file_path}: {e}")

        # Get pending expenses
        expense_dir = self.vault_path / "pending_approval" / "accounting" / "expenses"
        if expense_dir.exists():
            for file_path in expense_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        draft_data = json.load(f)
                        draft_data['file_path'] = str(file_path.relative_to(self.vault_path))
                        pending_drafts['expenses'].append(draft_data)
                except Exception as e:
                    print(f"Error reading expense draft {file_path}: {e}")

        return pending_drafts

    def sync_with_local_odoo(self, approved_drafts: List[str]):
        """
        Sync approved drafts with the local Odoo instance.
        This would be called by the local component after approval.
        """
        # This method would be called by the local component after approval
        # For the cloud component, we just track what needs to be synced
        synced_drafts = []

        for draft_path in approved_drafts:
            draft_full_path = self.vault_path / draft_path

            if draft_full_path.exists():
                try:
                    # Read the approved draft
                    with open(draft_full_path, 'r', encoding='utf-8') as f:
                        draft_data = json.load(f)

                    # Update status to indicate it's approved and ready for posting
                    draft_data['status'] = 'approved'
                    draft_data['approved_at'] = datetime.now().isoformat()
                    draft_data['ready_for_posting'] = True

                    # Save the updated draft
                    with open(draft_full_path, 'w', encoding='utf-8') as f:
                        json.dump(draft_data, f, indent=2)

                    synced_drafts.append({
                        'draft_id': draft_path,
                        'status': 'updated_to_approved'
                    })

                except Exception as e:
                    synced_drafts.append({
                        'draft_id': draft_path,
                        'status': 'error',
                        'error': str(e)
                    })

        return synced_drafts

    def run_continuous_processing(self, interval_seconds: int = 300):
        """
        Run continuous processing of accounting requests.
        """
        print(f"Starting continuous accounting processing (checking every {interval_seconds}s)...")

        try:
            while True:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Processing accounting requests...")

                processed = self.process_accounting_requests()
                if processed:
                    print(f"Processed {len(processed)} accounting requests")
                    for req in processed:
                        print(f"  - {req['request']}: {req['result']['message']}")
                else:
                    print("No new accounting requests to process")

                # Check for any special accounting tasks that need attention
                pending_drafts = self.get_pending_accounting_drafts()
                total_pending = len(pending_drafts['invoices']) + len(pending_drafts['expenses'])

                print(f"Total pending drafts awaiting local approval: {total_pending}")

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\\nAccounting processing stopped by user.")


def main():
    """
    Main function to demonstrate the Cloud Accounting Integration.
    """
    print("Initializing Cloud Agent Integration with Odoo...")

    # Initialize the integration
    integration = CloudAccountingIntegration()

    print("Cloud Accounting Integration initialized successfully!")
    print(f"Vault path: {integration.vault_path}")
    print(f"Odoo URL: {integration.odoo_url}")

    # Example: Show current pending drafts
    pending = integration.get_pending_accounting_drafts()
    print(f"\\nCurrently pending drafts:")
    print(f"  - Invoices: {len(pending['invoices'])}")
    print(f"  - Expenses: {len(pending['expenses'])}")

    print("\\nIntegration ready. The cloud component will create draft accounting entries")
    print("that require local approval before posting to Odoo.")


if __name__ == "__main__":
    main()