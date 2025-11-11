"""
Simple runner for the agent with a single dummy input
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

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


async def main():
    """Run agent with a single dummy input"""

    print("🚀 Starting agent...")

    # Create queues for communication
    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    # Start agent loop in background
    agent_task = asyncio.create_task(submission_loop(submission_queue, event_queue))

    # Wait a moment for agent to initialize
    await asyncio.sleep(0.1)

    # Submit dummy input
    print("\n📝 Submitting dummy input...")
    dummy_submission = Submission(
        id="sub_1",
        operation=Operation(
            op_type=OpType.USER_INPUT,
            data={"text": "Hello! What tools do you have available?"},
        ),
    )
    await submission_queue.put(dummy_submission)

    # Listen for events
    print("\n👂 Listening for events...\n")
    events_received = 0
    max_events = 10  # Safety limit

    while events_received < max_events:
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=2.0)
            events_received += 1

            # Display event
            if event.event_type == "assistant_message":
                msg = event.data.get("message", {})
                content = msg.get("content", "")
                print(f"🤖 Assistant: {content}")
            elif event.event_type == "tool_output":
                msg = event.data.get("message", {})
                content = msg.get("content", "")
                print(f"🔧 Tool output: {content}")
            elif event.event_type == "turn_complete":
                print(f"✅ Turn complete: {event.data}")
                break
            elif event.event_type == "error":
                print(f"❌ Error: {event.data}")
                break
            else:
                print(f"📨 Event: {event.event_type} - {event.data}")

        except asyncio.TimeoutError:
            print("⏱️  No more events, timing out...")
            break

    # Shutdown
    print("\n🛑 Shutting down agent...")
    shutdown_submission = Submission(
        id="sub_shutdown", operation=Operation(op_type=OpType.SHUTDOWN)
    )
    await submission_queue.put(shutdown_submission)

    # Wait for shutdown event
    try:
        event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
        print(f"✅ {event.event_type}")
    except asyncio.TimeoutError:
        pass

    # Wait for agent task to complete
    await agent_task

    print("\n✨ Done!")


if __name__ == "__main__":
    asyncio.run(main())
