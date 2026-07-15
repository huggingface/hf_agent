"""LiteLLM kwargs resolution for provider-aware model ids."""

import os

from agent.core.hf_tokens import resolve_hf_router_token
from agent.core.local_models import (
    LOCAL_MODEL_API_KEY_DEFAULT,
    LOCAL_MODEL_API_KEY_ENV,
    LOCAL_MODEL_BASE_URL_ENV,
    local_model_provider,
)
from agent.core.model_routing import ModelProvider, resolve_model_route


def _resolve_hf_router_token(session_hf_token: str | None = None) -> str | None:
    """Backward-compatible private wrapper used by tests and older imports."""
    return resolve_hf_router_token(session_hf_token)


_HF_EFFORTS = {"low", "medium", "high"}
_OPENAI_EFFORTS = {"minimal", "low", "medium", "high"}


def _hf_router_effort_level(reasoning_effort: str) -> str:
    return "low" if reasoning_effort == "minimal" else reasoning_effort


class UnsupportedEffortError(ValueError):
    """The requested effort isn't valid for this provider's API surface."""


def _local_api_base(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def _resolve_local_model_params(
    model_name: str, reasoning_effort: str | None = None, strict: bool = False
) -> dict:
    if reasoning_effort and strict:
        raise UnsupportedEffortError(
            "Local OpenAI-compatible endpoints don't accept reasoning_effort"
        )
    route = resolve_model_route(model_name)
    provider = local_model_provider(route.configured_id)
    if provider is None:
        raise ValueError(f"Unsupported local model id: {model_name}")
    raw_base = (
        os.environ.get(provider["base_url_env"])
        or os.environ.get(LOCAL_MODEL_BASE_URL_ENV)
        or provider["base_url_default"]
    )
    api_key = (
        os.environ.get(provider["api_key_env"])
        or os.environ.get(LOCAL_MODEL_API_KEY_ENV)
        or LOCAL_MODEL_API_KEY_DEFAULT
    )
    return {
        "model": route.litellm_model,
        "api_base": _local_api_base(raw_base),
        "api_key": api_key,
    }


def _openrouter_headers() -> dict[str, str]:
    headers = {}
    referer = os.environ.get("OPENROUTER_SITE_URL") or os.environ.get("OR_SITE_URL")
    title = os.environ.get("OPENROUTER_APP_NAME") or os.environ.get("OR_APP_NAME")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title
    return headers


def _resolve_llm_params(
    model_name: str,
    session_hf_token: str | None = None,
    reasoning_effort: str | None = None,
    strict: bool = False,
) -> dict:
    """Build LiteLLM kwargs for a configured model id without destructive prefix stripping."""
    route = resolve_model_route(model_name)

    if route.is_local_provider:
        return _resolve_local_model_params(
            route.configured_id, reasoning_effort, strict
        )

    params = {"model": route.litellm_model}

    if route.provider is ModelProvider.HUGGINGFACE:
        params.update(
            {
                "api_base": route.api_base,
                "api_key": _resolve_hf_router_token(session_hf_token),
            }
        )
        if reasoning_effort:
            hf_level = _hf_router_effort_level(reasoning_effort)
            if hf_level not in _HF_EFFORTS:
                if strict:
                    raise UnsupportedEffortError(
                        f"HF Router doesn't accept effort={hf_level!r}"
                    )
            else:
                params["extra_body"] = {"reasoning_effort": hf_level}
        return params

    if route.provider is ModelProvider.OPENAI and reasoning_effort:
        if reasoning_effort not in _OPENAI_EFFORTS:
            if strict:
                raise UnsupportedEffortError(
                    f"OpenAI doesn't accept effort={reasoning_effort!r}"
                )
        else:
            params["reasoning_effort"] = reasoning_effort

    if route.provider is ModelProvider.OPENROUTER:
        headers = _openrouter_headers()
        if headers:
            params["extra_headers"] = headers

    # Moonshot/Kimi, Gemini, Vertex, and OpenRouter credentials are read by LiteLLM
    # from their native environment variables. Do not attach HF Router state.
    return params
