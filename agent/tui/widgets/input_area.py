"""
Input area widget for user text input
"""

from textual import on
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, Static

from agent.tui.messages import SubmitMessage


class InputArea(Horizontal):
    """Widget for user text input with status indicator"""

    BINDINGS = [
        Binding("enter", "submit", "Send", show=True),
        Binding("escape", "clear", "Clear", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._enabled = True
        self._history: list[str] = []
        self._history_index = -1

    def compose(self):
        """Compose the input area"""
        yield Static(">", id="prompt")
        yield Input(placeholder="Type a message...", id="user-input")
        yield Static("", id="status")

    def _on_mount(self) -> None:
        """Focus input on mount"""
        self.query_one("#user-input", Input).focus()

    @on(Input.Submitted, "#user-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        if not self._enabled:
            return

        text = event.value.strip()
        if not text:
            return

        # Add to history
        self._history.append(text)
        self._history_index = -1

        # Clear input
        event.input.value = ""

        # Post submit message
        self.post_message(SubmitMessage(text))

    def action_submit(self) -> None:
        """Submit action (for binding)"""
        input_widget = self.query_one("#user-input", Input)
        input_widget.action_submit()

    def action_clear(self) -> None:
        """Clear the input"""
        input_widget = self.query_one("#user-input", Input)
        input_widget.value = ""

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable input"""
        self._enabled = enabled
        input_widget = self.query_one("#user-input", Input)
        input_widget.disabled = not enabled

        if enabled:
            self.remove_class("disabled")
            self.remove_class("processing")
            self.set_status("")
            input_widget.focus()
        else:
            self.add_class("disabled")
            self.add_class("processing")
            self.set_status("")

    def set_status(self, status: str) -> None:
        """Update the status text"""
        status_widget = self.query_one("#status", Static)
        status_widget.update(status)

    def focus_input(self) -> None:
        """Focus the input widget"""
        self.query_one("#user-input", Input).focus()

    def history_up(self) -> None:
        """Navigate to previous history item"""
        if not self._history:
            return

        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            input_widget = self.query_one("#user-input", Input)
            input_widget.value = self._history[-(self._history_index + 1)]

    def history_down(self) -> None:
        """Navigate to next history item"""
        if self._history_index > 0:
            self._history_index -= 1
            input_widget = self.query_one("#user-input", Input)
            input_widget.value = self._history[-(self._history_index + 1)]
        elif self._history_index == 0:
            self._history_index = -1
            input_widget = self.query_one("#user-input", Input)
            input_widget.value = ""
