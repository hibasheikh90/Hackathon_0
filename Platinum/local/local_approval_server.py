"""
Local MCP Server for Approval and Sensitive Operations
======================================================

Handles local-specific operations: approvals, payments, WhatsApp, final actions.
Follows the platinum tier architecture with proper security boundaries.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from mcp import Server, NotificationOptions
from mcp.types import CallToolResult, Prompt, TextContent, Tool, ToolCallResult, ExperimentalLLMContext


class LocalApprovalServer:
    def __init__(self, vault_path: str = "./vault"):
        self.vault_path = Path(vault_path)
        self.server = Server("local-approval-server")

        # Register handlers
        self.server.on_call_tool(self.handle_tool_call)
        self.server.on_prompt_request(self.handle_prompt_request)

        # Define local-specific tools (approvals and sensitive operations)
        self.tools = [
            Tool(
                name="approve_item",
                description="Approve an item that was created by the cloud component.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "item_path": {"type": "string", "description": "Path to the item in the vault that needs approval"},
                        "approval_notes": {"type": "string", "description": "Optional notes about the approval"}
                    },
                    "required": ["item_path"]
                }
            ),
            Tool(
                name="reject_item",
                description="Reject an item that was created by the cloud component.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "item_path": {"type": "string", "description": "Path to the item in the vault that needs rejection"},
                        "rejection_reason": {"type": "string", "description": "Reason for rejection"}
                    },
                    "required": ["item_path", "rejection_reason"]
                }
            ),
            Tool(
                name="send_approved_email",
                description="Send an email that has been approved from the vault.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "draft_path": {"type": "string", "description": "Path to the approved email draft in the vault"}
                    },
                    "required": ["draft_path"]
                }
            ),
            Tool(
                name="publish_approved_post",
                description="Publish a social media post that has been approved from the vault.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "draft_path": {"type": "string", "description": "Path to the approved post draft in the vault"}
                    },
                    "required": ["draft_path"]
                }
            ),
            Tool(
                name="execute_approved_payment",
                description="Execute a payment that has been approved from the vault.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "transaction_path": {"type": "string", "description": "Path to the approved transaction in the vault"}
                    },
                    "required": ["transaction_path"]
                }
            ),
            Tool(
                name="update_dashboard",
                description="Update the main Dashboard.md with information from cloud updates.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "update_path": {"type": "string", "description": "Path to the update file from cloud"},
                        "merge_strategy": {"type": "string", "description": "How to merge the update ('append', 'replace', 'section_update')"}
                    },
                    "required": ["update_path", "merge_strategy"]
                }
            ),
            Tool(
                name="get_pending_approvals",
                description="Get list of items that are pending local approval.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Filter by category (e.g., 'email', 'social', 'payment', 'accounting', 'all')"}
                    }
                }
            )
        ]

    def handle_tool_call(self, *, method_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle incoming tool calls."""
        if method_name == "approve_item":
            return self.approve_item(arguments)
        elif method_name == "reject_item":
            return self.reject_item(arguments)
        elif method_name == "send_approved_email":
            return self.send_approved_email(arguments)
        elif method_name == "publish_approved_post":
            return self.publish_approved_post(arguments)
        elif method_name == "execute_approved_payment":
            return self.execute_approved_payment(arguments)
        elif method_name == "update_dashboard":
            return self.update_dashboard(arguments)
        elif method_name == "get_pending_approvals":
            return self.get_pending_approvals(arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {method_name}")]
            )

    def approve_item(self, args: Dict[str, Any]) -> CallToolResult:
        """Approve an item that was created by the cloud component."""
        item_path = args["item_path"]
        approval_notes = args.get("approval_notes", "")

        item_full_path = self.vault_path / item_path

        if not item_full_path.exists():
            return CallToolResult(
                content=[TextContent(type="text", text=f"Item not found: {item_path}")]
            )

        try:
            # Read the item content
            content = item_full_path.read_text(encoding='utf-8')

            # Add approval metadata
            import datetime
            approval_info = f"\n\n---\n**APPROVED BY LOCAL EXECUTIVE**\nApproved: {datetime.datetime.now().isoformat()}\nNotes: {approval_notes}\n---\n"
            updated_content = content + approval_info

            # Write back the updated content
            item_full_path.write_text(updated_content, encoding='utf-8')

            # Move the item to an approved directory if it's in pending_approval
            if "pending_approval" in str(item_path):
                # Create new path in approved directory
                parts = item_path.split('/')
                new_parts = [part for part in parts if part != 'pending_approval']
                new_parts.insert(0, 'approved')
                approved_path = '/'.join(new_parts)

                approved_full_path = self.vault_path / approved_path
                approved_full_path.parent.mkdir(parents=True, exist_ok=True)

                # Move the file
                item_full_path.rename(approved_full_path)

                return CallToolResult(
                    content=[TextContent(type="text", text=f"Item approved and moved to {approved_path}. Notes: {approval_notes}")]
                )
            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Item approved. Notes: {approval_notes}")]
                )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error approving item: {str(e)}")]
            )

    def reject_item(self, args: Dict[str, Any]) -> CallToolResult:
        """Reject an item that was created by the cloud component."""
        item_path = args["item_path"]
        rejection_reason = args["rejection_reason"]

        item_full_path = self.vault_path / item_path

        if not item_full_path.exists():
            return CallToolResult(
                content=[TextContent(type="text", text=f"Item not found: {item_path}")]
            )

        try:
            # Read the item content
            content = item_full_path.read_text(encoding='utf-8')

            # Add rejection metadata
            import datetime
            rejection_info = f"\n\n---\n**REJECTED BY LOCAL EXECUTIVE**\nRejected: {datetime.datetime.now().isoformat()}\nReason: {rejection_reason}\n---\n"
            updated_content = content + rejection_info

            # Write back the updated content
            item_full_path.write_text(updated_content, encoding='utf-8')

            # Move the item to a rejected directory
            parts = item_path.split('/')
            new_parts = [part for part in parts if part != 'pending_approval']
            new_parts.insert(0, 'rejected')
            rejected_path = '/'.join(new_parts)

            rejected_full_path = self.vault_path / rejected_path
            rejected_full_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            item_full_path.rename(rejected_full_path)

            return CallToolResult(
                content=[TextContent(type="text", text=f"Item rejected and moved to {rejected_path}. Reason: {rejection_reason}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error rejecting item: {str(e)}")]
            )

    def send_approved_email(self, args: Dict[str, Any]) -> CallToolResult:
        """Send an email that has been approved from the vault."""
        draft_path = args["draft_path"]

        draft_full_path = self.vault_path / draft_path

        if not draft_full_path.exists():
            return CallToolResult(
                content=[TextContent(type="text", text=f"Draft not found: {draft_path}")]
            )

        try:
            # Read the draft content
            content = draft_full_path.read_text(encoding='utf-8')

            # Extract email details (this is a simplified example)
            # In a real implementation, you'd parse the markdown properly
            lines = content.split('\n')
            recipient = ""
            subject = ""
            body = ""

            in_body = False
            for line in lines:
                if line.startswith("**Recipient:**"):
                    recipient = line.replace("**Recipient:**", "").strip()
                elif line.startswith("**Subject:**"):
                    subject = line.replace("**Subject:**", "").strip()
                elif line.strip() == "## Email Body:":
                    in_body = True
                    continue
                elif in_body and line.startswith("**") and line.endswith("**"):
                    # End of body reached
                    break
                elif in_body:
                    body += line + "\n"

            # Here we would actually send the email using SMTP
            # For this example, we'll just simulate the action
            import datetime
            sent_status = f"EMAIL SENT SIMULATION\nTo: {recipient}\nSubject: {subject}\nSent: {datetime.datetime.now().isoformat()}\n\n{body}"

            # Move to sent directory
            parts = draft_path.split('/')
            new_parts = [part for part in parts if part not in ['pending_approval', 'needs_action']]
            new_parts.insert(0, 'done')
            sent_path = '/'.join(new_parts).replace('.md', f'_SENT_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.md')

            sent_full_path = self.vault_path / sent_path
            sent_full_path.parent.mkdir(parents=True, exist_ok=True)
            sent_full_path.write_text(sent_status, encoding='utf-8')

            # Remove the original draft
            draft_full_path.unlink()

            return CallToolResult(
                content=[TextContent(type="text", text=f"Email sent to {recipient}. Status saved to {sent_path}.")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error sending email: {str(e)}")]
            )

    def publish_approved_post(self, args: Dict[str, Any]) -> CallToolResult:
        """Publish a social media post that has been approved from the vault."""
        draft_path = args["draft_path"]

        draft_full_path = self.vault_path / draft_path

        if not draft_full_path.exists():
            return CallToolResult(
                content=[TextContent(type="text", text=f"Draft not found: {draft_path}")]
            )

        try:
            # Read the draft content
            content = draft_full_path.read_text(encoding='utf-8')

            # Extract post details (simplified parsing)
            lines = content.split('\n')
            platform = "unknown"
            post_content = ""

            in_content = False
            for line in lines:
                if line.startswith("**Platform:**"):
                    platform = line.replace("**Platform:**", "").strip()
                elif line.strip() == "## Post Content:":
                    in_content = True
                    continue
                elif in_content and line.startswith("**") and line.endswith("**"):
                    # End of content reached
                    break
                elif in_content:
                    post_content += line + "\n"

            # Here we would actually publish to social media
            # For this example, we'll just simulate the action
            import datetime
            published_status = f"POST PUBLISHED SIMULATION\nPlatform: {platform}\nPublished: {datetime.datetime.now().isoformat()}\n\n{post_content}"

            # Move to published directory
            parts = draft_path.split('/')
            new_parts = [part for part in parts if part not in ['pending_approval', 'needs_action']]
            new_parts.insert(0, 'done')
            published_path = '/'.join(new_parts).replace('.md', f'_PUBLISHED_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.md')

            published_full_path = self.vault_path / published_path
            published_full_path.parent.mkdir(parents=True, exist_ok=True)
            published_full_path.write_text(published_status, encoding='utf-8')

            # Remove the original draft
            draft_full_path.unlink()

            return CallToolResult(
                content=[TextContent(type="text", text=f"Post published to {platform}. Status saved to {published_path}.")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error publishing post: {str(e)}")]
            )

    def execute_approved_payment(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute a payment that has been approved from the vault."""
        transaction_path = args["transaction_path"]

        transaction_full_path = self.vault_path / transaction_path

        if not transaction_full_path.exists():
            return CallToolResult(
                content=[TextContent(type="text", text=f"Transaction not found: {transaction_path}")]
            )

        try:
            # Read the transaction content
            content = transaction_full_path.read_text(encoding='utf-8')

            # Extract transaction details (simplified parsing)
            lines = content.split('\n')
            recipient = ""
            amount = ""
            description = ""

            for line in lines:
                if line.startswith("**Recipient:**"):
                    recipient = line.replace("**Recipient:**", "").strip()
                elif line.startswith("**Amount:**"):
                    amount = line.replace("**Amount:**", "").strip()
                elif line.startswith("**Description:**"):
                    description = line.replace("**Description:**", "").strip()

            # Here we would actually execute the payment
            # For this example, we'll just simulate the action
            import datetime
            executed_status = f"PAYMENT EXECUTED SIMULATION\nTo: {recipient}\nAmount: {amount}\nDescription: {description}\nExecuted: {datetime.datetime.now().isoformat()}\nStatus: SUCCESS"

            # Move to executed directory
            parts = transaction_path.split('/')
            new_parts = [part for part in parts if part not in ['pending_approval', 'needs_action']]
            new_parts.insert(0, 'done')
            executed_path = '/'.join(new_parts).replace('.md', f'_EXECUTED_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.md')

            executed_full_path = self.vault_path / executed_path
            executed_full_path.parent.mkdir(parents=True, exist_ok=True)
            executed_full_path.write_text(executed_status, encoding='utf-8')

            # Remove the original transaction
            transaction_full_path.unlink()

            return CallToolResult(
                content=[TextContent(type="text", text=f"Payment executed to {recipient} for {amount}. Status saved to {executed_path}.")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error executing payment: {str(e)}")]
            )

    def update_dashboard(self, args: Dict[str, Any]) -> CallToolResult:
        """Update the main Dashboard.md with information from cloud updates."""
        update_path = args["update_path"]
        merge_strategy = args["merge_strategy"]

        update_full_path = self.vault_path / update_path
        dashboard_path = self.vault_path / "Dashboard.md"

        if not update_full_path.exists():
            return CallToolResult(
                content=[TextContent(type="text", text=f"Update file not found: {update_path}")]
            )

        if not dashboard_path.exists():
            # Create a new dashboard if it doesn't exist
            dashboard_path.write_text("# Dashboard\n\nWelcome to your AI Employee Dashboard.\n\n", encoding='utf-8')

        try:
            # Read both files
            update_content = update_full_path.read_text(encoding='utf-8')
            dashboard_content = dashboard_path.read_text(encoding='utf-8')

            import datetime
            update_header = f"\n\n---\n## Cloud Update ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n---\n"

            if merge_strategy == "append":
                # Simply append the update to the dashboard
                new_dashboard_content = dashboard_content + update_header + update_content
            elif merge_strategy == "section_update":
                # Look for specific sections to update
                # This is a simplified version - in practice, you'd have more sophisticated section management
                section_marker = f"<!-- AUTO-UPDATE-{hash(update_content[:50]) % 10000} -->"
                new_dashboard_content = dashboard_content + f"\n{section_marker}\n{update_content}\n{section_marker}\n"
            else:
                # Default to append
                new_dashboard_content = dashboard_content + update_header + update_content

            # Write the updated dashboard
            dashboard_path.write_text(new_dashboard_content, encoding='utf-8')

            return CallToolResult(
                content=[TextContent(type="text", text=f"Dashboard updated with content from {update_path} using {merge_strategy} strategy.")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error updating dashboard: {str(e)}")]
            )

    def get_pending_approvals(self, args: Dict[str, Any]) -> CallToolResult:
        """Get list of items that are pending local approval."""
        category = args.get("category", "all").lower()

        pending_items = []

        # Search in pending_approval directory
        pending_dir = self.vault_path / "pending_approval"

        if pending_dir.exists():
            for subdir in pending_dir.iterdir():
                if subdir.is_dir():
                    # Check if this category matches the filter
                    if category == "all" or subdir.name.lower().startswith(category):
                        for file_path in subdir.glob("*.md"):
                            pending_items.append(f"{subdir.name}/{file_path.name}")

        if pending_items:
            return CallToolResult(
                content=[TextContent(type="text", text="Pending approvals:\n" + "\n".join([f"- {item}" for item in pending_items]))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text="No pending approvals found.")]
            )

    def handle_prompt_request(self, *, name: str, arguments: Optional[Dict[str, str]]) -> Prompt:
        """Handle prompt requests."""
        if name == "local-approval-status":
            return Prompt(
                description="Check the status of local approval operations",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Local approval server operational. Vault path: {self.vault_path}. "
                                       f"Ready to handle approvals, sensitive operations, and final actions."
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
    server = LocalApprovalServer()
    print("Starting Local Approval MCP Server...")
    server.run()