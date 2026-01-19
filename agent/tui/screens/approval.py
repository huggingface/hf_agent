"""
Approval screen for tool execution approval - simple CLI-style
"""

import json
from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from agent.tui.messages import YoloModeActivated

HF_YELLOW = "#FFD21E"
HF_GREEN = "#98C379"
HF_RED = "#E06C75"
HF_CYAN = "#56B6C2"
HF_FG = "#ABB2BF"
HF_FG_DIM = "#5C6370"


class ApprovalScreen(ModalScreen[list[dict[str, Any]]]):
    """Simple approval screen - type yes/no/yolo or feedback"""

    DEFAULT_CSS = """
    ApprovalScreen {
        align: center middle;
    }

    ApprovalScreen > #approval-container {
        width: 90%;
        max-width: 140;
        height: 85%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    ApprovalScreen #tool-info {
        height: 1fr;
        scrollbar-size: 1 1;
    }

    ApprovalScreen #prompt-line {
        height: auto;
        padding: 1 0 0 0;
    }

    ApprovalScreen #prompt-label {
        color: $text-muted;
        margin-bottom: 1;
    }

    ApprovalScreen #approval-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "reject_all", "Reject All"),
    ]

    def __init__(self, tools_data: list[dict[str, Any]], **kwargs):
        super().__init__(**kwargs)
        self.tools_data = tools_data
        self.current_index = 0
        self.approvals: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-container"):
            with VerticalScroll(id="tool-info"):
                yield Static(self._render_tool_info(), id="tool-display")

            with Vertical(id="prompt-line"):
                yield Static(
                    "Approve? (yes/no/yolo or type feedback to reject):",
                    id="prompt-label",
                )
                yield Input(placeholder="yes/no/yolo/feedback...", id="approval-input")

    def _render_tool_info(self) -> Text:
        """Render tool info - NO TRUNCATION"""
        tool = self.tools_data[self.current_index]
        tool_name = tool.get("tool", "")
        arguments = tool.get("arguments", {})

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                pass

        content = Text()

        # Header
        progress = f"[{self.current_index + 1}/{len(self.tools_data)}]"
        content.append(f"{progress} ", style=HF_FG_DIM)
        content.append(f"{tool_name}\n", style=f"bold {HF_YELLOW}")
        content.append("─" * 80 + "\n", style=HF_FG_DIM)

        # Format based on tool type
        if tool_name == "hf_jobs":
            self._format_hf_jobs(content, arguments)
        elif tool_name == "hf_repo_files":
            self._format_hf_repo_files(content, arguments)
        elif tool_name == "hf_repo_git":
            self._format_hf_repo_git(content, arguments)
        else:
            self._format_generic(content, arguments)

        return content

    def _format_hf_jobs(self, content: Text, args: dict) -> None:
        """Format hf_jobs - FULL SCRIPT, NO TRUNCATION"""
        operation = args.get("operation", "run")

        if operation in ("run", "uv"):
            script = args.get("script")
            command = args.get("command")

            if script:
                # Show FULL script
                deps = args.get("dependencies", [])
                if deps:
                    content.append(
                        f"Dependencies: {', '.join(deps)}\n", style=HF_FG_DIM
                    )

                python_ver = args.get("python")
                if python_ver:
                    content.append(f"Python: {python_ver}\n", style=HF_FG_DIM)

                lines = script.split("\n")
                content.append(f"\nScript ({len(lines)} lines):\n", style=HF_FG_DIM)
                content.append(script + "\n", style=HF_FG)

                # Reliability check
                try:
                    from agent.utils.reliability_checks import (
                        check_training_script_save_pattern,
                    )

                    warning = check_training_script_save_pattern(script)
                    if warning:
                        import re

                        clean_warning = re.sub(r"\033\[[0-9;]*m", "", warning)
                        content.append(
                            f"\n⚠️  {clean_warning}\n", style=f"bold {HF_RED}"
                        )
                except ImportError:
                    pass

            elif command:
                image = args.get("image", "python:3.12")
                cmd_str = (
                    " ".join(command) if isinstance(command, list) else str(command)
                )
                content.append(f"Image: {image}\n", style=HF_FG_DIM)
                content.append(f"Command: {cmd_str}\n", style=HF_FG)

            hardware = args.get("hardware_flavor", "cpu-basic")
            timeout = args.get("timeout", "30m")
            content.append(f"\nHardware: {hardware}\n", style=HF_GREEN)
            content.append(f"Timeout: {timeout}\n", style=HF_FG_DIM)

            env = args.get("env", {})
            if env:
                content.append(f"Env: {', '.join(env.keys())}\n", style=HF_FG_DIM)

        elif operation == "logs":
            job_id = args.get("job_id", "")
            content.append(f"Job ID: {job_id}\n", style=HF_CYAN)

        elif operation == "inspect":
            job_id = args.get("job_id", "")
            content.append(f"Job ID: {job_id}\n", style=HF_CYAN)

    def _format_hf_repo_files(self, content: Text, args: dict) -> None:
        """Format hf_repo_files - FULL CONTENT"""
        repo_id = args.get("repo_id", "")
        operation = args.get("operation", "")

        content.append(f"Repo: {repo_id}\n", style=HF_CYAN)
        content.append(f"Operation: {operation}\n\n", style=HF_FG_DIM)

        if operation == "upload":
            path = args.get("path", "")
            file_content = args.get("content", "")
            create_pr = args.get("create_pr", False)

            content.append(f"File: {path}\n", style=HF_FG)
            if create_pr:
                content.append("Mode: Create PR\n", style=HF_YELLOW)

            if isinstance(file_content, str):
                lines = file_content.split("\n")
                size_kb = len(file_content.encode("utf-8")) / 1024
                content.append(
                    f"Size: {size_kb:.2f} KB ({len(lines)} lines)\n\n", style=HF_FG_DIM
                )
                content.append(file_content + "\n", style=HF_FG)

        elif operation == "delete":
            patterns = args.get("patterns", [])
            if isinstance(patterns, str):
                patterns = [patterns]
            content.append(
                f"Delete patterns: {', '.join(patterns)}\n", style=f"bold {HF_RED}"
            )

    def _format_hf_repo_git(self, content: Text, args: dict) -> None:
        """Format hf_repo_git"""
        repo_id = args.get("repo_id", "")
        operation = args.get("operation", "")

        content.append(f"Repo: {repo_id}\n", style=HF_CYAN)
        content.append(f"Operation: {operation}\n", style=HF_FG_DIM)

        if operation == "delete_branch":
            branch = args.get("branch", "")
            content.append(f"\nDelete branch: {branch}\n", style=f"bold {HF_RED}")
        elif operation == "delete_tag":
            tag = args.get("tag", "")
            content.append(f"\nDelete tag: {tag}\n", style=f"bold {HF_RED}")
        elif operation == "merge_pr":
            pr_num = args.get("pr_num", "")
            content.append(f"\nMerge PR #{pr_num}\n", style=f"bold {HF_GREEN}")

    def _format_generic(self, content: Text, args: dict) -> None:
        """Generic - FULL JSON"""
        try:
            args_str = json.dumps(args, indent=2)
            content.append(args_str + "\n", style=HF_FG)
        except (TypeError, ValueError):
            content.append(f"{args}\n", style=HF_FG)

    def _on_mount(self) -> None:
        """Focus input"""
        self.query_one("#approval-input", Input).focus()

    def _update_tool_view(self) -> None:
        """Update display"""
        tool_display = self.query_one("#tool-display", Static)
        tool_display.update(self._render_tool_info())

        input_widget = self.query_one("#approval-input", Input)
        input_widget.value = ""
        input_widget.focus()

    def _process_response(self, response: str) -> None:
        """Process response - yes/no/yolo or feedback"""
        response = response.strip().lower()
        tool_call_id = self.tools_data[self.current_index].get("tool_call_id", "")

        if response == "yolo":
            # Approve current
            self.approvals.append(
                {"tool_call_id": tool_call_id, "approved": True, "feedback": None}
            )
            # Approve all remaining
            for tool in self.tools_data[self.current_index + 1 :]:
                self.approvals.append(
                    {
                        "tool_call_id": tool.get("tool_call_id", ""),
                        "approved": True,
                        "feedback": None,
                    }
                )
            self.post_message(YoloModeActivated())
            self.dismiss(self.approvals)
            return

        # yes/y = approve, no/n = reject, anything else = feedback (reject with message)
        if response in ["yes", "y"]:
            self.approvals.append(
                {"tool_call_id": tool_call_id, "approved": True, "feedback": None}
            )
        elif response in ["no", "n"]:
            self.approvals.append(
                {"tool_call_id": tool_call_id, "approved": False, "feedback": None}
            )
        else:
            # Feedback = reject with message
            self.approvals.append(
                {"tool_call_id": tool_call_id, "approved": False, "feedback": response}
            )

        # Next or finish
        self.current_index += 1
        if self.current_index >= len(self.tools_data):
            self.dismiss(self.approvals)
        else:
            self._update_tool_view()

    @on(Input.Submitted, "#approval-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input"""
        if event.value.strip():
            self._process_response(event.value)

    def action_reject_all(self) -> None:
        """Reject all"""
        tool_call_id = self.tools_data[self.current_index].get("tool_call_id", "")
        self.approvals.append(
            {"tool_call_id": tool_call_id, "approved": False, "feedback": None}
        )

        for tool in self.tools_data[self.current_index + 1 :]:
            self.approvals.append(
                {
                    "tool_call_id": tool.get("tool_call_id", ""),
                    "approved": False,
                    "feedback": None,
                }
            )

        self.dismiss(self.approvals)
