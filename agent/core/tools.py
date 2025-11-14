"""
Tool system for the agent
Provides ToolSpec and ToolRouter for managing both built-in and MCP tools
"""

import subprocess
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from agent.core.mcp_client import McpConnectionManager


@dataclass
class ToolSpec:
    """Tool specification for LLM"""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Optional[Callable[[dict[str, Any]], Awaitable[tuple[str, bool]]]] = None


class ToolRouter:
    """
    Routes tool calls to appropriate handlers.
    Based on codex-rs/core/src/tools/router.rs
    """

    def __init__(self, mcp_manager: Optional[McpConnectionManager] = None):
        self.tools: dict[str, ToolSpec] = {}
        self.mcp_manager = mcp_manager

    def register_tool(self, spec: ToolSpec) -> None:
        """Register a tool with its handler"""
        self.tools[spec.name] = spec

    def register_mcp_tools(self) -> None:
        """Register all MCP tools from the connection manager"""
        if not self.mcp_manager:
            return

        mcp_tools = self.mcp_manager.list_all_tools()
        for tool_name, tool_def in mcp_tools.items():
            spec = ToolSpec(
                name=tool_name,
                description=tool_def.get("description", ""),
                parameters=tool_def.get(
                    "inputSchema", {"type": "object", "properties": {}}
                ),
                handler=None,  # MCP tools use the manager
            )
            self.tools[tool_name] = spec

    def get_tool_specs_for_llm(self) -> list[dict[str, Any]]:
        """Get tool specifications in OpenAI format"""
        specs = []
        for tool in self.tools.values():
            specs.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return specs

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[str, bool]:
        """Execute a tool by name"""
        if tool_name not in self.tools:
            return f"Unknown tool: {tool_name}", False

        tool = self.tools[tool_name]

        # MCP tool
        if tool_name.startswith("mcp__") and self.mcp_manager:
            return await self.mcp_manager.call_tool(tool_name, arguments)

        # Built-in tool with handler
        if tool.handler:
            return await tool.handler(arguments)

        return "Tool has no handler", False


# ============================================================================
# BUILT-IN TOOL HANDLERS
# ============================================================================


async def bash_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Execute bash command"""
    try:
        command = arguments.get("command", "")
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout if result.returncode == 0 else result.stderr
        success = result.returncode == 0
        return output, success
    except Exception as e:
        return f"Error: {str(e)}", False


async def read_file_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Read file contents"""
    try:
        path = arguments.get("path", "")
        with open(path, "r") as f:
            content = f.read()
        return content, True
    except Exception as e:
        return f"Error reading file: {str(e)}", False


async def write_file_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Write to file"""
    try:
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {path}", True
    except Exception as e:
        return f"Error writing file: {str(e)}", False


def create_builtin_tools() -> list[ToolSpec]:
    """Create built-in tool specifications"""
    return [
        ToolSpec(
            name="bash",
            description="Execute a bash command and return its output",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute",
                    }
                },
                "required": ["command"],
            },
            handler=bash_handler,
        ),
        ToolSpec(
            name="read_file",
            description="Read the contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read",
                    }
                },
                "required": ["path"],
            },
            handler=read_file_handler,
        ),
        ToolSpec(
            name="write_file",
            description="Write content to a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
            handler=write_file_handler,
        ),
    ]
