from types import SimpleNamespace

from litellm import ChatCompletionMessageToolCall as ToolCall

from agent.core.agent_loop import LLMResult, _assistant_message_from_result
from agent.tools.research_tool import _assistant_message_for_replay


def _tool_call() -> ToolCall:
    return ToolCall(
        id="call_1",
        type="function",
        function={"name": "read", "arguments": "{}"},
    )


def test_kimi_reasoning_replay_survives_assistant_tool_turn():
    result = LLMResult(
        content=None,
        tool_calls_acc={
            0: {
                "id": "call_1",
                "type": "function",
                "function": {"name": "read", "arguments": "{}"},
            }
        },
        token_count=42,
        finish_reason="tool_calls",
        reasoning_content="hidden chain state",
    )

    assistant = _assistant_message_from_result(
        result,
        tool_calls=[_tool_call()],
        model_id="moonshot/kimi-k2.7-code-highspeed",
    )

    assert assistant.tool_calls[0].id == "call_1"
    assert assistant.reasoning_content == "hidden chain state"


def test_hf_router_does_not_replay_kimi_reasoning_metadata():
    result = LLMResult(
        content=None,
        tool_calls_acc={},
        token_count=1,
        finish_reason="stop",
        reasoning_content="must not be sent to router",
    )

    assistant = _assistant_message_from_result(
        result,
        model_id="huggingface/moonshotai/Kimi-K2.7-Code:novita",
    )

    assert getattr(assistant, "reasoning_content", None) is None


def test_research_subagent_replays_reasoning_only_for_moonshot():
    msg = SimpleNamespace(
        content=None,
        tool_calls=[_tool_call()],
        reasoning_content="research hidden state",
        provider_specific_fields=None,
    )

    kimi_msg = _assistant_message_for_replay("moonshot/kimi-k2.7-code-highspeed", msg)
    hf_msg = _assistant_message_for_replay(
        "huggingface/moonshotai/Kimi-K2.7-Code:novita", msg
    )

    assert kimi_msg.reasoning_content == "research hidden state"
    assert getattr(hf_msg, "reasoning_content", None) is None
