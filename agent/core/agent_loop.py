"""
Main agent implementation with integrated tool system and MCP support
"""

import asyncio
import json

from litellm import ChatCompletionMessageToolCall, Message, ModelResponse, acompletion

from agent.config import Config
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
            tools = session.tool_router.get_tool_specs_for_llm()

            try:
                response: ModelResponse = await acompletion(
                    model=session.config.model_name,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
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
                        Event(event_type="assistant_message", data={"content": content})
                    )

                # If no tool calls, we're done
                if not tool_calls:
                    break

                # Execute tools
                for tc in tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)

                    await session.send_event(
                        Event(
                            event_type="tool_call",
                            data={"tool": tool_name, "arguments": tool_args},
                        )
                    )

                    output, success = await session.tool_router.execute_tool(
                        tool_name, tool_args
                    )

                    # Add tool result to history
                    tool_msg = Message(
                        role="tool",
                        content=output,
                        tool_call_id=tc.id,
                        name=tool_name,
                    )
                    session.context_manager.add_message(tool_msg)

                    await session.send_event(
                        Event(
                            event_type="tool_output",
                            data={
                                "tool": tool_name,
                                "output": output[:200]
                                + ("..." if len(output) > 200 else ""),
                                "success": success,
                            },
                        )
                    )

                iteration += 1

            except Exception as e:
                await session.send_event(
                    Event(event_type="error", data={"error": str(e)})
                )
                break

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


async def process_submission(session: Session, submission) -> bool:
    """
    Process a single submission and return whether to continue running.

    Returns:
        bool: True to continue, False to shutdown
    """
    op = submission.operation
    print(f"📨 Received: {op.op_type.value}")

    if op.op_type == OpType.USER_INPUT:
        text = op.data.get("text", "") if op.data else ""
        await Handlers.user_input(session, text)
        return True

    if op.op_type == OpType.INTERRUPT:
        await Handlers.interrupt(session)
        return True

    if op.op_type == OpType.COMPACT:
        await Handlers.compact(session)
        return True

    if op.op_type == OpType.UNDO:
        await Handlers.undo(session)
        return True

    if op.op_type == OpType.SHUTDOWN:
        return not await Handlers.shutdown(session)

    print(f"⚠️  Unknown operation: {op.op_type}")
    return True


async def submission_loop(
    submission_queue: asyncio.Queue,
    event_queue: asyncio.Queue,
    tool_router=None,
    config: Config | None = None,
) -> None:
    """
    Main agent loop - processes submissions and dispatches to handlers.
    This is the core of the agent (like submission_loop in codex.rs:1259-1340)
    """
    # Import here to avoid circular imports
    from agent.core.mcp_client import McpConnectionManager
    from agent.core.tools import ToolRouter, create_builtin_tools

    # Initialize MCP and tools
    if tool_router is None:
        mcp_manager = McpConnectionManager()

        # Add MCP servers from config
        if config and config.mcp_servers:
            print("🔌 Initializing MCP connections...")
            for server_config in config.mcp_servers:
                try:
                    await mcp_manager.add_server(
                        server_name=server_config.name,
                        command=server_config.command,
                        args=server_config.args,
                        env=server_config.env,
                    )
                except Exception as e:
                    print(
                        f"⚠️  Failed to connect to MCP server {server_config.name}: {e}"
                    )

        # Create tool router
        tool_router = ToolRouter(mcp_manager)

        # Register built-in tools
        for tool in create_builtin_tools():
            tool_router.register_tool(tool)

        # Register MCP tools
        tool_router.register_mcp_tools()

        print(f"📦 Registered {len(tool_router.tools)} tools:")
        for tool_name in tool_router.tools.keys():
            print(f"   - {tool_name}")

    # Create session and assign tool router
    session = Session(event_queue, config=config)
    session.tool_router = tool_router
    print("🤖 Agent loop started")

    try:
        # Main processing loop
        while session.is_running:
            submission = await submission_queue.get()

            try:
                should_continue = await process_submission(session, submission)
                if not should_continue:
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error in agent loop: {e}")
                await session.send_event(
                    Event(event_type="error", data={"error": str(e)})
                )
    finally:
        # Cleanup MCP connections
        if hasattr(tool_router, "mcp_manager") and tool_router.mcp_manager:
            await tool_router.mcp_manager.shutdown_all()

    print("🛑 Agent loop exited")
