"""Test script to check MCP server connection"""
import asyncio
from pathlib import Path
from agent.config import load_config
from agent.core.tools import ToolRouter


async def test_mcp():
    print("Loading config...")
    config_path = Path(__file__).parent / "configs" / "main_agent_config.json"
    config = load_config(config_path)

    print(f"MCP Servers configured: {list(config.mcpServers.keys())}")
    print(f"\nInitializing ToolRouter...")

    tool_router = ToolRouter(config.mcpServers)

    print("Entering async context (this will init MCP servers)...")
    try:
        async with tool_router as router:
            print("✓ MCP initialization successful!")
            tools = router.get_tool_specs_for_llm()
            print(f"\nTotal tools available: {len(tools)}")

            builtin = [t for t in tools if t['function']['name'] in ['hf_jobs', 'hf_private_repos', 'hf_doc_search', 'plan_tool']]
            mcp = [t for t in tools if t not in builtin]

            print(f"Built-in tools: {len(builtin)}")
            for tool in builtin:
                print(f"  - {tool['function']['name']}")

            print(f"\nMCP tools: {len(mcp)}")
            for tool in mcp[:5]:  # Show first 5
                print(f"  - {tool['function']['name']}")
            if len(mcp) > 5:
                print(f"  ... and {len(mcp) - 5} more")

    except Exception as e:
        print(f"✗ Error during MCP initialization: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp())
