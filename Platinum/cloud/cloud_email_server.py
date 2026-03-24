"""
Cloud MCP Server for Email Operations
=====================================

Handles cloud-specific email operations: triage, draft creation.
Final sending is handled by local component after approval.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from mcp import Server, NotificationOptions
from mcp.types import CallToolResult, Prompt, TextContent, Tool, ToolCallResult, ExperimentalLLMContext
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class CloudEmailServer:
    def __init__(self, vault_path: str = "./vault", smtp_host: str = "", smtp_port: int = 587):
        self.vault_path = Path(vault_path)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.server = Server("cloud-email-server")

        # Register handlers
        self.server.on_call_tool(self.handle_tool_call)
        self.server.on_prompt_request(self.handle_prompt_request)

        # Define cloud-safe email tools (triage and draft only)
        self.tools = [
            Tool(
                name="email_triage",
                description="Analyze incoming emails and categorize them. Creates draft responses in vault.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "email_content": {"type": "string", "description": "Raw content of the email"},
                        "sender": {"type": "string", "description": "Email address of sender"},
                        "subject": {"type": "string", "description": "Subject of the email"},
                        "category": {"type": "string", "description": "Category for classification (e.g., urgent, marketing, personal, business)"}
                    },
                    "required": ["email_content", "sender", "subject", "category"]
                }
            ),
            Tool(
                name="create_email_draft",
                description="Create a draft email response. Draft will be stored in vault for local approval.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Subject of the email"},
                        "body": {"type": "string", "description": "Body content of the email"},
                        "priority": {"type": "string", "description": "Priority level (low, medium, high)"},
                        "approval_required": {"type": "boolean", "description": "Whether this draft requires approval before sending"}
                    },
                    "required": ["recipient", "subject", "body", "approval_required"]
                }
            ),
            Tool(
                name="get_pending_emails",
                description="Get list of pending emails that need attention.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Filter by status (e.g., 'draft', 'awaiting_approval', 'sent')"}
                    }
                }
            ),
            Tool(
                name="analyze_email_thread",
                description="Analyze an email thread to understand context and suggest responses.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string", "description": "Identifier for the email thread"},
                        "previous_emails": {"type": "array", "items": {"type": "string"}, "description": "Previous emails in the thread"}
                    },
                    "required": ["thread_id", "previous_emails"]
                }
            )
        ]

    def handle_tool_call(self, *, method_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle incoming tool calls."""
        if method_name == "email_triage":
            return self.email_triage(arguments)
        elif method_name == "create_email_draft":
            return self.create_email_draft(arguments)
        elif method_name == "get_pending_emails":
            return self.get_pending_emails(arguments)
        elif method_name == "analyze_email_thread":
            return self.analyze_email_thread(arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {method_name}")]
            )

    def email_triage(self, args: Dict[str, Any]) -> CallToolResult:
        """Analyze incoming emails and categorize them."""
        email_content = args["email_content"]
        sender = args["sender"]
        subject = args["subject"]
        category = args["category"]

        # Create a unique filename for the email analysis
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_triage_{timestamp}_{sender.replace('@', '_').replace('.', '_')}_{category}.md"

        # Create triage analysis content
        analysis_content = f"""# Email Triage Analysis

**Received:** {datetime.datetime.now().isoformat()}
**Sender:** {sender}
**Subject:** {subject}
**Category:** {category}

## Original Content:
{email_content}

## Action Required:
Based on the category '{category}', this email has been categorized for appropriate handling.
"""

        # Save to needs_action directory for further processing
        analysis_path = f"needs_action/email_triage/{filename}"
        analysis_full_path = self.vault_path / analysis_path

        try:
            analysis_full_path.parent.mkdir(parents=True, exist_ok=True)
            analysis_full_path.write_text(analysis_content, encoding='utf-8')

            # Also create a draft response based on the category
            if category.lower() in ['urgent', 'business']:
                draft_subject = f"RE: {subject}" if not subject.lower().startswith('re:') else subject
                draft_body = self.generate_response_template(category, email_content)

                draft_result = self.create_email_draft({
                    "recipient": sender,
                    "subject": draft_subject,
                    "body": draft_body,
                    "priority": "high" if category.lower() == "urgent" else "medium",
                    "approval_required": True
                })

                return CallToolResult(
                    content=[TextContent(type="text", text=f"Email triaged as '{category}'. Analysis saved to {analysis_path}. Draft response created: {draft_result.content[0].text}")]
                )
            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Email triaged as '{category}'. Analysis saved to {analysis_path}.")]
                )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error during email triage: {str(e)}")]
            )

    def generate_response_template(self, category: str, email_content: str) -> str:
        """Generate a response template based on the category."""
        if category.lower() == 'urgent':
            return f"""Thank you for your urgent message regarding:

{email_content[:200]}...

We acknowledge receipt of your urgent inquiry and will address it promptly. Someone will contact you within 24 hours.

Best regards,
AI Assistant"""
        elif category.lower() == 'business':
            return f"""Thank you for your business-related inquiry:

{email_content[:200]}...

We have received your message and will review it carefully. We will respond with a detailed response shortly.

Best regards,
AI Assistant"""
        elif category.lower() == 'marketing':
            return f"""Thank you for reaching out.

{email_content[:200]}...

We have received your marketing inquiry and will review it when appropriate.

Best regards,
AI Assistant"""
        else:
            return f"""Thank you for your message:

{email_content[:200]}...

We have received your correspondence and will review it.

Best regards,
AI Assistant"""

    def create_email_draft(self, args: Dict[str, Any]) -> CallToolResult:
        """Create a draft email response for local approval."""
        recipient = args["recipient"]
        subject = args["subject"]
        body = args["body"]
        priority = args.get("priority", "medium")
        approval_required = args.get("approval_required", True)

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"draft_email_{timestamp}_{recipient.replace('@', '_').replace('.', '_')}.md"

        # Create draft email content with approval workflow
        draft_content = f"""# Draft Email

**Draft Created:** {datetime.datetime.now().isoformat()}
**Recipient:** {recipient}
**Subject:** {subject}
**Priority:** {priority}
**Approval Required:** {approval_required}

## Email Body:
{body}

---
**Status:** Pending Approval
**Next Action:** Local component will review and approve for sending
"""

        # Determine where to save the draft based on approval requirement
        if approval_required:
            draft_path = f"pending_approval/email_drafts/{filename}"
        else:
            # If no approval required, still save as draft but marked as ready
            draft_path = f"needs_action/email_drafts/{filename}"

        draft_full_path = self.vault_path / draft_path

        try:
            draft_full_path.parent.mkdir(parents=True, exist_ok=True)
            draft_full_path.write_text(draft_content, encoding='utf-8')

            return CallToolResult(
                content=[TextContent(type="text", text=f"Email draft created at {draft_path}. Approval required: {approval_required}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error creating email draft: {str(e)}")]
            )

    def get_pending_emails(self, args: Dict[str, Any]) -> CallToolResult:
        """Get list of pending emails that need attention."""
        status_filter = args.get("status", "all")

        pending_dir = self.vault_path / "pending_approval" / "email_drafts"
        needs_action_dir = self.vault_path / "needs_action" / "email_drafts"

        pending_emails = []

        # Look in pending approval directory
        if pending_dir.exists():
            for file_path in pending_dir.glob("*.md"):
                pending_emails.append(f"Pending Approval: {file_path.name}")

        # Look in needs action directory if not filtered
        if status_filter in ["all", "needs_action"] and needs_action_dir.exists():
            for file_path in needs_action_dir.glob("*.md"):
                pending_emails.append(f"Needs Action: {file_path.name}")

        if pending_emails:
            return CallToolResult(
                content=[TextContent(type="text", text="Pending emails:\n" + "\n".join(pending_emails))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text="No pending emails found.")]
            )

    def analyze_email_thread(self, args: Dict[str, Any]) -> CallToolResult:
        """Analyze an email thread to understand context and suggest responses."""
        thread_id = args["thread_id"]
        previous_emails = args["previous_emails"]

        # Create analysis content
        analysis_content = f"""# Thread Analysis for {thread_id}

## Previous Messages:
{chr(10).join([f"- {email[:100]}..." for email in previous_emails[:5]])}

## Context Summary:
Based on the email thread, the main topics discussed are...

## Suggested Response Approach:
Given the context, the following approach is suggested...

## Next Steps:
Consider the following actions for this thread...
"""

        # Save analysis to vault
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"thread_analysis_{thread_id}_{timestamp}.md"
        analysis_path = f"needs_action/email_analysis/{filename}"

        analysis_full_path = self.vault_path / analysis_path

        try:
            analysis_full_path.parent.mkdir(parents=True, exist_ok=True)
            analysis_full_path.write_text(analysis_content, encoding='utf-8')

            return CallToolResult(
                content=[TextContent(type="text", text=f"Thread analysis completed for {thread_id}. Saved to {analysis_path}.")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error analyzing email thread: {str(e)}")]
            )

    def handle_prompt_request(self, *, name: str, arguments: Optional[Dict[str, str]]) -> Prompt:
        """Handle prompt requests."""
        if name == "cloud-email-status":
            return Prompt(
                description="Check the status of cloud email operations",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Cloud email server operational. Vault path: {self.vault_path}. "
                                       f"Handling email triage and draft creation. All outgoing emails require local approval."
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
    server = CloudEmailServer()
    print("Starting Cloud Email MCP Server...")
    server.run()