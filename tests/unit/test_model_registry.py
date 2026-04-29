import sys
from pathlib import Path


_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from routes.agent import AVAILABLE_MODELS  # noqa: E402


def test_deepseek_v4_pro_is_available_as_free_hf_model():
    model = next(
        (
            candidate
            for candidate in AVAILABLE_MODELS
            if candidate["id"] == "deepseek-ai/DeepSeek-V4-Pro:deepinfra"
        ),
        None,
    )

    assert model == {
        "id": "deepseek-ai/DeepSeek-V4-Pro:deepinfra",
        "label": "DeepSeek V4 Pro",
        "provider": "huggingface",
        "tier": "free",
    }
