"""
Status bar widget for displaying agent state
"""

from textual.widgets import Static
from textual.reactive import reactive


class StatusBar(Static):
    """Minimal status bar showing agent and session state."""

    DEFAULT_CSS = """
    StatusBar {
        background: transparent;
        color: #8B949E;
        height: 1;
        padding: 0 1;
        dock: top;
    }
    """

    agent_status: reactive[str] = reactive("Initializing")
    model_name: reactive[str] = reactive("")
    token_count: reactive[int] = reactive(0)
    yolo_mode: reactive[bool] = reactive(False)
    show_tools: reactive[bool] = reactive(True)

    def render(self) -> str:
        """Render the status bar."""
        parts = []

        # Agent status
        if self.agent_status == "Ready":
            parts.append(f"[green]{self.agent_status}[/]")
        elif self.agent_status == "Processing":
            parts.append(f"[yellow]{self.agent_status}...[/]")
        else:
            parts.append(f"[dim]{self.agent_status}[/]")

        # Model name (shortened)
        if self.model_name:
            model_short = self.model_name.split("/")[-1][:20]
            parts.append(f"[dim]{model_short}[/]")

        # Token count
        if self.token_count > 0:
            parts.append(f"[dim]{self.token_count:,}t[/]")

        # Tool output toggle
        if self.show_tools:
            parts.append("[dim]tools:on[/]")
        else:
            parts.append("[yellow]tools:off[/]")

        # YOLO mode indicator
        if self.yolo_mode:
            parts.append("[bold yellow]YOLO[/]")

        return " | ".join(parts)

    def set_ready(self) -> None:
        """Set status to ready."""
        self.agent_status = "Ready"

    def set_processing(self) -> None:
        """Set status to processing."""
        self.agent_status = "Processing"

    def set_waiting_approval(self) -> None:
        """Set status to waiting for approval."""
        self.agent_status = "Approval"

    def update_tokens(self, count: int) -> None:
        """Update token count."""
        self.token_count = count

    def update_yolo(self, enabled: bool) -> None:
        """Update YOLO mode status."""
        self.yolo_mode = enabled

    def toggle_tools(self) -> bool:
        """Toggle tool output visibility. Returns new state."""
        self.show_tools = not self.show_tools
        return self.show_tools
