"""Session manager for handling multiple concurrent agent sessions with user isolation."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from event_manager import event_manager
from lifecycle import lifecycle_manager

from agent.config import load_config
from agent.core.agent_loop import process_submission
from agent.core.session import Event, OpType, Session
from agent.core.tools import ToolRouter

# Get project root (parent of backend directory)
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG_PATH = str(PROJECT_ROOT / "configs" / "main_agent_config.json")


# These dataclasses match agent/main.py structure
@dataclass
class Operation:
    """Operation to be executed by the agent."""

    op_type: OpType
    data: Optional[dict[str, Any]] = None


@dataclass
class Submission:
    """Submission to the agent loop."""

    id: str
    operation: Operation


logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """Context for the authenticated user of a session."""

    user_id: str  # HF username
    hf_token: str  # HF OAuth access token
    anthropic_key: Optional[str] = None  # User's Anthropic API key


@dataclass
class AgentSession:
    """Wrapper for an agent session with its associated resources."""

    session_id: str
    session: Session
    tool_router: ToolRouter
    submission_queue: asyncio.Queue
    task: asyncio.Task | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    # User isolation
    user_id: Optional[str] = None  # Owner of this session
    user_context: Optional[UserContext] = None  # User's auth context


class SessionManager:
    """Manages multiple concurrent agent sessions with user isolation."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config = load_config(config_path or DEFAULT_CONFIG_PATH)
        self.sessions: dict[str, AgentSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        user_id: Optional[str] = None,
        hf_token: Optional[str] = None,
        anthropic_key: Optional[str] = None,
    ) -> str:
        """Create a new agent session and return its ID.

        Args:
            user_id: Optional owner user ID (HF username)
            hf_token: Optional HF OAuth token for the user
            anthropic_key: Optional Anthropic API key for the user

        Returns:
            Session ID (UUID)
        """
        session_id = str(uuid.uuid4())

        # Create queues for this session
        submission_queue: asyncio.Queue = asyncio.Queue()
        event_queue: asyncio.Queue = asyncio.Queue()

        # Create user context if user is authenticated
        user_context = None
        if user_id and hf_token:
            user_context = UserContext(
                user_id=user_id,
                hf_token=hf_token,
                anthropic_key=anthropic_key,
            )

        # Create tool router with user context for token injection
        tool_router = ToolRouter(
            self.config.mcpServers,
            hf_token=hf_token,  # Pass user's HF token
        )

        # Create the agent session with user's keys if provided
        session = Session(
            event_queue,
            config=self.config,
            tool_router=tool_router,
            anthropic_key=anthropic_key,
            hf_token=hf_token,
        )

        # Create wrapper
        agent_session = AgentSession(
            session_id=session_id,
            session=session,
            tool_router=tool_router,
            submission_queue=submission_queue,
            user_id=user_id,
            user_context=user_context,
        )

        async with self._lock:
            self.sessions[session_id] = agent_session

        # Start the agent loop task
        task = asyncio.create_task(
            self._run_session(session_id, submission_queue, event_queue, tool_router)
        )
        agent_session.task = task

        return session_id

    async def create_session_with_id(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        hf_token: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        """Create an agent session with a specific ID (for resuming).

        Args:
            session_id: The session ID to use
            user_id: Optional owner user ID (HF username)
            hf_token: Optional HF OAuth token for the user
            anthropic_key: Optional Anthropic API key for the user

        Returns:
            Session ID
        """
        # Check if session already exists in memory
        if session_id in self.sessions:
            return session_id

        # Create queues for this session
        submission_queue: asyncio.Queue = asyncio.Queue()
        event_queue: asyncio.Queue = asyncio.Queue()

        # Create user context if user is authenticated
        user_context = None
        if user_id and hf_token:
            user_context = UserContext(
                user_id=user_id,
                hf_token=hf_token,
                anthropic_key=anthropic_key,
            )

        # Create tool router with user context for token injection
        tool_router = ToolRouter(
            self.config.mcpServers,
            hf_token=hf_token,
        )

        # Create the agent session
        session = Session(
            event_queue,
            config=self.config,
            tool_router=tool_router,
            anthropic_key=anthropic_key,
            hf_token=hf_token,
        )

        # Restore conversation history if provided
        if history:
            from litellm import Message

            for msg in history:
                if msg.get("role") != "system":  # Skip system, we have our own
                    session.context_manager.items.append(Message(**msg))

        # Create wrapper with the specified session_id
        agent_session = AgentSession(
            session_id=session_id,
            session=session,
            tool_router=tool_router,
            submission_queue=submission_queue,
            user_id=user_id,
            user_context=user_context,
        )

        async with self._lock:
            self.sessions[session_id] = agent_session

        # Start the agent loop task
        task = asyncio.create_task(
            self._run_session(session_id, submission_queue, event_queue, tool_router)
        )
        agent_session.task = task

        return session_id

    def _check_session_ownership(
        self, session_id: str, user_id: Optional[str]
    ) -> AgentSession | None:
        """Check if user owns the session and return it if so.

        Args:
            session_id: Session to check
            user_id: User to verify ownership

        Returns:
            AgentSession if user owns it or session has no owner, None otherwise
        """
        agent_session = self.sessions.get(session_id)
        if not agent_session:
            return None

        # If session has an owner, verify it matches
        if agent_session.user_id and agent_session.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to access session {session_id} "
                f"owned by {agent_session.user_id}"
            )
            return None

        return agent_session

    async def _run_session(
        self,
        session_id: str,
        submission_queue: asyncio.Queue,
        event_queue: asyncio.Queue,
        tool_router: ToolRouter,
    ) -> None:
        """Run the agent loop for a session and forward events to SSE clients."""
        agent_session = self.sessions.get(session_id)
        if not agent_session:
            logger.error(f"Session {session_id} not found")
            return

        session = agent_session.session

        # Start event forwarder task
        event_forwarder = asyncio.create_task(
            self._forward_events(session_id, event_queue)
        )

        try:
            async with tool_router:
                # Send ready event
                await session.send_event(
                    Event(event_type="ready", data={"message": "Agent initialized"})
                )

                while session.is_running:
                    try:
                        # Wait for submission with timeout to allow checking is_running
                        submission = await asyncio.wait_for(
                            submission_queue.get(), timeout=1.0
                        )
                        should_continue = await process_submission(session, submission)

                        # Persist session after each turn
                        await self._persist_session(session_id)

                        if not should_continue:
                            break
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error in session {session_id}: {e}")
                        await session.send_event(
                            Event(event_type="error", data={"error": str(e)})
                        )

        finally:
            event_forwarder.cancel()
            try:
                await event_forwarder
            except asyncio.CancelledError:
                pass

            async with self._lock:
                if session_id in self.sessions:
                    self.sessions[session_id].is_active = False

    async def _persist_session(self, session_id: str) -> None:
        """Persist session state to HF Dataset."""
        agent_session = self.sessions.get(session_id)
        if not agent_session:
            return

        # Serialize full message objects (preserves tool_calls, tool_call_id, etc.)
        messages = [
            item.model_dump() for item in agent_session.session.context_manager.items
        ]

        await lifecycle_manager.persist_session(
            session_id=session_id,
            user_id=agent_session.user_id or "anonymous",
            messages=messages,
            config={"model_name": self.config.model_name},
            title=f"Chat {session_id[:8]}",
            status="active",
        )

    async def _forward_events(
        self, session_id: str, event_queue: asyncio.Queue
    ) -> None:
        """Forward events from the agent to SSE clients."""
        while True:
            try:
                event: Event = await event_queue.get()
                await event_manager.send_event(session_id, event.event_type, event.data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error forwarding event for {session_id}: {e}")

    async def submit(
        self, session_id: str, operation: Operation, user_id: Optional[str] = None
    ) -> bool:
        """Submit an operation to a session.

        Args:
            session_id: Target session
            operation: Operation to submit
            user_id: User making the request (for ownership check)

        Returns:
            True if submitted successfully
        """
        async with self._lock:
            agent_session = self._check_session_ownership(session_id, user_id)

        if not agent_session or not agent_session.is_active:
            logger.warning(
                f"Session {session_id} not found, inactive, or access denied"
            )
            return False

        submission = Submission(id=f"sub_{uuid.uuid4().hex[:8]}", operation=operation)
        await agent_session.submission_queue.put(submission)
        return True

    async def submit_user_input(
        self, session_id: str, text: str, user_id: Optional[str] = None
    ) -> bool:
        """Submit user input to a session."""
        operation = Operation(op_type=OpType.USER_INPUT, data={"text": text})
        return await self.submit(session_id, operation, user_id)

    async def submit_approval(
        self,
        session_id: str,
        approvals: list[dict[str, Any]],
        user_id: Optional[str] = None,
    ) -> bool:
        """Submit tool approvals to a session."""
        operation = Operation(
            op_type=OpType.EXEC_APPROVAL, data={"approvals": approvals}
        )
        return await self.submit(session_id, operation, user_id)

    async def interrupt(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Interrupt a session."""
        operation = Operation(op_type=OpType.INTERRUPT)
        return await self.submit(session_id, operation, user_id)

    async def undo(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Undo last turn in a session."""
        operation = Operation(op_type=OpType.UNDO)
        return await self.submit(session_id, operation, user_id)

    async def compact(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Compact context in a session."""
        operation = Operation(op_type=OpType.COMPACT)
        return await self.submit(session_id, operation, user_id)

    async def shutdown_session(
        self, session_id: str, user_id: Optional[str] = None
    ) -> bool:
        """Shutdown a specific session."""
        operation = Operation(op_type=OpType.SHUTDOWN)
        success = await self.submit(session_id, operation, user_id)

        if success:
            async with self._lock:
                agent_session = self._check_session_ownership(session_id, user_id)
                if agent_session and agent_session.task:
                    # Wait for task to complete
                    try:
                        await asyncio.wait_for(agent_session.task, timeout=5.0)
                    except asyncio.TimeoutError:
                        agent_session.task.cancel()

            # Close and persist the session
            agent_session = self.sessions.get(session_id)
            if agent_session:
                messages = [
                    item.model_dump()
                    for item in agent_session.session.context_manager.items
                ]
                await lifecycle_manager.close_session(
                    session_id=session_id,
                    user_id=agent_session.user_id or "anonymous",
                    messages=messages,
                    config={"model_name": self.config.model_name},
                    title=f"Chat {session_id[:8]}",
                )

        return success

    async def delete_session(
        self, session_id: str, user_id: Optional[str] = None
    ) -> bool:
        """Delete a session entirely.

        Args:
            session_id: Session to delete
            user_id: User making the request (for ownership check)

        Returns:
            True if deleted successfully
        """
        async with self._lock:
            agent_session = self._check_session_ownership(session_id, user_id)
            if not agent_session:
                return False

            # Remove from sessions
            self.sessions.pop(session_id, None)

        # Cancel the task if running
        if agent_session.task and not agent_session.task.done():
            agent_session.task.cancel()
            try:
                await agent_session.task
            except asyncio.CancelledError:
                pass

        return True

    async def update_session_model(
        self, session_id: str, model_name: str, user_id: Optional[str] = None
    ) -> bool:
        """Update the model for an active session.

        Args:
            session_id: Target session
            model_name: New model name
            user_id: User making the request (for ownership check)

        Returns:
            True if updated successfully
        """
        async with self._lock:
            agent_session = self._check_session_ownership(session_id, user_id)

        if not agent_session:
            return False

        # Update the model in session config
        agent_session.session.config.model_name = model_name
        
        # Persist the change
        await self._persist_session(session_id)
        
        return True

    def get_session_info(
        self, session_id: str, user_id: Optional[str] = None
    ) -> dict[str, Any] | None:
        """Get information about a session.

        Args:
            session_id: Session to get info for
            user_id: User making the request (for ownership check)

        Returns:
            Session info dict or None if not found/access denied
        """
        agent_session = self._check_session_ownership(session_id, user_id)
        if not agent_session:
            return None

        return {
            "session_id": session_id,
            "created_at": agent_session.created_at.isoformat(),
            "is_active": agent_session.is_active,
            "message_count": len(agent_session.session.context_manager.items),
            "user_id": agent_session.user_id,
            "model_name": agent_session.session.config.model_name,
        }

    def list_sessions(self, user_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List sessions, optionally filtered by user.

        Args:
            user_id: If provided, only return sessions owned by this user

        Returns:
            List of session info dicts
        """
        results = []
        for sid, agent_session in self.sessions.items():
            # If user_id provided, only include sessions owned by that user
            if user_id and agent_session.user_id != user_id:
                continue

            info = self.get_session_info(sid, user_id)
            if info:
                results.append(info)

        return results

    @property
    def active_session_count(self) -> int:
        """Get count of active sessions."""
        return sum(1 for s in self.sessions.values() if s.is_active)


# Global session manager instance
session_manager = SessionManager()
