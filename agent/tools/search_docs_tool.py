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
    user_query = arguments.get("user_query", "")

    if not query:
        return "Error: No search query provided", False

    if not user_query:
        return "Error: No user query provided", False

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

            # make search prompt
            search_prompt = f"What the user tasked the main agent with: {user_query}\nWhat you have asked to research by the main agent: {query}. Use both to find the best practices, code examples, and determine the recommended approach for solving the user's task."

            # Run the sub-agent
            result = await Handlers.run_agent(
                session=sub_session, text=search_prompt, max_iterations=30
            )

        # Return the final result or compiled events
        if result:
            return f"Search Results:\n\n{result}", True
        else:
            return "Search completed but no results were generated", False
    except Exception as e:
        return f"Error in search_docs tool: {str(e)}", False


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


# Tool specification to be used by the main agent
SEARCH_DOCS_TOOL_SPEC = {
    "name": "research_solution",
    "description": (
        "Spawns a specialized research sub-agent to search to find best practices, locate code examples, and determine the recommended approach for solving the user's task.\n\n"
        "SEARCH AGENT CAPABILITIES:\n"
        "The search subagent has access to these specialized tools:\n"
        "  - explore_hf_docs: Discovers documentation structure by parsing sidebar navigation, returns page titles, URLs, and content glimpses\n"
        "  - fetch_hf_docs: Retrieves full markdown content from specific HF documentation pages\n"
        "  - search_hf_api_endpoints: Searches HF OpenAPI specification by tag to find API endpoints with usage examples\n"
        "  - GitHub tools: search_code, search_repositories, get_file_contents, list_issues, list_pull_requests (for searching HF repositories)\n"
        "MANDATORY FIRST STEP for:\n"
        "  - ANY task involving training, fine-tuning, or model deployment with HF libraries\n"
        "  - Implementing ML workflows (data loading, preprocessing, training loops, inference pipelines)\n"
        "  - Working with specific HF libraries (transformers, diffusers, trl, datasets, accelerate, etc.)\n"
        "  - Finding the recommended/official way to accomplish ML tasks\n"
        "  - Understanding which libraries and methods to use for a user's goal\n\n"
        "ALSO USE for:\n"
        "  - Verifying current API signatures, parameters, or available methods\n"
        "  - Finding code examples and best practices from official documentation\n"
        "  - Understanding relationships between HF libraries and components\n\n"
        "SKIP ONLY when:\n"
        "  - User asks simple factual questions answerable from general ML knowledge (e.g., 'What is fine-tuning?')\n"
        "  - Task is about general Python/programming unrelated to ML or HF libraries\n"
        "QUERY FORMAT:\n"
        "Write queries as if delegating to an engineer. Include:\n"
        "  - Specific library names (e.g., 'trl', 'transformers', 'diffusers')\n"
        "  - Technical terminology from the domain (e.g., 'DPO trainer', 'GRPO', 'LoRA adapter')\n"
        "  - Clear success criteria (e.g., 'find code example', 'verify parameter exists', 'get recommended approach')\n\n"
        "QUERY EXAMPLES:\n"
        "  Good: 'Find the best way to implement DPO training in trl. Get code example showing dataset format, trainer configuration, and reward model setup'\n"
        "  Bad: 'dpo trainer'\n"
        "  Good: 'Search transformers docs for the recommended approach to load and run quantized models with 4-bit precision. Find the specific classes and methods to use'\n"
        "  Bad: 'quantization'\n"
        "  Good: 'Research the best way to fine-tune a diffusion model for custom image generation. Find which library to use (diffusers/PEFT), required components, and complete training example'\n"
        "  Bad: 'fine-tune diffusion'\n\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_query": {
                "type": "string",
                "description": (
                    "The original user query that you received. This will be used to search the documentation."
                ),
            },
            "query": {
                "type": "string",
                "description": (
                    "Detailed search query for the specialized agent. Must include: (1) specific library/component names, "
                    "(2) technical terms or concepts to search for, (3) clear objective (e.g., 'find code example', "
                    "'verify API exists', 'get implementation details'). The search agent will autonomously explore "
                    "documentation structure, retrieve relevant pages, and compile results until the objective is met."
                ),
            },
        },
        "required": ["user_query", "query"],
    },
}
