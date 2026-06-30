import json

import pytest

from teacher_distill.prompts import build_teacher_messages
from teacher_distill.schemas import CodingTask
from teacher_distill.teacher_client import parse_teacher_response


def sample_task() -> CodingTask:
    return CodingTask(
        task_id="taco:1",
        source="BAAI/TACO",
        split="train",
        prompt="Read an integer and print it.",
        starter_code="",
        input_output=json.dumps({"inputs": ["5\n"], "outputs": ["5\n"]}),
        difficulty="easy",
    )


def test_teacher_prompt_requests_public_rationale_not_hidden_cot():
    messages = build_teacher_messages(sample_task())
    joined = "\n".join(str(m["content"]) for m in messages)

    assert "public solution rationale" in joined
    assert "Do not claim to expose hidden chain-of-thought" in joined
    assert "JSON" in joined


def test_parse_teacher_response_accepts_json_object():
    raw = json.dumps(
        {
            "rationale": "The task is identity, so read stdin and print it unchanged.",
            "solution": "import sys\nprint(sys.stdin.read().strip())\n",
        }
    )

    trajectory = parse_teacher_response("taco:1", "github_copilot/claude-opus-4.8", raw)

    assert trajectory.task_id == "taco:1"
    assert trajectory.teacher_model == "github_copilot/claude-opus-4.8"
    assert trajectory.solution.startswith("import sys")


def test_parse_teacher_response_rejects_non_json():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_teacher_response("taco:1", "github_copilot/claude-opus-4.8", "not json")
