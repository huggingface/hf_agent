import json

from teacher_distill.schemas import CodingTask, TeacherTrajectory
from teacher_distill.verifier import verify_trajectory


def make_task() -> CodingTask:
    return CodingTask(
        task_id="apps:identity",
        source="codeparrot/apps",
        split="train",
        prompt="Read stdin and print it unchanged.",
        starter_code="",
        input_output=json.dumps({"inputs": ["abc\n"], "outputs": ["abc\n"]}),
        difficulty="introductory",
    )


def test_verifier_passes_stdout_task():
    trajectory = TeacherTrajectory(
        task_id="apps:identity",
        teacher_model="github_copilot/claude-opus-4.8",
        rationale="Identity task: echo stdin.",
        solution="import sys\nprint(sys.stdin.read().strip())\n",
    )

    result = verify_trajectory(make_task(), trajectory, timeout_seconds=3)

    assert result.passed is True
    assert result.tests_run == 1


def test_verifier_fails_wrong_output():
    trajectory = TeacherTrajectory(
        task_id="apps:identity",
        teacher_model="github_copilot/claude-opus-4.8",
        rationale="Wrong solution prints a constant.",
        solution="print('wrong')\n",
    )

    result = verify_trajectory(make_task(), trajectory, timeout_seconds=3)

    assert result.passed is False
    assert result.tests_run == 1
    assert "expected" in result.stderr_tail.lower()
