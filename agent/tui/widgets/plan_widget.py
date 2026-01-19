"""
Plan widget for displaying the current agent plan
"""

from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static

# HuggingFace color palette
HF_YELLOW = "#FFD21E"
HF_GREEN = "#98C379"
HF_RED = "#E06C75"
HF_CYAN = "#56B6C2"
HF_BLUE = "#61AFEF"
HF_FG = "#ABB2BF"
HF_FG_DIM = "#5C6370"


class PlanWidget(Static):
    """Widget for displaying the current plan from plan_tool"""

    DEFAULT_CSS = """
    PlanWidget {
        margin: 0 1;
        padding: 0;
        height: auto;
    }

    PlanWidget.hidden {
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._plan: list[dict] = []

    def render(self):
        """Render the plan"""
        if not self._plan:
            return ""

        content = Text()

        # Group by status
        completed = [t for t in self._plan if t.get("status") == "completed"]
        in_progress = [t for t in self._plan if t.get("status") == "in_progress"]
        pending = [t for t in self._plan if t.get("status") == "pending"]

        if completed:
            for todo in completed:
                content.append("[x] ", style=f"bold {HF_GREEN}")
                content.append(f"{todo.get('id', '?')}. ", style=HF_FG_DIM)
                content.append(f"{todo.get('content', '')}\n", style=HF_GREEN)

        if in_progress:
            for todo in in_progress:
                content.append("[~] ", style=f"bold {HF_YELLOW}")
                content.append(f"{todo.get('id', '?')}. ", style=HF_FG_DIM)
                content.append(
                    f"{todo.get('content', '')}\n", style=f"bold {HF_YELLOW}"
                )

        if pending:
            for todo in pending:
                content.append("[ ] ", style=HF_FG_DIM)
                content.append(f"{todo.get('id', '?')}. ", style=HF_FG_DIM)
                content.append(f"{todo.get('content', '')}\n", style=HF_FG)

        # Summary line
        total = len(self._plan)
        summary = f"{len(completed)}/{total} completed"
        if in_progress:
            summary += f", {len(in_progress)} in progress"
        content.append(f"\n{summary}", style=HF_FG_DIM)

        return Panel(
            content,
            title=f"[bold {HF_BLUE}]Plan[/]",
            title_align="left",
            border_style=HF_BLUE,
            padding=(0, 1),
        )

    def update_plan(self, plan: list[dict] | None = None) -> None:
        """Update the plan display"""
        if plan is None:
            # Try to get plan from plan_tool
            try:
                from agent.tools.plan_tool import get_current_plan

                plan = get_current_plan() or []
            except ImportError:
                plan = []

        self._plan = plan

        if self._plan:
            self.remove_class("hidden")
        else:
            self.add_class("hidden")

        self.refresh()

    def clear_plan(self) -> None:
        """Clear the plan display"""
        self._plan = []
        self.add_class("hidden")
        self.refresh()
