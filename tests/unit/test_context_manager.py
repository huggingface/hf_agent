"""Unit tests for the context manager."""

from agent.context_manager.manager import ContextManager


def test_add_message_accepts_zero_token_count():
    """A token_count of 0 should update running_context_usage, not be treated as missing."""
    manager = ContextManager(tool_specs=[])
    manager.running_context_usage = 100

    class _Message:
        role = "user"
        content = "hi"

    manager.add_message(_Message(), token_count=0)
    assert manager.running_context_usage == 0
