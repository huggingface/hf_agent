"""WebSocket connection manager for real-time communication with multi-tab support."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class TabConnection:
    """Represents a single tab's WebSocket connection."""

    websocket: WebSocket
    tab_id: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TabCoordinator:
    """Coordinates multiple tabs for the same session.

    Features:
    - Tracks all tabs connected to a session
    - Broadcasts events to all tabs
    - Handles tab conflicts gracefully
    """

    def __init__(self) -> None:
        # session_id -> list of TabConnections
        self._tabs: dict[str, list[TabConnection]] = {}
        self._lock = asyncio.Lock()

    async def add_tab(
        self, session_id: str, websocket: WebSocket, tab_id: str
    ) -> TabConnection:
        """Add a new tab connection for a session.

        Args:
            session_id: Session ID
            websocket: The WebSocket connection
            tab_id: Unique identifier for this tab

        Returns:
            The TabConnection that was created
        """
        async with self._lock:
            if session_id not in self._tabs:
                self._tabs[session_id] = []

            tab = TabConnection(websocket=websocket, tab_id=tab_id)
            self._tabs[session_id].append(tab)

            # Notify other tabs about new connection
            if len(self._tabs[session_id]) > 1:
                await self._notify_tabs(
                    session_id,
                    "tab_joined",
                    {"tab_id": tab_id, "total_tabs": len(self._tabs[session_id])},
                    exclude_tab=tab_id,
                )

            return tab

    async def remove_tab(self, session_id: str, tab_id: str) -> None:
        """Remove a tab connection.

        Args:
            session_id: Session ID
            tab_id: Tab to remove
        """
        async with self._lock:
            if session_id not in self._tabs:
                return

            self._tabs[session_id] = [
                t for t in self._tabs[session_id] if t.tab_id != tab_id
            ]

            # Clean up empty session entries
            if not self._tabs[session_id]:
                del self._tabs[session_id]
            else:
                # Notify remaining tabs
                await self._notify_tabs(
                    session_id,
                    "tab_left",
                    {"tab_id": tab_id, "total_tabs": len(self._tabs[session_id])},
                )

    async def _notify_tabs(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
        exclude_tab: Optional[str] = None,
    ) -> None:
        """Notify tabs about an event (internal, called with lock held)."""
        if session_id not in self._tabs:
            return

        for tab in self._tabs[session_id]:
            if exclude_tab and tab.tab_id == exclude_tab:
                continue
            try:
                await tab.websocket.send_json({"event_type": event_type, "data": data})
            except Exception:
                pass  # Tab might be disconnecting

    def get_tab_count(self, session_id: str) -> int:
        """Get number of tabs connected to a session."""
        return len(self._tabs.get(session_id, []))

    def get_tabs(self, session_id: str) -> list[TabConnection]:
        """Get all tabs for a session."""
        return self._tabs.get(session_id, [])


class ConnectionManager:
    """Manages WebSocket connections for multiple sessions with multi-tab support."""

    def __init__(self) -> None:
        # session_id -> list of WebSockets (multiple tabs per session)
        self.active_connections: dict[str, list[WebSocket]] = {}
        # session_id -> asyncio.Queue for outgoing messages
        self.message_queues: dict[str, asyncio.Queue] = {}
        # Tab coordinator for multi-tab management
        self.tab_coordinator = TabCoordinator()

    async def connect(
        self, websocket: WebSocket, session_id: str, tab_id: Optional[str] = None
    ) -> None:
        """Accept a WebSocket connection and register it.

        Args:
            websocket: The WebSocket to accept
            session_id: Session ID
            tab_id: Optional unique tab identifier
        """
        logger.info(f"Attempting to accept WebSocket for session {session_id}")
        await websocket.accept()

        # Register with connection list
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
            self.message_queues[session_id] = asyncio.Queue()

        self.active_connections[session_id].append(websocket)

        # Register with tab coordinator if tab_id provided
        if tab_id:
            await self.tab_coordinator.add_tab(session_id, websocket, tab_id)

        tab_count = len(self.active_connections[session_id])
        logger.info(
            f"WebSocket connected for session {session_id} (total tabs: {tab_count})"
        )

    def disconnect(
        self, session_id: str, websocket: Optional[WebSocket] = None
    ) -> None:
        """Remove a WebSocket connection.

        Args:
            session_id: Session ID
            websocket: Specific WebSocket to remove (removes all if None)
        """
        if session_id not in self.active_connections:
            return

        if websocket:
            # Remove specific WebSocket
            self.active_connections[session_id] = [
                ws for ws in self.active_connections[session_id] if ws != websocket
            ]
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                if session_id in self.message_queues:
                    del self.message_queues[session_id]
        else:
            # Remove all connections for session
            del self.active_connections[session_id]
            if session_id in self.message_queues:
                del self.message_queues[session_id]

        logger.info(f"WebSocket disconnected for session {session_id}")

    async def send_event(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send an event to all WebSockets for a session.

        Args:
            session_id: Target session
            event_type: Event type string
            data: Optional event data
        """
        if session_id not in self.active_connections:
            logger.warning(f"No active connection for session {session_id}")
            return

        message = {"event_type": event_type}
        if data is not None:
            message["data"] = data

        # Send to all connected tabs
        disconnected = []
        for websocket in self.active_connections[session_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to session {session_id}: {e}")
                disconnected.append(websocket)

        # Clean up disconnected
        for ws in disconnected:
            self.disconnect(session_id, ws)

    async def send_session_sync(
        self, session_id: str, last_synced: str, pending_count: int
    ) -> None:
        """Send session sync status to clients.

        Args:
            session_id: Session that was synced
            last_synced: ISO timestamp of last sync
            pending_count: Number of pending changes
        """
        await self.send_event(
            session_id,
            "session_sync",
            {
                "last_synced": last_synced,
                "pending_count": pending_count,
            },
        )

    async def send_tab_conflict(self, session_id: str, conflicting_tab: str) -> None:
        """Notify about a tab conflict.

        Args:
            session_id: Affected session
            conflicting_tab: Tab that caused the conflict
        """
        await self.send_event(
            session_id,
            "tab_conflict",
            {"conflicting_tab": conflicting_tab},
        )

    async def send_server_shutdown(self, message: str = "Server shutting down") -> None:
        """Broadcast server shutdown warning to all sessions."""
        await self.broadcast("server_shutdown", {"message": message})

    async def broadcast(
        self, event_type: str, data: dict[str, Any] | None = None
    ) -> None:
        """Broadcast an event to all connected sessions."""
        for session_id in list(self.active_connections.keys()):
            await self.send_event(session_id, event_type, data)

    def is_connected(self, session_id: str) -> bool:
        """Check if a session has an active WebSocket connection."""
        return (
            session_id in self.active_connections
            and len(self.active_connections[session_id]) > 0
        )

    def get_queue(self, session_id: str) -> asyncio.Queue | None:
        """Get the message queue for a session."""
        return self.message_queues.get(session_id)

    def get_connection_count(self, session_id: str) -> int:
        """Get number of connections for a session."""
        return len(self.active_connections.get(session_id, []))

    @property
    def total_connections(self) -> int:
        """Get total number of active connections across all sessions."""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()
