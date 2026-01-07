import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from litellm import get_max_tokens

from agent.config import Config
from agent.context_manager.manager import ContextManager


class OpType(Enum):
    USER_INPUT = "user_input"
    EXEC_APPROVAL = "exec_approval"
    INTERRUPT = "interrupt"
    UNDO = "undo"
    COMPACT = "compact"
    SHUTDOWN = "shutdown"


@dataclass
class Event:
    event_type: str
    data: Optional[dict[str, Any]] = None


class Session:
    """
    Maintains agent session state
    Similar to Session in codex-rs/core/src/codex.rs
    """

    def __init__(
        self,
        event_queue: asyncio.Queue,
        config: Config | None = None,
        tool_router=None,
        context_manager: ContextManager | None = None,
    ):
        self.tool_router = tool_router
        tool_specs = tool_router.get_tool_specs_for_llm() if tool_router else []
        self.context_manager = context_manager or ContextManager(
            max_context=get_max_tokens(config.model_name),
            compact_size=0.1,
            untouched_messages=5,
            tool_specs=tool_specs,
        )
        self.event_queue = event_queue
        self.session_id = str(uuid.uuid4())
        self.config = config or Config(
            model_name="anthropic/claude-sonnet-4-5-20250929",
        )
        self.is_running = True
        self.current_task: asyncio.Task | None = None
        self.pending_approval: Optional[dict[str, Any]] = None

        # Session trajectory logging
        self.logged_events: list[dict] = []
        self.session_start_time = datetime.now().isoformat()

    async def send_event(self, event: Event) -> None:
        """Send event back to client and log to trajectory"""
        await self.event_queue.put(event)

        # Log event to trajectory
        self.logged_events.append(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": event.event_type,
                "data": event.data,
            }
        )

    def interrupt(self) -> None:
        """Interrupt current running task"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    def get_trajectory(self) -> dict:
        """Serialize complete session trajectory for logging"""
        return {
            "session_id": self.session_id,
            "session_start_time": self.session_start_time,
            "session_end_time": datetime.now().isoformat(),
            "model_name": self.config.model_name,
            "messages": [msg.model_dump() for msg in self.context_manager.items],
            "events": self.logged_events,
        }

    async def push_to_dataset(self, repo_id: str) -> Optional[str]:
        """
        Push session trajectory to Hugging Face dataset

        Args:
            repo_id: HuggingFace dataset repo ID (e.g. 'username/dataset-name')

        Returns:
            URL to the uploaded file if successful, None otherwise
        """
        try:
            import os

            from datasets import Dataset

            # Get trajectory data
            trajectory = self.get_trajectory()

            # Convert to dataset row format
            row = {
                "session_id": trajectory["session_id"],
                "session_start_time": trajectory["session_start_time"],
                "session_end_time": trajectory["session_end_time"],
                "model_name": trajectory["model_name"],
                "messages": json.dumps(trajectory["messages"]),
                "events": json.dumps(trajectory["events"]),
            }

            # Try to load existing dataset and append
            try:
                from datasets import load_dataset

                existing_dataset = load_dataset(repo_id, split="train")
                new_dataset = Dataset.from_dict(
                    {k: list(existing_dataset[k]) + [v] for k, v in row.items()}
                )
            except Exception:
                # Dataset doesn't exist yet, create new one
                new_dataset = Dataset.from_dict({k: [v] for k, v in row.items()})

            # Push to hub
            new_dataset.push_to_hub(repo_id, private=True, token=os.getenv("HF_TOKEN"))

            return f"https://huggingface.co/datasets/{repo_id}"

        except Exception as e:
            print(f"Failed to push session to dataset: {e}")
            return None
