"""
Hugging Face tools for the agent
"""

from agent.tools.github_find_examples import (
    FIND_EXAMPLES_TOOL_SPEC,
    FindExamplesTool,
    find_examples_handler,
)
from agent.tools.github_list_repos import (
    LIST_REPOS_TOOL_SPEC,
    ListReposTool,
    list_repos_handler,
)
from agent.tools.github_read_file import (
    READ_FILE_TOOL_SPEC,
    ReadFileTool,
    read_file_handler,
)
from agent.tools.github_search_code import (
    SEARCH_CODE_TOOL_SPEC,
    SearchCodeTool,
    search_code_handler,
)
from agent.tools.jobs_tool import HF_JOBS_TOOL_SPEC, HfJobsTool, hf_jobs_handler
from agent.tools.types import ToolResult

__all__ = [
    "ToolResult",
    "HF_JOBS_TOOL_SPEC",
    "hf_jobs_handler",
    "HfJobsTool",
    "FIND_EXAMPLES_TOOL_SPEC",
    "find_examples_handler",
    "FindExamplesTool",
    "READ_FILE_TOOL_SPEC",
    "read_file_handler",
    "ReadFileTool",
    "LIST_REPOS_TOOL_SPEC",
    "list_repos_handler",
    "ListReposTool",
    "SEARCH_CODE_TOOL_SPEC",
    "search_code_handler",
    "SearchCodeTool",
]
