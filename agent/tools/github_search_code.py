"""
GitHub Code Search Tool - Search code across GitHub with advanced filtering

Find code patterns using regex and glob filters for repositories and file paths.
"""

import fnmatch
import os
import re
from typing import Any, Dict, Optional

import requests

from agent.tools.types import ToolResult


def _glob_match(text: str, pattern: str) -> bool:
    """Check if text matches glob pattern, supporting ** for multi-level paths"""
    if "**" in pattern:
        regex_pattern = pattern.replace("**", "<<<DOUBLESTAR>>>")
        regex_pattern = fnmatch.translate(regex_pattern)
        regex_pattern = regex_pattern.replace("<<<DOUBLESTAR>>>", ".*")
        return re.match(regex_pattern, text) is not None
    return fnmatch.fnmatch(text, pattern)


def search_code(
    query: str,
    repo_glob: Optional[str] = None,
    path_glob: Optional[str] = None,
    regex: bool = False,
    max_results: int = 20,
) -> ToolResult:
    """
    Search for code across GitHub with glob filtering.

    Args:
        query: Search term or pattern to find in code
        repo_glob: Glob pattern to filter repositories (e.g., "github/*", "*/react")
        path_glob: Glob pattern to filter file paths (e.g., "*.py", "src/**/*.js")
        regex: If True, treat query as regular expression
        max_results: Maximum number of results to return (default 20)

    Returns:
        ToolResult with code matches and snippets
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {
            "formatted": "Error: GITHUB_TOKEN environment variable is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    # Build GitHub query
    query_parts = []

    if regex:
        query_parts.append(f"/{query}/")
    else:
        query_parts.append(f'"{query}"' if " " in query else query)

    # Add repo filter
    if repo_glob:
        if "/" in repo_glob:
            query_parts.append(f"repo:{repo_glob}")
        else:
            query_parts.append(f"user:{repo_glob}")

    # Add path filter
    if path_glob:
        if "*" not in path_glob and "?" not in path_glob:
            query_parts.append(f"path:{path_glob}")
        elif path_glob.startswith("*."):
            ext = path_glob[2:]
            query_parts.append(f"extension:{ext}")
        elif "/" not in path_glob and "*" in path_glob:
            query_parts.append(f"filename:{path_glob}")
        else:
            # Complex pattern, extract extension if possible
            ext_match = re.search(r"\*\.(\w+)", path_glob)
            if ext_match:
                query_parts.append(f"extension:{ext_match.group(1)}")

    github_query = " ".join(query_parts)

    headers = {
        "Accept": "application/vnd.github.text-match+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    all_matches = []
    page = 1
    per_page = min(100, max_results)

    try:
        while len(all_matches) < max_results:
            params = {
                "q": github_query,
                "page": page,
                "per_page": per_page,
            }

            response = requests.get(
                "https://api.github.com/search/code",
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 403:
                error_data = response.json()
                return {
                    "formatted": f"GitHub API rate limit or permission error: {error_data.get('message', 'Unknown error')}",
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True,
                }

            if response.status_code != 200:
                error_msg = f"GitHub API error (status {response.status_code})"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg += f": {error_data['message']}"
                except Exception:
                    pass
                return {
                    "formatted": error_msg,
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True,
                }

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            for item in items:
                repo_name = item.get("repository", {}).get("full_name", "unknown")
                file_path = item.get("path", "")
                sha = item.get("sha", "")

                # Apply client-side glob filtering
                if repo_glob and not _glob_match(repo_name, repo_glob):
                    continue
                if path_glob and not _glob_match(file_path, path_glob):
                    continue

                # Extract text matches
                text_matches = item.get("text_matches", [])
                if text_matches:
                    for text_match in text_matches:
                        fragment = text_match.get("fragment", "")
                        lines = fragment.split("\n")
                        line_count = len([line for line in lines if line.strip()])

                        all_matches.append(
                            {
                                "repo": repo_name,
                                "path": file_path,
                                "ref": sha,
                                "line_start": 1,
                                "line_end": line_count,
                                "snippet": fragment.strip(),
                                "url": item.get("html_url", ""),
                            }
                        )
                else:
                    all_matches.append(
                        {
                            "repo": repo_name,
                            "path": file_path,
                            "ref": sha,
                            "line_start": 1,
                            "line_end": 1,
                            "snippet": "(snippet not available)",
                            "url": item.get("html_url", ""),
                        }
                    )

            if len(all_matches) >= data.get("total_count", 0):
                break

            page += 1

    except requests.exceptions.RequestException as e:
        return {
            "formatted": f"Failed to connect to GitHub API: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    results = all_matches[:max_results]

    if not results:
        return {
            "formatted": f"No code matches found for query: {query}",
            "totalResults": 0,
            "resultsShared": 0,
        }

    # Format output
    lines_output = [f"**Found {len(results)} code matches:**\n"]

    for i, match in enumerate(results, 1):
        lines_output.append(f"{i}. **{match['repo']}:{match['path']}**")
        lines_output.append(
            f"   Lines: {match['line_start']}-{match['line_end']} | Ref: {match['ref'][:7]}"
        )
        lines_output.append(f"   URL: {match['url']}")

        # Show snippet (first 5 lines)
        snippet_lines = match["snippet"].split("\n")[:5]
        if snippet_lines:
            lines_output.append("   ```")
            for line in snippet_lines:
                lines_output.append(f"   {line}")
            if len(match["snippet"].split("\n")) > 5:
                lines_output.append("   ...")
            lines_output.append("   ```")
        lines_output.append("")

    return {
        "formatted": "\n".join(lines_output),
        "totalResults": len(results),
        "resultsShared": len(results),
    }


# Tool specification
GITHUB_SEARCH_CODE_TOOL_SPEC = {
    "name": "search_code",
    "description": (
        "Search for code patterns across GitHub with advanced glob filtering.\n\n"
        "Features:\n"
        "- Text or regex search\n"
        "- Repository glob patterns (e.g., 'github/*', '*/react')\n"
        "- File path glob patterns (e.g., '*.py', 'src/**/*.js')\n"
        "- Returns code snippets with line numbers\n"
        "- Direct URLs to matches\n\n"
        "## Examples:\n\n"
        "**Search for Python function definitions:**\n"
        "{'query': 'def search', 'path_glob': '*.py', 'max_results': 10}\n\n"
        "**Search for TODO comments in specific org:**\n"
        "{'query': 'TODO', 'repo_glob': 'github/*', 'max_results': 5}\n\n"
        "**Regex search for test functions:**\n"
        "{'query': r'func Test\\w+', 'path_glob': '*.go', 'regex': True}\n\n"
        "**Search in specific repo with path filter:**\n"
        "{'query': 'SearchCode', 'repo_glob': 'github/github-mcp-server', 'path_glob': '*.go'}\n\n"
        "**Find imports in TypeScript files:**\n"
        "{'query': 'import', 'path_glob': 'src/**/*.ts', 'repo_glob': 'facebook/*'}\n\n"
        "Perfect for finding code patterns, learning from examples, or exploring implementations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term or pattern to find in code. Required.",
            },
            "repo_glob": {
                "type": "string",
                "description": "Glob pattern to filter repositories (e.g., 'github/*', '*/react'). Optional.",
            },
            "path_glob": {
                "type": "string",
                "description": "Glob pattern to filter file paths (e.g., '*.py', 'src/**/*.js'). Optional.",
            },
            "regex": {
                "type": "boolean",
                "description": "If true, treat query as regular expression. Default: false.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return. Default: 20.",
            },
        },
        "required": ["query"],
    },
}


async def github_search_code_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        result = search_code(
            query=arguments["query"],
            repo_glob=arguments.get("repo_glob"),
            path_glob=arguments.get("path_glob"),
            regex=arguments.get("regex", False),
            max_results=arguments.get("max_results", 20),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error searching code: {str(e)}", False
