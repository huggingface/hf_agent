from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from teacher_distill.schemas import (
    CodingTask,
    TeacherTrajectory,
    VerificationResult,
    VerifiedTrajectory,
)


def _normalize_output(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _load_io_cases(task: CodingTask) -> list[tuple[str, str]]:
    payload = json.loads(task.input_output or "{}")
    inputs = payload.get("inputs") or []
    outputs = payload.get("outputs") or []
    return [
        (str(stdin), str(stdout))
        for stdin, stdout in zip(inputs, outputs, strict=False)
    ]


def verify_solution(
    task: CodingTask,
    solution: str,
    timeout_seconds: int = 10,
) -> VerificationResult:
    cases = _load_io_cases(task)
    if not cases:
        return VerificationResult(
            passed=False, tests_run=0, stderr_tail="No stdin/stdout tests found"
        )

    with tempfile.TemporaryDirectory(prefix="teacher_distill_") as tmp:
        script = Path(tmp) / "solution.py"
        script.write_text(solution, encoding="utf-8")
        for index, (stdin_text, expected) in enumerate(cases, start=1):
            proc = subprocess.run(
                [sys.executable, str(script)],
                input=stdin_text,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            actual = _normalize_output(proc.stdout)
            want = _normalize_output(expected)
            if proc.returncode != 0:
                return VerificationResult(
                    passed=False,
                    tests_run=index,
                    stderr_tail=proc.stderr[-1000:],
                )
            if actual != want:
                return VerificationResult(
                    passed=False,
                    tests_run=index,
                    stderr_tail=f"expected {want!r}, got {actual!r}",
                )
    return VerificationResult(passed=True, tests_run=len(cases), stderr_tail="")


def verify_trajectory(
    task: CodingTask,
    trajectory: TeacherTrajectory,
    timeout_seconds: int = 10,
) -> VerifiedTrajectory:
    result = verify_solution(task, trajectory.solution, timeout_seconds)
    return VerifiedTrajectory(
        task=task,
        trajectory=trajectory,
        passed=result.passed,
        tests_run=result.tests_run,
        stderr_tail=result.stderr_tail,
    )
