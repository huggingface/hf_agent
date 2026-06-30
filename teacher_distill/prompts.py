from __future__ import annotations

from teacher_distill.schemas import CodingTask, VerifiedTrajectory


def build_teacher_messages(task: CodingTask) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You generate training data for a code model. Return only valid JSON. "
                "Provide a public solution rationale and final Python solution. "
                "Do not claim to expose hidden chain-of-thought or private model internals."
            ),
        },
        {
            "role": "user",
            "content": (
                "Solve this Python programming task.\n\n"
                f"Task id: {task.task_id}\n"
                f"Difficulty: {task.difficulty}\n\n"
                f"Prompt:\n{task.prompt}\n\n"
                f"Starter code:\n{task.starter_code or '(none)'}\n\n"
                "Return JSON with exactly these keys:\n"
                '{"rationale": "public solution rationale", "solution": "complete Python code"}'
            ),
        },
    ]


def format_student_message(verified: VerifiedTrajectory) -> dict[str, str]:
    task = verified.task
    return {
        "role": "user",
        "content": (
            "Write a correct Python solution for the following task.\n\n"
            f"{task.prompt}\n\n"
            f"Starter code:\n{task.starter_code or '(none)'}"
        ),
    }


def format_student_answer(verified: VerifiedTrajectory) -> dict[str, str]:
    rationale = verified.trajectory.rationale.strip()
    solution = verified.trajectory.solution.strip()
    return {
        "role": "assistant",
        "content": (
            f"<|channel>thought\n{rationale}\n<channel|>\n```python\n{solution}\n```"
        ),
    }
