"""
Plan widget for displaying the current agent plan
"""

from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static

from agent.tui.colors import (
    HF_BLUE,
    HF_FG,
    HF_FG_DIM,
    HF_GREEN,
    HF_YELLOW,
    create_styled_panel,
)


class PlanWidget(Static):
    """Widget for displaying the current plan from plan_tool"""

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

        return create_styled_panel(content, "Plan", HF_BLUE)

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
