"""Agent API routes - SSE and REST endpoints with user isolation."""

import asyncio
import json
import logging
from typing import Optional

from auth.user_context import UserContext, get_current_user, require_auth
from event_manager import event_manager
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from lifecycle import lifecycle_manager
from models import (
    ApprovalRequest,
    HealthResponse,
    SessionInfo,
    SessionResponse,
    SubmitRequest,
)
from pydantic import BaseModel
from session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


# Models defined early so they can be used in route annotations
class PersistedSessionInfo(BaseModel):
    """Info about a persisted session."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    message_count: int
    last_message_preview: str


class SessionMessagesResponse(BaseModel):
    """Response containing session messages."""

    session_id: str
    messages: list[dict]  # Raw LiteLLM message objects for full UI reconstruction


class SessionUpdateRequest(BaseModel):
    """Request to update session metadata."""

    title: Optional[str] = None
    model_name: Optional[str] = None


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="ok", active_sessions=session_manager.active_session_count
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(
    user: UserContext | None = Depends(get_current_user),
) -> SessionResponse:
    """Create a new agent session.

    If authenticated, the session will be owned by the user and use their tokens.
    Anonymous sessions are allowed but have limited capabilities.
    """
    # Extract user info if authenticated
    user_id = user.user_id if user else None
    hf_token = user.hf_token if user else None
    anthropic_key = user.anthropic_key if user else None

    session_id = await session_manager.create_session(
        user_id=user_id,
        hf_token=hf_token,
        anthropic_key=anthropic_key,
    )

    # Get session info to retrieve model_name
    info = session_manager.get_session_info(session_id, user_id=user_id)
    model_name = info.get("model_name") if info else None

    return SessionResponse(session_id=session_id, ready=True, model_name=model_name)


@router.get("/session/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    user: UserContext | None = Depends(get_current_user),
) -> SessionInfo:
    """Get session information.

    Users can only access their own sessions.
    """
    user_id = user.user_id if user else None
    info = session_manager.get_session_info(session_id, user_id=user_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(**info)


@router.get("/sessions")
async def list_sessions(
    user: UserContext | None = Depends(get_current_user),
) -> list[PersistedSessionInfo]:
    """List all sessions for the current user (from HF Dataset).

    Returns empty list if not authenticated.
    """
    if not user:
        logger.debug("list_sessions: No authenticated user")
        return []

    logger.info(f"list_sessions: Fetching sessions for user_id={user.user_id}")
    entries = await lifecycle_manager.list_user_sessions(user.user_id)
    logger.info(f"list_sessions: Found {len(entries)} sessions for user_id={user.user_id}")

    result = [
        PersistedSessionInfo(
            session_id=e.session_id,
            title=e.title,
            created_at=e.created_at,
            updated_at=e.updated_at,
            status=e.status,
            message_count=e.message_count,
            last_message_preview=e.last_message_preview,
        )
        for e in entries
        if e.status != "deleted"
    ]

    logger.info(f"list_sessions: Returning {len(result)} sessions (after filtering deleted)")
    return result


class SessionActivateResponse(BaseModel):
    """Response from session activation."""

    session_id: str
    messages: list[dict]
    model_name: str | None = None
    status: str  # 'ready' or 'active'


@router.post("/session/{session_id}/activate", response_model=SessionActivateResponse)
async def activate_session(
    session_id: str,
    user: UserContext = Depends(require_auth),
) -> SessionActivateResponse:
    """Activate a session for use.

    This endpoint:
    1. Checks if session exists in memory (already active)
    2. If not, loads from persistence
    3. Creates in-memory session
    4. Returns messages and confirms session is ready

    This guarantees that after this call succeeds, the session is ready for SSE connection.
    """
    # First, check if session is already in memory
    info = session_manager.get_session_info(session_id, user_id=user.user_id)

    if info:
        # Session already in memory - return current messages
        agent_session = session_manager.sessions.get(session_id)
        if agent_session:
            messages = [
                item.model_dump()
                for item in agent_session.session.context_manager.items
                if item.role != "system"
            ]
            return SessionActivateResponse(
                session_id=session_id,
                messages=messages,
                model_name=info.get("model_name"),
                status="active",
            )

    # Session not in memory - load from persistence
    try:
        persisted = await lifecycle_manager.load_session(session_id)
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load session: {str(e)}")

    if not persisted:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    if persisted.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if persisted.status == "deleted":
        raise HTTPException(status_code=404, detail="Session has been deleted")

    # Parse messages
    raw_messages = []
    try:
        raw_messages = json.loads(persisted.messages_json)
        raw_messages = [m for m in raw_messages if m.get("role") != "system"]
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse messages for session {session_id}: {e}")
        raw_messages = []
    except Exception as e:
        logger.error(
            f"Failed to process messages for session {session_id}: {e}", exc_info=True
        )
        raw_messages = []

    # Create in-memory session - this MUST succeed for SSE to work
    try:
        await session_manager.create_session_with_id(
            session_id=session_id,
            user_id=user.user_id,
            hf_token=user.hf_token,
            anthropic_key=user.anthropic_key,
            history=raw_messages,
        )
    except Exception as e:
        logger.error(f"Failed to create in-memory session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate session")

    # Verify session was created
    info = session_manager.get_session_info(session_id, user_id=user.user_id)
    if not info:
        raise HTTPException(status_code=500, detail="Session activation failed")

    return SessionActivateResponse(
        session_id=session_id,
        messages=raw_messages,
        model_name=persisted.model_name,
        status="ready",
    )


@router.get("/session/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(
    session_id: str,
    user: UserContext = Depends(require_auth),
) -> SessionMessagesResponse:
    """Get messages for a session.

    Loads from HF Dataset and creates in-memory session if needed.

    Note: Consider using POST /session/{id}/activate instead, which guarantees
    the session is ready for SSE connection.
    """
    # Load persisted session
    try:
        persisted = await lifecycle_manager.load_session(session_id)
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load session: {str(e)}")

    if not persisted:
        raise HTTPException(status_code=404, detail="Session not found in storage")

    # Verify ownership
    if persisted.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if persisted.status == "deleted":
        raise HTTPException(status_code=404, detail="Session has been deleted")

    # Parse messages - return raw LiteLLM messages for full UI reconstruction
    raw_messages = []
    try:
        raw_messages = json.loads(persisted.messages_json)
        # Filter out system messages
        raw_messages = [m for m in raw_messages if m.get("role") != "system"]
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse messages for session {session_id}: {e}")
        raw_messages = []
    except Exception as e:
        logger.error(
            f"Failed to process messages for session {session_id}: {e}", exc_info=True
        )
        raw_messages = []

    # Create in-memory session if not already active (for continuing conversation)
    try:
        await session_manager.create_session_with_id(
            session_id=session_id,
            user_id=user.user_id,
            hf_token=user.hf_token,
            anthropic_key=user.anthropic_key,
            history=raw_messages,
        )
    except Exception as e:
        logger.error(f"Failed to create in-memory session {session_id}: {e}")
        # Still return messages even if session creation fails
        # User can retry or create a new session

    return SessionMessagesResponse(session_id=session_id, messages=raw_messages)


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Delete a session (soft delete in HF Dataset).

    Users can only delete their own sessions.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Delete from in-memory if exists
    await session_manager.delete_session(session_id, user_id=user.user_id)

    # Soft delete from HF Dataset
    await lifecycle_manager.delete_session(session_id, user.user_id)

    return {"status": "deleted", "session_id": session_id}


@router.post("/submit")
async def submit_input(
    request: SubmitRequest,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Submit user input to a session.

    Users can only submit to their own sessions.
    """
    user_id = user.user_id if user else None
    success = await session_manager.submit_user_input(
        request.session_id, request.text, user_id=user_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    return {"status": "submitted", "session_id": request.session_id}


@router.post("/approve")
async def submit_approval(
    request: ApprovalRequest,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Submit tool approvals to a session.

    Users can only approve tools in their own sessions.
    """
    user_id = user.user_id if user else None
    approvals = [
        {
            "tool_call_id": a.tool_call_id,
            "approved": a.approved,
            "feedback": a.feedback,
        }
        for a in request.approvals
    ]
    success = await session_manager.submit_approval(
        request.session_id, approvals, user_id=user_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    return {"status": "submitted", "session_id": request.session_id}


@router.post("/interrupt/{session_id}")
async def interrupt_session(
    session_id: str,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Interrupt the current operation in a session.

    Users can only interrupt their own sessions.
    """
    user_id = user.user_id if user else None
    success = await session_manager.interrupt(session_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    return {"status": "interrupted", "session_id": session_id}


@router.post("/undo/{session_id}")
async def undo_session(
    session_id: str,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Undo the last turn in a session.

    Users can only undo in their own sessions.
    """
    user_id = user.user_id if user else None
    success = await session_manager.undo(session_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    return {"status": "undo_requested", "session_id": session_id}


@router.post("/compact/{session_id}")
async def compact_session(
    session_id: str,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Compact the context in a session.

    Users can only compact their own sessions.
    """
    user_id = user.user_id if user else None
    success = await session_manager.compact(session_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    return {"status": "compact_requested", "session_id": session_id}


@router.post("/shutdown/{session_id}")
async def shutdown_session(
    session_id: str,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Shutdown a session.

    Users can only shutdown their own sessions.
    """
    user_id = user.user_id if user else None
    success = await session_manager.shutdown_session(session_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    return {"status": "shutdown_requested", "session_id": session_id}


# ============================================================================
# PERSISTENCE ENDPOINTS
# ============================================================================


@router.patch("/session/{session_id}")
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    user: UserContext = Depends(require_auth),
) -> dict:
    """Update session metadata (e.g., title, model).

    Users can only update their own sessions.
    """
    # Check in-memory session ownership
    info = session_manager.get_session_info(session_id, user_id=user.user_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update model if provided
    if request.model_name:
        success = await session_manager.update_session_model(
            session_id, request.model_name, user_id=user.user_id
        )
        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to update session model"
            )

    # For now, just return success
    return {"status": "updated", "session_id": session_id}


@router.get("/events/{session_id}")
async def event_stream(
    session_id: str,
    request: Request,
    token: str | None = None,
) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time agent events.

    Authentication is passed via query parameter for SSE compatibility.
    """

    # Extract user_id from token
    user_id = None
    if token:
        from auth.jwt_handler import jwt_handler

        payload = jwt_handler.verify_token(token)
        if payload:
            user_id = payload.user_id

    # Verify session exists and user has access
    info = session_manager.get_session_info(session_id, user_id=user_id)
    if not info:
        logger.warning(
            f"SSE connection rejected: Session {session_id} not found or not authorized"
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not authorized"
        )

    async def event_generator():
        """Generate SSE events from the event queue."""
        queue = await event_manager.subscribe(session_id)

        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event_type': 'connected'})}\n\n"

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with timeout to allow disconnect check
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"

        finally:
            await event_manager.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
