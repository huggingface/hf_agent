import logging

from agent.core.model_routing import ModelProvider, resolve_model_route


def test_huggingface_prefixed_route_preserves_suffix():
    route = resolve_model_route("huggingface/zai-org/GLM-5.2:novita")

    assert route.provider is ModelProvider.HUGGINGFACE
    assert route.configured_id == "huggingface/zai-org/GLM-5.2:novita"
    assert route.provider_model_id == "zai-org/GLM-5.2:novita"
    assert route.litellm_model == "openai/zai-org/GLM-5.2:novita"
    assert route.requires_hf_token
    assert route.uses_hf_catalog


def test_unprefixed_hf_fallback_warns(caplog):
    caplog.set_level(logging.WARNING)
    route = resolve_model_route("zai-org/GLM-5.2:novita")

    assert route.provider is ModelProvider.HUGGINGFACE
    assert route.deprecated_unprefixed_hf
    assert "deprecated" in caplog.text


def test_openai_is_direct_not_hf_org():
    route = resolve_model_route("openai/gpt-5.5")

    assert route.provider is ModelProvider.OPENAI
    assert route.litellm_model == "openai/gpt-5.5"
    assert route.is_direct_provider
    assert not route.requires_hf_token


def test_openai_responses_is_preserved():
    route = resolve_model_route("openai/responses/gpt-5.6")

    assert route.provider is ModelProvider.OPENAI
    assert route.litellm_model == "openai/responses/gpt-5.6"


def test_direct_provider_routes():
    assert (
        resolve_model_route("openrouter/anthropic/claude-sonnet-4").provider
        is ModelProvider.OPENROUTER
    )
    assert resolve_model_route(
        "moonshot/kimi-k2.7-code-highspeed"
    ).supports_reasoning_replay
    assert resolve_model_route("gemini/gemini-2.5-pro").provider is ModelProvider.GEMINI
    assert (
        resolve_model_route("vertex_ai/gemini-2.5-pro").provider
        is ModelProvider.VERTEX_AI
    )
