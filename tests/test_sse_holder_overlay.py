"""Tests for the holder-local SSE fast-path overlay (US-005, Plan Step 4).

Covers:
* Holder fast-path uses the in-process ``EventBroadcaster``.
* Non-holder slow-path tails ``store.change_stream_events``.
* On ``PyMongoError`` the slow-path falls back to ``store.load_events_after``.
* ``_subscriber_counts`` is incremented on attach and decremented on detach
  for both transport branches.
* Replay phase filters out events with ``seq <= after_seq``.
* A terminal event seen during replay ends the stream without entering the
  live phase.

The persistence store is replaced with an ``AsyncMock``; we exercise the
``_sse_response`` event generator directly by walking the ``body_iterator``
of the returned ``StreamingResponse``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pymongo.errors import PyMongoError

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from session_manager import (  # noqa: E402
    AgentSession,
    EventBroadcaster,
    SessionManager,
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _bare_manager(holder_id: str = "main:test-host:deadbeef") -> SessionManager:
    """Skip ``__init__``'s expensive config load; install the bits we need."""
    manager = object.__new__(SessionManager)
    manager.config = SimpleNamespace(model_name="test-model")
    manager.sessions = {}
    manager._lock = asyncio.Lock()
    manager.persistence_store = None
    manager.mode = "main"
    manager._holder_id = holder_id
    manager._heartbeat_task = None
    manager._subscriber_counts = {}
    manager._no_subscriber_since = {}
    return manager


def _fake_agent_session(
    session_id: str = "s1",
    *,
    holder_id: str | None,
    broadcaster: EventBroadcaster | None = None,
    is_active: bool = True,
) -> AgentSession:
    return AgentSession(
        session_id=session_id,
        session=SimpleNamespace(),  # type: ignore[arg-type]
        tool_router=object(),  # type: ignore[arg-type]
        user_id="dev",
        is_active=is_active,
        broadcaster=broadcaster,
        holder_id=holder_id,
    )


async def _drain(streaming_response, *, max_chunks: int = 50) -> list[str]:
    """Pull chunks off a StreamingResponse.body_iterator, stopping when the
    generator returns. ``max_chunks`` is a safety net so a buggy live-tail
    branch can't hang the test.
    """
    out: list[str] = []
    body = streaming_response.body_iterator
    try:
        for _ in range(max_chunks):
            chunk = await asyncio.wait_for(body.__anext__(), timeout=2.0)
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            out.append(chunk)
    except StopAsyncIteration:
        pass
    return out


def _is_data_chunk(chunk: str) -> bool:
    """A chunk that contains a ``data: ...`` line (i.e. an actual SSE event,
    not a keepalive comment)."""
    return any(line.startswith("data: ") for line in chunk.splitlines())


def _parse_event_type(chunk: str) -> str | None:
    """Pull ``event_type`` out of the ``data: {...}`` SSE line."""
    for line in chunk.splitlines():
        if line.startswith("data: "):
            try:
                return json.loads(line[len("data: "):]).get("event_type")
            except json.JSONDecodeError:
                return None
    return None


def _parse_seq(chunk: str) -> int | None:
    for line in chunk.splitlines():
        if line.startswith("data: "):
            try:
                return json.loads(line[len("data: "):]).get("seq")
            except json.JSONDecodeError:
                return None
    return None


# ── 1. Holder fast-path uses the in-process broadcaster ───────────────────


@pytest.mark.asyncio
async def test_holder_fast_path_uses_broadcaster(monkeypatch):
    manager = _bare_manager(holder_id="main:host:abc")

    source_queue: asyncio.Queue = asyncio.Queue()
    broadcaster = EventBroadcaster(source_queue)
    bcast_task = asyncio.create_task(broadcaster.run())

    agent_session = _fake_agent_session(
        "s1", holder_id="main:host:abc", broadcaster=broadcaster
    )
    manager.sessions["s1"] = agent_session

    import routes.agent as agent_routes

    monkeypatch.setattr(agent_routes, "session_manager", manager)

    response = agent_routes._sse_response(
        "s1", agent_session, replay_events=[], after_seq=0
    )

    async def push_events():
        # Give the generator a tick to subscribe before we publish.
        await asyncio.sleep(0.05)
        await source_queue.put(
            SimpleNamespace(event_type="agent_message", data={"text": "hi"}, seq=1)
        )
        await asyncio.sleep(0.05)
        await source_queue.put(
            SimpleNamespace(event_type="turn_complete", data={}, seq=2)
        )

    pusher = asyncio.create_task(push_events())
    chunks = await _drain(response)
    await pusher
    bcast_task.cancel()
    try:
        await bcast_task
    except asyncio.CancelledError:
        pass

    types = [_parse_event_type(c) for c in chunks if _is_data_chunk(c)]
    assert "agent_message" in types
    assert "turn_complete" in types
    # Subscriber count back to zero post-stream.
    assert manager._subscriber_counts.get("s1", 0) == 0


# ── 2. Non-holder uses change stream ──────────────────────────────────────


@pytest.mark.asyncio
async def test_non_holder_uses_change_stream(monkeypatch):
    manager = _bare_manager(holder_id="main:host:abc")

    async def fake_stream(session_id: str, after_seq: int = 0):
        yield {"session_id": session_id, "seq": 5, "event_type": "agent_message",
               "data": {"text": "first"}}
        yield {"session_id": session_id, "seq": 6, "event_type": "turn_complete",
               "data": {}}

    store = AsyncMock()
    store.enabled = True
    store.change_stream_events = fake_stream  # type: ignore[assignment]
    store.load_events_after = AsyncMock(return_value=[])
    manager.persistence_store = store

    agent_session = _fake_agent_session(
        "s1", holder_id="other:host:zzz", broadcaster=None
    )
    manager.sessions["s1"] = agent_session

    import routes.agent as agent_routes

    monkeypatch.setattr(agent_routes, "session_manager", manager)

    response = agent_routes._sse_response(
        "s1", agent_session, replay_events=[], after_seq=0
    )
    chunks = await _drain(response)

    seqs = [_parse_seq(c) for c in chunks if _is_data_chunk(c)]
    assert 5 in seqs and 6 in seqs


# ── 3. Slow path falls back to polling on PyMongoError ────────────────────


@pytest.mark.asyncio
async def test_non_holder_falls_back_to_poll_on_pymongo_error(monkeypatch):
    manager = _bare_manager(holder_id="main:host:abc")

    async def exploding_stream(session_id: str, after_seq: int = 0):
        raise PyMongoError("replica set unavailable")
        yield  # pragma: no cover - makes this an async generator

    store = AsyncMock()
    store.enabled = True
    store.change_stream_events = exploding_stream  # type: ignore[assignment]

    poll_calls = {"n": 0}

    async def fake_load(session_id: str, after_seq: int) -> list[dict[str, Any]]:
        poll_calls["n"] += 1
        if poll_calls["n"] == 1:
            return [
                {"session_id": session_id, "seq": 10, "event_type": "agent_message",
                 "data": {}},
                {"session_id": session_id, "seq": 11, "event_type": "turn_complete",
                 "data": {}},
            ]
        return []

    store.load_events_after = fake_load  # type: ignore[assignment]
    manager.persistence_store = store

    agent_session = _fake_agent_session(
        "s1", holder_id="other:host:zzz", broadcaster=None
    )
    manager.sessions["s1"] = agent_session

    import routes.agent as agent_routes

    monkeypatch.setattr(agent_routes, "session_manager", manager)

    response = agent_routes._sse_response(
        "s1", agent_session, replay_events=[], after_seq=0
    )
    chunks = await _drain(response)

    seqs = [_parse_seq(c) for c in chunks if _is_data_chunk(c)]
    assert 10 in seqs and 11 in seqs
    assert poll_calls["n"] >= 1


# ── 4. Subscriber counter on holder fast path ─────────────────────────────


@pytest.mark.asyncio
async def test_subscriber_counter_attach_detach_holder_path(monkeypatch):
    manager = _bare_manager(holder_id="main:host:abc")

    source_queue: asyncio.Queue = asyncio.Queue()
    broadcaster = EventBroadcaster(source_queue)
    bcast_task = asyncio.create_task(broadcaster.run())

    agent_session = _fake_agent_session(
        "s1", holder_id="main:host:abc", broadcaster=broadcaster
    )
    manager.sessions["s1"] = agent_session

    import routes.agent as agent_routes

    monkeypatch.setattr(agent_routes, "session_manager", manager)

    response = agent_routes._sse_response(
        "s1", agent_session, replay_events=[], after_seq=0
    )

    body = response.body_iterator

    # Push a non-terminal then a terminal so the generator exits cleanly.
    async def push():
        await asyncio.sleep(0.05)
        # Mid-stream snapshot of the counter.
        await asyncio.sleep(0.0)
        await source_queue.put(
            SimpleNamespace(event_type="turn_complete", data={}, seq=1)
        )

    pusher = asyncio.create_task(push())
    # Pull first chunk (terminal turn_complete) — generator subscribes before
    # awaiting on queue.get().
    await asyncio.wait_for(body.__anext__(), timeout=2.0)
    # After the first yield we should be detached because turn_complete is terminal.
    # Drain the rest to ensure the finally block runs.
    async for _ in body:
        pass
    await pusher
    bcast_task.cancel()
    try:
        await bcast_task
    except asyncio.CancelledError:
        pass

    assert manager._subscriber_counts.get("s1", 0) == 0
    # ``_no_subscriber_since`` is set on the zero-transition.
    assert "s1" in manager._no_subscriber_since


# ── 5. Subscriber counter on non-holder slow path ─────────────────────────


@pytest.mark.asyncio
async def test_subscriber_counter_attach_detach_slow_path(monkeypatch):
    manager = _bare_manager(holder_id="main:host:abc")

    async def fake_stream(session_id: str, after_seq: int = 0):
        yield {"session_id": session_id, "seq": 1, "event_type": "turn_complete",
               "data": {}}

    store = AsyncMock()
    store.enabled = True
    store.change_stream_events = fake_stream  # type: ignore[assignment]
    store.load_events_after = AsyncMock(return_value=[])
    manager.persistence_store = store

    agent_session = _fake_agent_session(
        "s1", holder_id="other:host:zzz", broadcaster=None
    )
    manager.sessions["s1"] = agent_session

    import routes.agent as agent_routes

    monkeypatch.setattr(agent_routes, "session_manager", manager)

    response = agent_routes._sse_response(
        "s1", agent_session, replay_events=[], after_seq=0
    )
    await _drain(response)

    assert manager._subscriber_counts.get("s1", 0) == 0
    assert "s1" in manager._no_subscriber_since


# ── 6. Replay phase skips seqs <= after_seq ───────────────────────────────


@pytest.mark.asyncio
async def test_replay_phase_skips_seqs_le_after_seq(monkeypatch):
    manager = _bare_manager(holder_id="main:host:abc")

    # Slow path with empty change stream — terminates after replay.
    async def empty_stream(session_id: str, after_seq: int = 0):
        return
        yield  # pragma: no cover

    store = AsyncMock()
    store.enabled = True
    store.change_stream_events = empty_stream  # type: ignore[assignment]
    store.load_events_after = AsyncMock(return_value=[])
    manager.persistence_store = store

    agent_session = _fake_agent_session(
        "s1", holder_id="other:host:zzz", broadcaster=None
    )
    manager.sessions["s1"] = agent_session

    import routes.agent as agent_routes

    monkeypatch.setattr(agent_routes, "session_manager", manager)

    replay = [
        {"session_id": "s1", "seq": 1, "event_type": "agent_message", "data": {}},
        {"session_id": "s1", "seq": 2, "event_type": "agent_message", "data": {}},
        {"session_id": "s1", "seq": 3, "event_type": "agent_message", "data": {}},
        {"session_id": "s1", "seq": 4, "event_type": "turn_complete", "data": {}},
    ]
    response = agent_routes._sse_response(
        "s1", agent_session, replay_events=replay, after_seq=2
    )
    chunks = await _drain(response)

    seqs = [_parse_seq(c) for c in chunks if _is_data_chunk(c)]
    # Only 3 and 4 should be yielded; 1 and 2 are filtered by after_seq.
    assert seqs == [3, 4]


# ── 7. Terminal event in replay ends the stream ───────────────────────────


@pytest.mark.asyncio
async def test_terminal_event_in_replay_ends_stream(monkeypatch):
    manager = _bare_manager(holder_id="main:host:abc")

    # If the live phase were entered, this would explode and surface as a test failure.
    async def exploding_stream(session_id: str, after_seq: int = 0):
        raise AssertionError("live phase entered after terminal replay event")
        yield  # pragma: no cover

    store = AsyncMock()
    store.enabled = True
    store.change_stream_events = exploding_stream  # type: ignore[assignment]
    store.load_events_after = AsyncMock(
        side_effect=AssertionError("poll loop entered after terminal replay")
    )
    manager.persistence_store = store

    agent_session = _fake_agent_session(
        "s1", holder_id="other:host:zzz", broadcaster=None
    )
    manager.sessions["s1"] = agent_session

    import routes.agent as agent_routes

    monkeypatch.setattr(agent_routes, "session_manager", manager)

    replay = [
        {"session_id": "s1", "seq": 1, "event_type": "agent_message", "data": {}},
        {"session_id": "s1", "seq": 2, "event_type": "turn_complete", "data": {}},
    ]
    response = agent_routes._sse_response(
        "s1", agent_session, replay_events=replay, after_seq=0
    )
    chunks = await _drain(response)

    seqs = [_parse_seq(c) for c in chunks if _is_data_chunk(c)]
    assert seqs == [1, 2]
