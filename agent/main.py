"""
Interactive CLI chat with the agent - Textual-based UI
"""

import os

import litellm
from lmnr import Laminar, LaminarLiteLLMCallback

litellm.drop_params = True

# Initialize Laminar if API key is available
lmnr_api_key = os.environ.get("LMNR_API_KEY")
if lmnr_api_key:
    try:
        Laminar.initialize(project_api_key=lmnr_api_key)
        litellm.callbacks = [LaminarLiteLLMCallback()]
        print("Laminar initialized")
    except Exception as e:
        print(f"Failed to initialize Laminar: {e}")


def main():
    """Run the HF Agent CLI."""
    from agent.cli.app import run_app
    run_app()


if __name__ == "__main__":
    main()
