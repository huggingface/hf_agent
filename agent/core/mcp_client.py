"""
MCP (Model Context Protocol) client integration for the agent
"""

from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPServerConfig:
    """Configuration for an MCP server"""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str],
        env: Optional[dict[str, str]] = None,
    ):
        self.name = name
        self.command = command
        self.args = args
        self.env = env


class MCPClient:
    """
    Manages connections to MCP servers and provides tool access
    """

    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self._tools_cache: Optional[list[dict]] = None

    async def connect_to_server(self, server_config: MCPServerConfig) -> None:
        """
        Connect to an MCP server

        Args:
            server_config: Configuration for the MCP server
        """
        server_params = StdioServerParameters(
            command=server_config.command,
            args=server_config.args,
            env=server_config.env,
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

        await session.initialize()

        # Store the session
        self.sessions[server_config.name] = session

        # Invalidate tools cache
        self._tools_cache = None

        print(f"✅ Connected to MCP server: {server_config.name}")

    async def list_tools(self) -> list[dict]:
        """
        Get all available tools from all connected servers

        Returns:
            List of tool definitions compatible with LiteLLM format
        """
        if self._tools_cache is not None:
            return self._tools_cache

        all_tools = []

        for server_name, session in self.sessions.items():
            try:
                response = await session.list_tools()
                for tool in response.tools:
                    # Convert MCP tool format to LiteLLM tool format
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": f"{server_name}__{tool.name}",  # Prefix with server name
                            "description": tool.description or "",
                            "parameters": tool.inputSchema,
                        },
                    }
                    all_tools.append(tool_def)
            except Exception as e:
                print(f"⚠️  Error listing tools from {server_name}: {e}")

        self._tools_cache = all_tools
        return all_tools

    async def call_tool(self, tool_name: str, tool_args: dict) -> tuple[bool, str]:
        """
        Call a tool on the appropriate MCP server

        Args:
            tool_name: Name of the tool (format: "server_name__tool_name")
            tool_args: Arguments to pass to the tool

        Returns:
            Tuple of (success, result_content)
        """
        # Parse server name from tool name
        if "__" not in tool_name:
            return False, f"Invalid tool name format: {tool_name}"

        server_name, actual_tool_name = tool_name.split("__", 1)

        if server_name not in self.sessions:
            return False, f"Server not found: {server_name}"

        session = self.sessions[server_name]

        try:
            result = await session.call_tool(actual_tool_name, tool_args)

            # Extract content from result
            if hasattr(result, "content"):
                if isinstance(result.content, list):
                    # Handle list of content items
                    content_parts = []
                    for item in result.content:
                        if hasattr(item, "text"):
                            content_parts.append(item.text)
                        else:
                            content_parts.append(str(item))
                    content = "\n".join(content_parts)
                else:
                    content = str(result.content)
            else:
                content = str(result)

            return True, content

        except Exception as e:
            return False, f"Error calling tool {tool_name}: {str(e)}"

    async def cleanup(self) -> None:
        """Clean up all MCP connections"""
        await self.exit_stack.aclose()
        self.sessions.clear()
        self._tools_cache = None
