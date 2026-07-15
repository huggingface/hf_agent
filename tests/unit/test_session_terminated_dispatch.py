"""Tests for session_terminated event dispatch in the CLI event listener.

Covers two requirements from issue #345:
1. ``session_terminated`` events are explicitly handled (error printed,
   turn_complete_event set) instead of silently dropped.
2. Unknown/unhandled event types now produce a ``logger.warning`` instead
   of silently passing — a regression guard for this entire bug class.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.core.session import Event


# ── helpers ────────────────────────────────────────────────────────────


def _make_queues():
    return asyncio.Queue(), asyncio.Queue()


def _make_events():
    return asyncio.Event(), asyncio.Event()


async def _run_listener_with_events(
    events: list[Event],
    *,
    config=None,
    timeout: float = 2.0,
):
    """Feed *events* into the event_listener, then send a shutdown to stop it.

    Returns the turn_complete_event so callers can assert on it.
    """
    from agent.main import event_listener

    event_queue, submission_queue = _make_queues()
    turn_complete_event, ready_event = _make_events()

    # Minimal prompt_session stub (not exercised for these event types)
    prompt_session = SimpleNamespace(prompt_async=AsyncMock(return_value="n"))

    if config is None:
        config = SimpleNamespace(yolo_mode=False)

    for ev in events:
        await event_queue.put(ev)

    # Sentinel to break the listener's while-True loop
    await event_queue.put(Event(event_type="shutdown"))

    await asyncio.wait_for(
        event_listener(
            event_queue,
            submission_queue,
            turn_complete_event,
            ready_event,
            prompt_session,
            config,
            session_holder=[None],
        ),
        timeout=timeout,
    )
    return turn_complete_event


# ── session_terminated handling ────────────────────────────────────────


@pytest.mark.asyncio
async def test_event_listener_handles_session_terminated(capsys):
    """session_terminated must print an error and set turn_complete_event."""
    ev = Event(
        event_type="session_terminated",
        data={
            "reason": "compaction_failed",
            "user_message": "Conversation too large to continue.",
        },
    )

    turn_complete = await _run_listener_with_events([ev])

    assert turn_complete.is_set(), (
        "turn_complete_event must be set so the CLI prompt loop doesn't hang"
    )

    captured = capsys.readouterr()
    assert "compaction_failed" in captured.out or "compaction_failed" in captured.err


@pytest.mark.asyncio
async def test_session_terminated_uses_default_message_when_data_missing(capsys):
    """If data is None the handler must still work with defaults."""
    ev = Event(event_type="session_terminated", data=None)

    turn_complete = await _run_listener_with_events([ev])

    assert turn_complete.is_set()
    captured = capsys.readouterr()
    # The default reason should appear
    assert "unknown" in captured.out or "unknown" in captured.err


# ── unknown event type warning ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_event_listener_warns_on_unknown_event_type(caplog):
    """An event type with no explicit handler must produce a warning log."""
    ev = Event(
        event_type="completely_novel_event_type",
        data={"some": "payload"},
    )

    with caplog.at_level(logging.WARNING, logger="agent.main"):
        await _run_listener_with_events([ev])

    assert any(
        "completely_novel_event_type" in record.message for record in caplog.records
    ), (
        "Unknown event types must trigger a logger.warning with the event type name. "
        f"Got log records: {[r.message for r in caplog.records]}"
    )
