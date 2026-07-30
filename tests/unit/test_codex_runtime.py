from types import SimpleNamespace

import pytest

from agent.core.codex_runtime import (
    CODEX_TOOL_NAMESPACE,
    CodexAppServerRuntime,
    CodexRuntimeError,
    build_dynamic_tool_namespace,
    codex_login_status,
)
from agent.core.tools import ToolSpec


class StubRouter:
    def __init__(self):
        self.tools = {
            "bash": ToolSpec(
                name="bash",
                description="shell",
                parameters={"type": "object"},
                handler=None,
            ),
            "research": ToolSpec(
                name="research",
                description="nested research",
                parameters={"type": "object"},
                handler=None,
            ),
            "hf_papers": ToolSpec(
                name="hf_papers",
                description="papers",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
                handler=None,
            ),
            "invalid.tool": ToolSpec(
                name="invalid.tool",
                description="invalid name",
                parameters={"type": "object"},
                handler=None,
            ),
        }


def test_dynamic_namespace_keeps_ml_tools_and_skips_codex_duplicates():
    namespace, dispatch = build_dynamic_tool_namespace(
        StubRouter(),
        local_mode=True,
    )

    assert namespace is not None
    assert namespace["name"] == CODEX_TOOL_NAMESPACE
    assert [tool["name"] for tool in namespace["tools"]] == ["hf_papers"]
    assert dispatch == {"hf_papers": "hf_papers"}


def test_remote_sandbox_tools_can_expose_namespaced_bash():
    namespace, dispatch = build_dynamic_tool_namespace(
        StubRouter(),
        local_mode=False,
    )

    assert namespace is not None
    assert [tool["name"] for tool in namespace["tools"]] == [
        "bash",
        "hf_papers",
    ]
    assert dispatch == {"bash": "bash", "hf_papers": "hf_papers"}


@pytest.mark.asyncio
async def test_codex_login_status_reports_missing_cli(monkeypatch):
    monkeypatch.setattr(
        "agent.core.codex_runtime.shutil.which",
        lambda _binary: None,
    )

    with pytest.raises(CodexRuntimeError, match="Codex CLI is not installed"):
        await codex_login_status()


@pytest.mark.asyncio
async def test_codex_login_status_uses_public_cli_status(monkeypatch):
    class Process:
        returncode = 0

        async def communicate(self):
            return b"Logged in using ChatGPT\n", b""

    async def fake_subprocess(*_args, **_kwargs):
        return Process()

    monkeypatch.setattr(
        "agent.core.codex_runtime.shutil.which",
        lambda _binary: "/usr/local/bin/codex",
    )
    monkeypatch.setattr(
        "agent.core.codex_runtime.asyncio.create_subprocess_exec",
        fake_subprocess,
    )

    assert await codex_login_status() == "Logged in using ChatGPT"


@pytest.mark.asyncio
async def test_dynamic_tool_failure_is_returned_to_codex(tmp_path):
    class FailingRouter:
        async def call_tool(self, *_args, **_kwargs):
            raise RuntimeError("probe failed")

    responses = []
    runtime = CodexAppServerRuntime(
        config=SimpleNamespace(model_name="codex/default"),
        tool_router=FailingRouter(),
        hf_token=None,
        local_mode=True,
        cwd=tmp_path,
        autonomous_mode=False,
    )
    runtime._dispatch = {"hf_papers": "hf_papers"}
    runtime._tool_session = object()

    async def capture_response(message):
        responses.append(message)

    runtime._write = capture_response

    await runtime._handle_server_request(
        {
            "id": 7,
            "method": "item/tool/call",
            "params": {
                "namespace": CODEX_TOOL_NAMESPACE,
                "tool": "hf_papers",
                "arguments": {"operation": "search", "query": "LoRA"},
            },
        }
    )

    assert responses[0]["id"] == 7
    assert responses[0]["result"]["success"] is False
    assert "probe failed" in responses[0]["result"]["contentItems"][0]["text"]


@pytest.mark.asyncio
async def test_builtin_command_item_uses_tool_callback(tmp_path):
    calls = []

    async def on_tool(name, arguments, output, success, tool_call_id):
        calls.append((name, arguments, output, success, tool_call_id))

    runtime = CodexAppServerRuntime(
        config=SimpleNamespace(model_name="codex/default"),
        tool_router=SimpleNamespace(),
        hf_token=None,
        local_mode=False,
        cwd=tmp_path,
        autonomous_mode=False,
        on_tool=on_tool,
    )

    item = {
        "id": "cmd-1",
        "type": "commandExecution",
        "command": "pwd",
        "cwd": str(tmp_path),
        "status": "completed",
        "exitCode": 0,
        "aggregatedOutput": str(tmp_path),
    }
    await runtime._emit_builtin_item(item, completed=False)
    await runtime._emit_builtin_item(item, completed=True)

    assert calls[0] == (
        "codex_command",
        {"command": "pwd", "cwd": str(tmp_path)},
        None,
        None,
        "cmd-1",
    )
    assert calls[1][0] == "codex_command"
    assert calls[1][2] == str(tmp_path)
    assert calls[1][3] is True
