"""
Sandbox tools — expose the Sandbox client as agent tools.

7 tools total:
  bash, read, write, edit, glob, grep, upload — operations on the sandbox

Auto-creation: if any operation tool is called without an active sandbox,
a cpu-basic sandbox is auto-created (no approval needed).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from huggingface_hub import HfApi

from agent.core.session import Event
from agent.tools.sandbox_client import Sandbox

# ── Tool name mapping (short agent names → Sandbox client names) ──────


async def _ensure_sandbox(
    session: Any, hardware: str = "cpu-basic", **create_kwargs
) -> tuple[Sandbox | None, str | None]:
    """
    Ensure a sandbox exists on the session. Auto-creates with given hardware if needed.

    Returns:
        (sandbox, error_message) — one will be None.
    """
    if session and getattr(session, "sandbox", None):
        return session.sandbox, None

    if not session:
        return None, "No session available."

    token = os.environ.get("HF_TOKEN")
    if not token:
        return None, "HF_TOKEN environment variable not set. Cannot create sandbox."

    api = HfApi(token=token)
    user_info = api.whoami()
    owner = user_info.get("name", user_info.get("user", ""))
    if not owner:
        return None, "Could not determine HF username from token."

    await session.send_event(
        Event(
            event_type="tool_log",
            data={
                "tool": "sandbox",
                "log": f"Auto-creating sandbox for {owner} ({hardware})...",
            },
        )
    )

    kwargs = {"owner": owner, "hardware": hardware, "token": token, **create_kwargs}
    sb = await asyncio.to_thread(Sandbox.create, **kwargs)
    session.sandbox = sb

    await session.send_event(
        Event(
            event_type="tool_log",
            data={"tool": "sandbox", "log": f"Sandbox ready: {sb.space_id} ({sb.url})"},
        )
    )

    return sb, None


def _make_tool_handler(sandbox_tool_name: str):
    """Factory: create a handler for a sandbox operation tool."""

    async def handler(args: dict[str, Any], session: Any = None) -> tuple[str, bool]:
        # Auto-create sandbox if not present
        try:
            sb, error = await _ensure_sandbox(session)
        except Exception as e:
            return f"Failed to auto-create sandbox: {e}", False

        if error:
            return error, False

        try:
            result = await asyncio.to_thread(sb.call_tool, sandbox_tool_name, args)
            if result.success:
                return result.output or "(no output)", True
            else:
                error_msg = result.error or "Unknown error"
                output = result.output
                if output:
                    return f"{output}\n\nERROR: {error_msg}", False
                return f"ERROR: {error_msg}", False
        except Exception as e:
            return f"Sandbox operation failed: {e}", False

    return handler


def get_sandbox_tools():
    """Return all 8 sandbox ToolSpecs."""
    from agent.core.tools import ToolSpec

    tools = []

    for name in Sandbox.TOOLS.keys():
        spec = Sandbox.TOOLS[name]
        tools.append(
            ToolSpec(
                name=name,
                description=spec["description"],
                parameters=spec["parameters"],
                handler=_make_tool_handler(name),
            )
        )

    return tools
