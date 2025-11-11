import asyncio
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel

from agent.context_manager.manager import ContextManager
from agent.core import ToolExecutor
from agent.config import Config


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
        self.tool_executor = ToolExecutor()
        self.event_queue = event_queue
        self.config = config or Config(
            model_name="gpt-3.5-turbo", tools=[], system_prompt_path=""
        )
        self.is_running = True
        self.current_task: asyncio.Task | None = None

    async def send_event(self, event: Event) -> None:
        """Send event back to client"""
        await self.event_queue.put(event)

    def interrupt(self) -> None:
        """Interrupt current running task"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
