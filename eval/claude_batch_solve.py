import asyncio
import json
import os
import threading
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from dotenv import load_dotenv

load_dotenv()

# Thread-safe file writing
file_lock = threading.Lock()


def convert_message_to_chat_format(message: Any) -> dict | None:
    """Convert SDK message to standard chat format with role/content/tool_calls."""

    if isinstance(message, SystemMessage):
        # Extract tools list from init data for system message
        if message.subtype == "init":
            tools = message.data.get("tools", [])
            tools_desc = "\n".join(f"- {tool}" for tool in tools)
            return {
                "role": "system",
                "content": f"You are a helpful assistant with access to the following tools:\n{tools_desc}",
            }
        return None

    elif isinstance(message, AssistantMessage):
        text_content = ""
        tool_calls = []

        for block in message.content:
            if isinstance(block, TextBlock):
                text_content += block.text
            elif isinstance(block, ToolUseBlock):
                tool_calls.append(
                    {
                        "id": block.id,
                        "function": {
                            "name": block.name,
                            "arguments": block.input,
                        },
                    }
                )

        result = {"role": "assistant", "content": text_content}
        if tool_calls:
            result["tool_calls"] = tool_calls
        return result

    elif isinstance(message, UserMessage):
        # UserMessage can contain tool results or text
        if isinstance(message.content, str):
            return {"role": "user", "content": message.content}
        elif isinstance(message.content, list):
            # Check for tool results
            tool_results = []
            text_content = ""
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    # Format tool result content
                    if isinstance(block.content, str):
                        content = block.content
                    elif isinstance(block.content, list):
                        content = json.dumps(block.content)
                    else:
                        content = str(block.content) if block.content else ""

                    tool_results.append(
                        {
                            "tool_use_id": block.tool_use_id,
                            "content": content,
                            "is_error": block.is_error,
                        }
                    )
                elif isinstance(block, TextBlock):
                    text_content += block.text

            if tool_results:
                return {
                    "role": "user",
                    "content": f"<tool_response>\n{json.dumps(tool_results, indent=2)}\n</tool_response>",
                }
            else:
                return {"role": "user", "content": text_content}
        return None

    elif isinstance(message, ResultMessage):
        # ResultMessage is metadata, not a conversation message
        return None

    return None


async def solve_task(
    question: str,
    difficulty: str,
    task_idx: int,
    total: int,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Solve a single task using Claude Agent SDK."""
    async with semaphore:
        print(f"[{task_idx}/{total}] Starting: {question[:60]}...")

        messages = []
        solution = None

        try:
            async for message in query(
                prompt=question,
                options=ClaudeAgentOptions(
                    cwd=os.getcwd(),
                    permission_mode="bypassPermissions",
                    disallowed_tools=["Write", "Edit", "Bash", "Glob", "Grep"],
                    mcp_servers={
                        "huggingface": {
                            "type": "http",
                            "url": "https://huggingface.co/mcp",
                            "headers": {
                                "Authorization": f"Bearer {os.environ['HF_TOKEN']}"
                            },
                        }
                    },
                ),
            ):
                # Convert to chat format and append if valid
                chat_msg = convert_message_to_chat_format(message)
                if chat_msg:
                    messages.append(chat_msg)

                # Extract text from assistant messages
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            solution = block.text
                # Check for result messages
                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        print(f"[{task_idx}/{total}] ✗ Agent error: {message.subtype}")
                        return {
                            "question": question,
                            "difficulty": difficulty,
                            "solution": None,
                            "messages": messages,
                            "error": f"Agent error: {message.subtype}",
                        }
                    elif message.result:
                        solution = message.result

            print(f"[{task_idx}/{total}] ✓ Done: {question[:60]}...")
            return {
                "question": question,
                "difficulty": difficulty,
                "solution": solution,
                "messages": messages,
                "error": None,
            }
        except Exception as e:
            print(f"[{task_idx}/{total}] ✗ Error: {e}")
            return {
                "question": question,
                "difficulty": difficulty,
                "solution": None,
                "messages": messages,
                "error": str(e),
            }


def write_result(output_path: Path, result: dict):
    """Thread-safe write to output file."""
    with file_lock:
        with open(output_path, "a") as f:
            f.write(json.dumps(result) + "\n")


async def main():
    # Load tasks from filled_tasks.jsonl
    tasks_path = Path(__file__).parent / "filled_tasks.jsonl"
    tasks = []
    with open(tasks_path) as f:
        for line in f:
            tasks.append(json.loads(line))

    # Output file - clear it first
    output_path = Path(__file__).parent / "solved_tasks.jsonl"
    output_path.write_text("")

    # Semaphore to limit concurrency
    max_concurrent = 5
    semaphore = asyncio.Semaphore(max_concurrent)

    total = len(tasks)
    print(f"Processing {total} tasks with {max_concurrent} concurrent agents...")

    async def process_and_save(task: dict, idx: int):
        result = await solve_task(
            task["question"], task["difficulty"], idx, total, semaphore
        )
        write_result(output_path, result)
        return result

    # Create all tasks
    coroutines = [process_and_save(task, i + 1) for i, task in enumerate(tasks)]

    # Run all concurrently (semaphore limits actual parallelism)
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    successful = sum(
        1 for r in results if isinstance(r, dict) and r.get("error") is None
    )
    print(f"\nCompleted: {successful}/{total} successful")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
