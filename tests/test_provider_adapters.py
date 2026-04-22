from agent.core.llm_params import _resolve_llm_params


def test_native_adapter_keeps_model_name():
    params = _resolve_llm_params("anthropic/claude-opus-4-6", reasoning_effort="high")

    assert params == {
        "model": "anthropic/claude-opus-4-6",
        "reasoning_effort": "high",
    }


def test_hf_adapter_builds_router_params(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf-test")

    params = _resolve_llm_params(
        "moonshotai/Kimi-K2.6:novita", reasoning_effort="minimal"
    )

    assert params == {
        "model": "openai/moonshotai/Kimi-K2.6:novita",
        "api_base": "https://router.huggingface.co/v1",
        "api_key": "hf-test",
        "extra_body": {"reasoning_effort": "low"},
    }


def test_hf_adapter_adds_bill_to_header(monkeypatch):
    monkeypatch.setenv("INFERENCE_TOKEN", "hf-space-token")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    params = _resolve_llm_params("MiniMaxAI/MiniMax-M2.7")

    assert params["extra_headers"] == {"X-HF-Bill-To": "smolagents"}
    assert params["api_key"] == "hf-space-token"
