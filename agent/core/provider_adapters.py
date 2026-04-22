"""Provider-specific LiteLLM parameter builders."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ProviderAdapter:
    """Build LiteLLM kwargs for one family of model ids."""

    def matches(self, model_name: str) -> bool:
        raise NotImplementedError

    def build_params(
        self,
        model_name: str,
        session_hf_token: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class NativeAdapter(ProviderAdapter):
    prefixes: tuple[str, ...] = ("anthropic/", "openai/")

    def matches(self, model_name: str) -> bool:
        return model_name.startswith(self.prefixes)

    def build_params(
        self,
        model_name: str,
        session_hf_token: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict:
        del session_hf_token
        params: dict = {"model": model_name}
        if reasoning_effort:
            params["reasoning_effort"] = reasoning_effort
        return params


@dataclass(frozen=True)
class HfRouterAdapter(ProviderAdapter):
    allowed_efforts: tuple[str, ...] = ("low", "medium", "high")

    def matches(self, model_name: str) -> bool:
        return "/" in model_name and not model_name.startswith(
            ("anthropic/", "openai/")
        )

    def build_params(
        self,
        model_name: str,
        session_hf_token: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict:
        hf_model = model_name.removeprefix("huggingface/")
        inference_token = os.environ.get("INFERENCE_TOKEN")
        api_key = inference_token or session_hf_token or os.environ.get("HF_TOKEN")
        params = {
            "model": f"openai/{hf_model}",
            "api_base": "https://router.huggingface.co/v1",
            "api_key": api_key,
        }
        if inference_token:
            params["extra_headers"] = {"X-HF-Bill-To": "huggingface"}
        if reasoning_effort:
            hf_level = "low" if reasoning_effort == "minimal" else reasoning_effort
            if hf_level in self.allowed_efforts:
                params["extra_body"] = {"reasoning_effort": hf_level}
        return params


ADAPTERS: tuple[ProviderAdapter, ...] = (
    NativeAdapter(),
    HfRouterAdapter(),
)
