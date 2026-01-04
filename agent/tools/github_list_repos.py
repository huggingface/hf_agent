"""
GitHub List Repositories Tool - List and sort repositories for any user or organization

Efficiently discover repositories with flexible sorting options.
"""

import os
from typing import Any, Dict, Literal, Optional

import requests

from agent.tools.types import ToolResult


def list_repos(
    owner: str,
    owner_type: Literal["user", "org"] = "org",
    sort: Literal["stars", "forks", "updated", "created"] = "stars",
    order: Literal["asc", "desc"] = "desc",
    limit: Optional[int] = None,
) -> ToolResult:
    """
    List repositories for a user or organization using GitHub Search API.

    Args:
        owner: GitHub username or organization name
        owner_type: Whether the owner is a "user" or "org" (default: "org")
        sort: Sort field - "stars", "forks", "updated", or "created"
        order: Sort order - "asc" or "desc" (default: "desc")
        limit: Maximum number of repositories to return

    Returns:
        ToolResult with repository information
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {
            "formatted": "Error: GITHUB_TOKEN environment variable is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    # Build search query
    query = f"org:{owner}" if owner_type == "org" else f"user:{owner}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    all_repos = []
    page = 1
    per_page = min(100, limit) if limit else 100

    try:
        while True:
            params = {
                "q": query,
                "sort": sort,
                "order": order,
                "page": page,
                "per_page": per_page,
            }

            response = requests.get(
                "https://api.github.com/search/repositories",
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
                all_repos.append(
                    {
                        "name": item.get("name"),
                        "full_name": item.get("full_name"),
                        "description": item.get("description"),
                        "html_url": item.get("html_url"),
                        "language": item.get("language"),
                        "stars": item.get("stargazers_count", 0),
                        "forks": item.get("forks_count", 0),
                        "open_issues": item.get("open_issues_count", 0),
                        "topics": item.get("topics", []),
                        "updated_at": item.get("updated_at"),
                    }
                )

            # Check limits
            if limit and len(all_repos) >= limit:
                all_repos = all_repos[:limit]
                break

            total_count = data.get("total_count", 0)
            if len(all_repos) >= total_count or page * per_page >= 1000:
                break

            page += 1

    except requests.exceptions.RequestException as e:
        return {
            "formatted": f"Failed to connect to GitHub API: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    if not all_repos:
        return {
            "formatted": f"No repositories found for {owner_type} '{owner}'",
            "totalResults": 0,
            "resultsShared": 0,
        }

    # Format output
    lines = [f"**Found {len(all_repos)} repositories for {owner}:**\n"]

    for i, repo in enumerate(all_repos, 1):
        lines.append(f"{i}. **{repo['full_name']}**")
        lines.append(
            f"   ⭐ {repo['stars']:,} stars | 🍴 {repo['forks']:,} forks | Language: {repo['language'] or 'N/A'}"
        )
        if repo["description"]:
            desc = (
                repo["description"][:100] + "..."
                if len(repo["description"]) > 100
                else repo["description"]
            )
            lines.append(f"   {desc}")
        lines.append(f"   URL: {repo['html_url']}")
        if repo["topics"]:
            lines.append(f"   Topics: {', '.join(repo['topics'][:5])}")
        lines.append("")

    return {
        "formatted": "\n".join(lines),
        "totalResults": len(all_repos),
        "resultsShared": len(all_repos),
    }


# Tool specification
GITHUB_LIST_REPOS_TOOL_SPEC = {
    "name": "list_repos",
    "description": (
        "List and sort repositories for any GitHub user or organization.\n\n"
        "Uses GitHub Search API for efficient sorting by stars, forks, update date, or creation date.\n"
        "Returns comprehensive repository information including:\n"
        "- Stars, forks, and open issues count\n"
        "- Primary programming language\n"
        "- Repository topics/tags\n"
        "- Last update timestamp\n"
        "- Direct URLs\n\n"
        "## Examples:\n\n"
        "**List top 10 starred Hugging Face repos:**\n"
        "{'owner': 'huggingface', 'owner_type': 'org', 'sort': 'stars', 'limit': 10}\n\n"
        "**List recently updated Microsoft repos:**\n"
        "{'owner': 'microsoft', 'sort': 'updated', 'order': 'desc', 'limit': 5}\n\n"
        "**List all repos for a user:**\n"
        "{'owner': 'torvalds', 'owner_type': 'user', 'sort': 'stars'}\n\n"
        "**Find most forked Google repos:**\n"
        "{'owner': 'google', 'sort': 'forks', 'order': 'desc', 'limit': 20}\n\n"
        "Perfect for discovering popular projects, finding active repositories, or exploring an organization's work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "GitHub username or organization name. Required.",
            },
            "owner_type": {
                "type": "string",
                "enum": ["user", "org"],
                "description": "Whether the owner is a 'user' or 'org'. Default: 'org'.",
            },
            "sort": {
                "type": "string",
                "enum": ["stars", "forks", "updated", "created"],
                "description": "Sort field. Options: 'stars', 'forks', 'updated', 'created'. Default: 'stars'.",
            },
            "order": {
                "type": "string",
                "enum": ["asc", "desc"],
                "description": "Sort order. Options: 'asc', 'desc'. Default: 'desc'.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of repositories to return. No limit if not specified.",
            },
        },
        "required": ["owner"],
    },
}


async def github_list_repos_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        result = list_repos(
            owner=arguments["owner"],
            owner_type=arguments.get("owner_type", "org"),
            sort=arguments.get("sort", "stars"),
            order=arguments.get("order", "desc"),
            limit=arguments.get("limit"),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error listing repositories: {str(e)}", False
