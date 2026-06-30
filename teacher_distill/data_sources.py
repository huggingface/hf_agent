from __future__ import annotations

import hashlib
from collections.abc import Iterable

from datasets import load_dataset

from teacher_distill.schemas import CodingTask


def normalize_taco_row(row: dict, index: int) -> CodingTask:
    return CodingTask(
        task_id=f"taco:{index}",
        source="BAAI/TACO",
        split="train",
        prompt=str(row["question"]).strip(),
        starter_code=str(row.get("starter_code") or ""),
        input_output=str(row["input_output"]),
        difficulty=str(row.get("difficulty") or "unknown"),
    )


def normalize_apps_row(row: dict, index: int) -> CodingTask:
    return CodingTask(
        task_id=f"apps:{index}",
        source="codeparrot/apps",
        split="train",
        prompt=str(row["question"]).strip(),
        starter_code=str(row.get("starter_code") or ""),
        input_output=str(row["input_output"]),
        difficulty=str(row.get("difficulty") or "unknown"),
    )


def _prompt_key(task: CodingTask) -> str:
    body = f"{task.source}\n{task.prompt}\n{task.starter_code}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def dedupe_tasks(tasks: Iterable[CodingTask]) -> list[CodingTask]:
    seen: set[str] = set()
    result: list[CodingTask] = []
    for task in tasks:
        key = _prompt_key(task)
        if key in seen:
            continue
        seen.add(key)
        result.append(task)
    return result


def load_taco_tasks(limit: int | None = None) -> list[CodingTask]:
    ds = load_dataset("BAAI/TACO", "ALL", split="train")
    rows = ds if limit is None else ds.select(range(min(limit, len(ds))))
    return [normalize_taco_row(row, i) for i, row in enumerate(rows)]


def load_apps_tasks(limit: int | None = None) -> list[CodingTask]:
    ds = load_dataset("codeparrot/apps", split="train")
    rows = ds if limit is None else ds.select(range(min(limit, len(ds))))
    return [normalize_apps_row(row, i) for i, row in enumerate(rows)]


def load_training_tasks(taco_limit: int, apps_limit: int) -> list[CodingTask]:
    return dedupe_tasks([*load_taco_tasks(taco_limit), *load_apps_tasks(apps_limit)])
