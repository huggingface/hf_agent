from __future__ import annotations

import argparse
import asyncio
from importlib import import_module
from typing import Any

from huggingface_hub import get_token


BUILD_SCRIPT = r"""
import subprocess, sys
subprocess.run([sys.executable, "scripts/build_gemma4_distill_dataset.py", "--output", "{output}", "--taco-limit", "{taco_limit}", "--apps-limit", "{apps_limit}", "--max-verified", "{max_verified}", "--concurrency", "{concurrency}"], check=True)
"""

TRAIN_SCRIPT = r"""
import subprocess, sys
subprocess.run([sys.executable, "scripts/train_gemma4_sft_lora.py", "--dataset", "{dataset}", "--output_dir", "{output_dir}", "--model", "google/gemma-4-12B-it"], check=True)
"""

EVAL_SCRIPT = r"""
import subprocess, sys
subprocess.run([sys.executable, "scripts/eval_gemma4_public_benchmarks.py", "--model", "{model}", "--output", "{output}", "--tp", "4"], check=True)
"""


def resolve_azure_aml_handler():
    try:
        module = import_module("agent.tools.azure_aml_tool")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "agent.tools.azure_aml_tool is required to submit AML jobs. "
            "Merge or install the Azure ML tool before running this command."
        ) from exc
    return module.azure_aml_handler


def build_job_config(args: argparse.Namespace, hf_token: str) -> dict[str, Any]:
    env_vars = {"HF_TOKEN": hf_token}
    if args.teacher_model:
        env_vars["TEACHER_MODEL"] = args.teacher_model

    if args.command == "build":
        script = BUILD_SCRIPT.format(
            output=args.output,
            taco_limit=args.taco_limit,
            apps_limit=args.apps_limit,
            max_verified=args.max_verified,
            concurrency=args.concurrency,
        )
        display_name = "gemma4-claude48-build-data"
        timeout = 12
    elif args.command == "train-smoke":
        script = TRAIN_SCRIPT.format(
            dataset=args.dataset, output_dir="${{outputs.output_path}}"
        )
        display_name = "gemma4-claude48-train-smoke"
        timeout = 4
    elif args.command == "eval":
        script = EVAL_SCRIPT.format(
            model=args.model, output="${{outputs.output_path}}/eval"
        )
        display_name = "gemma4-claude48-eval"
        timeout = 8
    else:
        raise ValueError(args.command)

    return {
        "operation": "run",
        "compute": "a100x4",
        "pip_packages": ".[eval,train]",
        "timeout_hours": timeout,
        "display_name": display_name,
        "num_gpus": 4,
        "env_vars": env_vars,
        "script": script,
    }


async def submit(args: argparse.Namespace) -> None:
    azure_aml_handler = resolve_azure_aml_handler()
    result = await azure_aml_handler(build_job_config(args, hf_token=get_token() or ""))
    print(result)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument(
        "--output", default="${{outputs.output_path}}/gemma4-distill.jsonl"
    )
    build.add_argument("--taco-limit", type=int, default=5000)
    build.add_argument("--apps-limit", type=int, default=5000)
    build.add_argument("--max-verified", type=int, default=5000)
    build.add_argument("--concurrency", type=int, default=2)
    build.add_argument("--teacher-model", default="github_copilot/claude-opus-4.8")

    train = sub.add_parser("train-smoke")
    train.add_argument("--dataset", required=True)
    train.add_argument("--teacher-model", default="")

    eval_parser = sub.add_parser("eval")
    eval_parser.add_argument("--model", required=True)
    eval_parser.add_argument("--teacher-model", default="")

    return parser.parse_args(argv)


def main() -> None:
    asyncio.run(submit(parse_args()))


if __name__ == "__main__":
    main()
