"""
Chat widget - scrollable container for messages and tool calls
"""

from typing import Any

from rich.text import Text
from textual.containers import Container, VerticalScroll
from textual.widgets import Static

from agent.tui.screens.approval import HF_GREEN
from agent.tui.widgets.message_cell import MessageCell, MessageType
from agent.tui.widgets.plan_widget import PlanWidget
from agent.tui.widgets.tool_call import ToolCallWidget, ToolOutputWidget


class StreamingLogWidget(Container):
    """Scrollable container for streaming job logs"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.log_lines: list[str] = []
        self._log_content: Static | None = None
        self._scroll_container: VerticalScroll | None = None

    def compose(self):
        """Create the scrollable log container"""
        with VerticalScroll(classes="log-scroll") as scroll:
            self._scroll_container = scroll
            self._log_content = Static("", classes="log-content")
            yield self._log_content

    def add_line(self, line: str) -> None:
        """Add a log line and update the display"""
        self.log_lines.append(line)
        if self._log_content is not None:
            content = Text("\n".join(self.log_lines), style=HF_GREEN)
            self._log_content.update(content)
            # Auto-scroll to bottom
            if self._scroll_container is not None:
                self._scroll_container.scroll_end(animate=False)


class ChatWidget(VerticalScroll):
    """Scrollable container for chat transcript"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._last_tool_name: str | None = None
        self._assistant_message_widget: MessageCell | None = None
        self._log_widget: StreamingLogWidget | None = None

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
        if self._log_widget is None:
            try:
                # Reuse existing widget if present
                self._log_widget = self.query_one("#log-output", StreamingLogWidget)
            except Exception:
                # Create new widget
                self._log_widget = StreamingLogWidget(id="log-output")
                self.mount(self._log_widget)

        self._log_widget.add_line(log_line)
        self.scroll_end(animate=False)

    def finalize_logs(self) -> None:
        """Finalize log streaming"""
        if self._log_widget:
            try:
                self._log_widget.remove()
            except Exception:
                pass
            self._log_widget = None

    def clear(self) -> None:
        """Clear all messages"""
        for child in list(self.children):
            if child.id != "plan-widget":
                child.remove()
        self._assistant_message_widget = None
        self._last_tool_name = None
        self._log_widget = None
