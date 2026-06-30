from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from teacher_distill.data_sources import load_training_tasks
from teacher_distill.jsonl import append_jsonl, read_seen_task_ids
from teacher_distill.teacher_client import (
    DEFAULT_TEACHER_MODEL,
    generate_teacher_trajectory,
)
from teacher_distill.verifier import verify_trajectory


async def process_task(task, args, semaphore: asyncio.Semaphore):
    async with semaphore:
        trajectory = await generate_teacher_trajectory(
            task,
            teacher_model=args.teacher_model,
            timeout_seconds=args.teacher_timeout,
        )
        return verify_trajectory(task, trajectory, timeout_seconds=args.verify_timeout)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--teacher-model", default=DEFAULT_TEACHER_MODEL)
    parser.add_argument("--taco-limit", type=int, default=5000)
    parser.add_argument("--apps-limit", type=int, default=5000)
    parser.add_argument("--max-verified", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--teacher-timeout", type=float, default=120.0)
    parser.add_argument("--verify-timeout", type=int, default=10)
    args = parser.parse_args()

    tasks = load_training_tasks(taco_limit=args.taco_limit, apps_limit=args.apps_limit)
    seen = read_seen_task_ids(args.output)
    pending = [task for task in tasks if task.task_id not in seen]
    semaphore = asyncio.Semaphore(args.concurrency)
    verified_count = 0

    for task in pending:
        if verified_count >= args.max_verified:
            break
        try:
            verified = await process_task(task, args, semaphore)
        except Exception as exc:
            append_jsonl(
                args.output.with_suffix(".errors.jsonl"),
                {"task_id": task.task_id, "error": repr(exc)},
            )
            continue
        if verified.passed:
            append_jsonl(args.output, verified.model_dump(mode="json"))
            verified_count += 1
        else:
            append_jsonl(
                args.output.with_suffix(".failed.jsonl"),
                verified.model_dump(mode="json"),
            )
        print(
            f"verified={verified_count} task={task.task_id} passed={verified.passed}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
