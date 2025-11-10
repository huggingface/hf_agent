"""
Main agent implementation
"""

import asyncio

from litellm import (
    ChatCompletionMessageToolCall,
    Message,
    ModelResponse,
    acompletion,
)

from agent.core.session import Event, OpType, Session

ToolCall = ChatCompletionMessageToolCall


class Handlers:
    """Handler functions for each operation type"""

    @staticmethod
    async def run_agent(session: Session, text: str, max_iterations: int = 10) -> None:
        """Handle user input (like user_input_or_turn in codex.rs:1291)"""
        # Add user message to history
        user_msg = Message(role="user", content=text)
        session.context_manager.add_message(user_msg)

        # Send event that we're processing
        await session.send_event(
            Event(event_type="processing", data={"message": "Processing user input"})
        )

        # Agentic loop - continue until model doesn't call tools or max iterations is reached
        iteration = 0
        while iteration < max_iterations:
            messages = session.context_manager.get_messages()

            try:
                response: ModelResponse = await acompletion(
                    model=session.config.model_name,
                    messages=messages,
                    tools=session.config.tools,
                )
                message = response.choices[0].message

                # Extract content and tool calls
                content = message.content
                tool_calls: list[ToolCall] = message.get("tool_calls", [])

                # Record assistant message if there's content
                if content:
                    assistant_msg = Message(role="assistant", content=content)
                    session.context_manager.add_message(assistant_msg)

                    await session.send_event(
                        Event(
                            event_type="assistant_message",
                            data={"message": assistant_msg},
                        )
                    )

                # If no tool calls, we're done
                if not tool_calls:
                    break

                for tool_call in tool_calls:
                    result = await session.tool_executor.execute_tool(tool_call)

                    tool_output = Message(role="tool", content=result.output)
                    session.context_manager.add_message(tool_output)

                    await session.send_event(
                        Event(
                            event_type="tool_output",
                            data={"message": tool_output},
                        )
                    )

                iteration += 1

            except Exception as e:
                await session.send_event(
                    Event(event_type="error", data={"error": str(e)})
                )
                break

        # Send completion event
        await session.send_event(
            Event(
                event_type="turn_complete",
                data={"history_size": len(session.context_manager.items)},
            )
        )

    @staticmethod
    async def interrupt(session: Session) -> None:
        """Handle interrupt (like interrupt in codex.rs:1266)"""
        session.interrupt()
        await session.send_event(Event(event_type="interrupted"))

    @staticmethod
    async def compact(session: Session) -> None:
        """Handle compact (like compact in codex.rs:1317)"""
        old_size = len(session.context_manager.items)
        session.context_manager.compact(target_size=10)
        new_size = len(session.context_manager.items)

        await session.send_event(
            Event(
                event_type="compacted",
                data={"removed": old_size - new_size, "remaining": new_size},
            )
        )

    @staticmethod
    async def undo(session: Session) -> None:
        """Handle undo (like undo in codex.rs:1314)"""
        # Remove last user turn and all following items
        # Simplified: just remove last 2 items
        for _ in range(min(2, len(session.context_manager.items))):
            session.context_manager.items.pop()

        await session.send_event(Event(event_type="undo_complete"))

    @staticmethod
    async def shutdown(session: Session) -> bool:
        """Handle shutdown (like shutdown in codex.rs:1329)"""
        session.is_running = False
        await session.send_event(Event(event_type="shutdown"))
        return True


async def submission_loop(
    submission_queue: asyncio.Queue, event_queue: asyncio.Queue
) -> None:
    """
    Main agent loop - processes submissions and dispatches to handlers.
    This is the core of the agent (like submission_loop in codex.rs:1259-1340)
    """
    session = Session(event_queue)

    print("🤖 Agent loop started")

    # Main processing loop
    while session.is_running:
        try:
            # Wait for next submission (like rx_sub.recv() in codex.rs:1262)
            submission = await submission_queue.get()

            print(f"📨 Received: {submission.operation.op_type.value}")

            # Dispatch to handler based on operation type
            op = submission.operation

            if op.op_type == OpType.USER_INPUT:
                text = op.data.get("text", "") if op.data else ""
                await Handlers.run_agent(session, text, max_iterations=10)

            elif op.op_type == OpType.INTERRUPT:
                # im not currently sure what this does lol
                await Handlers.interrupt(session)

            elif op.op_type == OpType.COMPACT:
                await Handlers.compact(session)

            elif op.op_type == OpType.UNDO:
                await Handlers.undo(session)

            elif op.op_type == OpType.SHUTDOWN:
                if await Handlers.shutdown(session):
                    break

            else:
                print(f"⚠️  Unknown operation: {op.op_type}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Error in agent loop: {e}")
            await session.send_event(Event(event_type="error", data={"error": str(e)}))

    print("🛑 Agent loop exited")
