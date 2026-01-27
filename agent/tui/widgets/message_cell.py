"""
Message cell widget for displaying user/assistant/system messages
"""

from enum import Enum

from rich.markdown import Markdown
from rich.text import Text
from textual.widgets import Static

from agent.tui.colors import (
    HF_CYAN,
    HF_FG_DIM,
    HF_GREEN,
    HF_RED,
    create_styled_panel,
)


class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    NOTE = "note"
    ERROR = "error"
    SUCCESS = "success"


class MessageCell(Static):
    """Widget for displaying a single message in the chat"""

    def __init__(
        self,
        content: str,
        message_type: MessageType = MessageType.ASSISTANT,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.content = content
        self.message_type = message_type
        self.add_class(message_type.value)

    def render(self):
        """Render the message with appropriate styling"""
        if self.message_type == MessageType.USER:
            content = Text(self.content)
            return create_styled_panel(content, "You", HF_CYAN)
        elif self.message_type == MessageType.ASSISTANT:
            content = Markdown(self.content)
            return create_styled_panel(content, "Assistant", HF_GREEN)
        elif self.message_type == MessageType.NOTE:
            content = Text(self.content, style=HF_FG_DIM)
            return create_styled_panel(content, "Note", HF_FG_DIM)
        elif self.message_type == MessageType.SUCCESS:
            # No panel for success messages, just styled text
            return Text(self.content, style=f"bold {HF_GREEN}")
        else:  # ERROR
            content = Text(self.content, style=HF_RED)
            return create_styled_panel(content, "Error", HF_RED)

    def update_content(self, new_content: str) -> None:
        """Update the message content (for streaming)"""
        self.content = new_content
        self.refresh()
