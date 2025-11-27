"""
Utilities for logging solver scores to a Hugging Face dataset.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download

AVERAGE_RE = re.compile(r"Average normalized score:\s*([0-9.]+)")
DEFAULT_FILENAME = "records.jsonl"


def _hydra_join(*parts: str | None) -> str:
    tokens = [str(part).strip().replace(" ", "_") for part in parts if part]
    return "/".join(tokens) if tokens else "default"


def detect_agent_version(config_path: str = "agent/config_mcp_example.json") -> str:
    """
    Returns a short string identifying the current agent version:
    <git short sha>-<config hash>.
    """

    try:
        commit = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode()
            .strip()
        )
    except Exception:
        commit = "unknown"

    config_file = Path(config_path)
    config_stem = config_file.stem or "config"
    parent_name = config_file.parent.name if config_file.parent.name else None
    return _hydra_join(parent_name, config_stem, commit)


def parse_average_score(text: str) -> float | None:
    """Extracts the 'Average normalized score' value from Inspect logs."""

    match = AVERAGE_RE.search(text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def latest_log_file(
    log_dir: Path, extensions: tuple[str, ...] = (".eval", ".json")
) -> Path | None:
    """Returns the most recent log file in log_dir matching the provided extensions."""

    if not log_dir.exists():
        return None

    files: list[Path] = []
    for ext in extensions:
        files.extend(log_dir.glob(f"*{ext}"))

    if not files:
        return None

    files.sort(key=lambda path: path.stat().st_mtime)
    return files[-1]


@dataclass
class LeaderboardClient:
    """Simple helper to append JSONL rows to a HF dataset."""

    repo_id: str
    token: str
    filename: str = DEFAULT_FILENAME

    def append_record(self, record: dict[str, Any]) -> None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="leaderboard_"))
        local_file = tmp_dir / self.filename

        self._download_existing(local_file)
        if not local_file.exists():
            local_file.write_text("", encoding="utf-8")

        with local_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        HfApi(token=self.token).upload_file(
            path_or_fileobj=str(local_file),
            path_in_repo=self.filename,
            repo_id=self.repo_id,
            repo_type="dataset",
        )

        try:
            local_file.unlink()
            tmp_dir.rmdir()
        except OSError:
            pass

    def _download_existing(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            downloaded = hf_hub_download(
                repo_id=self.repo_id,
                filename=self.filename,
                repo_type="dataset",
                token=self.token,
            )
            shutil.copy(Path(downloaded), destination)
        except Exception:
            destination.write_text("", encoding="utf-8")


def build_record(
    solver_name: str,
    solver_kwargs: dict[str, Any],
    dataset_name: str,
    dataset_split: str,
    limit: int | None,
    score: float,
    command: list[str],
    log_path: Path | None,
    criterion_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assembles a JSON-serialisable record for the leaderboard dataset."""

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "solver": solver_name,
        "solver_kwargs": solver_kwargs,
        "dataset_name": dataset_name,
        "dataset_split": dataset_split,
        "limit": limit,
        "score": score,
        "command": command,
    }

    if solver_name == "hf_agent":
        record["solver_version"] = detect_agent_version(
            solver_kwargs.get("config_path", "agent/config_mcp_example.json")
        )
    else:
        version_spec = solver_kwargs.get("version")
        if isinstance(version_spec, (list, tuple)):
            record["solver_version"] = _hydra_join(*version_spec)
        elif isinstance(version_spec, dict):
            record["solver_version"] = _hydra_join(
                *[f"{k}={v}" for k, v in version_spec.items()]
            )
        elif isinstance(version_spec, str):
            record["solver_version"] = version_spec
        else:
            record["solver_version"] = _hydra_join(solver_name, "default")

    if log_path:
        record["log_artifact"] = str(log_path)
    record["criterion_checks"] = criterion_checks or []

    return record
