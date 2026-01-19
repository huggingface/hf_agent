"""
Main chat screen for the HF Agent CLI
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical
from textual.worker import Worker, get_current_worker

from textual.containers import Horizontal

from agent.cli.widgets.chat_log import ChatLog
from agent.cli.widgets.user_input import UserInput
from agent.cli.widgets.status_bar import StatusBar
from agent.cli.widgets.plan_panel import PlanPanel
from agent.cli.widgets.job_monitor import JobMonitor
from agent.config import Config, load_config
from agent.core.session import OpType, Event
from agent.core.tools import ToolRouter
from agent.tools.plan_tool import get_current_plan


@dataclass
class Operation:
    """Operation to be executed by the agent."""

    op_type: OpType
    data: Optional[dict[str, Any]] = None


@dataclass
class Submission:
    """Submission to the agent loop."""

    id: str
    operation: Operation


class MainScreen(Screen):
    """Primary chat screen with agent interaction."""

    BINDINGS = [
        ("ctrl+c", "interrupt", "Interrupt"),
        ("ctrl+d", "quit", "Quit"),
        ("ctrl+t", "toggle_tools", "Toggle Tools"),
        ("ctrl+j", "toggle_job_monitor", "Toggle Jobs"),
        ("ctrl+r", "refresh_job_logs", "Refresh Logs"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.submission_queue: Optional[asyncio.Queue] = None
        self.event_queue: Optional[asyncio.Queue] = None
        self.config: Optional[Config] = None
        self.tool_router: Optional[ToolRouter] = None
        self.submission_id = 0
        self._agent_worker: Optional[Worker] = None
        self._event_worker: Optional[Worker] = None
        self._turn_complete = asyncio.Event()
        self._ready_event = asyncio.Event()
        self._last_tool_name: Optional[str] = None
        self._last_tool_args: Optional[dict] = None
        self._last_ctrl_c_time: float = 0.0

    def compose(self) -> ComposeResult:
        """Compose the main screen layout."""
        yield StatusBar(id="status_bar")
        with Horizontal(id="main_layout"):
            with Vertical(id="main_container"):
                yield ChatLog(id="chat_log")
                yield PlanPanel(id="plan_panel")
                yield UserInput(id="user_input")
            yield JobMonitor(id="job_monitor")

    async def on_mount(self) -> None:
        """Initialize the agent when screen mounts."""
        self._turn_complete.set()

        # Focus the input
        self.query_one("#user_input", UserInput).focus()

        # Start initialization worker
        self._agent_worker = self.run_worker(
            self._initialize_agent(),
            name="agent_init",
            exclusive=True,
        )

    async def _initialize_agent(self) -> None:
        """Initialize the agent loop in a worker."""
        from agent.core.agent_loop import submission_loop

        chat_log = self.query_one("#chat_log", ChatLog)
        status_bar = self.query_one("#status_bar", StatusBar)

        chat_log.write_info("Initializing agent...")

        # Create queues
        self.submission_queue = asyncio.Queue()
        self.event_queue = asyncio.Queue()

        # Load config
        config_path = Path(__file__).parent.parent.parent.parent / "configs" / "main_agent_config.json"
        self.config = load_config(config_path)

        # Update status bar with model name
        status_bar.model_name = self.config.model_name

        # Create tool router
        chat_log.write_info(f"Loading MCP servers: {', '.join(self.config.mcpServers.keys())}")
        self.tool_router = ToolRouter(self.config.mcpServers)

        # Start event listener worker
        self._event_worker = self.run_worker(
            self._event_listener(),
            name="event_listener",
            exclusive=False,
        )

        # Run the submission loop (this blocks until shutdown)
        await submission_loop(
            self.submission_queue,
            self.event_queue,
            config=self.config,
            tool_router=self.tool_router,
        )

    async def _event_listener(self) -> None:
        """Listen for events from the agent and update UI."""
        chat_log = self.query_one("#chat_log", ChatLog)
        status_bar = self.query_one("#status_bar", StatusBar)
        plan_panel = self.query_one("#plan_panel", PlanPanel)
        user_input = self.query_one("#user_input", UserInput)

        while True:
            try:
                if self.event_queue is None:
                    await asyncio.sleep(0.1)
                    continue

                event: Event = await self.event_queue.get()

                if event.event_type == "ready":
                    chat_log.write_ready()
                    status_bar.set_ready()
                    self._ready_event.set()

                elif event.event_type == "assistant_message":
                    content = event.data.get("content", "") if event.data else ""
                    if content:
                        chat_log.write_assistant_message(content)

                elif event.event_type == "tool_call":
                    tool_name = event.data.get("tool", "") if event.data else ""
                    arguments = event.data.get("arguments", {}) if event.data else {}
                    if tool_name:
                        self._last_tool_name = tool_name
                        self._last_tool_args = arguments
                        chat_log.write_tool_call(tool_name, arguments)

                elif event.event_type == "tool_output":
                    output = event.data.get("output", "") if event.data else ""
                    success = event.data.get("success", False) if event.data else False
                    if output:
                        # Don't truncate plan_tool output
                        should_truncate = self._last_tool_name != "plan_tool"
                        chat_log.write_tool_output(output, success, truncate=should_truncate)

                        # Update plan panel if this was a plan_tool call
                        if self._last_tool_name == "plan_tool":
                            plan = get_current_plan()
                            plan_panel.update_plan(plan)

                        # Check if this is an hf_jobs run/uv operation
                        if self._last_tool_name == "hf_jobs" and success:
                            self._handle_job_output(output)

                elif event.event_type == "turn_complete":
                    chat_log.write_turn_complete()
                    status_bar.set_ready()
                    user_input.set_processing(False)

                    # Update plan display
                    plan = get_current_plan()
                    if plan:
                        plan_panel.update_plan(plan)

                    self._turn_complete.set()

                elif event.event_type == "error":
                    error = event.data.get("error", "Unknown error") if event.data else "Unknown error"
                    chat_log.write_error(error)
                    status_bar.set_ready()
                    user_input.set_processing(False)
                    self._turn_complete.set()

                elif event.event_type == "shutdown":
                    break

                elif event.event_type == "compacted":
                    old_tokens = event.data.get("old_tokens", 0) if event.data else 0
                    new_tokens = event.data.get("new_tokens", 0) if event.data else 0
                    chat_log.write_compacted(old_tokens, new_tokens)
                    status_bar.update_tokens(new_tokens)

                elif event.event_type == "approval_required":
                    status_bar.set_waiting_approval()
                    await self._handle_approval_required(event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                chat_log.write_error(f"Event listener error: {e}")

    async def _handle_approval_required(self, event: Event) -> None:
        """Handle approval required event by showing approval screen."""
        from agent.cli.screens.approval_screen import ApprovalScreen

        tools_data = event.data.get("tools", []) if event.data else []
        count = event.data.get("count", 0) if event.data else 0

        # If YOLO mode is active, auto-approve
        if self.config and self.config.yolo_mode:
            approvals = [
                {
                    "tool_call_id": t.get("tool_call_id", ""),
                    "approved": True,
                    "feedback": None,
                }
                for t in tools_data
            ]
            chat_log = self.query_one("#chat_log", ChatLog)
            chat_log.write_info(f"\nYOLO MODE: Auto-approving {count} item(s)")
            await self._submit_approval(approvals)
            return

        # Show approval screen
        approval_screen = ApprovalScreen(tools_data, self.config)

        def handle_approval_result(approvals: list | None) -> None:
            if approvals is not None:
                # Check if YOLO mode was activated
                if self.config and self.config.yolo_mode:
                    chat_log = self.query_one("#chat_log", ChatLog)
                    chat_log.write_info("YOLO MODE ACTIVATED - Auto-approving all future tool calls")

                # Submit approvals asynchronously
                asyncio.create_task(self._submit_approval(approvals))

            # Reset status
            status_bar = self.query_one("#status_bar", StatusBar)
            status_bar.set_processing()

        self.app.push_screen(approval_screen, handle_approval_result)

    async def _submit_approval(self, approvals: list) -> None:
        """Submit approval decision to the agent."""
        self.submission_id += 1
        submission = Submission(
            id=f"approval_{self.submission_id}",
            operation=Operation(
                op_type=OpType.EXEC_APPROVAL,
                data={"approvals": approvals},
            ),
        )
        await self.submission_queue.put(submission)

    async def on_user_input_submitted(self, event: UserInput.Submitted) -> None:
        """Handle user input submission."""
        text = event.value.strip()

        # Check for exit commands
        if text.lower() in ["exit", "quit", "/quit", "/exit"]:
            await self._shutdown()
            return

        # Skip empty input
        if not text:
            return

        # Wait for ready
        await self._ready_event.wait()

        # Wait for previous turn
        await self._turn_complete.wait()
        self._turn_complete.clear()

        # Update UI
        chat_log = self.query_one("#chat_log", ChatLog)
        status_bar = self.query_one("#status_bar", StatusBar)
        user_input = self.query_one("#user_input", UserInput)

        chat_log.write_user_message(text)
        status_bar.set_processing()
        user_input.set_processing(True)

        # Submit to agent
        self.submission_id += 1
        submission = Submission(
            id=f"sub_{self.submission_id}",
            operation=Operation(
                op_type=OpType.USER_INPUT,
                data={"text": text},
            ),
        )
        await self.submission_queue.put(submission)

    async def action_interrupt(self) -> None:
        """Handle Ctrl+C interrupt. Double Ctrl+C exits."""
        current_time = time.time()
        time_since_last = current_time - self._last_ctrl_c_time
        self._last_ctrl_c_time = current_time

        chat_log = self.query_one("#chat_log", ChatLog)

        # Double Ctrl+C within 500ms exits
        if time_since_last < 0.5:
            chat_log.write_info("\nExiting...")
            await self._shutdown()
            return

        # Single Ctrl+C interrupts agent
        if self.submission_queue:
            self.submission_id += 1
            submission = Submission(
                id=f"int_{self.submission_id}",
                operation=Operation(op_type=OpType.INTERRUPT),
            )
            await self.submission_queue.put(submission)

        chat_log.write_info("\nInterrupted (Ctrl+C again to exit)")

    async def action_quit(self) -> None:
        """Handle Ctrl+D quit."""
        await self._shutdown()

    def action_toggle_tools(self) -> None:
        """Toggle tool output visibility."""
        chat_log = self.query_one("#chat_log", ChatLog)
        status_bar = self.query_one("#status_bar", StatusBar)

        # Toggle in status bar (tracks state)
        new_state = status_bar.toggle_tools()

        # Apply to chat log
        chat_log.show_tool_outputs = new_state

        # Show feedback
        state_text = "on" if new_state else "off"
        chat_log.write_info(f"Tool outputs: {state_text}")

    def action_toggle_job_monitor(self) -> None:
        """Toggle job monitor panel visibility."""
        job_monitor = self.query_one("#job_monitor", JobMonitor)
        if job_monitor.has_class("visible"):
            job_monitor.hide()
        else:
            job_monitor.add_class("visible")

    def action_refresh_job_logs(self) -> None:
        """Refresh job logs."""
        job_monitor = self.query_one("#job_monitor", JobMonitor)
        if job_monitor.has_class("visible"):
            job_monitor.refresh_logs()

    def _handle_job_output(self, output: str) -> None:
        """Handle hf_jobs tool output - extract job info and show monitor."""
        import json
        import re

        # Check if this is a run/uv operation from the last args
        if not self._last_tool_args:
            return

        operation = self._last_tool_args.get("operation", "")
        if operation not in ["run", "uv", "scheduled run", "scheduled uv"]:
            return

        # Try to parse job info from output
        job_id = None
        job_url = None

        # Look for job URL pattern
        url_match = re.search(r'https://huggingface\.co/[^\s"\']+/jobs/[^\s"\']+', output)
        if url_match:
            job_url = url_match.group(0)
            # Extract job ID from URL
            id_match = re.search(r'/jobs/([a-f0-9-]+)', job_url)
            if id_match:
                job_id = id_match.group(1)

        # Try parsing as JSON for structured output
        if not job_id:
            try:
                data = json.loads(output)
                job_id = data.get("job_id") or data.get("id")
                job_url = data.get("url") or data.get("job_url")
            except (json.JSONDecodeError, TypeError):
                pass

        if job_id and job_url:
            job_monitor = self.query_one("#job_monitor", JobMonitor)
            title = f"Job: {operation}"
            job_monitor.show_job(job_id, job_url, title)

            # Also append initial output as logs
            job_monitor.append_log_lines(output.split("\n")[:20])

    async def _shutdown(self) -> None:
        """Shutdown the agent and exit."""
        chat_log = self.query_one("#chat_log", ChatLog)
        chat_log.write_info("\nShutting down agent...")

        if self.submission_queue:
            submission = Submission(
                id="sub_shutdown",
                operation=Operation(op_type=OpType.SHUTDOWN),
            )
            await self.submission_queue.put(submission)

            # Give agent time to shutdown
            await asyncio.sleep(0.5)

        self.app.exit()
