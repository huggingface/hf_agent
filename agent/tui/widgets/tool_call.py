"""
Tool call widget for displaying tool calls and their outputs
"""

import json
from typing import Any

from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.widgets import Collapsible, Static

# HuggingFace color palette
HF_YELLOW = "#FFD21E"
HF_YELLOW_DIM = "#B8960F"
HF_GREEN = "#98C379"
HF_RED = "#E06C75"
HF_CYAN = "#56B6C2"
HF_FG = "#ABB2BF"
HF_FG_DIM = "#5C6370"


class ToolCallWidget(Static):
    """Widget for displaying a tool call with its arguments"""

    DEFAULT_CSS = """
    ToolCallWidget {
        margin: 0 1;
        padding: 0;
    }
    """

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        collapsed: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.arguments = arguments
        self.collapsed = collapsed

    def render(self):
        """Render the tool call"""
        # Format arguments for display
        try:
            args_str = json.dumps(self.arguments, indent=2)
            # Truncate if too long for collapsed view
            if self.collapsed and len(args_str) > 200:
                args_preview = json.dumps(self.arguments)[:100] + "..."
            else:
                args_preview = args_str
        except (TypeError, ValueError):
            args_preview = str(self.arguments)[:200]

        content = Text()
        content.append("Calling tool: ", style=HF_YELLOW)
        content.append(f"{self.tool_name}", style=f"bold {HF_YELLOW}")
        content.append("\n")
        content.append(args_preview, style=HF_FG_DIM)

        return Panel(
            content,
            title=f"[bold {HF_YELLOW}]Tool Call[/]",
            title_align="left",
            border_style=HF_YELLOW,
            padding=(0, 1),
        )


class ToolOutputWidget(Static):
    """Widget for displaying tool output with scrollable container for long outputs"""

    DEFAULT_CSS = """
    ToolOutputWidget {
        margin: 0 1;
        padding: 0;
    }

    ToolOutputWidget .output-scroll {
        height: auto;
        max-height: 30;
        border: none;
        padding: 0 1;
    }

    ToolOutputWidget .output-text {
        padding: 0;
    }
    """

    def __init__(
        self,
        output: str,
        success: bool = True,
        tool_name: str = "",
        truncate: bool = True,
        max_lines: int = 100,  # Increased from 10 to 100
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.output = output
        self.success = success
        self.tool_name = tool_name
        self.truncate = truncate
        self.max_lines = max_lines
        self.add_class("success" if success else "error")

    def render(self):
        """Render the tool output"""
        lines = self.output.split("\n")
        line_count = len(lines)

        # Yellow for success (like original), red for error
        if self.success:
            border_style = HF_YELLOW
            title_style = f"bold {HF_YELLOW}"
            text_style = HF_FG
        else:
            border_style = HF_RED
            title_style = f"bold {HF_RED}"
            text_style = HF_RED

        # Show line count and char count in title
        title = f"Tool output ({line_count} lines, {len(self.output)} chars)"

        # If output is short enough, render directly
        if line_count <= 30:
            content = Text(self.output, style=text_style)
        else:
            # For long output, show indication that it's scrollable
            content = Text(self.output, style=text_style)
            title = f"Tool output ({line_count} lines, {len(self.output)} chars) - Scrollable"

        return Panel(
            content,
            title=f"[{title_style}]{title}[/]",
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
        )


class CollapsibleToolCall(Collapsible):
    """Collapsible container for tool call and output"""

    DEFAULT_CSS = """
    CollapsibleToolCall {
        margin: 0 1;
        padding: 0;
    }
    """

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        output: str | None = None,
        success: bool = True,
        **kwargs,
    ) -> None:
        title = f"Tool: {tool_name}"
        super().__init__(title=title, collapsed=True, **kwargs)
        self.tool_name = tool_name
        self.arguments = arguments
        self.output = output
        self.success = success

    def compose(self):
        """Compose the collapsible content"""
        # Arguments section
        try:
            args_str = json.dumps(self.arguments, indent=2)
            yield Static(
                Panel(
                    Syntax(args_str, "json", theme="monokai"),
                    title=f"[bold {HF_YELLOW}]Arguments[/]",
                    border_style=HF_YELLOW,
                )
            )
        except (TypeError, ValueError):
            yield Static(
                Panel(
                    str(self.arguments),
                    title=f"[bold {HF_YELLOW}]Arguments[/]",
                    border_style=HF_YELLOW,
                )
            )

        # Output section if available
        if self.output is not None:
            if self.success:
                border_style = HF_YELLOW
                title_style = f"bold {HF_YELLOW}"
            else:
                border_style = HF_RED
                title_style = f"bold {HF_RED}"

            yield Static(
                Panel(
                    self.output,
                    title=f"[{title_style}]Output[/]",
                    border_style=border_style,
                )
            )
