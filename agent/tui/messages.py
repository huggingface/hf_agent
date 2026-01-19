"""
Custom Textual messages for the HF Agent TUI
"""

from typing import Any

from textual.message import Message


class AgentEvent(Message):
    """Event from the agent loop"""

    def __init__(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        self.event_type = event_type
        self.data = data or {}
        super().__init__()


class SubmitMessage(Message):
    """User submitted a message"""

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


class ApprovalResponse(Message):
    """User responded to approval request"""

    def __init__(self, approvals: list[dict[str, Any]]) -> None:
        self.approvals = approvals
        super().__init__()


class InputStateChanged(Message):
    """Input state changed (enabled/disabled)"""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        super().__init__()


class YoloModeActivated(Message):
    """YOLO mode was activated"""

    pass
