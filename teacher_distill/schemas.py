from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CodingTask(BaseModel):
    task_id: str
    source: str
    split: str
    prompt: str
    starter_code: str = ""
    input_output: str
    difficulty: str = "unknown"
    benchmark_safe: bool = True

    @field_validator("split")
    @classmethod
    def require_train_split(cls, value: str) -> str:
        if value != "train":
            raise ValueError(
                "Only train split tasks may enter the distillation dataset"
            )
        return value

    @field_validator("source")
    @classmethod
    def reject_public_eval_sources(cls, value: str) -> str:
        blocked = {
            "evalplus/humanevalplus",
            "evalplus/mbppplus",
            "bigcode/bigcodebench",
        }
        if value in blocked:
            raise ValueError(f"{value} is reserved for evaluation only")
        return value


class TeacherTrajectory(BaseModel):
    task_id: str
    teacher_model: str
    rationale: str = Field(min_length=20)
    solution: str = Field(min_length=10)


class VerificationResult(BaseModel):
    passed: bool
    tests_run: int
    stderr_tail: str = ""


class VerifiedTrajectory(BaseModel):
    task: CodingTask
    trajectory: TeacherTrajectory
    passed: bool
    tests_run: int
    stderr_tail: str = ""
