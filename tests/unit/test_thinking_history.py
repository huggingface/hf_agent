from litellm import ChatCompletionMessageToolCall, Message

from agent.core.agent_loop import (
    LLMResult,
    _assistant_message_from_result,
    _extract_thinking_state,
)


def test_extract_thinking_state_from_litellm_message():
    message = Message(
        role="assistant",
        content="working",
        thinking_blocks=[{"type": "thinking", "thinking": "reasoned"}],
        reasoning_content="reasoned",
    )

    thinking_blocks, reasoning_content = _extract_thinking_state(message)

    assert thinking_blocks == [{"type": "thinking", "thinking": "reasoned"}]
    assert reasoning_content == "reasoned"


def test_assistant_message_from_result_preserves_thinking_with_tool_calls():
    tool_call = ChatCompletionMessageToolCall(
        id="call_1",
        type="function",
        function={"name": "bash", "arguments": '{"command": "date"}'},
    )
    result = LLMResult(
        content=None,
        tool_calls_acc={},
        token_count=12,
        finish_reason="tool_calls",
        thinking_blocks=[{"type": "thinking", "thinking": "reasoned"}],
        reasoning_content="reasoned",
    )

    message = _assistant_message_from_result(result, tool_calls=[tool_call])

    assert message.tool_calls == [tool_call]
    assert message.thinking_blocks == [{"type": "thinking", "thinking": "reasoned"}]
    assert message.reasoning_content == "reasoned"


def test_assistant_message_from_result_omits_absent_thinking_fields():
    result = LLMResult(
        content="done",
        tool_calls_acc={},
        token_count=12,
        finish_reason="stop",
    )

    message = _assistant_message_from_result(result)

    assert message.content == "done"
    assert getattr(message, "thinking_blocks", None) is None
    assert getattr(message, "reasoning_content", None) is None
