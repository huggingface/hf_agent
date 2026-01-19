"""
Chat log widget for displaying messages and tool outputs
"""

import json

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.widgets import RichLog


class ChatLog(RichLog):
    """RichLog-based widget for displaying chat messages and tool outputs."""

    DEFAULT_CSS = """
    ChatLog {
        background: transparent;
        scrollbar-background: transparent;
        scrollbar-color: #484F58;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            **kwargs,
        )
        self._show_tool_outputs = True

    @property
    def show_tool_outputs(self) -> bool:
        return self._show_tool_outputs

    @show_tool_outputs.setter
    def show_tool_outputs(self, value: bool) -> None:
        self._show_tool_outputs = value

    def write_user_message(self, text: str) -> None:
        """Write a user message to the log."""
        self.write(Text(f"\n> {text}", style="bold cyan"))

    def write_assistant_message(self, content: str) -> None:
        """Write an assistant message with markdown rendering."""
        self.write(Text())  # Empty line
        # Render as markdown for better formatting
        md = Markdown(content)
        self.write(md)

    def write_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Write a tool call to the log."""
        if not self._show_tool_outputs:
            # Collapsed view - just tool name
            self.write(Text(f"  > {tool_name}", style="dim yellow"))
            return

        # Expanded view - full details
        # Format arguments nicely
        args_formatted = json.dumps(arguments, indent=2)

        # Truncate if too long
        lines = args_formatted.split("\n")
        if len(lines) > 10:
            args_formatted = "\n".join(lines[:10]) + f"\n  ... ({len(lines) - 10} more lines)"

        tool_text = Text()
        tool_text.append(f"\n  v {tool_name}", style="bold yellow")

        # Show arguments in a subtle way
        if len(args_formatted) < 200:
            tool_text.append(f" {args_formatted}", style="dim")
        else:
            self.write(tool_text)
            # Use syntax highlighting for JSON
            syntax = Syntax(args_formatted, "json", theme="monokai", line_numbers=False)
            self.write(syntax)
            return

        self.write(tool_text)

    def write_tool_output(self, output: str, success: bool, truncate: bool = True, tool_name: str = None) -> None:
        """Write tool output with proper formatting."""
        if not self._show_tool_outputs:
            # Collapsed view - just show success/fail indicator
            icon = "+" if success else "x"
            style = "dim green" if success else "dim red"
            self.write(Text(f"    {icon}", style=style))
            return

        # Truncate output if needed
        original_lines = output.split("\n")
        if truncate and len(original_lines) > 15:
            display_output = "\n".join(original_lines[:15])
            truncated_msg = f"\n... ({len(original_lines) - 15} more lines)"
        else:
            display_output = output
            truncated_msg = ""

        # Determine style based on success
        border_style = "green" if success else "red"

        # Try to detect and format different output types
        content = self._format_output_content(display_output, tool_name)

        if truncated_msg:
            if isinstance(content, str):
                content = content + truncated_msg
            else:
                content = Group(content, Text(truncated_msg, style="dim"))

        # Create a subtle panel for the output
        panel = Panel(
            content,
            border_style=border_style,
            padding=(0, 1),
            expand=False,
        )
        self.write(panel)

    def _format_output_content(self, output: str, tool_name: str = None):
        """Format output content based on type detection."""
        output_stripped = output.strip()

        # Try to detect JSON
        if output_stripped.startswith("{") or output_stripped.startswith("["):
            try:
                parsed = json.loads(output_stripped)
                formatted_json = json.dumps(parsed, indent=2)
                return Syntax(formatted_json, "json", theme="monokai", line_numbers=False)
            except json.JSONDecodeError:
                pass

        # Try to detect Python code or tracebacks
        if "Traceback (most recent call last)" in output or "def " in output or "class " in output:
            return Syntax(output, "python", theme="monokai", line_numbers=False)

        # Try to detect markdown-like content
        if output_stripped.startswith("#") or "```" in output:
            return Markdown(output)

        # Default: plain text
        return Text(output)

    def write_error(self, message: str) -> None:
        """Write an error message to the log."""
        error_panel = Panel(
            Text(message, style="red"),
            title="Error",
            title_align="left",
            border_style="red",
            padding=(0, 1),
        )
        self.write(error_panel)

    def write_success(self, message: str) -> None:
        """Write a success message to the log."""
        self.write(Text(f"\n{message}", style="green"))

    def write_turn_complete(self) -> None:
        """Write turn complete message."""
        self.write(Text("\n\U0001f917 Turn complete", style="bold green"))

    def write_ready(self) -> None:
        """Write agent ready message."""
        self.write(Text("\U0001f917 Agent ready", style="green"))

    def write_compacted(self, old_tokens: int, new_tokens: int) -> None:
        """Write context compaction message."""
        self.write(Text(
            f"\nCompacted: {old_tokens:,} -> {new_tokens:,} tokens",
            style="dim cyan"
        ))

    def write_info(self, message: str) -> None:
        """Write an info message to the log."""
        self.write(Text(message, style="dim"))
