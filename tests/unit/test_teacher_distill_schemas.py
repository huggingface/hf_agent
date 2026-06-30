import json

import pytest
from pydantic import ValidationError

from teacher_distill.schemas import CodingTask, TeacherTrajectory, VerifiedTrajectory


def test_coding_task_requires_public_train_source():
    task = CodingTask(
        task_id="taco:123",
        source="BAAI/TACO",
        split="train",
        prompt="Write solve().",
        starter_code="",
        input_output=json.dumps({"inputs": ["1\n"], "outputs": ["1\n"]}),
        difficulty="easy",
    )

    assert task.task_id == "taco:123"
    assert task.benchmark_safe is True


def test_coding_task_rejects_eval_split():
    with pytest.raises(ValidationError, match="Only train split"):
        CodingTask(
            task_id="humaneval:0",
            source="evalplus/humanevalplus",
            split="test",
            prompt="def add(a, b):",
            starter_code="",
            input_output="{}",
            difficulty="eval",
        )


def test_verified_trajectory_round_trip():
    task = CodingTask(
        task_id="apps:1",
        source="codeparrot/apps",
        split="train",
        prompt="Return x.",
        starter_code="",
        input_output=json.dumps({"inputs": ["2\n"], "outputs": ["2\n"]}),
        difficulty="introductory",
    )
    trajectory = TeacherTrajectory(
        task_id="apps:1",
        teacher_model="github_copilot/claude-opus-4.8",
        rationale="Use the input directly because the task asks for identity.",
        solution="import sys\nprint(sys.stdin.read().strip())\n",
    )
    verified = VerifiedTrajectory(
        task=task,
        trajectory=trajectory,
        passed=True,
        tests_run=1,
        stderr_tail="",
    )

    dumped = verified.model_dump_json()
    loaded = VerifiedTrajectory.model_validate_json(dumped)
    assert loaded.task.task_id == "apps:1"
    assert loaded.trajectory.solution.startswith("import sys")
