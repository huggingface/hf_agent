"""OpenCode model router.

OpenCode exposes an OpenAI-compatible API at ``https://opencode.ai/zen/go/v1``.
Model ids in this agent use the ``opencode/<id>`` prefix; the router strips
that prefix and sends the bare model id to the configured OpenCode base URL.

The router can fetch the live model list from ``/v1/models`` so the CLI and
backend can validate switches and show available models without hard-coding
the catalog.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_API_BASE = "https://opencode.ai/zen/go/v1"
_CACHE_TTL_SECONDS = 300
_HTTP_TIMEOUT_SECONDS = 5.0

_models_cache: Optional[list[str]] = None
_cache_time: float = 0.0

# Curated models shown in the CLI / backend.  The full live list is fetched
# on demand from the OpenCode ``/v1/models`` endpoint.
SUGGESTED_MODELS = [
    {"id": "opencode/kimi-k2.7-code", "label": "Kimi K2.7", "recommended": True},
    {"id": "opencode/kimi-k2.6", "label": "Kimi K2.6"},
    {"id": "opencode/glm-5.2", "label": "GLM 5.2"},
    {"id": "opencode/minimax-m3", "label": "MiniMax M3"},
    {"id": "opencode/deepseek-v4-pro", "label": "DeepSeek V4 Pro"},
    {"id": "opencode/qwen3.7-max", "label": "Qwen 3.7 Max"},
]


def get_api_base() -> str:
    """Return the OpenCode API base URL.

    Precedence:
      1. ``OPENAI_API_BASE`` env var (OpenCode is currently consumed through
         the OpenAI-compatible endpoint).
      2. ``OPENCODE_API_BASE`` env var.
      3. Default ``https://opencode.ai/zen/go/v1``.
    """
    return (
        os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OPENCODE_API_BASE")
        or _DEFAULT_API_BASE
    )


def get_api_key() -> str | None:
    """Return the OpenCode API key.

    Precedence:
      1. ``OPENAI_API_KEY`` env var.
      2. ``OPENCODE_API_KEY`` env var.
    """
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENCODE_API_KEY")


def is_opencode_model_id(model_id: str) -> bool:
    """Whether ``model_id`` is scoped to the OpenCode router."""
    return model_id.startswith("opencode/")


def normalize_model_id(model_id: str) -> str:
    """Strip the ``opencode/`` prefix and any routing tag.

    ``opencode/kimi-k2.7-code:fastest`` becomes ``kimi-k2.7-code``.
    """
    return model_id.removeprefix("opencode/").split(":", 1)[0]


def _models_url() -> str:
    base = get_api_base().rstrip("/")
    return f"{base}/models"


def fetch_models(force: bool = False) -> list[str]:
    """Fetch and cache the live OpenCode model list.

    Returns a sorted list of bare model ids.  On failure returns stale cached
    data if available, otherwise an empty list.
    """
    global _models_cache, _cache_time

    now = time.time()
    if (
        not force
        and _models_cache is not None
        and now - _cache_time < _CACHE_TTL_SECONDS
    ):
        return _models_cache

    try:
        resp = httpx.get(_models_url(), timeout=_HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        models = sorted(
            m["id"] for m in data.get("data", []) if isinstance(m, dict) and m.get("id")
        )
        _models_cache = models
        _cache_time = now
        logger.debug("Fetched %d OpenCode models", len(models))
    except Exception as e:
        logger.warning("Failed to fetch OpenCode model list: %s", e)
        if _models_cache is None:
            _models_cache = []
            _cache_time = now

    return _models_cache or []


def prewarm() -> None:
    """Warm the OpenCode model cache in the background.  Swallows failures."""
    try:
        fetch_models(force=False)
    except Exception:
        pass


def is_valid_opencode_model(model_id: str) -> bool:
    """Validate that ``model_id`` is present in the OpenCode model list."""
    bare = normalize_model_id(model_id)
    return bare in fetch_models()


def fuzzy_suggest(model_id: str, limit: int = 3) -> list[str]:
    """Return the closest OpenCode model ids to ``model_id``."""
    from difflib import get_close_matches

    bare = normalize_model_id(model_id)
    return get_close_matches(bare, fetch_models(), n=limit, cutoff=0.4)
