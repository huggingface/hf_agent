"""
GitHub Read File Tool - Read file contents from any GitHub repository with line range support

Fetch exact file contents with metadata, supporting line ranges for efficient reading.
"""

import base64
import os
from typing import Any, Dict, Optional

import requests

from agent.tools.types import ToolResult


def read_file(
    repo: str,
    path: str,
    ref: str = "HEAD",
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
) -> ToolResult:
    """
    Read file contents from a GitHub repository with line range support.

    Args:
        repo: Repository in format "owner/repo" (e.g., "github/github-mcp-server")
        path: Path to file in repository (e.g., "pkg/github/search.go")
        ref: Git reference - branch name, tag, or commit SHA (default: "HEAD")
        line_start: Starting line number (1-indexed, inclusive)
        line_end: Ending line number (1-indexed, inclusive)

    Returns:
        ToolResult with file contents and metadata
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {
            "formatted": "Error: GITHUB_TOKEN environment variable is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    # Parse repo
    if "/" not in repo:
        return {
            "formatted": "Error: repo must be in format 'owner/repo'",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    owner, repo_name = repo.split("/", 1)

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    # Fetch file contents
    url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
    params = {}
    if ref and ref != "HEAD":
        params["ref"] = ref

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 404:
            return {
                "formatted": f"File not found: {path} in {repo} (ref: {ref})",
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

        # Check if it's a file
        if data.get("type") != "file":
            return {
                "formatted": f"Path {path} is not a file (type: {data.get('type')})",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

        # Decode content
        content_b64 = data.get("content", "")
        if content_b64:
            content_b64 = content_b64.replace("\n", "").replace(" ", "")
            content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        else:
            # For large files, fetch raw content
            raw_headers = {
                "Accept": "application/vnd.github.raw",
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {token}",
            }
            raw_response = requests.get(
                url, headers=raw_headers, params=params, timeout=30
            )
            if raw_response.status_code != 200:
                return {
                    "formatted": "Failed to fetch file content",
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True,
                }
            content = raw_response.text

        # Get metadata
        file_sha = data.get("sha")
        file_size = data.get("size", 0)

        # Process line ranges
        lines = content.split("\n")
        total_lines = len(lines)

        truncated = False
        message = None

        if line_start is None and line_end is None:
            # No range specified
            if total_lines > 300:
                line_start = 1
                line_end = 300
                truncated = True
                message = f"File has {total_lines} lines. Showing first 300 lines. Use line_start and line_end to view more."
            else:
                line_start = 1
                line_end = total_lines
        else:
            # Range specified
            if line_start is None:
                line_start = 1
            if line_end is None:
                line_end = total_lines

            # Validate range
            line_start = max(1, line_start)
            line_end = min(total_lines, line_end)
            if line_start > line_end:
                return {
                    "formatted": f"Invalid range: line_start ({line_start}) > line_end ({line_end})",
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True,
                }

        # Extract lines
        selected_lines = lines[line_start - 1 : line_end]
        selected_content = "\n".join(selected_lines)

        # Format output
        lines_output = [f"**File: {repo}/{path}**"]
        lines_output.append(f"SHA: {file_sha}")
        lines_output.append(f"Size: {file_size:,} bytes")
        lines_output.append(
            f"Lines: {line_start}-{line_end} of {total_lines} total lines"
        )
        if ref and ref != "HEAD":
            lines_output.append(f"Ref: {ref}")
        if truncated and message:
            lines_output.append(f"⚠️  {message}")
        lines_output.append("\n**Content:**")
        lines_output.append("```")
        lines_output.append(selected_content)
        lines_output.append("```")

        return {
            "formatted": "\n".join(lines_output),
            "totalResults": 1,
            "resultsShared": 1,
        }

    except requests.exceptions.RequestException as e:
        return {
            "formatted": f"Failed to connect to GitHub API: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }


# Tool specification
GITHUB_READ_FILE_TOOL_SPEC = {
    "name": "read_file",
    "description": (
        "Read file contents from any GitHub repository with precise line range control.\n\n"
        "Features:\n"
        "- Read entire files or specific line ranges\n"
        "- Auto-truncates large files to 300 lines (with warning)\n"
        "- Works with any branch, tag, or commit SHA\n"
        "- Returns file metadata (SHA, size, line count)\n"
        "- Handles both small and large files efficiently\n\n"
        "## Examples:\n\n"
        "**Read entire README:**\n"
        "{'repo': 'facebook/react', 'path': 'README.md'}\n\n"
        "**Read specific line range:**\n"
        "{'repo': 'torvalds/linux', 'path': 'kernel/sched/core.c', 'line_start': 100, 'line_end': 150}\n\n"
        "**Read from specific branch:**\n"
        "{'repo': 'python/cpython', 'path': 'Lib/ast.py', 'ref': 'main', 'line_start': 1, 'line_end': 50}\n\n"
        "**Read from specific commit:**\n"
        "{'repo': 'github/github-mcp-server', 'path': 'pkg/github/search.go', 'ref': 'abc123def'}\n\n"
        "Perfect for examining code, reading documentation, or investigating specific implementations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in format 'owner/repo' (e.g., 'github/github-mcp-server'). Required.",
            },
            "path": {
                "type": "string",
                "description": "Path to file in repository (e.g., 'src/index.js'). Required.",
            },
            "ref": {
                "type": "string",
                "description": "Git reference - branch name, tag, or commit SHA. Default: 'HEAD'.",
            },
            "line_start": {
                "type": "integer",
                "description": "Starting line number (1-indexed, inclusive). Optional.",
            },
            "line_end": {
                "type": "integer",
                "description": "Ending line number (1-indexed, inclusive). Optional.",
            },
        },
        "required": ["repo", "path"],
    },
}


async def github_read_file_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        result = read_file(
            repo=arguments["repo"],
            path=arguments["path"],
            ref=arguments.get("ref", "HEAD"),
            line_start=arguments.get("line_start"),
            line_end=arguments.get("line_end"),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error reading file: {str(e)}", False
