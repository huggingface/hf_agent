"""
User input widget with history support
"""

from textual.widgets import Input
from textual.message import Message


class UserInput(Input):
    """Input widget with submit handling."""

    DEFAULT_CSS = """
    UserInput {
        background: transparent;
        border: none;
        padding: 0 1;
        height: auto;
        min-height: 1;
    }

    UserInput:focus {
        border: none;
    }

    UserInput > .input--placeholder {
        color: #6E7681;
    }
    """

    class Submitted(Message):
        """Message sent when user submits input."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(self, **kwargs):
        super().__init__(
            placeholder="> Type your message...",
            **kwargs,
        )
        self._history: list[str] = []
        self._history_index: int = -1

    async def action_submit(self) -> None:
        """Handle input submission."""
        value = self.value.strip()
        if value:
            # Add to history
            self._history.append(value)
            self._history_index = -1

            # Post message and clear
            self.post_message(self.Submitted(value))
            self.value = ""

    def action_cursor_up(self) -> None:
        """Navigate up in history."""
        if self._history:
            if self._history_index == -1:
                self._history_index = len(self._history) - 1
            elif self._history_index > 0:
                self._history_index -= 1
            self.value = self._history[self._history_index]
            self.cursor_position = len(self.value)

    def action_cursor_down(self) -> None:
        """Navigate down in history."""
        if self._history and self._history_index != -1:
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.value = self._history[self._history_index]
            else:
                self._history_index = -1
                self.value = ""
            self.cursor_position = len(self.value)

    def set_processing(self, processing: bool) -> None:
        """Enable/disable input during processing."""
        self.disabled = processing
        if processing:
            self.placeholder = "Processing..."
        else:
            self.placeholder = "> Type your message..."
