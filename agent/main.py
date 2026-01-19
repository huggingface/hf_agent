"""
HuggingFace Agent - Interactive CLI for ML Engineering

Entry point for the Textual-based TUI that provides an interactive
chat interface with the agent.
"""

import asyncio

from agent.tui import run_app


def main():
    """Main entry point"""
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
