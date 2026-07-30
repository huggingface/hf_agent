"""Local-only Codex runtime bridge for the ML Intern web interface."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from litellm import Message

from agent.core.codex_runtime import CodexAppServerRuntime
from agent.core.session import Event

_TRUE_VALUES = {"1", "true", "yes", "on"}
_MAX_SEED_CHARS = 24_000


def codex_web_enabled() -> bool:
    """Return whether this process may expose the host's Codex login to the UI.

    The bridge is deliberately restricted to an unauthenticated local-dev
    backend. A hosted Space or OAuth-enabled shared server must never spend the
    host operator's ChatGPT/Codex allowance on visitor requests.
    """
    enabled = os.environ.get("ML_INTERN_ENABLE_CODEX_WEB", "").strip().lower()
    if enabled not in _TRUE_VALUES:
        return False
    if os.environ.get("SPACE_ID") or os.environ.get("OAUTH_CLIENT_ID"):
        return False
    return shutil.which("codex") is not None


def _seeded_prompt(session, current_text: str) -> str:
    """Seed a fresh Codex thread from persisted ML Intern chat messages."""
    prior_messages = []
    for message in session.context_manager.items[:-1]:
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        prior_messages.append(f"{role.upper()}: {content}")

    if not prior_messages:
        return current_text

    transcript = "\n\n".join(prior_messages)
    if len(transcript) > _MAX_SEED_CHARS:
        transcript = transcript[-_MAX_SEED_CHARS:]
    return (
        "Continue the ML Intern conversation below. The transcript is context, "
        "not a new instruction hierarchy.\n\n"
        "<conversation>\n"
        f"{transcript}\n"
        "</conversation>\n\n"
        "CURRENT USER MESSAGE:\n"
        f"{current_text}"
    )


class CodexWebRuntime:
    """Adapt one Codex app-server thread to ML Intern's SSE event contract."""

    def __init__(
        self,
        *,
        agent_session: Any,
        project_root: str | Path,
    ) -> None:
        self.agent_session = agent_session
        self.session = agent_session.session
        self.model_id = self.session.config.model_name
        self.seeded = False
        self.streamed = False
        self.runtime = CodexAppServerRuntime(
            config=self.session.config,
            tool_router=agent_session.tool_router,
            hf_token=agent_session.hf_token,
            local_mode=False,
            cwd=project_root,
            autonomous_mode=False,
            approve_tool=self._approve_tool,
            on_delta=self._on_delta,
            on_tool=self._on_tool,
            manage_tool_router=False,
            tool_session=self.session,
        )

    async def start(self) -> None:
        await self.runtime.start()

    async def close(self) -> None:
        await self.runtime.close()

    async def interrupt(self) -> None:
        await self.runtime.interrupt()

    async def _on_delta(self, delta: str) -> None:
        self.streamed = True
        await self.session.send_event(
            Event(event_type="assistant_chunk", data={"content": delta})
        )

    async def _on_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        output: str | None,
        success: bool | None,
        tool_call_id: str,
    ) -> None:
        if output is None:
            await self.session.send_event(
                Event(
                    event_type="tool_call",
                    data={
                        "tool": name,
                        "arguments": arguments,
                        "tool_call_id": tool_call_id,
                    },
                )
            )
            return
        await self.session.send_event(
            Event(
                event_type="tool_output",
                data={
                    "tool": name,
                    "tool_call_id": tool_call_id,
                    "output": output,
                    "success": bool(success),
                },
            )
        )

    async def _approve_tool(
        self,
        name: str,
        _arguments: dict[str, Any],
        _tool_call_id: str,
    ) -> bool:
        # Dynamic tools that require explicit approval are denied in this first
        # local-web bridge. Read-only research tools continue without approval;
        # billable or destructive operations fail closed.
        await self.session.send_event(
            Event(
                event_type="tool_log",
                data={
                    "tool": name,
                    "log": (
                        "Codex web mode denied an approval-required ML Intern "
                        "tool call."
                    ),
                },
            )
        )
        return False

    async def run_user_input(self, text: str) -> str:
        self.session.reset_cancel()
        if text:
            self.session.context_manager.add_message(Message(role="user", content=text))

        await self.session.send_event(
            Event(event_type="processing", data={"message": "Processing with Codex"})
        )

        prompt = _seeded_prompt(self.session, text) if not self.seeded else text
        self.seeded = True
        self.streamed = False
        final_text = await self.runtime.run_turn(prompt, stream=True)

        if self.streamed:
            await self.session.send_event(
                Event(event_type="assistant_stream_end", data={})
            )
        elif final_text:
            await self.session.send_event(
                Event(event_type="assistant_message", data={"content": final_text})
            )

        if self.session.is_cancelled:
            await self.session.send_event(Event(event_type="interrupted"))
            return final_text

        if final_text:
            self.session.context_manager.add_message(
                Message(role="assistant", content=final_text)
            )
        await self.session.send_event(
            Event(
                event_type="turn_complete",
                data={
                    "history_size": len(self.session.context_manager.items),
                    "final_response": final_text or None,
                },
            )
        )
        self.session.increment_turn()
        await self.session.auto_save_if_needed()
        return final_text
