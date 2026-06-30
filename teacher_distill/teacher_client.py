from __future__ import annotations

import asyncio
import json
from typing import Any

from litellm import acompletion

from agent.core.llm_params import _resolve_llm_params
from teacher_distill.prompts import build_teacher_messages
from teacher_distill.schemas import CodingTask, TeacherTrajectory


DEFAULT_TEACHER_MODEL = "github_copilot/claude-opus-4.8"


def _message_text(response: Any) -> str:
    choice = response.choices[0]
    content = choice.message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return str(content)


def parse_teacher_response(
    task_id: str, teacher_model: str, raw: str
) -> TeacherTrajectory:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Teacher response must be valid JSON") from exc
    return TeacherTrajectory(
        task_id=task_id,
        teacher_model=teacher_model,
        rationale=str(payload["rationale"]).strip(),
        solution=str(payload["solution"]).strip(),
    )


async def generate_teacher_trajectory(
    task: CodingTask,
    teacher_model: str = DEFAULT_TEACHER_MODEL,
    timeout_seconds: float = 120.0,
) -> TeacherTrajectory:
    params = _resolve_llm_params(teacher_model, session_hf_token=None)
    response = await asyncio.wait_for(
        acompletion(
            messages=build_teacher_messages(task),
            temperature=0.2,
            max_tokens=4096,
            stream=False,
            **params,
        ),
        timeout=timeout_seconds,
    )
    return parse_teacher_response(task.task_id, teacher_model, _message_text(response))
