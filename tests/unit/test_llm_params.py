"""Tests for agent/core/llm_params.py local routing branches."""

import os
import sys
import importlib.util
from pathlib import Path

# Ensure imports work when running tests from repo root.
_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

_LLM_PARAMS_PATH = _ROOT_DIR / "agent" / "core" / "llm_params.py"
_SPEC = importlib.util.spec_from_file_location("_test_llm_params_module", _LLM_PARAMS_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_resolve_llm_params = _MODULE._resolve_llm_params


def test_resolve_ollama_params_from_env():
    old_base = os.environ.get("OLLAMA_BASE_URL")
    old_key = os.environ.get("OLLAMA_API_KEY")
    try:
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["OLLAMA_API_KEY"] = "sk-local"

        params = _resolve_llm_params("ollama/llama3.1")

        assert params["model"] == "openai/llama3.1"
        assert params["api_base"] == "http://localhost:11434/v1"
        assert params["api_key"] == "sk-local"
        assert "timeout" not in params
    finally:
        if old_base is None:
            os.environ.pop("OLLAMA_BASE_URL", None)
        else:
            os.environ["OLLAMA_BASE_URL"] = old_base
        if old_key is None:
            os.environ.pop("OLLAMA_API_KEY", None)
        else:
            os.environ["OLLAMA_API_KEY"] = old_key


def test_resolve_llamacpp_params_defaults():
    old_base = os.environ.get("LLAMACPP_BASE_URL")
    old_key = os.environ.get("LLAMACPP_API_KEY")
    try:
        os.environ.pop("LLAMACPP_BASE_URL", None)
        os.environ.pop("LLAMACPP_API_KEY", None)

        params = _resolve_llm_params("llamacpp/unsloth/Qwen3.5-2B")

        assert params["model"] == "openai/unsloth/Qwen3.5-2B"
        assert params["api_base"] == "http://localhost:8001/v1"
        assert params["api_key"] == "sk-no-key-required"
        assert "timeout" not in params
    finally:
        if old_base is None:
            os.environ.pop("LLAMACPP_BASE_URL", None)
        else:
            os.environ["LLAMACPP_BASE_URL"] = old_base
        if old_key is None:
            os.environ.pop("LLAMACPP_API_KEY", None)
        else:
            os.environ["LLAMACPP_API_KEY"] = old_key


def test_resolve_vllm_params_from_env():
    old_base = os.environ.get("VLLM_BASE_URL")
    old_key = os.environ.get("VLLM_API_KEY")
    try:
        os.environ["VLLM_BASE_URL"] = "http://127.0.0.1:8000/"
        os.environ["VLLM_API_KEY"] = "token"

        params = _resolve_llm_params("vllm/Qwen/Qwen3-4B")

        assert params["model"] == "openai/Qwen/Qwen3-4B"
        assert params["api_base"] == "http://127.0.0.1:8000/v1"
        assert params["api_key"] == "token"
        assert "timeout" not in params
    finally:
        if old_base is None:
            os.environ.pop("VLLM_BASE_URL", None)
        else:
            os.environ["VLLM_BASE_URL"] = old_base
        if old_key is None:
            os.environ.pop("VLLM_API_KEY", None)
        else:
            os.environ["VLLM_API_KEY"] = old_key


def test_resolve_generic_local_params_trims_trailing_slash():
    old_base = os.environ.get("LOCAL_LLM_BASE_URL")
    try:
        os.environ["LOCAL_LLM_BASE_URL"] = "http://127.0.0.1:9000/"

        params = _resolve_llm_params("local://my-model")

        assert params["model"] == "openai/my-model"
        assert params["api_base"] == "http://127.0.0.1:9000/v1"
    finally:
        if old_base is None:
            os.environ.pop("LOCAL_LLM_BASE_URL", None)
        else:
            os.environ["LOCAL_LLM_BASE_URL"] = old_base
