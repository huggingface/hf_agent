"""
Inspect AI task definition that runs the existing agent and reuses the rubric scorer.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, hf_dataset
from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver._task_state import TaskState
import litellm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.rubric_eval import RubricData, evaluate_with_rubrics  # noqa: E402
from eval.solvers import get_solver  # noqa: E402


def _record_to_sample(record: dict[str, Any]) -> Sample:
    rubric_payload = json.loads(record["rubric"])
    rubrics = rubric_payload.get("rubrics", [])

    metadata = {
        "question": record["question"],
        "discussion_title": record.get("discussion_title"),
        "discussion_url": record.get("discussion_url"),
        "rubric_title": rubric_payload.get("title"),
        "rubric_description": rubric_payload.get("description"),
        "rubrics": rubrics,
    }

    return Sample(
        input=record["question"],
        target=record["solution"],
        id=record.get("discussion_topic_id"),
        metadata=metadata,
    )


def _load_dataset(dataset_name: str, split: str, limit: int | None) -> Sequence[Sample]:
    return hf_dataset(
        dataset_name, sample_fields=_record_to_sample, split=split, limit=limit
    )


def _metadata_to_rubrics(metadata: dict[str, Any]) -> list[RubricData]:
    raw_rubrics = metadata.get("rubrics", [])
    return [RubricData(**rubric) for rubric in raw_rubrics]


@scorer(metrics=[mean()], name="rubric_scorer")
def rubric_scorer(judge_model: str = "gpt-5-mini"):
    async def score(state: TaskState, target: Target) -> Score:
        response_text = state.output.completion or state.output.message.text
        question = state.metadata.get("question", state.input_text)
        rubrics = _metadata_to_rubrics(state.metadata)

        evaluation = await asyncio.to_thread(
            evaluate_with_rubrics,
            question,
            response_text,
            rubrics,
            judge_model,
        )

        score_metadata = {
            "raw_score": evaluation.raw_score,
            "criterion_checks": [
                check.model_dump() for check in evaluation.criterion_checks
            ],
            "discussion_title": state.metadata.get("discussion_title"),
            "discussion_url": state.metadata.get("discussion_url"),
            "reference_answer": target.text,
        }

        return Score(
            value=evaluation.normalized_score,
            answer=response_text,
            explanation=f"Normalized score {evaluation.normalized_score:.3f}",
            metadata=score_metadata,
        )

    return score


@task(name="hf-benchmark-with-rubrics")
def hf_benchmark_with_rubrics(
    solver_name: str = "hf_agent",
    solver_kwargs: dict[str, Any] = {
        "max_iterations": 10,
        "config_path": "agent/config_mcp_example.json",
    },
    dataset_name: str = "akseljoonas/hf-agent-rubrics@train",
    limit: int | None = None,
    judge_model: str = "gpt-5-mini",
) -> Task:
    litellm.drop_params = True
    if "@" not in dataset_name:
        raise ValueError("Dataset name must be in the format 'author/dataset@split'")
    dataset_name, dataset_split = dataset_name.split("@")
    dataset = _load_dataset(dataset_name, dataset_split, limit=limit)

    return Task(
        dataset=dataset,
        solver=get_solver(solver_name, **solver_kwargs),
        scorer=rubric_scorer(judge_model=judge_model),
        metadata={
            "dataset_name": dataset_name,
            "dataset_split": dataset_split,
            "solver_name": solver_name,
            "judge_model": judge_model,
        },
    )
