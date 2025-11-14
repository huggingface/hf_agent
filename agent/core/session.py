import asyncio
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel

from agent.config import Config
from agent.context_manager.manager import ContextManager
from agent.core import ToolExecutor
from agent.core.mcp_client import MCPClient, MCPServerConfig as MCPServerConfigClass


class OpType(Enum):
    USER_INPUT = "user_input"
    EXEC_APPROVAL = "exec_approval"
    INTERRUPT = "interrupt"
    UNDO = "undo"
    COMPACT = "compact"
    SHUTDOWN = "shutdown"


class Event(BaseModel):
    event_type: Literal[
        "processing",
        "assistant_message",
        "tool_output",
        "turn_complete",
        "compacted",
        "undo_complete",
        "shutdown",
        "error",
        "interrupted",
    ]
    data: dict[str, Any] | None = None


class Session:
    """
    Maintains agent session state
    Similar to Session in codex-rs/core/src/codex.rs
    """

    def __init__(self, event_queue: asyncio.Queue, config: Config | None = None):
        self.context_manager = ContextManager()
        self.event_queue = event_queue
        self.config = config or Config(
            model_name="anthropic/claude-sonnet-4-5-20250929",
            tools=[],
            system_prompt_path="",
        )

        # Initialize MCP client
        self.mcp_client = MCPClient()
        self.tool_executor = ToolExecutor(mcp_client=self.mcp_client)

        self.is_running = True
        self.current_task: asyncio.Task | None = None
        self._mcp_initialized = False

    async def initialize_mcp(self) -> None:
        """Initialize MCP server connections"""
        if self._mcp_initialized:
            return

        for server_config in self.config.mcp_servers:
            try:
                mcp_server_config = MCPServerConfigClass(
                    name=server_config.name,
                    command=server_config.command,
                    args=server_config.args,
                    env=server_config.env,
                )
                await self.mcp_client.connect_to_server(mcp_server_config)
            except Exception as e:
                print(f"⚠️  Failed to connect to MCP server {server_config.name}: {e}")

        # Get MCP tools and merge with config tools
        try:
            mcp_tools = await self.mcp_client.list_tools()
            # Merge with existing tools
            self.config.tools = list(self.config.tools) + mcp_tools
            print(f"📦 Loaded {len(mcp_tools)} tools from MCP servers")
        except Exception as e:
            print(f"⚠️  Error loading MCP tools: {e}")

        self._mcp_initialized = True

    async def send_event(self, event: Event) -> None:
        """Send event back to client"""
        await self.event_queue.put(event)

    def interrupt(self) -> None:
        """Interrupt current running task"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    async def cleanup(self) -> None:
        """Cleanup session resources"""
        await self.mcp_client.cleanup()
