"""
Interactive CLI chat with the agent
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from agent.config import Config
from agent.core.agent_loop import submission_loop
from agent.core.session import OpType


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
    event_queue: asyncio.Queue, turn_complete_event: asyncio.Event
) -> None:
    """Background task that listens for events and displays them"""
    while True:
        try:
            event = await event_queue.get()

            # Display event
            if event.event_type == "assistant_message":
                msg = event.data.get("message", {})
                content = msg.get("content", "")
                if content:
                    print(f"\n🤖 Assistant: {content}")
            elif event.event_type == "tool_output":
                msg = event.data.get("message", {})
                content = msg.get("content", "")
                if content:
                    print(
                        f"🔧 Tool: {content[:200]}{'...' if len(content) > 200 else ''}"
                    )
            elif event.event_type == "turn_complete":
                print("✅ Turn complete\n")
                turn_complete_event.set()
            elif event.event_type == "error":
                import traceback

                traceback.print_exc()
                print(f"❌ Error: {event.data.get('error', 'Unknown error')}")
                turn_complete_event.set()
            elif event.event_type == "shutdown":
                print("🛑 Agent shutdown")
                break
            elif event.event_type == "processing":
                print("⏳ Processing...", flush=True)
            # Silently ignore other events

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ Event listener error: {e}")


async def get_user_input() -> str:
    """Get user input asynchronously"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, "You: ")


async def main():
    """Interactive chat with the agent"""

    print("=" * 60)
    print("🤖 Interactive Agent Chat")
    print("=" * 60)
    print("Type your messages below. Type 'exit', 'quit', or '/quit' to end.\n")

    # Create queues for communication
    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    # Event to signal turn completion
    turn_complete_event = asyncio.Event()
    turn_complete_event.set()  # Ready for first input

    # Start agent loop in background
    agent_task = asyncio.create_task(
        submission_loop(
            submission_queue,
            event_queue,
            config=Config(
                model_name="anthropic/claude-sonnet-4-5-20250929",
                tools=[],
                system_prompt_path="",
            ),
        )
    )

    # Start event listener in background
    listener_task = asyncio.create_task(
        event_listener(event_queue, turn_complete_event)
    )

    # Wait for agent to initialize
    await asyncio.sleep(0.2)

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
            await submission_queue.put(submission)

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")

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
