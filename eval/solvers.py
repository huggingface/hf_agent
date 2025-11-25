"""
Collection of Inspect AI solvers used by the rubric task.
"""

from __future__ import annotations

import asyncio
import json
from typing import Callable, Dict, List, Sequence

from inspect_ai.model import ChatMessageAssistant, ModelOutput
from inspect_ai.solver import Solver, solver
from inspect_ai.solver._task_state import TaskState

from eval.hf_agent_connector import AgentResponseGenerator


async def _run_subprocess(command: Sequence[str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(command)} failed with code {process.returncode}:\n"
            f"{stderr.decode().strip()}"
        )
    return stdout.decode().strip()


@solver(name="hf_agent_solver")
def hf_agent_solver(
    config_path: str = "agent/config_mcp_example.json",
    max_iterations: int = 10,
) -> Solver:
    runner = AgentResponseGenerator(
        config_path=config_path,
        max_iterations=max_iterations,
    )

    async def solve(state: TaskState, generate) -> TaskState:
        response = await runner.run(state.input_text)
        assistant_message = ChatMessageAssistant(
            content=response,
            model=runner.model_name,
            source="generate",
        )
        state.messages.append(assistant_message)
        state.output = ModelOutput.from_message(assistant_message)
        state.completed = True
        return state

    return solve


@solver(name="claude_code")
def claude_code(
    output_format: str = "json",
    mcp_config: str | None = None,
) -> Solver:
    if output_format not in {"text", "json", "stream-json"}:
        raise ValueError("output_format must be one of: text, json, stream-json")

    async def solve(state: TaskState, generate) -> TaskState:
        prompt = state.input_text

        cmd: List[str] = ["claude", "-p", prompt, "--output-format", output_format]
        if mcp_config:
            cmd += ["--mcp-config", mcp_config]

        stdout = await _run_subprocess(cmd)
        response_text = stdout
        session_id = None

        if output_format in {"json", "stream-json"}:
            # stream-json may emit multiple JSON objects; take the last complete line
            candidate_line = stdout.strip().splitlines()[-1]
            try:
                payload = json.loads(candidate_line)
                response_text = (
                    payload.get("result") or payload.get("message", "") or stdout
                )
                session_id = payload.get("session_id")
            except (json.JSONDecodeError, AttributeError):
                response_text = stdout

        assistant_message = ChatMessageAssistant(
            content=response_text,
            model="claude-code",
            source="generate",
            metadata={"session_id": session_id} if session_id else None,
        )
        state.messages.append(assistant_message)
        state.output = ModelOutput.from_message(assistant_message)
        state.completed = True
        return state

    return solve


SOLVER_REGISTRY: Dict[str, Callable[..., Solver]] = {
    "hf_agent_solver": hf_agent_solver,
    "claude_code": claude_code,
}


def get_solver(name: str, **kwargs) -> Solver:
    try:
        factory = SOLVER_REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(SOLVER_REGISTRY))
        raise ValueError(f"Unknown solver '{name}'. Available: {available}") from exc

    return factory(**kwargs)
