"""
Plan panel widget for displaying todo list
"""

from rich.table import Table
from rich.text import Text
from textual.widgets import Static


class PlanPanel(Static):
    """Panel displaying the current plan/todo list."""

    DEFAULT_CSS = """
    PlanPanel {
        background: transparent;
        padding: 0 1;
        height: auto;
        display: none;
    }

    PlanPanel.visible {
        display: block;
        padding-top: 1;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._plan_data: list = []

    def update_plan(self, todos: list) -> None:
        """Update the plan display with new todos."""
        self._plan_data = todos
        if todos:
            self.add_class("visible")
        else:
            self.remove_class("visible")
        self.refresh()

    def render(self):
        """Render the plan panel as a table."""
        if not self._plan_data:
            return ""

        # Create a minimal table
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=(0, 1),
            expand=False,
        )
        table.add_column("Status", width=3)
        table.add_column("Task")

        for todo in self._plan_data:
            status = todo.get("status", "pending")
            content = todo.get("content", "")

            if status == "completed":
                status_icon = Text("[x]", style="green")
                task_text = Text(content, style="dim")
            elif status == "in_progress":
                status_icon = Text("[~]", style="yellow")
                task_text = Text(content, style="bold")
            else:
                status_icon = Text("[ ]", style="dim")
                task_text = Text(content)

            table.add_row(status_icon, task_text)

        return table

    def clear_plan(self) -> None:
        """Clear the plan display."""
        self._plan_data = []
        self.remove_class("visible")
        self.refresh()
