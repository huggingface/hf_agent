"""Pydantic models for API requests and responses."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class OpType(str, Enum):
    """Operation types matching agent/core/agent_loop.py."""

    USER_INPUT = "user_input"
    EXEC_APPROVAL = "exec_approval"
    INTERRUPT = "interrupt"
    UNDO = "undo"
    COMPACT = "compact"
    SHUTDOWN = "shutdown"


class Operation(BaseModel):
    """Operation to be submitted to the agent."""

    op_type: OpType
    data: dict[str, Any] | None = None


class Submission(BaseModel):
    """Submission wrapper with ID and operation."""

    id: str
    operation: Operation


class ToolApproval(BaseModel):
    """Approval decision for a single tool call."""

    tool_call_id: str
    approved: bool
    feedback: str | None = None
    modified_arguments: dict[str, Any] | None = None  # For edited scripts


class ApprovalRequest(BaseModel):
    """Request to approve/reject tool calls."""

    session_id: str
    approvals: list[ToolApproval]


class SubmitRequest(BaseModel):
    """Request to submit user input."""

    session_id: str
    text: str


class SessionResponse(BaseModel):
    """Response when creating a new session."""

    session_id: str
    ready: bool = True
    model_name: str | None = None


class MessageData(BaseModel):
    """A single message in a session."""

    role: str
    content: str


class ResumeSessionResponse(BaseModel):
    """Response when resuming a persisted session."""

    session_id: str
    ready: bool = True
    messages: list[MessageData] = []


class SessionInfo(BaseModel):
    """Session metadata."""

    session_id: str
    created_at: str
    is_active: bool
    message_count: int
    user_id: str | None = None  # Owner of the session
    model_name: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    active_sessions: int = 0
