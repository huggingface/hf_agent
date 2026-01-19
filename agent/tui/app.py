"""
Main Textual App for HuggingFace Agent TUI
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

import litellm
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from agent.config import Config, load_config
from agent.core.agent_loop import submission_loop
from agent.core.tools import ToolRouter
from agent.tui.screens.main import MainContainer, Operation, Submission

# Drop params that models don't support
litellm.drop_params = True


class AgentTUI(App):
    """HuggingFace Agent TUI Application"""

    TITLE = "HuggingFace Agent"
    SUB_TITLE = "Interactive ML Assistant"

    CSS_PATH = "styles/app.tcss"

    # Disable command palette
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Interrupt", show=True),
    ]

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

    def compose(self) -> ComposeResult:
        """Compose the app UI"""
        yield Header()
        yield MainContainer(
            self.submission_queue,
            self.event_queue,
            self.config,
            id="main",
        )
        yield Footer()

    def action_quit(self) -> None:
        """Quit the application"""
        from agent.core.session import OpType

        submission = Submission(
            id="shutdown",
            operation=Operation(op_type=OpType.SHUTDOWN),
        )
        self.submission_queue.put_nowait(submission)
        self.exit()

    def action_interrupt(self) -> None:
        """Forward interrupt to main container"""
        try:
            main = self.query_one("#main", MainContainer)
            main.action_interrupt()
        except Exception:
            pass


async def run_app(config_path: Optional[Path] = None) -> None:
    """
    Run the HuggingFace Agent TUI

    This is the main entry point that:
    1. Loads configuration
    2. Initializes MCP servers / tool router
    3. Creates communication queues
    4. Starts the agent loop in background
    5. Runs the TUI
    6. Handles shutdown
    """
    # Initialize Laminar if available
    lmnr_api_key = os.environ.get("LMNR_API_KEY")
    if lmnr_api_key:
        try:
            from lmnr import Laminar, LaminarLiteLLMCallback

            Laminar.initialize(project_api_key=lmnr_api_key)
            litellm.callbacks = [LaminarLiteLLMCallback()]

        except Exception as e:
            print(f"Failed to initialize Laminar: {e}")

    # Load config
    if config_path is None:
        config_path = (
            Path(__file__).parent.parent.parent / "configs" / "main_agent_config.json"
        )

    config = load_config(config_path)

    # Create tool router (MCP server loading message will be shown in TUI)
    tool_router = ToolRouter(config.mcpServers)

    # Create communication queues
    submission_queue: asyncio.Queue = asyncio.Queue()
    event_queue: asyncio.Queue = asyncio.Queue()

    # Start agent loop in background
    agent_task = asyncio.create_task(
        submission_loop(
            submission_queue,
            event_queue,
            config=config,
            tool_router=tool_router,
        )
    )

    # Run TUI
    app = AgentTUI(submission_queue, event_queue, config)

    try:
        await app.run_async()
    finally:
        # Shutdown agent
        from agent.core.session import OpType

        shutdown_submission = Submission(
            id="shutdown",
            operation=Operation(op_type=OpType.SHUTDOWN),
        )
        await submission_queue.put(shutdown_submission)

        # Wait for agent to finish
        try:
            await asyncio.wait_for(agent_task, timeout=5.0)
        except asyncio.TimeoutError:
            agent_task.cancel()

        print("Goodbye!")
