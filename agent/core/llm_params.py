"""LiteLLM kwargs resolution for the model ids this agent accepts.

Kept separate from ``agent_loop`` so tools (research, context compaction, etc.)
can import it without pulling in the whole agent loop / tool router and
creating circular imports.

Provider-specific logic (Anthropic thinking config, OpenAI reasoning_effort,
HF router extra_body) lives in ``provider_adapters.py``.  This module is the
stable import surface for ``effort_probe`` and ``agent_loop``.
"""

from agent.core.provider_adapters import (
    UnsupportedEffortError,
    resolve_adapter,
)

# Re-export so existing ``from agent.core.llm_params import
# UnsupportedEffortError`` in effort_probe.py keeps working.
__all__ = ["UnsupportedEffortError", "_resolve_llm_params"]


def _patch_litellm_effort_validation() -> None:
    """Neuter LiteLLM 1.83's hardcoded effort-level validation.

    Context: at ``litellm/llms/anthropic/chat/transformation.py:~1443`` the
    Anthropic adapter validates ``output_config.effort ∈ {high, medium,
    low, max}`` and gates ``max`` behind an ``_is_opus_4_6_model`` check
    that only matches the substring ``opus-4-6`` / ``opus_4_6``. Result:

    * ``xhigh`` — valid on Anthropic's real API for Claude 4.7 — is
      rejected pre-flight with "Invalid effort value: xhigh".
    * ``max`` on Opus 4.7 is rejected with "effort='max' is only supported
      by Claude Opus 4.6", even though Opus 4.7 accepts it in practice.

    We don't want to maintain a parallel model table, so we let the
    Anthropic API itself be the validator: widen ``_is_opus_4_6_model``
    to also match ``opus-4-7``+ families, and drop the valid-effort-set
    check entirely. If Anthropic rejects an effort level, we see a 400
    and the cascade walks down — exactly the behavior we want for any
    future model family.

    Removable once litellm ships 1.83.8-stable (which merges PR #25867,
    "Litellm day 0 opus 4.7 support") — see commit 0868a82 on their main
    branch. Until then, this one-time patch is the escape hatch.
    """
    try:
        from litellm.llms.anthropic.chat import transformation as _t
    except Exception:
        return

    cfg = getattr(_t, "AnthropicConfig", None)
    if cfg is None:
        return

    original = getattr(cfg, "_is_opus_4_6_model", None)
    if original is None or getattr(original, "_hf_agent_patched", False):
        return

    def _widened(model: str) -> bool:
        m = model.lower()
        # Original 4.6 match plus any future Opus >= 4.6. We only need this
        # to return True for families where "max" / "xhigh" are acceptable
        # at the API; the cascade handles the case when they're not.
        return any(
            v in m for v in (
                "opus-4-6", "opus_4_6", "opus-4.6", "opus_4.6",
                "opus-4-7", "opus_4_7", "opus-4.7", "opus_4.7",
            )
        )

    _widened._hf_agent_patched = True  # type: ignore[attr-defined]
    cfg._is_opus_4_6_model = staticmethod(_widened)


_patch_litellm_effort_validation()


def _resolve_llm_params(
    model_name: str,
    session_hf_token: str | None = None,
    reasoning_effort: str | None = None,
    strict: bool = False,
) -> dict:
    """Build LiteLLM kwargs for a given model id.

    Delegates to the matching provider adapter.  See ``provider_adapters.py``
    for the per-provider logic (Anthropic thinking config, OpenAI
    reasoning_effort, HF router extra_body, etc.).

    ``strict=True`` raises ``UnsupportedEffortError`` when the requested
    effort isn't in the provider's accepted set, instead of silently
    dropping it. The probe cascade uses strict mode so it can walk down
    (``max`` → ``xhigh`` → ``high`` …) without making an API call. Regular
    runtime callers leave ``strict=False``, so a stale cached effort
    can't crash a turn — it just doesn't get sent.

    Token precedence (first non-empty wins):
      1. INFERENCE_TOKEN env — shared key on the hosted Space (inference is
         free for users, billed to the Space owner via ``X-HF-Bill-To``).
      2. session.hf_token — the user's own token (CLI / OAuth / cache file).
      3. HF_TOKEN env — belt-and-suspenders fallback for CLI users.
    """
    adapter = resolve_adapter(model_name)
    if adapter is None:
        raise ValueError(f"Unsupported model id: {model_name}")
    return adapter.build_params(
        model_name,
        session_hf_token=session_hf_token,
        reasoning_effort=reasoning_effort,
        strict=strict,
    )
