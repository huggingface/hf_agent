"""Unit tests for the context manager."""

from unittest.mock import patch

from agent.context_manager.manager import ContextManager


def test_prompt_file_suffix_is_passed_to_loader():
    """ContextManager should use the prompt_file_suffix parameter instead of hardcoding it."""
    with patch.object(ContextManager, "_load_system_prompt", return_value="system prompt") as mock_load:
        ContextManager(prompt_file_suffix="custom_prompt.yaml", tool_specs=[])

    mock_load.assert_called_once()
    _, kwargs = mock_load.call_args
    assert kwargs["prompt_file_suffix"] == "custom_prompt.yaml"
