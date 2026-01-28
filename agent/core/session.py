import asyncio
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
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
        anthropic_key: Optional[str] = None,
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

        # User's Anthropic API key (optional, overrides env var)
        self.anthropic_key = anthropic_key

        # Session trajectory logging
        self.logged_events: list[dict] = []
        self.session_start_time = datetime.now().isoformat()
        self.turn_count: int = 0
        self.last_auto_save_turn: int = 0

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

    def increment_turn(self) -> None:
        """Increment turn counter (called after each user interaction)"""
        self.turn_count += 1

    async def auto_save_if_needed(self) -> None:
        """Check if auto-save should trigger and save if so (completely non-blocking)"""
        if not self.config.save_sessions:
            return

        interval = self.config.auto_save_interval
        if interval <= 0:
            return

        turns_since_last_save = self.turn_count - self.last_auto_save_turn
        if turns_since_last_save >= interval:
            print(f"\n💾 Auto-saving session (turn {self.turn_count})...")
            # Fire-and-forget save - returns immediately
            self.save_and_upload_detached(self.config.session_dataset_repo)
            self.last_auto_save_turn = self.turn_count

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

    def save_trajectory_local(
        self,
        directory: str = "session_logs",
        upload_status: str = "pending",
        dataset_url: Optional[str] = None,
    ) -> Optional[str]:
        """
        Save trajectory to local JSON file as backup with upload status

        Args:
            directory: Directory to save logs (default: "session_logs")
            upload_status: Status of upload attempt ("pending", "success", "failed")
            dataset_url: URL of dataset if upload succeeded

        Returns:
            Path to saved file if successful, None otherwise
        """
        try:
            log_dir = Path(directory)
            log_dir.mkdir(parents=True, exist_ok=True)

            trajectory = self.get_trajectory()

            # Add upload metadata
            trajectory["upload_status"] = upload_status
            trajectory["upload_url"] = dataset_url
            trajectory["last_save_time"] = datetime.now().isoformat()

            filename = f"session_{self.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = log_dir / filename

            with open(filepath, "w") as f:
                json.dump(trajectory, f, indent=2)

            return str(filepath)
        except Exception as e:
            print(f"Failed to save session locally: {e}")
            return None

    def update_local_save_status(
        self, filepath: str, upload_status: str, dataset_url: Optional[str] = None
    ) -> bool:
        """Update the upload status of an existing local save file"""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            data["upload_status"] = upload_status
            data["upload_url"] = dataset_url
            data["last_save_time"] = datetime.now().isoformat()

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

            return True
        except Exception as e:
            print(f"Failed to update local save status: {e}")
            return False

    def save_and_upload_detached(self, repo_id: str) -> Optional[str]:
        """
        Save session locally and spawn detached subprocess for upload (fire-and-forget)

        Args:
            repo_id: HuggingFace dataset repo ID

        Returns:
            Path to local save file
        """
        # Save locally first (fast, synchronous)
        local_path = self.save_trajectory_local(upload_status="pending")
        if not local_path:
            return None

        # Spawn detached subprocess for upload (fire-and-forget)
        try:
            uploader_script = Path(__file__).parent / "session_uploader.py"

            # Use Popen with detached process
            subprocess.Popen(
                [sys.executable, str(uploader_script), "upload", local_path, repo_id],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
            )
        except Exception as e:
            print(f"⚠️  Failed to spawn upload subprocess: {e}")

        return local_path

    @staticmethod
    def retry_failed_uploads_detached(
        directory: str = "session_logs", repo_id: Optional[str] = None
    ) -> None:
        """
        Spawn detached subprocess to retry failed/pending uploads (fire-and-forget)

        Args:
            directory: Directory containing session logs
            repo_id: Target dataset repo ID
        """
        if not repo_id:
            return

        try:
            uploader_script = Path(__file__).parent / "session_uploader.py"

            # Spawn detached subprocess for retry
            subprocess.Popen(
                [sys.executable, str(uploader_script), "retry", directory, repo_id],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
            )
        except Exception as e:
            print(f"⚠️  Failed to spawn retry subprocess: {e}")
