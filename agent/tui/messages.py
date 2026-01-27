"""
Custom Textual messages for the HF Agent TUI
"""

from dataclasses import dataclass, field
from typing import Any

from textual.message import Message


@dataclass
class AgentEvent(Message):
    """Event from the agent loop

    Args:
        event_type: Type of event (e.g., 'ready', 'processing', 'tool_call')
        data: Optional event payload
    """
    event_type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubmitMessage(Message):
    """User submitted a message

    Args:
        text: The user's input text
    """
    text: str


@dataclass
class ApprovalResponse(Message):
    """User responded to approval request

    Args:
        approvals: List of approval decisions for each tool
    """
    approvals: list[dict[str, Any]]


@dataclass
class InputStateChanged(Message):
    """Input state changed (enabled/disabled)

    Args:
        enabled: Whether input is now enabled
    """
    enabled: bool


class YoloModeActivated(Message):
    """YOLO mode was activated - marker message"""
    pass
