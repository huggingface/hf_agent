"""
GitHub Search Code Tool

Searches code across GitHub with glob filtering and line-level results.
"""

import asyncio
import fnmatch
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    raise ImportError(
        "requests library is required. Install with: pip install requests"
    )

from agent.tools.types import ToolResult


@dataclass
class CodeMatch:
    """A code match with location information."""

    repo: str
    path: str
    ref: str
    line_start: int
    line_end: int
    snippet: str

    def to_dict(self):
        return asdict(self)


class GitHubAPIError(Exception):
    """Raised when GitHub API returns an error."""

    pass


def _get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubAPIError(
            "GITHUB_TOKEN environment variable is required. "
            "Set it with: export GITHUB_TOKEN=your_token_here"
        )
    return token


def _build_github_query(
    query: str, repo_glob: Optional[str], path_glob: Optional[str], regex: bool
) -> str:
    """Build GitHub search query string from parameters."""
    parts = []

    if regex:
        parts.append(f"/{query}/")
    else:
        if " " in query:
            parts.append(f'"{query}"')
        else:
            parts.append(query)

    if repo_glob:
        if "/" in repo_glob:
            parts.append(f"repo:{repo_glob}")
        else:
            parts.append(f"user:{repo_glob}")

    if path_glob:
        if "*" not in path_glob and "?" not in path_glob:
            parts.append(f"path:{path_glob}")
        elif path_glob.startswith("*."):
            ext = path_glob[2:]
            parts.append(f"extension:{ext}")
        elif "/" not in path_glob and "*" in path_glob:
            parts.append(f"filename:{path_glob}")
        else:
            if "." in path_glob:
                ext_match = re.search(r"\*\.(\w+)", path_glob)
                if ext_match:
                    parts.append(f"extension:{ext_match.group(1)}")

    return " ".join(parts)


def _fetch_code_search_results(
    query: str, token: str, max_results: int
) -> List[Dict[str, Any]]:
    """Fetch code search results from GitHub API."""
    headers = {
        "Accept": "application/vnd.github.text-match+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    all_items = []
    page = 1
    per_page = min(100, max_results)

    while len(all_items) < max_results:
        params = {
            "q": query,
            "page": page,
            "per_page": per_page,
        }

        url = "https://api.github.com/search/code"

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code != 200:
                break

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            all_items.extend(items)

            if len(all_items) >= data.get("total_count", 0):
                break

            page += 1

        except requests.exceptions.RequestException:
            break

    return all_items[:max_results]


def _glob_match(text: str, pattern: str) -> bool:
    """Check if text matches glob pattern, supporting ** for multi-level paths."""
    if "**" in pattern:
        regex_pattern = pattern.replace("**", "<<<DOUBLESTAR>>>")
        regex_pattern = fnmatch.translate(regex_pattern)
        regex_pattern = regex_pattern.replace("<<<DOUBLESTAR>>>", ".*")
        return re.match(regex_pattern, text) is not None
    else:
        return fnmatch.fnmatch(text, pattern)


def _estimate_line_numbers(fragment: str) -> Tuple[int, int]:
    """Estimate line numbers from a code fragment."""
    lines = fragment.split("\n")
    line_count = len([line for line in lines if line.strip()])
    return 1, line_count


def _parse_results_to_matches(
    raw_results: List[Dict[str, Any]],
    repo_glob: Optional[str],
    path_glob: Optional[str],
) -> List[CodeMatch]:
    """Parse raw GitHub API results into CodeMatch objects."""
    matches = []

    for item in raw_results:
        repo_name = item.get("repository", {}).get("full_name", "unknown/unknown")
        file_path = item.get("path", "")
        sha = item.get("sha", "unknown")

        if repo_glob and not _glob_match(repo_name, repo_glob):
            continue

        if path_glob and not _glob_match(file_path, path_glob):
            continue

        text_matches = item.get("text_matches", [])

        if text_matches:
            for text_match in text_matches:
                fragment = text_match.get("fragment", "")
                line_start, line_end = _estimate_line_numbers(fragment)

                match = CodeMatch(
                    repo=repo_name,
                    path=file_path,
                    ref=sha,
                    line_start=line_start,
                    line_end=line_end,
                    snippet=fragment.strip(),
                )
                matches.append(match)
        else:
            match = CodeMatch(
                repo=repo_name,
                path=file_path,
                ref=sha,
                line_start=1,
                line_end=1,
                snippet="<match found, but snippet not available>",
            )
            matches.append(match)

    return matches


def search_code(
    query: str,
    repo_glob: Optional[str] = None,
    path_glob: Optional[str] = None,
    regex: bool = False,
    max_results: int = 100,
) -> List[CodeMatch]:
    """
    Search for code across GitHub with glob filtering and line-level results.

    Returns: repo, path, ref, line_start, line_end, snippet

    Args:
        query: Search term or pattern to find in code
        repo_glob: Glob pattern to filter repositories (e.g., "github/*", "facebook/react")
        path_glob: Glob pattern to filter file paths (e.g., "*.py", "src/**/*.js")
        regex: If True, treat query as a regular expression
        max_results: Maximum number of results to return (default: 100)

    Returns:
        List of CodeMatch objects with repo, path, ref, line numbers, and snippet
    """
    github_query = _build_github_query(query, repo_glob, path_glob, regex)
    token = _get_github_token()

    raw_results = _fetch_code_search_results(github_query, token, max_results)
    matches = _parse_results_to_matches(raw_results, repo_glob, path_glob)

    return matches


async def _async_call(func, *args, **kwargs):
    """Wrap synchronous calls for async context."""
    return await asyncio.to_thread(func, *args, **kwargs)


def _format_code_matches(matches: List[CodeMatch]) -> str:
    """Format code matches."""
    if not matches:
        return "No matches found."

    lines = []
    for i, match in enumerate(matches, 1):
        lines.append(f"**{i}. {match.repo}/{match.path}:{match.line_start}**")
        lines.append("```")
        # Show first 5 lines of snippet
        snippet_lines = match.snippet.split("\n")[:5]
        lines.extend(snippet_lines)
        if len(match.snippet.split("\n")) > 5:
            lines.append("...")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


class SearchCodeTool:
    """Tool for searching code across GitHub."""

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute search_code operation."""
        query = params.get("query")
        if not query:
            return {
                "formatted": "Error: 'query' parameter is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

        repo_glob = params.get("repo_glob")
        path_glob = params.get("path_glob")
        regex = params.get("regex", False)
        max_results = params.get("max_results", 100)

        try:
            matches = await _async_call(
                search_code,
                query=query,
                repo_glob=repo_glob,
                path_glob=path_glob,
                regex=regex,
                max_results=max_results,
            )

            if not matches:
                return {
                    "formatted": "No matches found",
                    "totalResults": 0,
                    "resultsShared": 0,
                }

            formatted = _format_code_matches(matches)
            response = f"**Found {len(matches)} code matches:**\n\n{formatted}"

            # Add note about viewing full files
            if matches:
                response += "\n**To view full file, use:**\n"
                top_match = matches[0]
                response += (
                    f"read_file(repo='{top_match.repo}', path='{top_match.path}')"
                )

            return {
                "formatted": response,
                "totalResults": len(matches),
                "resultsShared": min(len(matches), 10),
            }

        except GitHubAPIError as e:
            return {
                "formatted": f"GitHub API Error: {str(e)}",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }
        except Exception as e:
            return {
                "formatted": f"Error: {str(e)}",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }


# Tool specification
SEARCH_CODE_TOOL_SPEC = {
    "name": "search_code",
    "description": (
        "Search code across GitHub with glob filtering and line-level results.\n\n"
        "Returns: repo, path, ref, line_start, line_end, snippet\n\n"
        "Examples:\n"
        "- Search Python functions: {'query': 'def train', 'path_glob': '*.py', 'repo_glob': 'huggingface/*'}\n"
        "- Search TODO comments: {'query': 'TODO', 'repo_glob': 'github/*', 'max_results': 10}\n"
        "- Regex search: {'query': r'func Test\\w+', 'path_glob': '*.go', 'regex': True}\n"
        "- Search in specific repo: {'query': 'HfApi', 'repo_glob': 'huggingface/huggingface_hub', 'path_glob': '*.py'}\n\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term or pattern to find in code",
            },
            "repo_glob": {
                "type": "string",
                "description": "Glob pattern to filter repositories (e.g., 'github/*', 'facebook/react')",
            },
            "path_glob": {
                "type": "string",
                "description": "Glob pattern to filter file paths (e.g., '*.py', 'src/**/*.js', 'test_*.py')",
            },
            "regex": {
                "type": "boolean",
                "description": "Treat query as regular expression (default: false)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 100)",
            },
        },
        "required": ["query"],
    },
}


async def search_code_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router."""
    try:
        tool = SearchCodeTool()
        result = await tool.execute(arguments)
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error executing search_code: {str(e)}", False
