"""Event manager for Server-Sent Events (SSE) communication."""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class EventManager:
    """Manages event queues for SSE streaming to clients.

    Each session can have multiple subscribers (browser tabs).
    Events are pushed to all subscriber queues for that session.
    """

    def __init__(self) -> None:
        # session_id -> list of asyncio.Queue (one per connected client)
        self.event_queues: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """Subscribe to events for a session.

        Returns a queue that will receive events for this session.
        The caller should iterate over this queue to get events.

        Args:
            session_id: Session to subscribe to

        Returns:
            Queue that will receive events
        """
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            if session_id not in self.event_queues:
                self.event_queues[session_id] = []
            self.event_queues[session_id].append(queue)

        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from events for a session.

        Args:
            session_id: Session to unsubscribe from
            queue: The queue that was returned by subscribe()
        """
        async with self._lock:
            if session_id in self.event_queues:
                try:
                    self.event_queues[session_id].remove(queue)
                except ValueError:
                    pass  # Already removed

                # Clean up empty session entries
                if not self.event_queues[session_id]:
                    del self.event_queues[session_id]


    async def send_event(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send an event to all subscribers of a session.

        Args:
            session_id: Target session
            event_type: Event type string
            data: Optional event data
        """
        async with self._lock:
            queues = self.event_queues.get(session_id, [])

        if not queues:
            # No subscribers - that's okay, events before connection are dropped
            return

        message = {"event_type": event_type}
        if data is not None:
            message["data"] = data

        # Send to all subscribed clients
        for queue in queues:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(f"Event queue full for session {session_id}")

    async def broadcast(
        self, event_type: str, data: dict[str, Any] | None = None
    ) -> None:
        """Broadcast an event to all sessions."""
        async with self._lock:
            session_ids = list(self.event_queues.keys())

        for session_id in session_ids:
            await self.send_event(session_id, event_type, data)

    async def send_server_shutdown(self, message: str = "Server shutting down") -> None:
        """Broadcast server shutdown warning to all sessions."""
        await self.broadcast("server_shutdown", {"message": message})

    def is_connected(self, session_id: str) -> bool:
        """Check if a session has any SSE subscribers."""
        return session_id in self.event_queues and len(self.event_queues[session_id]) > 0

    def get_connection_count(self, session_id: str) -> int:
        """Get number of SSE subscribers for a session."""
        return len(self.event_queues.get(session_id, []))

    @property
    def total_connections(self) -> int:
        """Get total number of active SSE connections across all sessions."""
        return sum(len(queues) for queues in self.event_queues.values())


# Global event manager instance
event_manager = EventManager()
