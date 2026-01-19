"""
Approval screen for tool execution confirmation
"""

import json
from typing import Optional

from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, RichLog

from agent.config import Config
from agent.utils.reliability_checks import check_training_script_save_pattern


class ApprovalScreen(ModalScreen[list | None]):
    """Modal screen for approving tool executions."""

    BINDINGS = [
        ("y", "approve", "Approve"),
        ("n", "reject", "Reject"),
        ("a", "approve_all", "YOLO Mode"),
        ("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ApprovalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #approval_dialog {
        background: #161B22;
        border: solid #FFD21E;
        width: 85%;
        max-width: 120;
        height: auto;
        max-height: 85%;
        padding: 1 2;
    }

    #approval_header {
        background: #FFD21E;
        color: #0D1117;
        text-align: center;
        padding: 0 1;
        text-style: bold;
    }

    #tool_info {
        height: 2;
        padding: 0 1;
        background: #21262D;
        margin-top: 1;
    }

    #approval_content {
        height: auto;
        max-height: 40;
        overflow-y: auto;
        background: #0D1117;
        padding: 1;
        margin-top: 1;
        border: solid #30363D;
    }

    #actions_footer {
        height: auto;
        padding: 1;
        margin-top: 1;
        background: #21262D;
        text-align: center;
    }

    #item_counter {
        text-align: center;
        color: #8B949E;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self, tools_data: list, config: Optional[Config] = None):
        super().__init__()
        self.tools_data = tools_data
        self.config = config
        self.current_index = 0
        self.approvals: list[dict] = []

    def compose(self) -> ComposeResult:
        """Compose the approval dialog."""
        count = len(self.tools_data)
        with Vertical(id="approval_dialog"):
            yield Static(f"APPROVAL REQUIRED", id="approval_header")
            yield Static("", id="tool_info")
            yield Static("", id="item_counter")
            yield RichLog(id="approval_content", highlight=True, markup=True, wrap=True)
            yield Static("", id="actions_footer")

    def on_mount(self) -> None:
        """Display the first tool when mounted."""
        self._update_actions_footer()
        self._display_current_tool()

    def _update_actions_footer(self) -> None:
        """Update the actions footer with available keybindings."""
        footer = self.query_one("#actions_footer", Static)

        actions = Table(show_header=False, show_edge=False, box=None, padding=(0, 2), expand=True)
        actions.add_column("key", style="bold yellow", justify="center")
        actions.add_column("action", justify="center")
        actions.add_column("key", style="bold yellow", justify="center")
        actions.add_column("action", justify="center")

        actions.add_row("y", "Approve", "n", "Reject")
        actions.add_row("a", "YOLO (approve all)", "esc", "Cancel all")

        footer.update(actions)

    def _display_current_tool(self) -> None:
        """Display the current tool in the approval dialog."""
        if self.current_index >= len(self.tools_data):
            return

        content = self.query_one("#approval_content", RichLog)
        counter = self.query_one("#item_counter", Static)
        tool_info = self.query_one("#tool_info", Static)

        content.clear()

        # Update counter
        total = len(self.tools_data)
        counter.update(f"[dim]Item {self.current_index + 1} of {total}[/]")

        tool_data = self.tools_data[self.current_index]
        tool_name = tool_data.get("tool", "")
        arguments = tool_data.get("arguments", {})

        # Handle case where arguments might be a JSON string
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        operation = arguments.get("operation", "")

        # Update tool info header
        info_text = Text()
        info_text.append(tool_name, style="bold yellow")
        if operation:
            info_text.append(f"  {operation}", style="cyan")
        tool_info.update(info_text)

        # Display tool-specific details
        if tool_name == "hf_jobs":
            self._display_hf_jobs(content, arguments)
        elif tool_name == "hf_private_repos":
            self._display_hf_private_repos(content, arguments, operation)
        elif tool_name == "hf_repo_files":
            self._display_hf_repo_files(content, arguments, operation)
        elif tool_name == "hf_repo_git":
            self._display_hf_repo_git(content, arguments, operation)
        else:
            # Generic display for other tools
            content.write(Text("Arguments:", style="bold"))
            syntax = Syntax(json.dumps(arguments, indent=2), "json", theme="monokai", line_numbers=False)
            content.write(syntax)

    def _display_hf_jobs(self, content: RichLog, arguments: dict) -> None:
        """Display hf_jobs tool details."""
        script = arguments.get("script")
        command = arguments.get("command")

        # Show summary table first
        summary = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
        summary.add_column("key", style="dim")
        summary.add_column("value")

        hardware = arguments.get("hardware_flavor", "cpu-basic")
        timeout = arguments.get("timeout", "30m")
        schedule = arguments.get("schedule")

        summary.add_row("Hardware:", Text(hardware, style="cyan bold"))
        summary.add_row("Timeout:", timeout)
        if schedule:
            summary.add_row("Schedule:", schedule)

        env = arguments.get("env", {})
        if env:
            summary.add_row("Env vars:", ", ".join(env.keys()))

        content.write(summary)
        content.write(Text())

        if script:
            # Python mode
            dependencies = arguments.get("dependencies", [])
            python_version = arguments.get("python")
            script_args = arguments.get("script_args", [])

            if dependencies:
                content.write(Text.assemble(
                    ("Dependencies: ", "dim"),
                    (", ".join(dependencies), ""),
                ))

            if python_version:
                content.write(Text.assemble(
                    ("Python: ", "dim"),
                    (python_version, ""),
                ))

            if script_args:
                content.write(Text.assemble(
                    ("Args: ", "dim"),
                    (" ".join(script_args), ""),
                ))

            content.write(Text("\nScript:", style="bold"))
            syntax = Syntax(script, "python", theme="monokai", line_numbers=True)
            content.write(syntax)

            # Run reliability checks
            check_message = check_training_script_save_pattern(script)
            if check_message:
                content.write(Text(f"\n{check_message}", style="yellow"))

        elif command:
            # Docker mode
            image = arguments.get("image", "python:3.12")
            command_str = " ".join(command) if isinstance(command, list) else str(command)

            content.write(Text.assemble(
                ("Image: ", "dim"),
                (image, ""),
            ))
            content.write(Text("\nCommand:", style="bold"))
            content.write(Text(command_str, style=""))

    def _display_hf_private_repos(self, content: RichLog, arguments: dict, operation: str) -> None:
        """Display hf_private_repos tool details."""
        args = arguments.get("args", {})
        if isinstance(args, str):
            args = {}

        if operation in ["create_repo", "upload_file"]:
            repo_id = args.get("repo_id", "")
            repo_type = args.get("repo_type", "dataset")

            type_path = "" if repo_type == "model" else f"{repo_type}s"
            repo_url = f"https://huggingface.co/{type_path}/{repo_id}".replace("//", "/")

            summary = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
            summary.add_column("key", style="dim")
            summary.add_column("value")

            summary.add_row("Repository:", Text(repo_id, style="cyan"))
            summary.add_row("Type:", repo_type)
            summary.add_row("Private:", Text("Yes", style="yellow"))
            summary.add_row("URL:", Text(repo_url, style="underline"))

            content.write(summary)

            if operation == "upload_file":
                path_in_repo = args.get("path_in_repo", "")
                file_content = args.get("file_content", "")

                content.write(Text(f"\nFile: {path_in_repo}", style="bold"))

                if isinstance(file_content, str):
                    all_lines = file_content.split("\n")
                    line_count = len(all_lines)
                    size_kb = len(file_content.encode("utf-8")) / 1024

                    content.write(Text(f"Size: {line_count} lines, {size_kb:.1f} KB", style="dim"))
                    content.write(Text("\nPreview:", style="bold"))

                    preview = "\n".join(all_lines[:10])
                    if len(all_lines) > 10:
                        preview += f"\n... ({len(all_lines) - 10} more lines)"
                    content.write(Text(preview, style="dim"))

    def _display_hf_repo_files(self, content: RichLog, arguments: dict, operation: str) -> None:
        """Display hf_repo_files tool details."""
        repo_id = arguments.get("repo_id", "")
        repo_type = arguments.get("repo_type", "model")
        revision = arguments.get("revision", "main")

        if repo_type == "model":
            repo_url = f"https://huggingface.co/{repo_id}"
        else:
            repo_url = f"https://huggingface.co/{repo_type}s/{repo_id}"

        summary = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
        summary.add_column("key", style="dim")
        summary.add_column("value")

        summary.add_row("Repository:", Text(repo_id, style="cyan"))
        summary.add_row("Type:", repo_type)
        summary.add_row("Branch:", revision)
        summary.add_row("URL:", Text(repo_url, style="underline"))

        content.write(summary)

        if operation == "upload":
            path = arguments.get("path", "")
            file_content = arguments.get("content", "")
            create_pr = arguments.get("create_pr", False)

            content.write(Text(f"\nFile: {path}", style="bold"))
            if create_pr:
                content.write(Text("Mode: Create PR", style="yellow"))

            if isinstance(file_content, str):
                all_lines = file_content.split("\n")
                line_count = len(all_lines)
                size_kb = len(file_content.encode("utf-8")) / 1024

                content.write(Text(f"Size: {line_count} lines, {size_kb:.1f} KB", style="dim"))
                content.write(Text("\nContent:", style="bold"))

                # Detect file type for syntax highlighting
                ext = path.split(".")[-1] if "." in path else ""
                lang_map = {"py": "python", "js": "javascript", "json": "json", "yaml": "yaml", "yml": "yaml", "md": "markdown"}
                lang = lang_map.get(ext, "text")

                syntax = Syntax(file_content, lang, theme="monokai", line_numbers=True)
                content.write(syntax)

        elif operation == "delete":
            patterns = arguments.get("patterns", [])
            if isinstance(patterns, str):
                patterns = [patterns]
            content.write(Text("\nPatterns to delete:", style="bold red"))
            for p in patterns:
                content.write(Text(f"  - {p}", style="red"))

    def _display_hf_repo_git(self, content: RichLog, arguments: dict, operation: str) -> None:
        """Display hf_repo_git tool details."""
        repo_id = arguments.get("repo_id", "")
        repo_type = arguments.get("repo_type", "model")

        if repo_type == "model":
            repo_url = f"https://huggingface.co/{repo_id}"
        else:
            repo_url = f"https://huggingface.co/{repo_type}s/{repo_id}"

        summary = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
        summary.add_column("key", style="dim")
        summary.add_column("value")

        summary.add_row("Repository:", Text(repo_id, style="cyan"))
        summary.add_row("Type:", repo_type)
        summary.add_row("URL:", Text(repo_url, style="underline"))

        content.write(summary)

        if operation == "delete_branch":
            branch = arguments.get("branch", "")
            content.write(Text(f"\nBranch to delete: {branch}", style="red bold"))

        elif operation == "delete_tag":
            tag = arguments.get("tag", "")
            content.write(Text(f"\nTag to delete: {tag}", style="red bold"))

        elif operation == "merge_pr":
            pr_num = arguments.get("pr_num", "")
            content.write(Text(f"\nPR to merge: #{pr_num}", style="green bold"))

        elif operation == "create_repo":
            private = arguments.get("private", False)
            space_sdk = arguments.get("space_sdk")

            content.write(Text(f"\nPrivate: {'Yes' if private else 'No'}", style="yellow" if private else ""))
            if space_sdk:
                content.write(Text(f"Space SDK: {space_sdk}"))

        elif operation == "update_repo":
            private = arguments.get("private")
            gated = arguments.get("gated")

            if private is not None:
                content.write(Text(f"\nPrivate: {'Yes' if private else 'No'}"))
            if gated is not None:
                content.write(Text(f"Gated: {gated}"))

    def action_approve(self) -> None:
        """Approve current tool."""
        self._record_approval(approved=True)

    def action_reject(self) -> None:
        """Reject current tool."""
        self._record_approval(approved=False)

    def action_approve_all(self) -> None:
        """Enable YOLO mode and approve all remaining tools."""
        if self.config:
            self.config.yolo_mode = True

        # Approve current and all remaining
        for i in range(self.current_index, len(self.tools_data)):
            tool_info = self.tools_data[i]
            self.approvals.append({
                "tool_call_id": tool_info.get("tool_call_id", ""),
                "approved": True,
                "feedback": None,
            })

        self.dismiss(self.approvals)

    def action_cancel(self) -> None:
        """Cancel and reject all."""
        # Reject all remaining
        for i in range(self.current_index, len(self.tools_data)):
            tool_info = self.tools_data[i]
            self.approvals.append({
                "tool_call_id": tool_info.get("tool_call_id", ""),
                "approved": False,
                "feedback": "Cancelled by user",
            })

        self.dismiss(self.approvals)

    def _record_approval(self, approved: bool, feedback: str = None) -> None:
        """Record approval decision and move to next item."""
        tool_info = self.tools_data[self.current_index]
        self.approvals.append({
            "tool_call_id": tool_info.get("tool_call_id", ""),
            "approved": approved,
            "feedback": feedback,
        })

        self.current_index += 1

        if self.current_index >= len(self.tools_data):
            # All items processed
            self.dismiss(self.approvals)
        else:
            # Show next item
            self._display_current_tool()
