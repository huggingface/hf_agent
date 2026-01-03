"""
Interactive CLI chat with the agent
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import litellm
from lmnr import Laminar, LaminarLiteLLMCallback

from agent.config import load_config
from agent.core.agent_loop import submission_loop
from agent.core.session import OpType
from agent.core.tools import ToolRouter
from agent.utils.terminal_display import (
    format_error,
    format_header,
    format_plan_display,
    format_separator,
    format_success,
    format_tool_call,
    format_tool_output,
    format_turn_complete,
)

litellm.drop_params = True


def _safe_get_args(arguments: dict) -> dict:
    """Safely extract args dict from arguments, handling cases where LLM passes string."""
    args = arguments.get("args", {})
    # Sometimes LLM passes args as string instead of dict
    if isinstance(args, str):
        return {}
    return args if isinstance(args, dict) else {}


lmnr_api_key = os.environ.get("LMNR_API_KEY")
if lmnr_api_key:
    try:
        Laminar.initialize(project_api_key=lmnr_api_key)
        litellm.callbacks = [LaminarLiteLLMCallback()]
        print("Laminar initialized")
    except Exception as e:
        print(f"Failed to initialize Laminar: {e}")


@dataclass
class Operation:
    """Operation to be executed by the agent"""

    op_type: OpType
    data: Optional[dict[str, Any]] = None


@dataclass
class Submission:
    """Submission to the agent loop"""

    id: str
    operation: Operation


async def event_listener(
    event_queue: asyncio.Queue,
    submission_queue: asyncio.Queue,
    turn_complete_event: asyncio.Event,
    ready_event: asyncio.Event,
) -> None:
    """Background task that listens for events and displays them"""
    submission_id = [1000]  # Use list to make it mutable in closure
    last_tool_name = [None]  # Track last tool called

    while True:
        try:
            event = await event_queue.get()

            # Display event
            if event.event_type == "ready":
                print(format_success("\U0001f917 Agent ready"))
                ready_event.set()
            elif event.event_type == "assistant_message":
                content = event.data.get("content", "") if event.data else ""
                if content:
                    print(f"\nAssistant: {content}")
            elif event.event_type == "tool_call":
                tool_name = event.data.get("tool", "") if event.data else ""
                arguments = event.data.get("arguments", {}) if event.data else {}
                if tool_name:
                    last_tool_name[0] = tool_name  # Store for tool_output event
                    args_str = json.dumps(arguments)[:100] + "..."
                    print(format_tool_call(tool_name, args_str))
            elif event.event_type == "tool_output":
                output = event.data.get("output", "") if event.data else ""
                success = event.data.get("success", False) if event.data else False
                if output:
                    # Don't truncate plan_tool output, truncate everything else
                    should_truncate = last_tool_name[0] != "plan_tool"
                    print(format_tool_output(output, success, truncate=should_truncate))
            elif event.event_type == "turn_complete":
                print(format_turn_complete())
                # Display plan after turn complete
                plan_display = format_plan_display()
                if plan_display:
                    print(plan_display)
                turn_complete_event.set()
            elif event.event_type == "error":
                error = (
                    event.data.get("error", "Unknown error")
                    if event.data
                    else "Unknown error"
                )
                print(format_error(error))
                turn_complete_event.set()
            elif event.event_type == "shutdown":
                print("Agent shutdown")
                break
            elif event.event_type == "processing":
                print("Processing...", flush=True)
            elif event.event_type == "compacted":
                old_tokens = event.data.get("old_tokens", 0) if event.data else 0
                new_tokens = event.data.get("new_tokens", 0) if event.data else 0
                print(f"Compacted context: {old_tokens} → {new_tokens} tokens")
            elif event.event_type == "approval_required":
                # Display job details and prompt for approval
                tool_name = event.data.get("tool", "") if event.data else ""
                arguments = event.data.get("arguments", {}) if event.data else {}

                operation = arguments.get("operation", "")
                args = _safe_get_args(arguments)

                print(f"\nOperation: {operation}")

                if operation == "uv":
                    script = args.get("script", "")
                    dependencies = args.get("dependencies", [])
                    print(f"Script to run:\n{script}")
                    if dependencies:
                        print(f"Dependencies: {', '.join(dependencies)}")
                elif operation == "run":
                    image = args.get("image", "")
                    command = args.get("command", "")
                    print(f"Docker image: {image}")
                    print(f"Command: {command}")

                    # Common parameters
                    flavor = args.get("flavor", "cpu-basic")
                    detached = args.get("detached", False)
                    print(f"Hardware: {flavor}")
                    print(f"Detached mode: {detached}")

                    secrets = args.get("secrets", [])
                    if secrets:
                        print(f"Secrets: {', '.join(secrets)}")
                elif operation in ["create_repo", "upload_file"]:
                    repo_id = args.get("repo_id", "")
                    repo_type = args.get("repo_type", "dataset")

                    # Build repo URL
                    type_path = "" if repo_type == "model" else f"{repo_type}s"
                    repo_url = f"https://huggingface.co/{type_path}/{repo_id}".replace("//", "/")

                    print(f"Repository: {repo_id}")
                    print(f"Type: {repo_type}")
                    print(f"Private: Yes")
                    print(f"URL: {repo_url}")

                    # Show file preview for upload_file operation
                    if operation == "upload_file":
                        path_in_repo = args.get("path_in_repo", "")
                        file_content = args.get("file_content", "")
                        print(f"File: {path_in_repo}")

                        if isinstance(file_content, str):
                            # Calculate metrics
                            all_lines = file_content.split('\n')
                            line_count = len(all_lines)
                            size_bytes = len(file_content.encode('utf-8'))
                            size_kb = size_bytes / 1024
                            size_mb = size_kb / 1024

                            print(f"Line count: {line_count}")
                            if size_kb < 1024:
                                print(f"Size: {size_kb:.2f} KB")
                            else:
                                print(f"Size: {size_mb:.2f} MB")

                            # Show preview
                            preview_lines = all_lines[:5]
                            preview = '\n'.join(preview_lines)
                            print(f"Content preview (first 5 lines):\n{preview}")
                            if len(all_lines) > 5:
                                print("...")

                # Get user decision
                print("\n" + format_separator())
                if tool_name == "hf_jobs":
                    header_text = "JOB EXECUTION APPROVAL REQUIRED"
                elif operation == "upload_file":
                    header_text = "FILE UPLOAD APPROVAL REQUIRED"
                else:
                    header_text = "REPO CREATION APPROVAL REQUIRED"
                print(format_header(header_text))
                print(format_separator())
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    input,
                    "Approve? (y=yes, n=no, or provide feedback to reject): ",
                )

                response = response.strip()
                approved = response.lower() in ["y", "yes"]
                feedback = (
                    None if approved or response.lower() in ["n", "no"] else response
                )

                # Submit approval
                submission_id[0] += 1
                approval_submission = Submission(
                    id=f"approval_{submission_id[0]}",
                    operation=Operation(
                        op_type=OpType.EXEC_APPROVAL,
                        data={"approved": approved, "feedback": feedback},
                    ),
                )
                await submission_queue.put(approval_submission)
                print(format_separator() + "\n")
            # Silently ignore other events

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Event listener error: {e}")


async def get_user_input() -> str:
    """Get user input asynchronously"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, "You: ")


async def main():
    """Interactive chat with the agent"""
    from agent.utils.terminal_display import Colors

    # Clear screen
    os.system("clear" if os.name != "nt" else "cls")

    banner = r"""
  _   _                   _               _____                   _                    _   
 | | | |_   _  __ _  __ _(_)_ __   __ _  |  ___|_ _  ___ ___     / \   __ _  ___ _ __ | |_ 
 | |_| | | | |/ _` |/ _` | | '_ \ / _` | | |_ / _` |/ __/ _ \   / _ \ / _` |/ _ \ '_ \| __|
 |  _  | |_| | (_| | (_| | | | | | (_| | |  _| (_| | (_|  __/  / ___ \ (_| |  __/ | | | |_ 
 |_| |_|\__,_|\__, |\__, |_|_| |_|\__, | |_|  \__,_|\___\___| /_/   \_\__, |\___|_| |_|\__|
              |___/ |___/         |___/                               |___/
    """

    print(format_separator())
    print(f"{Colors.YELLOW} {banner}{Colors.RESET}")
    print("Type your messages below. Type 'exit', 'quit', or '/quit' to end.\n")
    print(format_separator())

    # Create queues for communication
    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    # Events to signal agent state
    turn_complete_event = asyncio.Event()
    turn_complete_event.set()
    ready_event = asyncio.Event()

    # Start agent loop in background
    config_path = Path(__file__).parent.parent / "configs" / "main_agent_config.json"
    config = load_config(config_path)

    # Create tool router
    print(f"Config: {config.mcpServers}")
    tool_router = ToolRouter(config.mcpServers)

    agent_task = asyncio.create_task(
        submission_loop(
            submission_queue,
            event_queue,
            config=config,
            tool_router=tool_router,
        )
    )

    # Start event listener in background
    listener_task = asyncio.create_task(
        event_listener(event_queue, submission_queue, turn_complete_event, ready_event)
    )

    # Wait for agent to initialize
    print("Initializing agent...")
    await ready_event.wait()

    submission_id = 0

    try:
        while True:
            # Wait for previous turn to complete
            await turn_complete_event.wait()
            turn_complete_event.clear()

            # Get user input
            try:
                user_input = await get_user_input()
            except EOFError:
                break

            # Check for exit commands
            if user_input.strip().lower() in ["exit", "quit", "/quit", "/exit"]:
                break

            # Skip empty input
            if not user_input.strip():
                turn_complete_event.set()
                continue

            # Submit to agent
            submission_id += 1
            submission = Submission(
                id=f"sub_{submission_id}",
                operation=Operation(
                    op_type=OpType.USER_INPUT, data={"text": user_input}
                ),
            )
            print(f"Main submitting: {submission.operation.op_type}")
            await submission_queue.put(submission)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    # Shutdown
    print("\n🛑 Shutting down agent...")
    shutdown_submission = Submission(
        id="sub_shutdown", operation=Operation(op_type=OpType.SHUTDOWN)
    )
    await submission_queue.put(shutdown_submission)

    # Wait for tasks to complete
    await asyncio.wait_for(agent_task, timeout=2.0)
    listener_task.cancel()

    print("✨ Goodbye!\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✨ Goodbye!")
