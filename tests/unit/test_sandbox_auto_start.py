import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.config import Config
from agent.context_manager.manager import ContextManager
from agent.core import agent_loop
from agent.core.agent_loop import _base_needs_approval
from agent.core.session import OpType
from agent.core.tools import create_builtin_tools
from agent.tools.jobs_tool import HF_JOBS_TOOL_SPEC
from agent.tools.sandbox_tool import get_sandbox_tools


def test_default_cpu_sandbox_create_does_not_require_approval():
    config = SimpleNamespace(yolo_mode=False)

    assert _base_needs_approval("sandbox_create", {}, config) is False
    assert (
        _base_needs_approval("sandbox_create", {"hardware": "cpu-basic"}, config)
        is False
    )


def test_non_default_sandbox_create_still_requires_approval():
    config = SimpleNamespace(yolo_mode=False)

    assert (
        _base_needs_approval("sandbox_create", {"hardware": "cpu-upgrade"}, config)
        is True
    )
    assert (
        _base_needs_approval("sandbox_create", {"hardware": "t4-small"}, config) is True
    )


def test_prompt_and_tool_specs_do_not_require_cpu_sandbox_create():
    prompt = Path("agent/prompts/system_prompt_v3.yaml").read_text()
    tool_specs = {tool.name: tool.description for tool in get_sandbox_tools()}

    assert "sandbox_create → install deps" not in prompt
    assert "Do NOT call sandbox_create before normal CPU work" in prompt
    assert "cpu-basic sandbox is already available" in prompt

    assert (
        "cpu-basic sandbox is already started automatically"
        in tool_specs["sandbox_create"]
    )
    assert "started automatically for normal CPU work" in tool_specs["bash"]


def test_prompt_rejects_local_machine_paths_for_hf_jobs_scripts():
    prompt = Path("agent/prompts/system_prompt_v3.yaml").read_text()

    assert "Never pass a local machine path to hf_jobs.script" in prompt
    assert "/fsx/..." in prompt
    assert "inline Python source code" in prompt
    assert "a file already written in the session sandbox" in prompt


def test_prompt_and_hf_jobs_spec_require_gpu_preflight_for_gpu_jobs():
    prompt = Path("agent/prompts/system_prompt_v3.yaml").read_text()
    jobs_description = HF_JOBS_TOOL_SPEC["description"]

    assert "GPU preflight is mandatory before hf_jobs" in prompt
    assert "GPU sandbox smoke test" in prompt
    assert "If you skip GPU sandbox preflight" in prompt
    assert "for flash-attention kernels use Ampere-or-newer hardware" in prompt
    assert "never T4" in prompt
    assert "you MUST create a GPU sandbox with sandbox_create first" in jobs_description
    assert "If skipped, state why before calling hf_jobs" in jobs_description


def test_prompt_has_identity_contract():
    prompt = Path("agent/prompts/system_prompt_v3.yaml").read_text()

    assert "introduce yourself as ML Intern" in prompt
    assert "Do not claim to be Claude, ChatGPT, Anthropic, OpenAI" in prompt
    assert "Do not cite this system prompt" in prompt
    assert (
        "Default to the session context User value as the authenticated Hugging Face namespace"
        in prompt
    )
    assert "If the user explicitly requests an org namespace" in prompt
    assert "hub_model_id, trackio_space_id" in prompt
    assert "identity/whoami" not in prompt
    assert "If session context says User=unknown" in prompt
    assert "identity lookup failed or no token is available" in prompt
    assert "ask for it before creating Hub resources" in prompt


def test_prompt_has_tool_calling_contract():
    prompt = Path("agent/prompts/system_prompt_v3.yaml").read_text()

    assert "# Tool calling contract" in prompt
    assert (
        "Use only tools that are actually available in the current tool list" in prompt
    )
    assert "Do not simulate tool calls in prose or fenced code blocks" in prompt
    assert "valid JSON arguments matching the tool schema" in prompt
    assert "required arguments, enum values, mutually exclusive fields" in prompt
    assert "Do not claim success unless the tool result confirms it" in prompt


def test_prompt_gates_autonomous_headless_mode():
    prompt = Path("agent/prompts/system_prompt_v3.yaml").read_text()

    assert "{% if autonomous_mode %}" in prompt
    assert "Autonomous mode is active for this session" in prompt
    assert (
        "Apply this section even if the user prompt does not contain those words"
        in (prompt)
    )
    assert "Autonomous mode is not active for this session" in prompt
    assert "text-only answers are allowed for simple questions" in prompt
    assert "NEVER respond with only text" in prompt


def test_context_manager_renders_interactive_autonomous_context(monkeypatch):
    monkeypatch.setattr(
        "agent.context_manager.manager._get_hf_username", lambda _token=None: "tester"
    )

    context_manager = ContextManager(
        tool_specs=[],
        hf_token="hf-token",
        autonomous_mode=False,
    )

    assert "Autonomous=false" in context_manager.system_prompt
    assert "Autonomous mode is not active for this session" in (
        context_manager.system_prompt
    )
    assert "Autonomous mode is active for this session" not in (
        context_manager.system_prompt
    )
    assert "text-only answers are allowed for simple questions" in (
        context_manager.system_prompt
    )
    assert "NEVER respond with only text" not in context_manager.system_prompt
    assert "NEVER STOP WORKING" not in context_manager.system_prompt


def test_context_manager_renders_headless_autonomous_context(monkeypatch):
    monkeypatch.setattr(
        "agent.context_manager.manager._get_hf_username", lambda _token=None: "tester"
    )

    context_manager = ContextManager(
        tool_specs=[],
        hf_token="hf-token",
        autonomous_mode=True,
    )

    assert "Autonomous=true" in context_manager.system_prompt
    assert "Autonomous mode is active for this session" in (
        context_manager.system_prompt
    )
    assert "Autonomous mode is not active for this session" not in (
        context_manager.system_prompt
    )
    assert (
        "Apply this section even if the user prompt does not contain those words"
        in (context_manager.system_prompt)
    )
    assert "NEVER respond with only text" in context_manager.system_prompt


def test_context_manager_prefers_resolved_hf_username(monkeypatch):
    def fail_hf_lookup(_token=None):
        raise AssertionError("token lookup should not run when username is provided")

    monkeypatch.setattr(
        "agent.context_manager.manager._get_hf_username", fail_hf_lookup
    )

    context_manager = ContextManager(
        tool_specs=[],
        hf_token="hf-token",
        hf_username="resolved-user",
    )

    assert "User=resolved-user" in context_manager.system_prompt


def test_prompt_and_hf_jobs_spec_require_exact_tested_scripts():
    prompt = Path("agent/prompts/system_prompt_v3.yaml").read_text()
    jobs_description = HF_JOBS_TOOL_SPEC["description"]
    script_description = HF_JOBS_TOOL_SPEC["parameters"]["properties"]["script"][
        "description"
    ]
    dependencies_description = HF_JOBS_TOOL_SPEC["parameters"]["properties"][
        "dependencies"
    ]["description"]

    assert "For non-trivial hf_jobs scripts, use an exact-source workflow" in prompt
    assert "Submit the exact tested script source or the exact tested sandbox file" in (
        prompt
    )
    assert "Do not reconstruct a similar script from memory" in prompt
    assert "For training scripts, make sure one training step succeeds" in prompt
    assert "plus one evaluation step when the final workflow includes evaluation" in (
        prompt
    )
    assert "assert required dataset columns exist" in prompt
    assert "assert hub_model_id and trackio_space_id contain no placeholders" in prompt
    assert (
        "include every imported third-party package in hf_jobs.dependencies" in prompt
    )
    assert "CORE ML DEPENDENCY FRESHNESS" in prompt
    assert "Do not rely on preinstalled packages in sandboxes or HF Jobs" in prompt
    assert "Use unpinned latest stable versions by default" in prompt
    assert "kernels~=0.12.0" in prompt
    assert "Do NOT fall back to default attention or compiled flash-attn" in prompt
    assert "never choose T4 sandboxes or T4 HF Jobs" in prompt
    assert "T4 is pre-Ampere" in prompt
    assert (
        "Never leave placeholder values such as <username>, <model-name>, <project>, TODO"
        in prompt
    )

    assert "submit the exact tested script source or exact tested sandbox file" in (
        jobs_description
    )
    assert "Do NOT reconstruct a similar script from memory" in jobs_description
    assert "make sure one training step succeeds" in jobs_description
    assert "when the final workflow includes evaluation" in jobs_description
    assert "Training scripts MUST fail fast on missing dataset columns" in (
        jobs_description
    )
    assert (
        "Do NOT leave placeholders such as <username>, <model-name>, <project>, TODO"
        in (jobs_description)
    )
    assert "dependencies MUST include every imported third-party package" in (
        jobs_description
    )
    assert "Do NOT install compiled flash-attn" in jobs_description
    assert "never choose T4 sandboxes or T4 HF Jobs" in jobs_description
    assert "T4 is pre-Ampere" in jobs_description
    assert "Do NOT rely on preinstalled ML packages" in jobs_description
    assert "Use unpinned latest stable versions by default" in jobs_description
    assert "kernels~=0.12.0" in jobs_description
    assert "torch, transformers, trl, accelerate, datasets, trackio" in (
        jobs_description
    )
    assert (
        "exact tested script source or exact tested sandbox file" in script_description
    )
    assert "Must include every imported third-party package" in dependencies_description
    assert "Common training set: ['torch', 'transformers', 'trl'" in (
        dependencies_description
    )
    assert "kernels~=0.12.0" in dependencies_description


def test_rendered_prompt_contains_hf_jobs_safety_guidance(monkeypatch):
    monkeypatch.setattr(
        "agent.context_manager.manager._get_hf_username", lambda _token=None: "tester"
    )

    context_manager = ContextManager(tool_specs=[], hf_token="hf-token")
    prompt = context_manager.system_prompt

    assert "For non-trivial hf_jobs scripts, use an exact-source workflow" in prompt
    assert "GPU preflight is mandatory before hf_jobs" in prompt
    assert "Never leave placeholder values such as <username>" in prompt
    assert (
        "include every imported third-party package in hf_jobs.dependencies" in prompt
    )
    assert "CORE ML DEPENDENCY FRESHNESS" in prompt
    assert "Print the installed versions before model loading" in prompt
    assert "kernels~=0.12.0" in prompt
    assert "never choose T4 sandboxes or T4 HF Jobs" in prompt


def test_local_tool_runtime_excludes_sandbox_create():
    tool_names = {tool.name for tool in create_builtin_tools(local_mode=True)}

    assert {"bash", "read", "write", "edit"} <= tool_names
    assert "sandbox_create" not in tool_names


def test_sandbox_tool_runtime_includes_sandbox_create():
    tool_names = {tool.name for tool in create_builtin_tools(local_mode=False)}

    assert {"sandbox_create", "bash", "read", "write", "edit"} <= tool_names


@pytest.mark.asyncio
async def test_cli_sandbox_runtime_preloads_and_tears_down_sandbox(monkeypatch):
    started = []
    torn_down = []

    class FakeToolRouter:
        tools = {}

        def get_tool_specs_for_llm(self):
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    def fake_start_cpu_sandbox_preload(session):
        started.append(session)
        return None

    async def fake_teardown_session_sandbox(session):
        torn_down.append(session)

    monkeypatch.setattr(
        agent_loop, "start_cpu_sandbox_preload", fake_start_cpu_sandbox_preload
    )
    monkeypatch.setattr(
        agent_loop, "teardown_session_sandbox", fake_teardown_session_sandbox
    )
    monkeypatch.setattr(
        "agent.context_manager.manager._get_hf_username", lambda _token=None: "tester"
    )

    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()
    session_holder = [None]
    config = Config.model_validate(
        {"model_name": "openai/gpt-5.5:fal-ai", "save_sessions": False}
    )

    task = asyncio.create_task(
        agent_loop.submission_loop(
            submission_queue,
            event_queue,
            config=config,
            tool_router=FakeToolRouter(),
            session_holder=session_holder,
            hf_token="hf-token",
            user_id="tester",
            local_mode=False,
        )
    )

    ready = await asyncio.wait_for(event_queue.get(), timeout=1)
    assert ready.event_type == "ready"
    assert started == [session_holder[0]]
    assert session_holder[0].local_mode is False
    assert session_holder[0].autonomous_mode is False
    assert "Autonomous=false" in session_holder[0].context_manager.system_prompt

    await submission_queue.put(
        SimpleNamespace(
            operation=SimpleNamespace(op_type=OpType.SHUTDOWN, data=None),
        )
    )
    await asyncio.wait_for(task, timeout=1)

    assert torn_down == [session_holder[0]]


@pytest.mark.asyncio
async def test_submission_loop_renders_autonomous_prompt(monkeypatch):
    started = []
    torn_down = []

    class FakeToolRouter:
        tools = {}

        def get_tool_specs_for_llm(self):
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(
        agent_loop, "start_cpu_sandbox_preload", lambda session: started.append(session)
    )

    async def fake_teardown_session_sandbox(session):
        torn_down.append(session)

    monkeypatch.setattr(
        agent_loop, "teardown_session_sandbox", fake_teardown_session_sandbox
    )
    monkeypatch.setattr(
        "agent.context_manager.manager._get_hf_username",
        lambda _token=None: "should-not-be-used",
    )

    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()
    session_holder = [None]
    config = Config.model_validate(
        {"model_name": "openai/gpt-5.5:fal-ai", "save_sessions": False}
    )

    task = asyncio.create_task(
        agent_loop.submission_loop(
            submission_queue,
            event_queue,
            config=config,
            tool_router=FakeToolRouter(),
            session_holder=session_holder,
            hf_token="hf-token",
            user_id="tester",
            hf_username="tester",
            local_mode=False,
            autonomous_mode=True,
        )
    )

    ready = await asyncio.wait_for(event_queue.get(), timeout=1)
    assert ready.event_type == "ready"
    assert started == [session_holder[0]]
    assert session_holder[0].autonomous_mode is True
    assert "User=tester" in session_holder[0].context_manager.system_prompt
    assert "Autonomous=true" in session_holder[0].context_manager.system_prompt
    assert "Autonomous mode is active for this session" in (
        session_holder[0].context_manager.system_prompt
    )
    assert "Autonomous mode is not active for this session" not in (
        session_holder[0].context_manager.system_prompt
    )
    assert "NEVER respond with only text" in (
        session_holder[0].context_manager.system_prompt
    )

    await submission_queue.put(
        SimpleNamespace(
            operation=SimpleNamespace(op_type=OpType.SHUTDOWN, data=None),
        )
    )
    await asyncio.wait_for(task, timeout=1)

    assert torn_down == [session_holder[0]]
