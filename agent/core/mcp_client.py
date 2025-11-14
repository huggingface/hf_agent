"""
MCP (Model Context Protocol) client integration for the agent
Based on the official MCP SDK implementation
"""

import os
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


class McpClient:
    """
    Client for connecting to MCP servers using the official MCP SDK.
    Based on codex-rs/core/src/mcp_connection_manager.rs
    """

    def __init__(
        self,
        server_name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.session: Optional[ClientSession] = None
        self.tools: dict[str, dict[str, Any]] = {}
        self.exit_stack = AsyncExitStack()

    async def start(self) -> None:
        """Start the MCP server connection using official SDK"""
        # Merge environment variables
        full_env = {**dict(os.environ), **self.env} if self.env else None

        # Create server parameters
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=full_env,
        )

        # Connect using stdio_client
        read, write = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        # Create session
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        # Initialize
        await self.session.initialize()

        # List available tools
        tools_result = await self.session.list_tools()
        for tool in tools_result.tools:
            qualified_name = f"mcp__{self.server_name}__{tool.name}"
            self.tools[qualified_name] = {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema,
            }

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[str, bool]:
        """Execute a tool on the MCP server"""
        if not self.session:
            return "Client not connected", False

        # Strip the mcp__servername__ prefix to get the actual tool name
        actual_tool_name = tool_name.split("__")[-1]

        try:
            result = await self.session.call_tool(actual_tool_name, arguments)

            # Extract text from content
            text_parts = []
            for content in result.content:
                if isinstance(content, types.TextContent):
                    text_parts.append(content.text)
                elif isinstance(content, types.ImageContent):
                    text_parts.append(f"[Image: {content.mimeType}]")
                elif isinstance(content, types.EmbeddedResource):
                    text_parts.append(f"[Resource: {content.resource}]")

            output = "\n".join(text_parts) if text_parts else str(result.content)
            success = not result.isError

            return output, success
        except Exception as e:
            return f"Tool call failed: {str(e)}", False

    def get_tools(self) -> dict[str, dict[str, Any]]:
        """Get all available tools from this server"""
        return self.tools.copy()

    async def shutdown(self) -> None:
        """Shutdown the MCP server connection"""
        await self.exit_stack.aclose()


class McpConnectionManager:
    """
    Manages multiple MCP server connections.
    Based on codex-rs/core/src/mcp_connection_manager.rs
    """

    def __init__(self):
        self.clients: dict[str, McpClient] = {}

    async def add_server(
        self,
        server_name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> bool:
        """Add and start an MCP server"""
        try:
            client = McpClient(server_name, command, args, env)
            await client.start()
            self.clients[server_name] = client
            print(
                f"✅ MCP server '{server_name}' connected with {len(client.tools)} tools"
            )
            return True
        except Exception as e:
            print(f"❌ Failed to start MCP server '{server_name}': {e}")
            return False

    def list_all_tools(self) -> dict[str, dict[str, Any]]:
        """Aggregate tools from all connected servers"""
        all_tools = {}
        for client in self.clients.values():
            all_tools.update(client.get_tools())
        return all_tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[str, bool]:
        """Route tool call to the appropriate MCP server"""
        # Extract server name from qualified tool name: mcp__servername__toolname
        if tool_name.startswith("mcp__"):
            parts = tool_name.split("__")
            if len(parts) >= 3:
                server_name = parts[1]
                if server_name in self.clients:
                    return await self.clients[server_name].call_tool(
                        tool_name, arguments
                    )

        return "Unknown MCP tool", False

    async def shutdown_all(self) -> None:
        """Shutdown all MCP servers"""
        for client in self.clients.values():
            await client.shutdown()
