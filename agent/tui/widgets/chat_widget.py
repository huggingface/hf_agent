"""
Chat widget - scrollable container for messages and tool calls
"""

from typing import Any

from textual.containers import VerticalScroll
from textual.widgets import Static

from agent.tui.screens.approval import HF_GREEN
from agent.tui.widgets.message_cell import MessageCell, MessageType
from agent.tui.widgets.plan_widget import PlanWidget
from agent.tui.widgets.tool_call import ToolCallWidget, ToolOutputWidget


class ChatWidget(VerticalScroll):
    """Scrollable container for chat transcript"""

    DEFAULT_CSS = """
    ChatWidget {
        height: 1fr;
        scrollbar-gutter: stable;
        padding: 0;
    }

    ChatWidget > .processing-indicator {
        text-align: center;
        color: $warning;
        padding: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._last_tool_name: str | None = None
        self._assistant_message_widget: MessageCell | None = None
        self._log_widget: Static | None = None
        self._log_lines: list[str] = []

    def compose(self):
        """Initial empty state"""
        yield PlanWidget(id="plan-widget")

    def add_user_message(self, content: str) -> None:
        """Add a user message to the chat"""
        widget = MessageCell(content, MessageType.USER)
        self.mount(widget)
        self.scroll_end(animate=False)

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the chat"""
        # If we already have an assistant message being built, update it
        if self._assistant_message_widget is not None:
            self._assistant_message_widget.update_content(content)
        else:
            widget = MessageCell(content, MessageType.ASSISTANT)
            self._assistant_message_widget = widget
            self.mount(widget)
        self.scroll_end(animate=False)

    def finalize_assistant_message(self) -> None:
        """Mark the current assistant message as complete"""
        self._assistant_message_widget = None

    def add_system_message(self, content: str) -> None:
        """Add a system message to the chat"""
        widget = MessageCell(content, MessageType.SYSTEM)
        self.mount(widget)
        self.scroll_end(animate=False)

    def add_error_message(self, content: str) -> None:
        """Add an error message to the chat"""
        widget = MessageCell(content, MessageType.ERROR)
        self.mount(widget)
        self.scroll_end(animate=False)

    def add_success_message(self, content: str) -> None:
        """Add a success message to the chat (green, no panel)"""
        widget = MessageCell(content, MessageType.SUCCESS)
        self.mount(widget)
        self.scroll_end(animate=False)

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Add a tool call to the chat"""
        self._last_tool_name = tool_name
        widget = ToolCallWidget(tool_name, arguments)
        self.mount(widget)
        self.scroll_end(animate=False)

    def add_tool_output(
        self, output: str, success: bool, tool_name: str | None = None
    ) -> None:
        """Add tool output to the chat"""
        # Use last tool name if not provided
        name = tool_name or self._last_tool_name or ""

        # Don't truncate plan_tool output
        truncate = name != "plan_tool"

        widget = ToolOutputWidget(
            output, success=success, tool_name=name, truncate=truncate
        )
        self.mount(widget)
        self.scroll_end(animate=False)

    def show_processing(self) -> None:
        """Show processing indicator"""
        # Remove existing indicator if any
        self.hide_processing()

        indicator = Static("", classes="processing-indicator")
        indicator.id = "processing-indicator"
        self.mount(indicator)
        self.scroll_end(animate=False)

    def hide_processing(self) -> None:
        """Hide processing indicator"""
        try:
            indicator = self.query_one("#processing-indicator")
            indicator.remove()
        except Exception:
            pass

    def update_plan(self, plan: list[dict] | None = None) -> None:
        """Update the plan widget"""
        try:
            plan_widget = self.query_one("#plan-widget", PlanWidget)
            plan_widget.update_plan(plan)
        except Exception:
            pass

    def add_log_line(self, log_line: str) -> None:
        """Add a log line (for streaming job logs)"""
        from rich.text import Text

        # Create log widget if needed
        if self._log_widget is None:
            self._log_widget = Static("", classes="log-output")
            self._log_widget.id = "log-output"
            self.mount(self._log_widget)
            self._log_lines = []

        # Add log line
        self._log_lines.append(log_line)

        # Update widget with all lines
        content = Text("\n".join(self._log_lines), style=HF_GREEN)
        self._log_widget.update(content)
        self.scroll_end(animate=False)

    def finalize_logs(self) -> None:
        """Finalize log streaming"""
        self._log_widget = None
        self._log_lines = []

    def clear(self) -> None:
        """Clear all messages"""
        for child in list(self.children):
            if child.id != "plan-widget":
                child.remove()
        self._assistant_message_widget = None
        self._last_tool_name = None
        self._log_widget = None
        self._log_lines = []
