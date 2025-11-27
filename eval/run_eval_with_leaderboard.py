from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from leaderboard import LeaderboardClient, build_record, latest_log_file

load_dotenv()


def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print(f"[leaderboard] running: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)


def build_inspect_command(args: argparse.Namespace) -> list[str]:
    cmd = []
    cmd.extend(args.inspect_launch)
    cmd.append(args.inspect_task)

    def add_task_arg(key: str, value: Any) -> None:
        if value is None:
            return
        cmd.extend(["-T", f"{key}={value}"])

    add_task_arg("solver_name", args.solver_name)
    add_task_arg("solver_kwargs", json.dumps(args.solver_kwargs))
    add_task_arg("dataset_name", args.dataset)
    if args.limit is not None:
        add_task_arg("limit", args.limit)

    cmd.extend(["--log-dir", args.log_dir])
    if args.log_format:
        cmd.extend(["--log-format", args.log_format])

    if args.extra_inspect_args:
        cmd.extend(args.extra_inspect_args)

    return cmd


def parse_score_from_outputs(log_dir: Path) -> tuple[float, Path, list[dict[str, Any]]]:
    log_path = latest_log_file(log_dir)
    if not log_path:
        raise RuntimeError("Inspect log file not found.")

    # Sanitization
    content = log_path.read_text(encoding="utf-8")
    # Regex to match hf_ followed by 34 alphanumeric chars
    sanitized_content = re.sub(r"hf_[a-zA-Z0-9]{34}", "<REDACTED_TOKEN>", content)

    if content != sanitized_content:
        log_path.write_text(sanitized_content, encoding="utf-8")
        print(f"[leaderboard] Redacted HF tokens in {log_path}")
        content = sanitized_content

    data = json.loads(content)
    results = data.get("results", {})
    scores = results.get("scores", [])
    score_value = None
    criterion_checks: list[dict[str, Any]] = []

    for score_entry in scores:
        metrics = score_entry.get("metrics", {})
        for metric in metrics.values():
            value = metric.get("value")
            if isinstance(value, (int, float)):
                score_value = float(value)
                break
        if score_value is not None:
            break

    if score_value is None:
        raise RuntimeError("Could not find a numeric metric value in the Inspect log.")

    for sample in data.get("samples", []):
        # Grab the question from metadata (fallback to input)
        question = "Unknown Question"
        if "metadata" in sample and "question" in sample["metadata"]:
            question = sample["metadata"]["question"]
        elif "input" in sample:
            question = sample["input"]

        # Check if any scorer produced criterion_checks
        for scorer in sample.get("scores", {}).values():
            metadata = scorer.get("metadata") or {}
            checks = metadata.get("criterion_checks")

            if isinstance(checks, list) and checks:
                # Create a grouped entry for this question/sample
                grouped_entry = {"question": question, "checks": []}
                for check in checks:
                    if isinstance(check, dict):
                        grouped_entry["checks"].append(check)

                if grouped_entry["checks"]:
                    criterion_checks.append(grouped_entry)

    return score_value, log_path, criterion_checks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Inspect eval and append the resulting score to a HF dataset."
    )
    parser.add_argument(
        "--hf-dataset",
        default="akseljoonas/hf-agent-leaderboard",
        help="HF dataset repo id for the leaderboard (e.g. user/leaderboard).",
    )

    parser.add_argument(
        "--solver-name",
        required=True,
        help="Solver name used in the Inspect task (e.g. hf_agent).",
    )
    parser.add_argument(
        "--solver-kwargs",
        type=json.loads,
        default="{}",
        help="JSON string with solver kwargs passed to the Inspect task.",
    )
    parser.add_argument(
        "--dataset",
        default="akseljoonas/hf-agent-rubrics@train",
        help="Dataset spec in the form author/dataset@split.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional sample limit passed to Inspect.",
    )
    parser.add_argument(
        "--inspect-task",
        default="eval/task.py@hf-benchmark-with-rubrics",
        help="Inspect task reference.",
    )
    parser.add_argument(
        "--inspect-launch",
        nargs="+",
        default=["uv", "run", "inspect", "eval"],
        help="Command used to invoke Inspect (default: uv run inspect eval).",
    )
    parser.add_argument(
        "--log-dir",
        default="logs/leaderboard",
        help="Directory where Inspect outputs .eval logs.",
    )
    parser.add_argument(
        "--extra-inspect-args",
        nargs="*",
        help="Additional args forwarded to Inspect after the standard task arguments.",
    )
    parser.add_argument(
        "--log-format",
        default="json",
        help="Log format passed to Inspect (default: json).",
    )

    args = parser.parse_args()

    if isinstance(args.solver_kwargs, str):
        args.solver_kwargs = json.loads(args.solver_kwargs or "{}")

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("ERROR: set HF_TOKEN in your environment.", file=sys.stderr)
        sys.exit(1)

    if "@" not in args.dataset:
        raise ValueError("Dataset must be in the format 'author/dataset@split'.")
    dataset_name, dataset_split = args.dataset.split("@", 1)

    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    inspect_cmd = build_inspect_command(args)
    result = run_command(inspect_cmd)

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)

    score, log_path, criterion_checks = parse_score_from_outputs(log_dir)

    client = LeaderboardClient(repo_id=args.hf_dataset, token=hf_token)
    record = build_record(
        solver_name=args.solver_name,
        solver_kwargs=args.solver_kwargs,
        dataset_name=dataset_name,
        dataset_split=dataset_split,
        limit=args.limit,
        score=score,
        command=inspect_cmd,
        log_path=log_path,
        criterion_checks=criterion_checks,
    )
    client.append_record(record)

    print(
        f"[leaderboard] recorded score {score:.3f} for solver '{args.solver_name}' to {args.hf_dataset}"
    )


if __name__ == "__main__":
    main()
