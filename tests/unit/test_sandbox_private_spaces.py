import asyncio
from types import SimpleNamespace

from agent.tools import sandbox_client, sandbox_tool
from agent.tools.sandbox_client import Sandbox
from agent.tools.sandbox_tool import sandbox_create_handler


def test_sandbox_client_defaults_to_private_spaces(monkeypatch):
    duplicate_kwargs = {}

    class FakeApi:
        def __init__(self, token=None):
            self.token = token

        def duplicate_space(self, **kwargs):
            duplicate_kwargs.update(kwargs)

        def add_space_secret(self, *args, **kwargs):
            pass

        def get_space_runtime(self, space_id):
            return SimpleNamespace(stage="RUNNING", hardware="cpu-basic")

    monkeypatch.setattr(sandbox_client, "HfApi", FakeApi)
    monkeypatch.setattr(
        Sandbox,
        "_setup_server",
        staticmethod(lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(Sandbox, "_wait_for_api", lambda self, *args, **kwargs: None)

    Sandbox.create(owner="alice", token="hf-token", log=lambda msg: None)

    assert duplicate_kwargs["private"] is True


def test_sandbox_tool_forces_private_spaces(monkeypatch):
    captured_kwargs = {}

    async def fake_ensure_sandbox(
        session,
        hardware="cpu-basic",
        extra_secrets=None,
        **create_kwargs,
    ):
        captured_kwargs.update(create_kwargs)
        return (
            SimpleNamespace(
                space_id="alice/sandbox-12345678",
                url="https://huggingface.co/spaces/alice/sandbox-12345678",
            ),
            None,
        )

    monkeypatch.setattr(sandbox_tool, "_ensure_sandbox", fake_ensure_sandbox)

    out, ok = asyncio.run(
        sandbox_create_handler(
            {"private": False},
            session=SimpleNamespace(sandbox=None),
        )
    )

    assert ok is True
    assert captured_kwargs["private"] is True
    assert "Visibility: private" in out
