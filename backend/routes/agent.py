"""Agent API routes - WebSocket and REST endpoints with user isolation."""

import logging
from typing import Optional

from auth.user_context import UserContext, get_current_user, require_auth
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from lifecycle import lifecycle_manager
from models import (
    ApprovalRequest,
    HealthResponse,
    MessageData,
    ResumeSessionResponse,
    SessionInfo,
    SessionResponse,
    SubmitRequest,
)
from pydantic import BaseModel
from session_manager import session_manager
from websocket import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


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
    return SessionResponse(session_id=session_id, ready=True)


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


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    user: UserContext | None = Depends(get_current_user),
) -> list[SessionInfo]:
    """List sessions owned by the current user.

    Returns empty list if not authenticated.
    """
    user_id = user.user_id if user else None
    sessions = session_manager.list_sessions(user_id=user_id)
    return [SessionInfo(**s) for s in sessions]


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Delete a session.

    Users can only delete their own sessions.
    """
    user_id = user.user_id if user else None
    success = await session_manager.delete_session(session_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
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


class SessionResumeRequest(BaseModel):
    """Request to resume a persisted session."""

    session_id: str


class SessionUpdateRequest(BaseModel):
    """Request to update session metadata."""

    title: Optional[str] = None


class PersistedSessionInfo(BaseModel):
    """Info about a persisted session."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    message_count: int
    last_message_preview: str


@router.get("/sessions/persisted", response_model=list[PersistedSessionInfo])
async def list_persisted_sessions(
    user: UserContext = Depends(require_auth),
) -> list[PersistedSessionInfo]:
    """List user's persisted sessions from HF Dataset.

    Returns sessions stored in the HF Dataset, not just in-memory sessions.
    """
    entries = await lifecycle_manager.list_user_sessions(user.user_id)
    return [
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
        if e.status != "deleted"  # Filter out soft-deleted sessions
    ]


@router.post("/session/{session_id}/resume", response_model=ResumeSessionResponse)
async def resume_session(
    session_id: str,
    user: UserContext = Depends(require_auth),
) -> ResumeSessionResponse:
    """Resume a persisted session.

    Loads the session from HF Dataset and returns the messages for frontend display.
    """
    import json

    # Load persisted session
    persisted = await lifecycle_manager.load_session(session_id)
    if not persisted:
        raise HTTPException(status_code=404, detail="Session not found in storage")

    # Verify ownership
    if persisted.user_id != user.user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this session"
        )

    if persisted.status == "deleted":
        raise HTTPException(status_code=404, detail="Session has been deleted")

    # Parse messages from persisted session
    messages = []
    try:
        raw_messages = json.loads(persisted.messages_json)
        messages = [
            MessageData(role=m.get("role", "unknown"), content=m.get("content", ""))
            for m in raw_messages
            if m.get("role") != "system"  # Skip system messages
        ]
    except json.JSONDecodeError:
        logger.error(f"Failed to parse messages for session {session_id}")

    # Create new in-memory session (uses the original session_id for continuity)
    new_session_id = await session_manager.create_session(
        user_id=user.user_id,
        hf_token=user.hf_token,
        anthropic_key=user.anthropic_key,
    )

    return ResumeSessionResponse(
        session_id=new_session_id,
        ready=True,
        messages=messages,
    )


@router.patch("/session/{session_id}")
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    user: UserContext = Depends(require_auth),
) -> dict:
    """Update session metadata (e.g., title).

    Users can only update their own sessions.
    """
    # Check in-memory session ownership
    info = session_manager.get_session_info(session_id, user_id=user.user_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")

    # For now, just return success - full implementation would update the session
    # and mark it dirty for persistence
    return {"status": "updated", "session_id": session_id}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket, session_id: str, token: str | None = None
) -> None:
    """WebSocket endpoint for real-time events.

    Authentication is passed via query parameter since WebSocket can't use custom headers.
    """
    logger.info(f"WebSocket connection request for session {session_id}")

    # Extract user_id from token (WebSocket auth via query param)
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
            f"WebSocket connection rejected: Session {session_id} not found or not authorized"
        )
        await websocket.close(code=4003, reason="Session not found or not authorized")
        return

    await ws_manager.connect(websocket, session_id)

    try:
        while True:
            # Keep connection alive, handle ping/pong
            data = await websocket.receive_json()

            # Handle client messages (e.g., ping)
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        ws_manager.disconnect(session_id)
