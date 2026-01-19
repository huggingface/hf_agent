"""
Main Textual App for the HF Agent CLI
"""

import os
from pathlib import Path

from textual.app import App

from agent.cli.screens.main_screen import MainScreen


class HFAgentApp(App):
    """Hugging Face Agent CLI Application."""

    TITLE = "Hugging Face Agent"
    SUB_TITLE = "Interactive AI Assistant"

    CSS_PATH = Path(__file__).parent / "styles.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        """Handle app mount - show banner and push main screen."""
        # Push the main screen
        self.push_screen(MainScreen())

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def run_app() -> None:
    """Run the HF Agent CLI application."""
    # Clear screen
    os.system("clear" if os.name != "nt" else "cls")

    app = HFAgentApp()
    app.run()


if __name__ == "__main__":
    run_app()
