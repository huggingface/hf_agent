"""
Hugging Face tools for the agent
"""

from agent.tools.jobs_tool import HF_JOBS_TOOL_SPEC, HfJobsTool, hf_jobs_handler
from agent.tools.search_docs_tool import SEARCH_DOCS_TOOL_SPEC, search_docs_handler
from agent.tools.types import ToolResult

__all__ = [
    "ToolResult",
    "HF_JOBS_TOOL_SPEC",
    "hf_jobs_handler",
    "HfJobsTool",
    "SEARCH_DOCS_TOOL_SPEC",
    "search_docs_handler",
]
