import json
from pathlib import Path

STATE_PATH = Path.home() / ".cache" / "ml-intern" / "state.json"


def save_last_model(model_name: str) -> None:
    """Persist the last successfully used model name."""
    _update_state({"last_model": model_name})


def get_last_model() -> str | None:
    """Retrieve the last used model name."""
    return _get_state().get("last_model")


def add_persisted_model(model_id: str, label: str) -> None:
    """Add a model to the persistent suggested models list."""
    state = _get_state()
    models = state.get("added_models", [])
    if not any(m["id"] == model_id for m in models):
        models.append({"id": model_id, "label": label})
        _update_state({"added_models": models})


def get_persisted_models() -> list[dict[str, str]]:
    """Retrieve the list of manually added models."""
    return _get_state().get("added_models", [])


def _get_state() -> dict:
    try:
        if STATE_PATH.exists():
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _update_state(updates: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state = _get_state()
        state.update(updates)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass
