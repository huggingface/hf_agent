from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def build_commands(
    model: str,
    tensor_parallel_size: int,
    run_bigcodebench: bool,
) -> list[list[str]]:
    commands: list[list[str]] = []
    for dataset in ["humaneval", "mbpp"]:
        commands.append(
            [
                "evalplus.evaluate",
                "--model",
                model,
                "--dataset",
                dataset,
                "--backend",
                "vllm",
                "--tp",
                str(tensor_parallel_size),
                "--greedy",
            ]
        )

    if run_bigcodebench:
        for split in ["instruct", "complete"]:
            commands.append(
                [
                    "bigcodebench.evaluate",
                    "--model",
                    model,
                    "--execution",
                    "gradio",
                    "--split",
                    split,
                    "--subset",
                    "hard",
                    "--backend",
                    "vllm",
                ]
            )
    return commands


def run_command(command: list[str], cwd: Path) -> None:
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def write_manifest(output: Path, model: str, run_bigcodebench: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "model": model,
                "evalplus": ["humaneval", "mbpp"],
                "bigcodebench": ["instruct-hard", "complete-hard"]
                if run_bigcodebench
                else [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tp", type=int, default=4)
    parser.add_argument("--run-bigcodebench", action="store_true")
    args = parser.parse_args()

    repo = Path.cwd()
    args.output.mkdir(parents=True, exist_ok=True)

    for command in build_commands(
        model=args.model,
        tensor_parallel_size=args.tp,
        run_bigcodebench=args.run_bigcodebench,
    ):
        run_command(command, cwd=repo)

    write_manifest(args.output, args.model, args.run_bigcodebench)


if __name__ == "__main__":
    main()
