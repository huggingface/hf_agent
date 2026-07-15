"""Provider-aware model routing for LiteLLM-backed inference."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from agent.core.local_models import (
    is_reserved_local_model_id,
    local_model_name,
    local_model_provider,
)
from agent.core.model_ids import HF_ROUTER_BASE_URL

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    MOONSHOT = "moonshot"
    GEMINI = "gemini"
    VERTEX_AI = "vertex_ai"
    OLLAMA = "ollama"
    VLLM = "vllm"
    LM_STUDIO = "lm_studio"
    LLAMACPP = "llamacpp"


DIRECT_PROVIDERS = {
    ModelProvider.OPENAI,
    ModelProvider.OPENROUTER,
    ModelProvider.MOONSHOT,
    ModelProvider.GEMINI,
    ModelProvider.VERTEX_AI,
}
LOCAL_PROVIDERS = {
    ModelProvider.OLLAMA,
    ModelProvider.VLLM,
    ModelProvider.LM_STUDIO,
    ModelProvider.LLAMACPP,
}


@dataclass(frozen=True)
class ModelRoute:
    """Resolved provider route for an external model id."""

    provider: ModelProvider
    configured_id: str
    provider_model_id: str
    deprecated_unprefixed_hf: bool = False

    @property
    def requires_hf_token(self) -> bool:
        return self.provider is ModelProvider.HUGGINGFACE

    @property
    def uses_hf_catalog(self) -> bool:
        return self.provider is ModelProvider.HUGGINGFACE

    @property
    def is_direct_provider(self) -> bool:
        return self.provider in DIRECT_PROVIDERS

    @property
    def is_local_provider(self) -> bool:
        return self.provider in LOCAL_PROVIDERS

    @property
    def supports_reasoning_replay(self) -> bool:
        return self.provider is ModelProvider.MOONSHOT

    @property
    def hf_router_model(self) -> str | None:
        if self.provider is ModelProvider.HUGGINGFACE:
            return self.provider_model_id
        return None

    @property
    def litellm_model(self) -> str:
        if self.provider is ModelProvider.HUGGINGFACE:
            return f"openai/{self.provider_model_id}"
        if self.is_local_provider:
            return f"openai/{self.provider_model_id}"
        return self.configured_id

    @property
    def api_base(self) -> str | None:
        if self.provider is ModelProvider.HUGGINGFACE:
            return HF_ROUTER_BASE_URL
        return None


_PROVIDER_PREFIXES = {
    "huggingface/": ModelProvider.HUGGINGFACE,
    "openai/": ModelProvider.OPENAI,
    "openrouter/": ModelProvider.OPENROUTER,
    "moonshot/": ModelProvider.MOONSHOT,
    "gemini/": ModelProvider.GEMINI,
    "vertex_ai/": ModelProvider.VERTEX_AI,
    "ollama/": ModelProvider.OLLAMA,
    "vllm/": ModelProvider.VLLM,
    "lm_studio/": ModelProvider.LM_STUDIO,
    "llamacpp/": ModelProvider.LLAMACPP,
}


def resolve_model_route(model_id: str) -> ModelRoute:
    """Resolve an externally configured model id into a provider route.

    Bare ``org/model[:tag]`` ids are retained as a backward-compatible HF Router
    route, but callers should prefer explicit ``huggingface/org/model[:tag]``.
    """
    model_id = (model_id or "").strip()
    if any(char.isspace() for char in model_id):
        raise ValueError(f"Unsupported model id: {model_id}")
    if not model_id:
        raise ValueError("model_id must not be empty")
    if is_reserved_local_model_id(model_id):
        raise ValueError(f"Unsupported local model id: {model_id}")

    for prefix, provider in _PROVIDER_PREFIXES.items():
        if model_id.startswith(prefix):
            provider_model_id = model_id[len(prefix) :]
            if not provider_model_id:
                if provider in LOCAL_PROVIDERS:
                    raise ValueError(f"Unsupported local model id: {model_id}")
                raise ValueError(f"Model id {model_id!r} is missing a model name")
            if provider in LOCAL_PROVIDERS:
                if (
                    local_model_provider(model_id) is None
                    or local_model_name(model_id) is None
                ):
                    raise ValueError(f"Unsupported local model id: {model_id}")
            return ModelRoute(provider, model_id, provider_model_id)

    if "/" not in model_id or model_id.startswith("openai-"):
        raise ValueError(f"Unsupported model id: {model_id}")

    logger.warning(
        "Unprefixed HF Router model id %r is deprecated; use 'huggingface/%s' instead.",
        model_id,
        model_id,
    )
    return ModelRoute(
        ModelProvider.HUGGINGFACE,
        model_id,
        model_id,
        deprecated_unprefixed_hf=True,
    )
