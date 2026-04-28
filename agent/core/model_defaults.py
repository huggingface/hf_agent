"""Model-specific defaults shared by CLI and web sessions."""

MODEL_REASONING_EFFORT_DEFAULTS = {
    # Product selector entry is intentionally the high-reasoning variant.
    "openai/gpt-5.5": "high",
    "gemini/gemini-3.1-pro-preview": "high",
}


def preferred_reasoning_effort(
    model_name: str,
    requested_effort: str | None,
) -> str | None:
    """Apply model defaults when the user left effort at the global maximum.

    ``max`` is a cross-provider preference meaning "use the strongest sensible
    reasoning level." Some providers either do not accept that literal value
    or expose a stronger level than we want in the product selector, so these
    model entries cap the default without overriding explicit user choices.
    """
    if requested_effort == "max":
        return MODEL_REASONING_EFFORT_DEFAULTS.get(model_name, requested_effort)
    return requested_effort
