"""
Cloud MCP Server for Vault Operations
=====================================

Handles cloud-specific vault operations that don't involve sensitive data.
Follows the platinum tier architecture with proper separation of duties.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from mcp import Server, NotificationOptions
from mcp.types import CallToolResult, Prompt, TextContent, Tool, ToolCallResult, ExperimentalLLMContext


class CloudVaultServer:
    def __init__(self, vault_path: str = "./vault"):
        self.vault_path = Path(vault_path)
        self.server = Server("cloud-vault-server")

        # Register handlers
        self.server.on_call_tool(self.handle_tool_call)
        self.server.on_prompt_request(self.handle_prompt_request)

        # Define cloud-safe tools
        self.tools = [
            Tool(
                name="read_vault_file",
                description="Read a file from the vault. Cloud component can read any file except sensitive ones.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file relative to vault root"}
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="write_vault_file",
                description="Write a file to the vault. Cloud component can write to designated cloud folders only.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file relative to vault root"},
                        "content": {"type": "string", "description": "Content to write to the file"}
                    },
                    "required": ["file_path", "content"]
                }
            ),
            Tool(
                name="list_vault_directory",
                description="List files in a vault directory. Cloud component can list any directory except sensitive ones.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dir_path": {"type": "string", "description": "Directory path relative to vault root"}
                    },
                    "required": ["dir_path"]
                }
            ),
            Tool(
                name="move_vault_file",
                description="Move a file in the vault. Used for claim-by-move operations.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source_path": {"type": "string", "description": "Source path relative to vault root"},
                        "dest_path": {"type": "string", "description": "Destination path relative to vault root"}
                    },
                    "required": ["source_path", "dest_path"]
                }
            ),
            Tool(
                name="create_draft_plan",
                description="Create a draft plan in the cloud-specific planning directory.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "plan_name": {"type": "string", "description": "Name for the plan file"},
                        "content": {"type": "string", "description": "Content of the plan"},
                        "domain": {"type": "string", "description": "Domain for the plan (e.g., 'email', 'social', 'accounting')"}
                    },
                    "required": ["plan_name", "content", "domain"]
                }
            )
        ]

    def is_cloud_safe_path(self, path: str) -> bool:
        """Check if a vault path is safe for cloud operations."""
        path_lower = path.lower()
        # Cloud should not access sensitive directories
        sensitive_dirs = ['banking', 'payment', 'whatsapp', 'credentials']
        sensitive_extensions = ['.env', '.key', '.pem', '.p12', '.secret']

        path_parts = Path(path).parts
        for part in path_parts:
            if part.lower() in sensitive_dirs:
                return False

        for ext in sensitive_extensions:
            if path_lower.endswith(ext):
                return False

        return True

    def handle_tool_call(self, *, method_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle incoming tool calls."""
        if method_name == "read_vault_file":
            return self.read_vault_file(arguments)
        elif method_name == "write_vault_file":
            return self.write_vault_file(arguments)
        elif method_name == "list_vault_directory":
            return self.list_vault_directory(arguments)
        elif method_name == "move_vault_file":
            return self.move_vault_file(arguments)
        elif method_name == "create_draft_plan":
            return self.create_draft_plan(arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {method_name}")]
            )

    def read_vault_file(self, args: Dict[str, Any]) -> CallToolResult:
        """Read a file from the vault."""
        file_path = args["file_path"]

        if not self.is_cloud_safe_path(file_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Access denied: {file_path} is not safe for cloud access")]
            )

        full_path = self.vault_path / file_path
        try:
            content = full_path.read_text(encoding='utf-8')
            return CallToolResult(
                content=[TextContent(type="text", text=f"Content of {file_path}:\n{content}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error reading file {file_path}: {str(e)}")]
            )

    def write_vault_file(self, args: Dict[str, Any]) -> CallToolResult:
        """Write a file to the vault (cloud-safe locations only)."""
        file_path = args["file_path"]
        content = args["content"]

        # Check if this is a cloud-safe location for writing
        path_obj = Path(file_path)
        first_dir = path_obj.parts[0] if path_obj.parts else ""

        cloud_write_allowed_dirs = ['inbox', 'needs_action', 'plans', 'updates', 'signals', 'done', 'drafts']
        if first_dir.lower() not in cloud_write_allowed_dirs:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Write denied: {file_path} is not in a cloud-writeable directory")]
            )

        if not self.is_cloud_safe_path(file_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Write denied: {file_path} is not safe for cloud operations")]
            )

        full_path = self.vault_path / file_path
        try:
            # Create parent directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)

            full_path.write_text(content, encoding='utf-8')
            return CallToolResult(
                content=[TextContent(type="text", text=f"Successfully wrote to {file_path}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error writing file {file_path}: {str(e)}")]
            )

    def list_vault_directory(self, args: Dict[str, Any]) -> CallToolResult:
        """List files in a vault directory."""
        dir_path = args["dir_path"]

        if not self.is_cloud_safe_path(dir_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Access denied: {dir_path} is not safe for cloud access")]
            )

        full_path = self.vault_path / dir_path
        try:
            if not full_path.exists():
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Directory does not exist: {dir_path}")]
                )

            files = []
            for item in full_path.iterdir():
                if item.is_file():
                    files.append(item.name)
                elif item.is_dir():
                    files.append(f"{item.name}/")

            return CallToolResult(
                content=[TextContent(type="text", text=f"Files in {dir_path}:\n" + "\n".join(files))]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error listing directory {dir_path}: {str(e)}")]
            )

    def move_vault_file(self, args: Dict[str, Any]) -> CallToolResult:
        """Move a file in the vault (for claim-by-move operations)."""
        source_path = args["source_path"]
        dest_path = args["dest_path"]

        if not self.is_cloud_safe_path(source_path) or not self.is_cloud_safe_path(dest_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Move denied: Source or destination not safe for cloud operations")]
            )

        # Validate that this is a legitimate claim-by-move operation
        source_parts = Path(source_path).parts
        dest_parts = Path(dest_path).parts

        # Check that we're moving from Needs_Action to In_Progress (claim operation)
        if (len(source_parts) >= 2 and
            source_parts[0].lower() == 'needs_action' and
            len(dest_parts) >= 2 and
            dest_parts[0].lower() == 'in_progress'):

            # Ensure we're claiming for the cloud agent
            if dest_parts[1].lower() != 'cloud':
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Cloud can only claim items for 'cloud' agent, not '{dest_parts[1]}'")]
                )

        source_full = self.vault_path / source_path
        dest_full = self.vault_path / dest_path

        try:
            # Create destination directory if it doesn't exist
            dest_full.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            source_full.rename(dest_full)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Successfully moved {source_path} to {dest_path}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error moving file from {source_path} to {dest_path}: {str(e)}")]
            )

    def create_draft_plan(self, args: Dict[str, Any]) -> CallToolResult:
        """Create a draft plan in the cloud-specific planning directory."""
        plan_name = args["plan_name"]
        content = args["content"]
        domain = args["domain"]

        # Create a cloud-specific draft plan
        plan_filename = f"Plan_{domain}_cloud_{plan_name.replace(' ', '_').replace('/', '_')}.md"
        plan_path = f"plans/{domain}/cloud/{plan_filename}"

        if not self.is_cloud_safe_path(plan_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Plan creation denied: {plan_path} is not safe for cloud operations")]
            )

        full_path = self.vault_path / plan_path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding='utf-8')

            return CallToolResult(
                content=[TextContent(type="text", text=f"Created cloud draft plan: {plan_path}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error creating plan {plan_path}: {str(e)}")]
            )

    def handle_prompt_request(self, *, name: str, arguments: Optional[Dict[str, str]]) -> Prompt:
        """Handle prompt requests."""
        if name == "cloud-status-check":
            return Prompt(
                description="Check the status of cloud operations",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Cloud vault server operational. Vault path: {self.vault_path}. "
                                       f"Ready to handle cloud-safe vault operations."
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
    server = CloudVaultServer()
    print("Starting Cloud Vault MCP Server...")
    server.run()