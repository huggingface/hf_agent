"""
Standalone test script for the search sub-agent
Run with: uv run python test_search_agent.py
"""

import asyncio

from litellm.utils import get_max_tokens

from agent.config import Config
from agent.context_manager.manager import ContextManager
from agent.core.agent_loop import Handlers
from agent.core.session import Session
from agent.tools.search_docs_tool import create_search_tool_router


async def test_search_agent(query: str):
    """Test the search sub-agent with a query"""
    print(f"Testing search agent with query: {query}\n")
    print("=" * 60)

    # Create event queue for the sub-agent
    sub_event_queue = asyncio.Queue()

    # Create search tool router
    search_tool_router = await create_search_tool_router()

    # Create config
    sub_config = Config(
        model_name="anthropic/claude-haiku-4-5",
    )

    # Create session with custom system prompt
    sub_session = Session(
        event_queue=sub_event_queue,
        config=sub_config,
        tool_router=search_tool_router,
        context_manager=ContextManager(
            tool_specs=search_tool_router.get_tool_specs_for_llm(),
            max_context=get_max_tokens(sub_config.model_name),
            compact_size=0.1,
            untouched_messages=5,
            prompt_file_suffix="search_docs_system_prompt.yaml",
        ),
    )

    # Event listener to show what the sub-agent is doing
    async def event_monitor():
        while True:
            try:
                event = await asyncio.wait_for(sub_event_queue.get(), timeout=1.0)

                if event.event_type == "assistant_message":
                    content = event.data.get("content", "") if event.data else ""
                    if content:
                        print(f"\n🤖 Sub-agent: {content}\n")

                elif event.event_type == "tool_call":
                    tool_name = event.data.get("tool", "") if event.data else ""
                    arguments = event.data.get("arguments", {}) if event.data else {}
                    print(f"🔧 Tool call: {tool_name}")
                    print(f"   Args: {arguments}")

                elif event.event_type == "tool_output":
                    output = event.data.get("output", "") if event.data else ""
                    success = event.data.get("success", False) if event.data else False
                    status = "✅" if success else "❌"

                    print(f"{status} Tool output: {output}\n")

                elif event.event_type == "turn_complete":
                    print("✅ Sub-agent turn complete")
                    break

            except asyncio.TimeoutError:
                # Check if agent is still running
                continue
            except Exception as e:
                print(f"⚠️  Event error: {e}")
                break

    # Run the sub-agent and event monitor concurrently
    async with search_tool_router:
        monitor_task = asyncio.create_task(event_monitor())

        result = await Handlers.run_agent(
            session=sub_session, text=query, max_iterations=30
        )

        # Wait for event monitor to finish
        await asyncio.wait_for(monitor_task, timeout=5.0)

    print("\n" + "=" * 60)
    print("FINAL RESULT:")
    print("=" * 60)
    if result:
        print(result)
    else:
        print("No result returned")
    print("=" * 60)


async def main():
    """Main test function"""
    print("🧪 Search Sub-Agent Test\n")

    # Example queries to test
    test_queries = [
        # "Explore the TRL documentation structure and find information about DPO trainer",
        # "is there a way to get the logs from a served huggingface space",
        # "How do I train GLM4.7 with a GRPO training loop with trl with llm judge as a reward model for training on hle?"
        "can i stream logs through the api for a served huggingface space",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 60}")
        print(f"TEST {i}/{len(test_queries)}")
        print(f"{'=' * 60}\n")

        try:
            await test_search_agent(query)
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

        if i < len(test_queries):
            print("\n\nPress Enter to continue to next test...")
            input()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
