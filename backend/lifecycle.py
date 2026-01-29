"""Session lifecycle management with HF persistence.

Coordinates:
- Session state transitions (active -> closing -> closed)
- Background sync to HF Dataset
- Graceful shutdown with flush
- Session resume from persistence
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from typing import Optional

from event_manager import event_manager
from storage.hf_storage import HFStorageManager, PersistedSession, SessionIndexEntry

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages session lifecycle with HF persistence.

    Handles:
    - Converting in-memory sessions to persisted format
    - Background sync coordination
    - Graceful shutdown
    - Session resume
    """

    def __init__(
        self,
        repo_id: Optional[str] = None,
        hf_token: Optional[str] = None,
        sync_interval: int = 30,
    ):
        """Initialize lifecycle manager.

        Args:
            repo_id: HF Dataset repo ID for persistence
            hf_token: HF token (uses env var if not provided)
            sync_interval: Sync interval in seconds
        """
        self.repo_id = repo_id or os.environ.get(
            "SESSION_DATASET_REPO", "smolagents/hf-agent-sessions"
        )
        # Use dedicated admin token for session storage (not user OAuth tokens)
        self.hf_token = hf_token or os.environ.get("HF_ADMIN_TOKEN")

        # Storage manager
        self._storage: Optional[HFStorageManager] = None
        if self.repo_id and self.hf_token:
            self._storage = HFStorageManager(
                repo_id=self.repo_id,
                hf_token=self.hf_token,
                sync_interval_seconds=sync_interval,
            )

        # Track session states
        self._session_states: dict[str, str] = {}  # session_id -> state
        self._lock = asyncio.Lock()

        # Shutdown handling
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the lifecycle manager."""
        if self._storage:
            await self._storage.start()
        else:
            logger.warning("No persistence configured (missing HF_ADMIN_TOKEN)")

        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()

    async def stop(self) -> None:
        """Stop the lifecycle manager and flush pending changes."""
        self._shutdown_event.set()

        if self._storage:
            await self._storage.stop()


    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_running_loop()

            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(self._handle_signal(s)),
                )
        except (RuntimeError, NotImplementedError):
            # Signal handlers not supported (e.g., Windows)
            pass

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signal."""

        # Notify clients about impending shutdown
        await event_manager.send_server_shutdown(
            f"Server shutting down ({sig.name}). Your session will be saved."
        )

        # Give 5 seconds for flush
        try:
            await asyncio.wait_for(self._flush_all(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Flush timeout during shutdown")

        self._shutdown_event.set()

    async def _flush_all(self) -> None:
        """Flush all dirty sessions immediately."""
        if self._storage:
            await self._storage.force_sync()

    async def persist_session(
        self,
        session_id: str,
        user_id: str,
        messages: list[dict],
        config: dict,
        title: str = "Untitled",
        status: str = "active",
    ) -> None:
        """Persist session state to HF Dataset.

        Args:
            session_id: Session ID
            user_id: Owner user ID
            messages: List of message dicts
            config: Session config
            title: Session title
            status: Session status
        """
        if not self._storage:
            return

        now = datetime.now(timezone.utc).isoformat()

        # Build persisted session
        messages_json = json.dumps(messages)
        message_count = len(messages)

        # Get last message preview
        last_preview = ""
        if messages:
            last_msg = messages[-1]
            content = last_msg.get("content", "")
            if isinstance(content, str):
                last_preview = content[:100]

        # Get version (increment if exists)
        async with self._lock:
            existing_state = self._session_states.get(session_id, "new")
            version = 1
            if existing_state != "new":
                # Try to get existing version
                existing = await self._storage.load_session(session_id)
                if existing:
                    version = existing.version + 1

        session = PersistedSession(
            session_id=session_id,
            user_id=user_id,
            version=version,
            created_at=now
            if existing_state == "new"
            else (existing.created_at if existing else now),
            updated_at=now,
            title=title,
            model_name=config.get("model_name", "unknown"),
            status=status,
            messages_json=messages_json,
            context_summary=None,
            metadata=json.dumps({"config": config}),
            message_count=message_count,
            last_message_preview=last_preview,
        )

        await self._storage.mark_dirty(session)

        async with self._lock:
            self._session_states[session_id] = status

        logger.debug(f"Marked session {session_id} dirty (status: {status})")

    async def close_session(
        self,
        session_id: str,
        user_id: str,
        messages: list[dict],
        config: dict,
        title: str = "Untitled",
    ) -> None:
        """Close a session and force immediate sync.

        Args:
            session_id: Session ID
            user_id: Owner user ID
            messages: Final message list
            config: Session config
            title: Session title
        """
        # Persist with closed status
        await self.persist_session(
            session_id=session_id,
            user_id=user_id,
            messages=messages,
            config=config,
            title=title,
            status="closed",
        )

        # Force immediate sync
        if self._storage:
            await self._storage.force_sync()


    async def load_session(self, session_id: str) -> Optional[PersistedSession]:
        """Load a session from persistence.

        Args:
            session_id: Session to load

        Returns:
            PersistedSession if found
        """
        if not self._storage:
            return None

        return await self._storage.load_session(session_id)

    async def list_user_sessions(self, user_id: str) -> list[SessionIndexEntry]:
        """List sessions for a user from persistence.

        Args:
            user_id: User ID

        Returns:
            List of session index entries
        """
        if not self._storage:
            return []

        return await self._storage.load_user_sessions(user_id)

    async def delete_session(self, session_id: str, user_id: str) -> None:
        """Soft-delete a session.

        Args:
            session_id: Session to delete
            user_id: Owner user ID
        """
        if not self._storage:
            return

        # Load existing session
        existing = await self._storage.load_session(session_id)
        if not existing or existing.user_id != user_id:
            return

        # Mark as deleted
        existing.status = "deleted"
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        existing.version += 1

        await self._storage.mark_dirty(existing)

        async with self._lock:
            self._session_states[session_id] = "deleted"

    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()

    @property
    def pending_sync_count(self) -> int:
        """Get count of sessions pending sync."""
        if self._storage:
            return self._storage.dirty_count
        return 0


# Global lifecycle manager instance
lifecycle_manager = LifecycleManager()
