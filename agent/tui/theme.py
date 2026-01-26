"""
Custom Textual theme for HuggingFace Agent TUI

Note: Textual themes don't support 'transparent' as a color value.
To get transparent backgrounds, we handle it in CSS with explicit overrides.
"""

from textual.theme import Theme

hf_transparent_theme = Theme(
    name="hf-transparent",
    primary="#FFD21E",        # HF Yellow
    secondary="#98C379",      # Green
    accent="#56B6C2",         # Cyan
    foreground="#ABB2BF",     # Light gray text
    background="#00000000",   # Transparent black (alpha=0)
    surface="#00000000",      # Transparent
    panel="#00000000",        # Transparent
    success="#98C379",        # Green
    warning="#EBCB8B",        # Yellow-orange
    error="#E06C75",          # Red
    dark=True,
    variables={
        # Override specific variables
        "block-cursor-foreground": "#000000",
        "block-cursor-background": "#FFD21E",
        "input-selection-background": "#FFD21E 30%",
        "scrollbar": "#5C6370",
        "scrollbar-background": "#00000000",  # Transparent
        "scrollbar-hover": "#B8960F",
        "scrollbar-active": "#FFD21E",
        "footer-background": "#00000000",  # Transparent
        "border": "#FFD21E",
        "border-blurred": "#5C6370",
    },
)
