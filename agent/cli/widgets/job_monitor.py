"""
Job monitor panel for streaming HF job logs
"""

import asyncio
from typing import Optional

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.reactive import reactive


class JobMonitor(Vertical):
    """Side panel for monitoring HF job logs with pinned URL header."""

    DEFAULT_CSS = """
    JobMonitor {
        width: 50;
        height: 100%;
        background: transparent;
        display: none;
        border-left: solid #30363D;
        padding: 0;
    }

    JobMonitor.visible {
        display: block;
    }

    #job_header {
        height: auto;
        padding: 0 1;
        background: #21262D;
    }

    #job_url {
        height: 1;
        padding: 0 1;
        background: #161B22;
        color: #58A6FF;
    }

    #job_status {
        height: 1;
        padding: 0 1;
        background: #21262D;
    }

    #job_logs {
        height: 1fr;
        background: transparent;
        padding: 0 1;
        scrollbar-background: transparent;
        scrollbar-color: #30363D;
    }

    #job_actions {
        height: 1;
        padding: 0 1;
        background: #21262D;
        text-align: center;
    }
    """

    job_id: reactive[str] = reactive("")
    job_status: reactive[str] = reactive("unknown")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._polling_task: Optional[asyncio.Task] = None
        self._job_url: str = ""
        self._last_log_position: int = 0

    def compose(self):
        """Compose the job monitor layout."""
        yield Static("", id="job_header")
        yield Static("", id="job_url")
        yield Static("", id="job_status")
        yield RichLog(id="job_logs", highlight=True, markup=True, wrap=True, auto_scroll=True)
        yield Static("[dim]Ctrl+J[/] close  [dim]Ctrl+R[/] refresh", id="job_actions")

    def show_job(self, job_id: str, job_url: str, title: str = "") -> None:
        """Start monitoring a job."""
        self.job_id = job_id
        self._job_url = job_url

        # Update header
        header = self.query_one("#job_header", Static)
        header.update(Text(title or f"Job: {job_id[:8]}...", style="bold yellow"))

        # Update URL (pinned)
        url_widget = self.query_one("#job_url", Static)
        url_widget.update(Text(job_url, style="underline cyan"))

        # Update status
        self._update_status("starting")

        # Clear logs
        logs = self.query_one("#job_logs", RichLog)
        logs.clear()
        self._last_log_position = 0

        # Show panel
        self.add_class("visible")

        # Start polling for logs
        self._start_polling()

    def hide(self) -> None:
        """Hide the job monitor and stop polling."""
        self._stop_polling()
        self.remove_class("visible")

    def _update_status(self, status: str) -> None:
        """Update the job status display."""
        self.job_status = status

        status_widget = self.query_one("#job_status", Static)

        status_styles = {
            "starting": ("dim", "Starting..."),
            "running": ("yellow", "Running"),
            "completed": ("green", "Completed"),
            "failed": ("red", "Failed"),
            "cancelled": ("dim red", "Cancelled"),
            "unknown": ("dim", "Unknown"),
        }

        style, text = status_styles.get(status, ("dim", status))
        status_widget.update(Text(f"Status: {text}", style=style))

    def append_log(self, text: str) -> None:
        """Append text to the log output."""
        logs = self.query_one("#job_logs", RichLog)
        logs.write(Text(text))

    def append_log_lines(self, lines: list[str]) -> None:
        """Append multiple lines to the log output."""
        logs = self.query_one("#job_logs", RichLog)
        for line in lines:
            # Detect and style different log types
            if "ERROR" in line or "error" in line.lower():
                logs.write(Text(line, style="red"))
            elif "WARNING" in line or "warn" in line.lower():
                logs.write(Text(line, style="yellow"))
            elif line.startswith(">>>") or line.startswith("==="):
                logs.write(Text(line, style="bold cyan"))
            else:
                logs.write(Text(line))

    def _start_polling(self) -> None:
        """Start polling for job logs."""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()

        self._polling_task = asyncio.create_task(self._poll_logs())

    def _stop_polling(self) -> None:
        """Stop polling for job logs."""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            self._polling_task = None

    async def _poll_logs(self) -> None:
        """Poll for job logs periodically."""
        try:
            while True:
                await self._fetch_logs()
                await asyncio.sleep(2)  # Poll every 2 seconds
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.append_log(f"Error polling logs: {e}")

    async def _fetch_logs(self) -> None:
        """Fetch latest logs from the job."""
        # This will be called by the main screen when it receives job output
        # For now, this is a placeholder - actual implementation depends on
        # how job logs are retrieved (via hf_jobs tool or direct API)
        pass

    def set_complete(self, success: bool = True) -> None:
        """Mark the job as complete."""
        self._stop_polling()
        self._update_status("completed" if success else "failed")
        self.append_log(f"\n{'=' * 40}")
        self.append_log("Job finished" if success else "Job failed")

    def refresh_logs(self) -> None:
        """Manually refresh logs."""
        if self.job_id:
            self._last_log_position = 0
            logs = self.query_one("#job_logs", RichLog)
            logs.clear()
            self._start_polling()
