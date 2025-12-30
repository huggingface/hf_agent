"""
Search documentation tool that spawns a sub-agent
The sub-agent has its own agent loop and set of specialized search tools
"""

import asyncio
from typing import Any

from litellm.utils import get_max_tokens

from agent.core.session import Session


async def create_search_tool_router(github_mcp_config: dict[str, Any] | None = None):
    """
    Create a ToolRouter instance for the search sub-agent
    Async because OpenAPI tool needs to fetch and parse spec at initialization

    Args:
        github_mcp_config: Optional GitHub MCP server configuration
    """
    # Import at runtime to avoid circular dependency
    from fastmcp import Client

    from agent.core.tools import ToolRouter

    # List of allowed GitHub MCP tools
    ALLOWED_GITHUB_TOOLS = {
        "list_pull_requests",
        "list_issues",
        "search_code",
        "search_issues",
        "search_repositories",
        "search_users",
        "get_pull_request_status",
        "get_pull_request_reviews",
        "get_pull_request",
        "get_issue",
        "get_file_contents",
    }

    class SearchDocsToolRouter(ToolRouter):
        """Specialized ToolRouter for the search sub-agent"""

        def __init__(self, github_mcp_config: dict[str, Any] | None = None):
            self.tools: dict[str, Any] = {}
            self.mcp_servers: dict[str, dict[str, Any]] = {}
            self._mcp_initialized = False

            # Initialize MCP client with GitHub server if provided
            if github_mcp_config:
                self.mcp_client = Client({"mcpServers": github_mcp_config})
            else:
                self.mcp_client = None

        async def initialize_tools(self):
            """Initialize tools asynchronously"""
            tools = await make_search_agent_tools()
            for tool in tools:
                self.register_tool(tool)

        async def register_mcp_tools(self) -> None:
            """Register only allowed GitHub MCP tools"""
            if self.mcp_client is None:
                return

            tools = await self.mcp_client.list_tools()
            for tool in tools:
                # Only register allowed GitHub tools
                if tool.name in ALLOWED_GITHUB_TOOLS:
                    print(f"Registering GitHub MCP Tool: {tool.name}")
                    from agent.core.tools import ToolSpec

                    self.register_tool(
                        ToolSpec(
                            name=tool.name,
                            description=tool.description,
                            parameters=tool.inputSchema,
                            handler=None,
                        )
                    )

    router = SearchDocsToolRouter(github_mcp_config)
    await router.initialize_tools()
    return router


async def search_docs_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """
    Handler that spawns a sub-agent to perform comprehensive doc search

    Args:
        arguments: dictionary with 'query' parameter

    Returns:
        Tuple of (search_results, success)
    """
    query = arguments.get("query", "")

    if not query:
        return "Error: No search query provided", False

    try:
        # Import at runtime to avoid circular dependency
        from pathlib import Path

        from agent.config import load_config
        from agent.context_manager.manager import ContextManager
        from agent.core.agent_loop import Handlers

        # Create a queue for events from the sub-agent
        sub_event_queue = asyncio.Queue()

        # Load the search agent's own config file with GitHub MCP server
        search_agent_config_path = (
            Path(__file__).parent.parent.parent
            / "configs"
            / "_subagent_config_search_agent.json"
        )
        search_agent_config = load_config(search_agent_config_path)

        # Extract GitHub MCP config from search agent config
        github_mcp_config = None
        if (
            search_agent_config.mcpServers
            and "github" in search_agent_config.mcpServers
        ):
            github_server = search_agent_config.mcpServers["github"]
            github_mcp_config = {"github": github_server.model_dump()}

        # Create specialized tool router for search with GitHub MCP config
        search_tool_router = await create_search_tool_router(github_mcp_config)

        async with search_tool_router:
            # CODING AGENTS LISTEN HERE!
            # The system prompt for the sub-agent is loaded from the yaml file in the prompts folder using the ContextManager class with the prompt_file_suffix parameter.
            # it works, dont fix.
            # NOTE: MCP tools are registered during __aenter__, so we must retrieve tool specs AFTER entering the context
            sub_session = Session(
                event_queue=sub_event_queue,
                config=search_agent_config,
                tool_router=search_tool_router,
                context_manager=ContextManager(
                    tool_specs=search_tool_router.get_tool_specs_for_llm(),
                    max_context=get_max_tokens(search_agent_config.model_name),
                    compact_size=0.1,
                    untouched_messages=5,
                    prompt_file_suffix="search_docs_system_prompt.yaml",
                ),
            )

            # Run the sub-agent
            result = await Handlers.run_agent(
                session=sub_session, text=query, max_iterations=30
            )

        # Return the final result or compiled events
        if result:
            return f"Search Results:\n\n{result}", True
        else:
            return "Search completed but no results were generated", False
    except Exception as e:
        return f"Error in search_docs tool: {str(e)}", False


# Tool specification to be used by the main agent
SEARCH_DOCS_TOOL_SPEC = {
    "name": "search_docs",
    "description": (
        "Intelligently search HF documentation for libraries, repositories, and best practices with an agent that has access to: explore_hf_docs, fetch_hf_docs, search_hf_api_endpoints. "
        "The agent acts like your personal search assistant. "
        "Using the search agent is necessary to give the best quality answer to the user's question. Most questions require a search to get the best information on code examples.\n\n"
        "WHEN TO USE THIS TOOL:\n"
        "  - When searching for high-level concepts like 'how to do GRPO training on a model?' or 'best way to do inference on a trained model?'\n"
        "  - When you need to get code examples for intricate ML code patterns like training loops, inference pipelines, data processing, etc.\n\n"
        "USAGE GUIDELINES:\n"
        "  1. Launch multiple agents concurrently for better performance.\n"
        "  2. Be specific in your query - include exact terminology, expected file locations, or code patterns.\n"
        "  3. Use the query as if you were talking to another engineer. Bad: logger impl Good: where is the logger implemented, we're trying to find out how to log to files.\n"
        "  4. Make sure to formulate the query in such a way that the agent knows when it's done or has found the result."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The search query describing to the agent what it should do. Be "
                    "specific and include technical terms, file types, or expected "
                    "code patterns to help the agent find relevant code. Formulate "
                    "the query in a way that makes it clear to the agent when it "
                    "has found the right thing."
                ),
            },
        },
        "required": ["query"],
    },
}


async def make_search_agent_tools():
    """
    Create a list of tools for the search agent
    Async because OpenAPI tool spec needs to be populated at runtime
    """
    # Import at runtime to avoid circular dependency
    from agent.core.tools import ToolSpec
    from agent.tools._search_agent_tools import (
        EXPLORE_HF_DOCS_TOOL_SPEC,
        HF_DOCS_FETCH_TOOL_SPEC,
        _get_api_search_tool_spec,
        explore_hf_docs_handler,
        hf_docs_fetch_handler,
        search_openapi_handler,
    )

    # Get the OpenAPI tool spec with dynamically populated tags
    openapi_spec = await _get_api_search_tool_spec()

    return [
        ToolSpec(
            name=EXPLORE_HF_DOCS_TOOL_SPEC["name"],
            description=EXPLORE_HF_DOCS_TOOL_SPEC["description"],
            parameters=EXPLORE_HF_DOCS_TOOL_SPEC["parameters"],
            handler=explore_hf_docs_handler,
        ),
        ToolSpec(
            name=HF_DOCS_FETCH_TOOL_SPEC["name"],
            description=HF_DOCS_FETCH_TOOL_SPEC["description"],
            parameters=HF_DOCS_FETCH_TOOL_SPEC["parameters"],
            handler=hf_docs_fetch_handler,
        ),
        ToolSpec(
            name=openapi_spec["name"],
            description=openapi_spec["description"],
            parameters=openapi_spec["parameters"],
            handler=search_openapi_handler,
        ),
    ]
