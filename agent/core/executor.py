"""
Task execution engine
"""

import json
from typing import Any, List

from litellm import ChatCompletionMessageToolCall
from pydantic import BaseModel

ToolCall = ChatCompletionMessageToolCall


class ToolResult(BaseModel):
    output: str
    success: bool


class ToolExecutor:
    """Executes planned tasks using available tools"""

    def __init__(self, tools: List[Any] = None, mcp_client=None):
        self.tools = tools or []
        self.mcp_client = mcp_client

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single step in the plan"""
        tool_name = tool_call.function.name

        # Parse arguments
        try:
            if isinstance(tool_call.function.arguments, str):
                tool_args = json.loads(tool_call.function.arguments)
            else:
                tool_args = tool_call.function.arguments
        except json.JSONDecodeError as e:
            return ToolResult(
                output=f"Error parsing tool arguments: {str(e)}", success=False
            )

        # Check if this is an MCP tool (prefixed with server name)
        if self.mcp_client and "__" in tool_name:
            success, result = await self.mcp_client.call_tool(tool_name, tool_args)
            return ToolResult(output=result, success=success)

        # If not an MCP tool, try local tools
        # TODO: Implement local tool execution
        return ToolResult(output=f"Tool {tool_name} not found", success=False)
