"""
GitHub List Repos Tool

Lists repositories for a user or organization with sorting options.
"""

import asyncio
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional

try:
    import requests
except ImportError:
    raise ImportError(
        "requests library is required. Install with: pip install requests"
    )

from agent.tools.types import ToolResult


@dataclass
class Repository:
    """Repository information."""

    id: int
    name: str
    full_name: str
    description: Optional[str]
    html_url: str
    language: Optional[str]
    stars: int
    forks: int
    open_issues: int
    private: bool
    fork: bool
    archived: bool
    default_branch: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    topics: Optional[List[str]] = None

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


def _fetch_repositories(
    query: str, sort: str, order: str, limit: Optional[int], token: str
) -> List[Repository]:
    """Fetch repositories from GitHub Search API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    all_repos = []
    page = 1
    per_page = min(100, limit) if limit else 100

    while True:
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "page": page,
            "per_page": per_page,
        }

        url = "https://api.github.com/search/repositories"

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code != 200:
                break

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            for item in items:
                repo = Repository(
                    id=item.get("id"),
                    name=item.get("name"),
                    full_name=item.get("full_name"),
                    description=item.get("description"),
                    html_url=item.get("html_url"),
                    language=item.get("language"),
                    stars=item.get("stargazers_count", 0),
                    forks=item.get("forks_count", 0),
                    open_issues=item.get("open_issues_count", 0),
                    private=item.get("private", False),
                    fork=item.get("fork", False),
                    archived=item.get("archived", False),
                    default_branch=item.get("default_branch", "main"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    topics=item.get("topics", []),
                )
                all_repos.append(repo)

            if limit and len(all_repos) >= limit:
                all_repos = all_repos[:limit]
                break

            total_count = data.get("total_count", 0)
            if len(all_repos) >= total_count:
                break

            if page * per_page >= 1000:
                break

            page += 1

        except requests.exceptions.RequestException:
            break

    return all_repos


def list_repos(
    owner: str,
    owner_type: Literal["user", "org"] = "org",
    sort: Literal["stars", "forks", "updated", "created"] = "stars",
    order: Literal["asc", "desc"] = "desc",
    limit: Optional[int] = None,
) -> List[Repository]:
    """
    List repositories for a user or organization using GitHub Search API.

    Backed by https://api.github.com/search/repositories?q=org:huggingface&sort=stars&order=desc
    or can use GraphQL + client-side sort.

    Args:
        owner: GitHub username or organization name
        owner_type: Whether the owner is a "user" or "org" (default: "org")
        sort: Sort field - "stars", "forks", "updated", or "created" (default: "stars")
        order: Sort order - "asc" or "desc" (default: "desc")
        limit: Maximum number of repositories to return (default: no limit)

    Returns:
        List of Repository objects
    """
    token = _get_github_token()

    if owner_type == "org":
        query = f"org:{owner}"
    else:
        query = f"user:{owner}"

    repos = _fetch_repositories(
        query=query, sort=sort, order=order, limit=limit, token=token
    )

    return repos


async def _async_call(func, *args, **kwargs):
    """Wrap synchronous calls for async context."""
    return await asyncio.to_thread(func, *args, **kwargs)


def _format_repos_table(repos: List[Repository]) -> str:
    """Format repositories as a markdown table."""
    if not repos:
        return "No repositories found."

    lines = [
        "| Repo | Stars | Forks | Language | Description |",
        "|------|-------|-------|----------|-------------|",
    ]

    for repo in repos:
        desc = repo.description or "N/A"
        if len(desc) > 50:
            desc = desc[:47] + "..."
        lang = repo.language or "N/A"
        lines.append(
            f"| {repo.full_name} | {repo.stars:,} | {repo.forks:,} | {lang} | {desc} |"
        )

    return "\n".join(lines)


class ListReposTool:
    """Tool for listing GitHub repositories."""

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute list_repos operation."""
        owner = params.get("owner")
        if not owner:
            return {
                "formatted": "Error: 'owner' parameter is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

        owner_type = params.get("owner_type", "org")
        sort = params.get("sort", "stars")
        order = params.get("order", "desc")
        limit = params.get("limit")

        try:
            repos = await _async_call(
                list_repos,
                owner=owner,
                owner_type=owner_type,
                sort=sort,
                order=order,
                limit=limit,
            )

            if not repos:
                return {
                    "formatted": f"No repositories found for {owner}",
                    "totalResults": 0,
                    "resultsShared": 0,
                }

            table = _format_repos_table(repos)
            response = f"**Found {len(repos)} repositories for {owner} (sorted by {sort}, {order}):**\n\n{table}"

            # Add links to top repos
            response += "\n\n**Top repositories:**\n"
            for i, repo in enumerate(repos[:5], 1):
                response += (
                    f"{i}. [{repo.full_name}]({repo.html_url}) - ⭐ {repo.stars:,}\n"
                )

            return {
                "formatted": response,
                "totalResults": len(repos),
                "resultsShared": len(repos),
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
LIST_REPOS_TOOL_SPEC = {
    "name": "list_repos",
    "description": (
        "List repositories for a user or organization with sorting options.\n\n"
        "Backed by GitHub Search API: https://api.github.com/search/repositories?q=org:huggingface&sort=stars&order=desc\n\n"
        "Examples:\n"
        "- Top 10 starred repos: {'owner': 'huggingface', 'sort': 'stars', 'limit': 10}\n"
        "- Recently updated: {'owner': 'microsoft', 'sort': 'updated', 'order': 'desc', 'limit': 5}\n"
        "- User repos: {'owner': 'torvalds', 'owner_type': 'user', 'sort': 'stars'}\n"
        "- All repos: {'owner': 'pytorch', 'sort': 'forks'}\n\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "GitHub username or organization name (e.g., 'huggingface', 'torvalds')",
            },
            "owner_type": {
                "type": "string",
                "enum": ["user", "org"],
                "description": "Whether the owner is a 'user' or 'org' (default: 'org')",
            },
            "sort": {
                "type": "string",
                "enum": ["stars", "forks", "updated", "created"],
                "description": "Sort field: 'stars', 'forks', 'updated', or 'created' (default: 'stars')",
            },
            "order": {
                "type": "string",
                "enum": ["asc", "desc"],
                "description": "Sort order: 'asc' or 'desc' (default: 'desc')",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of repositories to return (default: no limit, returns all)",
            },
        },
        "required": ["owner"],
    },
}


async def list_repos_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router."""
    try:
        tool = ListReposTool()
        result = await tool.execute(arguments)
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error executing list_repos: {str(e)}", False
