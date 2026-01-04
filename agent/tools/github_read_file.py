"""
GitHub Read File Tool

Reads file contents from a GitHub repository with line range support.
"""

import asyncio
import base64
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

try:
    import requests
except ImportError:
    raise ImportError(
        "requests library is required. Install with: pip install requests"
    )

from agent.tools.types import ToolResult


@dataclass
class FileContents:
    """File contents with metadata."""

    content: str
    sha: str
    path: str
    size: int
    last_modified: Optional[str]
    last_commit_sha: Optional[str]
    line_start: int
    line_end: int
    total_lines: int
    truncated: bool
    message: Optional[str] = None

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


def _fetch_raw_content(owner: str, repo: str, path: str, ref: str, token: str) -> str:
    """Fetch raw file content for large files."""
    headers = {
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    params = {"ref": ref}

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        raise GitHubAPIError(
            f"Failed to fetch raw content: HTTP {response.status_code}"
        )

    return response.text


def _get_last_commit_info(
    owner: str, repo: str, path: str, ref: Optional[str], token: str
) -> Tuple[Optional[str], Optional[str]]:
    """Get last commit information for a specific file."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"path": path, "per_page": 1}

    if ref and ref != "HEAD":
        params["sha"] = ref

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 200:
            commits = response.json()
            if commits:
                commit = commits[0]
                commit_sha = commit.get("sha")
                commit_date = commit.get("commit", {}).get("committer", {}).get("date")
                return commit_date, commit_sha

    except Exception:
        pass

    return None, None


def _fetch_file_contents(
    owner: str,
    repo: str,
    path: str,
    ref: str,
    line_start: Optional[int],
    line_end: Optional[int],
    token: str,
) -> FileContents:
    """Fetch file contents from GitHub API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    params = {}

    if ref and ref != "HEAD":
        params["ref"] = ref

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 404:
            raise GitHubAPIError(
                f"File not found: {path} in {owner}/{repo} (ref: {ref})"
            )

        if response.status_code != 200:
            error_msg = f"GitHub API error (status {response.status_code})"
            try:
                error_data = response.json()
                if "message" in error_data:
                    error_msg += f": {error_data['message']}"
            except Exception:
                pass
            raise GitHubAPIError(error_msg)

        data = response.json()

        if data.get("type") != "file":
            raise GitHubAPIError(
                f"Path {path} is not a file (type: {data.get('type')})"
            )

        file_sha = data.get("sha")
        file_size = data.get("size", 0)

        # Decode content
        content_b64 = data.get("content", "")
        if content_b64:
            content_b64 = content_b64.replace("\n", "").replace(" ", "")
            content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        else:
            content = _fetch_raw_content(owner, repo, path, ref or "HEAD", token)

    except requests.exceptions.RequestException as e:
        raise GitHubAPIError(f"Failed to connect to GitHub API: {e}")

    # Get last commit info
    last_modified, last_commit_sha = _get_last_commit_info(
        owner, repo, path, ref, token
    )

    # Process line ranges
    lines = content.split("\n")
    total_lines = len(lines)

    truncated = False
    message = None

    if line_start is None and line_end is None:
        if total_lines > 300:
            line_start = 1
            line_end = 300
            truncated = True
            message = (
                f"File has {total_lines} lines. Returned only the first 300 lines. "
                f"To view more, use the line_start and line_end parameters."
            )
        else:
            line_start = 1
            line_end = total_lines
    else:
        if line_start is None:
            line_start = 1
        if line_end is None:
            line_end = total_lines

        if line_start < 1:
            line_start = 1
        if line_end > total_lines:
            line_end = total_lines
        if line_start > line_end:
            raise ValueError(
                f"line_start ({line_start}) cannot be greater than line_end ({line_end})"
            )

    selected_lines = lines[line_start - 1 : line_end]
    selected_content = "\n".join(selected_lines)

    return FileContents(
        content=selected_content,
        sha=file_sha,
        path=path,
        size=file_size,
        last_modified=last_modified,
        last_commit_sha=last_commit_sha,
        line_start=line_start,
        line_end=line_end,
        total_lines=total_lines,
        truncated=truncated,
        message=message,
    )


def read_file(
    repo: str,
    path: str,
    ref: str = "HEAD",
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
) -> FileContents:
    """
    Read file contents from a GitHub repository.

    Returns raw file text plus metadata (commit SHA, last modified).
    If file is more than 300 lines and no line range is specified,
    returns only the first 300 lines with a message.

    Args:
        repo: Repository in format "owner/repo" (e.g., "huggingface/transformers")
        path: Path to file in repository (e.g., "README.md")
        ref: Git reference - branch name, tag, or commit SHA (default: "HEAD")
        line_start: Starting line number (1-indexed, inclusive)
        line_end: Ending line number (1-indexed, inclusive)

    Returns:
        FileContents object with content and metadata
    """
    if "/" not in repo:
        raise ValueError("repo must be in format 'owner/repo'")

    owner, repo_name = repo.split("/", 1)
    token = _get_github_token()

    return _fetch_file_contents(
        owner=owner,
        repo=repo_name,
        path=path,
        ref=ref,
        line_start=line_start,
        line_end=line_end,
        token=token,
    )


async def _async_call(func, *args, **kwargs):
    """Wrap synchronous calls for async context."""
    return await asyncio.to_thread(func, *args, **kwargs)


class ReadFileTool:
    """Tool for reading files from GitHub repositories."""

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute read_file operation."""
        repo = params.get("repo")
        path = params.get("path")

        if not repo or not path:
            return {
                "formatted": "Error: 'repo' and 'path' parameters are required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

        ref = params.get("ref", "HEAD")
        line_start = params.get("line_start")
        line_end = params.get("line_end")

        try:
            file_contents = await _async_call(
                read_file,
                repo=repo,
                path=path,
                ref=ref,
                line_start=line_start,
                line_end=line_end,
            )

            response = f"**File: {file_contents.path}**\n"
            response += f"**Repo: {repo}**\n"
            response += f"**Lines:** {file_contents.line_start}-{file_contents.line_end} of {file_contents.total_lines}\n"
            response += f"**SHA:** {file_contents.sha}\n"

            if file_contents.last_modified:
                response += f"**Last modified:** {file_contents.last_modified}\n"

            if file_contents.message:
                response += f"\n⚠️ {file_contents.message}\n"

            response += f"\n```\n{file_contents.content}\n```"

            return {
                "formatted": response,
                "totalResults": 1,
                "resultsShared": 1,
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
READ_FILE_TOOL_SPEC = {
    "name": "read_file",
    "description": (
        "Read file contents from a GitHub repository.\n\n"
        "Returns raw file text plus metadata (commit SHA, last modified).\n"
        "If file is more than 300 lines, returns only the first 300 lines and includes line_start and line_end indexes.\n"
        "Use line_start and line_end parameters to view specific line ranges.\n\n"
        "Examples:\n"
        "- Read README: {'repo': 'huggingface/transformers', 'path': 'README.md'}\n"
        "- Read specific lines: {'repo': 'huggingface/transformers', 'path': 'src/transformers/__init__.py', 'line_start': 1, 'line_end': 50}\n"
        "- Read from branch: {'repo': 'torvalds/linux', 'path': 'MAINTAINERS', 'ref': 'master', 'line_start': 1, 'line_end': 20}\n\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in format 'owner/repo' (e.g., 'huggingface/transformers')",
            },
            "path": {
                "type": "string",
                "description": "Path to file in repository (e.g., 'README.md', 'src/main.py')",
            },
            "ref": {
                "type": "string",
                "description": "Git reference: branch name, tag, or commit SHA (default: 'HEAD')",
            },
            "line_start": {
                "type": "integer",
                "description": "Starting line number (1-indexed, inclusive). Use to read specific range.",
            },
            "line_end": {
                "type": "integer",
                "description": "Ending line number (1-indexed, inclusive). Use to read specific range.",
            },
        },
        "required": ["repo", "path"],
    },
}


async def read_file_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router."""
    try:
        tool = ReadFileTool()
        result = await tool.execute(arguments)
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error executing read_file: {str(e)}", False
