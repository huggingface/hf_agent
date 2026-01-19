"""
Main container for the HF Agent TUI
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static

from agent.config import Config
from agent.core.session import OpType
from agent.tui.messages import (
    AgentEvent,
    SubmitMessage,
    YoloModeActivated,
)
from agent.tui.widgets.chat_widget import ChatWidget
from agent.tui.widgets.input_area import InputArea


@dataclass
class Operation:
    """Operation to be executed by the agent"""

    op_type: OpType
    data: Optional[dict[str, Any]] = None


@dataclass
class Submission:
    """Submission to the agent loop"""

    id: str
    operation: Operation


class MainContainer(Container):
    """Main container with chat and input"""

    DEFAULT_CSS = """
    MainContainer {
        height: 1fr;
        layout: vertical;
    }

    MainContainer > #chat-container {
        height: 1fr;
    }

    MainContainer > #status-bar {
        height: 1;
        background: $surface-darken-1;
        color: $text-muted;
        padding: 0 1;
        dock: bottom;
    }

    MainContainer > #status-bar.yolo {
        background: $warning 30%;
        color: $warning;
    }
    """

    def __init__(
        self,
        submission_queue: asyncio.Queue,
        event_queue: asyncio.Queue,
        config: Config,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.submission_queue = submission_queue
        self.event_queue = event_queue
        self.config = config
        self.submission_id = 0
        self.yolo_mode = config.yolo_mode
        self._turn_complete = asyncio.Event()
        self._turn_complete.set()
        self._interrupt_count = 0
        self._interrupt_timer: asyncio.TimerHandle | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-container"):
            yield ChatWidget(id="chat")

        yield InputArea(id="input-area")

        status = "YOLO MODE ACTIVE" if self.yolo_mode else ""
        yield Static(status, id="status-bar")

    def on_mount(self) -> None:
        """Start event listener when mounted"""
        self.run_worker(self._event_listener(), exclusive=True, thread=False)
        self._update_status_bar()

    async def _event_listener(self) -> None:
        """Background worker to listen for agent events"""
        while True:
            try:
                event = await self.event_queue.get()

                # Post message to handle in main thread
                self.post_message(AgentEvent(event.event_type, event.data))

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Event listener error: {e}")

    @on(AgentEvent)
    def on_agent_event(self, event: AgentEvent) -> None:
        """Handle agent events"""
        chat = self.query_one("#chat", ChatWidget)
        input_area = self.query_one("#input-area", InputArea)

        if event.event_type == "ready":
            # Display startup info
            mcp_servers = event.data.get("mcp_servers", [])

            if mcp_servers:
                mcp_servers_str = ", ".join(mcp_servers)
                chat.add_system_message(f"Loaded MCP servers: {mcp_servers_str}")

            input_area.set_enabled(True)
            self._turn_complete.set()

        elif event.event_type == "processing":
            chat.show_processing()
            input_area.set_enabled(False)

        elif event.event_type == "assistant_message":
            chat.hide_processing()
            content = event.data.get("content", "")
            if content:
                chat.add_assistant_message(content)

        elif event.event_type == "tool_call":
            chat.hide_processing()
            tool = event.data.get("tool", "")
            arguments = event.data.get("arguments", {})
            if tool:
                chat.add_tool_call(tool, arguments)

        elif event.event_type == "tool_output":
            # Finalize any streaming logs
            chat.finalize_logs()

            output = event.data.get("output", "")
            success = event.data.get("success", False)
            if output:
                chat.add_tool_output(output, success)

        elif event.event_type == "turn_complete":
            chat.hide_processing()
            chat.finalize_assistant_message()
            chat.update_plan()
            input_area.set_enabled(True)
            self._turn_complete.set()

        elif event.event_type == "error":
            chat.hide_processing()
            error = event.data.get("error", "Unknown error")
            chat.add_error_message(error)
            input_area.set_enabled(True)
            self._turn_complete.set()

        elif event.event_type == "compacted":
            old_tokens = event.data.get("old_tokens", 0)
            new_tokens = event.data.get("new_tokens", 0)
            chat.add_system_message(
                f"Context compacted: {old_tokens} -> {new_tokens} tokens"
            )

        elif event.event_type == "approval_required":
            tools_data = event.data.get("tools", [])

            # If YOLO mode, auto-approve
            if self.yolo_mode:
                approvals = [
                    {
                        "tool_call_id": t.get("tool_call_id", ""),
                        "approved": True,
                        "feedback": None,
                    }
                    for t in tools_data
                ]
                chat.add_system_message(
                    f"YOLO: Auto-approving {len(tools_data)} tool(s)"
                )
                self._submit_approval(approvals)
            else:
                # Show approval screen
                from agent.tui.screens.approval import ApprovalScreen

                self.app.push_screen(
                    ApprovalScreen(tools_data),
                    callback=self._on_approval_complete,
                )

        elif event.event_type == "system_message":
            # System message from tools
            message = event.data.get("message", "")
            if message:
                chat.add_system_message(message)

        elif event.event_type == "log_stream":
            # Stream job logs in real-time
            log_line = event.data.get("log", "")
            if log_line:
                chat.add_log_line(log_line)

        elif event.event_type == "shutdown":
            self.app.exit()

    def _on_approval_complete(self, approvals: list[dict[str, Any]]) -> None:
        """Callback when approval screen completes"""
        self._submit_approval(approvals)

    def _submit_approval(self, approvals: list[dict[str, Any]]) -> None:
        """Submit approval response to agent"""
        self.submission_id += 1
        submission = Submission(
            id=f"approval_{self.submission_id}",
            operation=Operation(
                op_type=OpType.EXEC_APPROVAL,
                data={"approvals": approvals},
            ),
        )
        self.submission_queue.put_nowait(submission)

    @on(SubmitMessage)
    def on_submit_message(self, message: SubmitMessage) -> None:
        """Handle user message submission"""
        text = message.text.strip()

        # Check for exit commands
        if text.lower() in ["exit", "quit", "/quit", "/exit"]:
            self.action_quit()
            return

        # Skip empty input
        if not text:
            return

        # Add to chat
        chat = self.query_one("#chat", ChatWidget)
        chat.add_user_message(text)

        # Disable input while processing
        input_area = self.query_one("#input-area", InputArea)
        input_area.set_enabled(False)
        self._turn_complete.clear()

        # Submit to agent
        self.submission_id += 1
        submission = Submission(
            id=f"sub_{self.submission_id}",
            operation=Operation(op_type=OpType.USER_INPUT, data={"text": text}),
        )
        self.submission_queue.put_nowait(submission)

    @on(YoloModeActivated)
    def on_yolo_mode_activated(self, event: YoloModeActivated) -> None:
        """Handle YOLO mode activation"""
        self.yolo_mode = True
        self.config.yolo_mode = True
        self._update_status_bar()
        chat = self.query_one("#chat", ChatWidget)
        chat.add_system_message("YOLO MODE ACTIVATED - Auto-approving all tool calls")

    def _update_status_bar(self) -> None:
        """Update the status bar"""
        status_bar = self.query_one("#status-bar", Static)
        if self.yolo_mode:
            status_bar.update("YOLO MODE ACTIVE")
            status_bar.add_class("yolo")
        else:
            status_bar.update("")
            status_bar.remove_class("yolo")

    def action_interrupt(self) -> None:
        """Handle ctrl+c - single press to exit when idle, double to interrupt when busy"""
        # If agent is idle (user's turn), exit immediately
        if self._turn_complete.is_set():
            self.action_quit()
            return

        # Agent is busy - check if this is second ctrl+c
        if self._interrupt_timer is not None:
            # Second ctrl+c - exit
            if self._interrupt_timer:
                self._interrupt_timer.cancel()
            self._interrupt_timer = None
            self._interrupt_count = 0
            self.action_quit()
            return

        # First ctrl+c - interrupt
        self._interrupt_count = 1
        self.submission_id += 1
        submission = Submission(
            id=f"interrupt_{self.submission_id}",
            operation=Operation(op_type=OpType.INTERRUPT),
        )
        self.submission_queue.put_nowait(submission)

        chat = self.query_one("#chat", ChatWidget)
        chat.hide_processing()
        chat.add_system_message("Interrupted (ctrl+c again to exit)")

        input_area = self.query_one("#input-area", InputArea)
        input_area.set_enabled(True)

        # Reset counter after 1 second
        def reset_count():
            self._interrupt_count = 0
            self._interrupt_timer = None

        loop = asyncio.get_event_loop()
        self._interrupt_timer = loop.call_later(1.0, reset_count)

    def action_quit(self) -> None:
        """Quit the application"""
        # Send shutdown to agent
        submission = Submission(
            id="shutdown",
            operation=Operation(op_type=OpType.SHUTDOWN),
        )
        self.submission_queue.put_nowait(submission)
        self.app.exit()
