"""
Message cell widget for displaying user/assistant/system messages
"""

from enum import Enum

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static

# HuggingFace color palette
HF_YELLOW = "#FFD21E"
HF_GREEN = "#98C379"
HF_RED = "#E06C75"
HF_CYAN = "#56B6C2"
HF_FG = "#ABB2BF"
HF_FG_DIM = "#5C6370"


class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"
    SUCCESS = "success"


class MessageCell(Static):
    """Widget for displaying a single message in the chat"""

    DEFAULT_CSS = """
    MessageCell {
        margin: 0 1;
        padding: 0;
    }
    """

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

    def compose(self):
        """No child widgets, we render directly"""
        return []

    def render(self):
        """Render the message with appropriate styling"""
        if self.message_type == MessageType.USER:
            title = "You"
            border_style = HF_CYAN
            title_style = f"bold {HF_CYAN}"
        elif self.message_type == MessageType.ASSISTANT:
            title = "Assistant"
            border_style = HF_GREEN
            title_style = f"bold {HF_GREEN}"
        elif self.message_type == MessageType.SYSTEM:
            title = "System"
            border_style = HF_FG_DIM
            title_style = HF_FG_DIM
        elif self.message_type == MessageType.SUCCESS:
            # No panel for success messages, just styled text
            return Text(self.content, style=f"bold {HF_GREEN}")
        else:  # ERROR
            title = "Error"
            border_style = HF_RED
            title_style = f"bold {HF_RED}"

        # Use markdown for assistant messages, plain text for others
        if self.message_type == MessageType.ASSISTANT:
            content = Markdown(self.content)
        elif self.message_type == MessageType.ERROR:
            content = Text(self.content, style=HF_RED)
        elif self.message_type == MessageType.SYSTEM:
            content = Text(self.content, style=HF_FG_DIM)
        else:
            content = Text(self.content)

        return Panel(
            content,
            title=f"[{title_style}]{title}[/]",
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
        )

    def update_content(self, new_content: str) -> None:
        """Update the message content (for streaming)"""
        self.content = new_content
        self.refresh()
