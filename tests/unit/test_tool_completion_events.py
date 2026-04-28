import asyncio
import json
from types import SimpleNamespace

import pytest

from agent.core.agent_loop import Handlers

@pytest.mark.asyncio
async def test_exec_approval_emits_complete_with_duration(monkeypatch):
    events = []

    async def send_event(ev):
        events.append(ev)

    class DummyToolRouter:
        async def call_tool(self, tool_name, arguments, session=None, tool_call_id=None):
            return "ok", True

    async def noop_run_agent(_session, _text):
        return None

    monkeypatch.setattr(Handlers, "run_agent", noop_run_agent)

    session = SimpleNamespace(
        pending_approval={"tool_calls": [
            SimpleNamespace(
                id="tc-1",
                function=SimpleNamespace(
                    name="bash",
                    arguments=json.dumps({"command": "date"}),
                ),
            )
        ]},
        tool_router=DummyToolRouter(),
        context_manager=SimpleNamespace(add_message=lambda _msg: None),
        _cancelled=asyncio.Event(),
        send_event=send_event,
    )

    await Handlers.exec_approval(session, approvals=[{"tool_call_id": "tc-1", "approved": True}])

    complete = [
        e for e in events
        if e.event_type == "tool_state_change" and (e.data or {}).get("state") == "complete"
    ]
    assert len(complete) == 1
    assert complete[0].data["tool_call_id"] == "tc-1"
    assert complete[0].data["success"] is True
    assert isinstance(complete[0].data["duration_ms"], int)
    assert complete[0].data["duration_ms"] >= 0


