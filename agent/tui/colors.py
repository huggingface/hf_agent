"""
HuggingFace color palette for TUI
Single source of truth for all color constants
"""

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

# Primary colors
HF_YELLOW = "#FFD21E"
HF_YELLOW_DIM = "#B8960F"
HF_GREEN = "#98C379"
HF_RED = "#E06C75"
HF_CYAN = "#56B6C2"
HF_BLUE = "#61AFEF"

# Text colors
HF_FG = "#ABB2BF"
HF_FG_DIM = "#5C6370"


def create_styled_panel(
    content: Text | Markdown | str,
    title: str,
    color: str,
    padding: tuple[int, int] = (0, 1),
) -> Panel:
    """Create a styled panel with consistent formatting"""
    return Panel(
        content,
        title=f"[bold {color}]{title}[/]",
        title_align="left",
        border_style=color,
        padding=padding,
    )
