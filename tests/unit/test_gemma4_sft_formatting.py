import json

from teacher_distill.prompts import format_student_answer, format_student_message
from teacher_distill.schemas import CodingTask, TeacherTrajectory, VerifiedTrajectory


def test_student_format_uses_gemma_thought_channel():
    verified = VerifiedTrajectory(
        task=CodingTask(
            task_id="taco:1",
            source="BAAI/TACO",
            split="train",
            prompt="Read n and print n.",
            starter_code="",
            input_output=json.dumps({"inputs": ["1\n"], "outputs": ["1\n"]}),
        ),
        trajectory=TeacherTrajectory(
            task_id="taco:1",
            teacher_model="github_copilot/claude-opus-4.8",
            rationale="Read the full input and echo it because this is identity.",
            solution="import sys\nprint(sys.stdin.read().strip())",
        ),
        passed=True,
        tests_run=1,
    )

    user = format_student_message(verified)
    assistant = format_student_answer(verified)

    assert user["role"] == "user"
    assert assistant["role"] == "assistant"
    assert "<|channel>thought" in assistant["content"]
    assert "```python" in assistant["content"]
