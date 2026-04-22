"""LiteLLM kwargs resolution for the model ids this agent accepts.

Kept separate from ``agent_loop`` so tools (research, context compaction, etc.)
can import it without pulling in the whole agent loop / tool router and
creating circular imports.
"""

from agent.core.provider_adapters import ADAPTERS


def _resolve_llm_params(
    model_name: str,
    session_hf_token: str | None = None,
    reasoning_effort: str | None = None,
) -> dict:
    """
    Build LiteLLM kwargs for a given model id.

    • ``anthropic/<model>`` / ``openai/<model>`` — passed straight through; the
      user's own ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY`` env vars are picked
      up by LiteLLM. ``reasoning_effort`` is forwarded as a top-level param
      (GPT-5 / o-series accept "minimal" | "low" | "medium" | "high"; Claude
      extended-thinking models accept "low" | "medium" | "high" and LiteLLM
      translates to the thinking config).

    • Anything else is treated as a HuggingFace router id. We hit the
      auto-routing OpenAI-compatible endpoint at
      ``https://router.huggingface.co/v1``, which bypasses LiteLLM's stale
      per-provider HF adapter entirely. The id can be bare or carry an HF
      routing suffix:

          MiniMaxAI/MiniMax-M2.7              # auto = fastest + failover
          MiniMaxAI/MiniMax-M2.7:cheapest
          moonshotai/Kimi-K2.6:novita         # pin a specific provider

      A leading ``huggingface/`` is stripped for convenience. ``reasoning_effort``
      is forwarded via ``extra_body`` (LiteLLM's OpenAI adapter refuses it as a
      top-level kwarg for non-OpenAI models). "minimal" is normalized to "low".

    Token precedence (first non-empty wins):
      1. INFERENCE_TOKEN env — shared key on the hosted Space (inference is
         free for users, billed to the Space owner via ``X-HF-Bill-To``).
      2. session.hf_token — the user's own token (CLI / OAuth / cache file).
      3. HF_TOKEN env — belt-and-suspenders fallback for CLI users.
    """
    for adapter in ADAPTERS:
        if adapter.matches(model_name):
            return adapter.build_params(
                model_name,
                session_hf_token=session_hf_token,
                reasoning_effort=reasoning_effort,
            )

    raise ValueError(f"Unsupported model id: {model_name}")
