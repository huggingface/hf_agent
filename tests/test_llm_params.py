from agent.core.llm_params import _resolve_llm_params
from agent.core.model_switcher import is_valid_model_id


def test_resolve_ollama_params(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    params = _resolve_llm_params("ollama/llama3.1:8b", reasoning_effort="low")

    assert params == {
        "model": "openai/llama3.1:8b",
        "api_base": "http://localhost:11434/v1",
        "api_key": "ollama",
        "extra_body": {"reasoning_effort": "low"},
    }


def test_resolve_lm_studio_params(monkeypatch):
    monkeypatch.delenv("LMSTUDIO_API_KEY", raising=False)
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")

    params = _resolve_llm_params("lm_studio/google/gemma-4-e4b")

    assert params == {
        "model": "openai/google/gemma-4-e4b",
        "api_base": "http://127.0.0.1:1234/v1",
        "api_key": "lm-studio",
    }


def test_resolve_vllm_params(monkeypatch):
    monkeypatch.delenv("VLLM_API_KEY", raising=False)
    monkeypatch.setenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")

    params = _resolve_llm_params(
        "vllm/meta-llama/Llama-3.1-8B-Instruct",
        reasoning_effort="medium",
    )

    assert params == {
        "model": "openai/meta-llama/Llama-3.1-8B-Instruct",
        "api_base": "http://127.0.0.1:8000/v1",
        "api_key": "EMPTY",
        "extra_body": {"reasoning_effort": "medium"},
    }


def test_resolve_openai_compat_params(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "compat-key")

    params = _resolve_llm_params("openai-compat/custom-model")

    assert params == {
        "model": "openai/custom-model",
        "api_base": "http://127.0.0.1:9000/v1",
        "api_key": "compat-key",
    }


def test_model_switcher_accepts_local_openai_compat_prefixes():
    assert is_valid_model_id("ollama/llama3.1:8b") is True
    assert is_valid_model_id("lm_studio/google/gemma-4-e4b") is True
    assert is_valid_model_id("vllm/meta-llama/Llama-3.1-8B-Instruct") is True
    assert is_valid_model_id("openai-compat/custom-model") is True
