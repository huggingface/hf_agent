"""
GitHub Find Examples Tool

Finds examples, guides, and tutorials for a library using deterministic queries and heuristics.
"""

import asyncio
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    raise ImportError(
        "requests library is required. Install with: pip install requests"
    )

from agent.tools.types import ToolResult


@dataclass
class Example:
    """An example file with metadata and relevance score."""

    repo: str
    path: str
    ref: str
    url: str
    score: float
    reason: str
    repo_stars: int
    repo_updated: str
    file_size: int

    def to_dict(self):
        return asdict(self)


class GitHubAPIError(Exception):
    """Raised when GitHub API returns an error."""

    pass


# Path-based scoring weights
PATH_SCORES = {
    "README.md": 100,
    "readme.md": 100,
    "docs/": 80,
    "doc/": 80,
    "examples/": 90,
    "example/": 90,
    "notebooks/": 70,
    "notebook/": 70,
    "tutorials/": 85,
    "tutorial/": 85,
    "guides/": 85,
    "guide/": 85,
    "tests/": 40,
    "test/": 40,
    "demos/": 75,
    "demo/": 75,
    "samples/": 75,
    "sample/": 75,
}

# Content-based scoring keywords
CONTENT_KEYWORDS = {
    'if __name__ == "__main__"': 50,
    "if __name__ == '__main__'": 50,
    "quickstart": 60,
    "quick start": 60,
    "getting started": 60,
    "tutorial": 50,
    "example usage": 55,
    "usage example": 55,
    "how to use": 45,
    "basic example": 50,
    "simple example": 50,
}

# File extension preferences
PREFERRED_EXTENSIONS = {
    ".py": 10,
    ".ipynb": 15,
    ".md": 20,
    ".rst": 10,
    ".js": 10,
    ".ts": 10,
    ".go": 10,
    ".java": 10,
    ".cpp": 10,
    ".c": 10,
}


def _get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubAPIError(
            "GITHUB_TOKEN environment variable is required. "
            "Set it with: export GITHUB_TOKEN=your_token_here"
        )
    return token


def _execute_search(query: str, token: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Execute a GitHub code search query."""
    headers = {
        "Accept": "application/vnd.github.text-match+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    results = []
    page = 1
    per_page = min(100, limit)

    try:
        while len(results) < limit:
            params = {"q": query, "per_page": per_page, "page": page}
            url = "https://api.github.com/search/code"
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code != 200:
                break

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            for item in items:
                results.append(
                    {
                        "repo": item.get("repository", {}).get("full_name", ""),
                        "path": item.get("path", ""),
                        "sha": item.get("sha", ""),
                        "url": item.get("html_url", ""),
                        "size": item.get("size", 0),
                        "text_matches": item.get("text_matches", []),
                    }
                )

            if len(results) >= limit or len(items) < per_page:
                break

            page += 1

    except Exception:
        pass

    return results[:limit]


def _fetch_repo_metadata(repos: List[str], token: str) -> Dict[str, Dict[str, Any]]:
    """Fetch metadata for repositories."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    metadata = {}

    for repo in repos:
        try:
            url = f"https://api.github.com/repos/{repo}"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                metadata[repo] = {
                    "stars": data.get("stargazers_count", 0),
                    "updated_at": data.get("updated_at", ""),
                    "description": data.get("description", ""),
                }
        except Exception:
            continue

    return metadata


def _score_and_rank(
    results: List[Dict[str, Any]], library: str, token: str
) -> List[Example]:
    """Score results based on heuristics and rank them."""
    repos = list(set(r["repo"] for r in results))
    repo_metadata = _fetch_repo_metadata(repos, token)

    scored_examples = []

    for result in results:
        repo = result["repo"]
        path = result["path"]

        score = 0.0
        reasons = []

        # Path-based scoring
        path_lower = path.lower()
        for pattern, points in PATH_SCORES.items():
            if pattern.lower() in path_lower:
                score += points
                reasons.append(f"in {pattern}")
                break

        # File extension scoring
        for ext, points in PREFERRED_EXTENSIONS.items():
            if path_lower.endswith(ext):
                score += points
                break

        # Content-based scoring
        text_content = ""
        for match in result.get("text_matches", []):
            text_content += match.get("fragment", "").lower() + " "

        for keyword, points in CONTENT_KEYWORDS.items():
            if keyword.lower() in text_content:
                score += points
                reasons.append(f"contains '{keyword}'")

        # Repo-based scoring
        metadata = repo_metadata.get(repo, {})
        stars = metadata.get("stars", 0)
        updated = metadata.get("updated_at", "")

        if stars > 0:
            star_score = math.log10(stars + 1) * 10
            score += star_score

        # Recency bonus
        if updated:
            try:
                updated_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if datetime.now(updated_date.tzinfo) - updated_date < timedelta(
                    days=180
                ):
                    score += 20
                    reasons.append("recently updated")
            except Exception:
                pass

        # Filename quality
        filename = path.split("/")[-1].lower()
        if any(
            word in filename
            for word in ["example", "tutorial", "guide", "quickstart", "demo"]
        ):
            score += 30
            reasons.append("descriptive filename")

        # Size penalty
        if result["size"] > 100000:
            score *= 0.5
            reasons.append("large file")

        example = Example(
            repo=repo,
            path=path,
            ref=result["sha"],
            url=result["url"],
            score=score,
            reason=", ".join(reasons) if reasons else "matches library",
            repo_stars=stars,
            repo_updated=updated,
            file_size=result["size"],
        )

        scored_examples.append(example)

    scored_examples.sort(key=lambda x: x.score, reverse=True)
    return scored_examples


def _search_by_path(
    library: str, org: str, repo_scope: Optional[str], token: str
) -> List[Dict[str, Any]]:
    """Search for library in example/tutorial/docs directories."""
    results = []
    path_patterns = [
        "examples/",
        "example/",
        "docs/",
        "tutorials/",
        "notebooks/",
        "guides/",
    ]

    for path in path_patterns:
        query_parts = [f"org:{org}", f"{library}", f"path:{path}"]
        if repo_scope:
            query_parts[0] = f"repo:{org}/{repo_scope}"

        query = " ".join(query_parts)
        results.extend(_execute_search(query, token, limit=20))

    return results


def _search_by_content(
    library: str, org: str, repo_scope: Optional[str], token: str
) -> List[Dict[str, Any]]:
    """Search for library with specific content patterns."""
    results = []
    content_patterns = [
        f"{library} if __name__",
        f"{library} quickstart",
        f"{library} tutorial",
        f"{library} usage example",
    ]

    for pattern in content_patterns:
        query_parts = [f"org:{org}", pattern]
        if repo_scope:
            query_parts[0] = f"repo:{org}/{repo_scope}"

        query = " ".join(query_parts)
        results.extend(_execute_search(query, token, limit=15))

    return results


def _search_readmes(
    library: str, org: str, repo_scope: Optional[str], token: str
) -> List[Dict[str, Any]]:
    """Search for library mentions in README files."""
    query_parts = [f"org:{org}", f"{library}", "filename:README"]
    if repo_scope:
        query_parts[0] = f"repo:{org}/{repo_scope}"

    query = " ".join(query_parts)
    return _execute_search(query, token, limit=20)


def find_examples(
    library: str,
    org: str = "huggingface",
    repo_scope: Optional[str] = None,
    max_results: int = 10,
) -> List[Example]:
    """
    Find examples, guides, and tutorials for a library using deterministic queries.

    Uses a playbook of smart searches and heuristics to find canonical examples:
    - Prefers README.md, docs/**, examples/**, notebooks/**, tests/**
    - Prefers files with if __name__ == "__main__", "quickstart", "tutorial"
    - Prefers repos with higher stars and more recent updates

    Args:
        library: Library name to search for (e.g., "transformers", "torch")
        org: GitHub organization to search in (default: "huggingface")
        repo_scope: Optional specific repository (e.g., "transformers")
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of Example objects, ranked by relevance score
    """
    token = _get_github_token()

    all_results = []
    all_results.extend(_search_by_path(library, org, repo_scope, token))
    all_results.extend(_search_by_content(library, org, repo_scope, token))
    all_results.extend(_search_readmes(library, org, repo_scope, token))

    # Deduplicate
    seen = set()
    unique_results = []
    for result in all_results:
        key = (result["repo"], result["path"])
        if key not in seen:
            seen.add(key)
            unique_results.append(result)

    scored_examples = _score_and_rank(unique_results, library, token)
    return scored_examples[:max_results]


async def _async_call(func, *args, **kwargs):
    """Wrap synchronous calls for async context."""
    return await asyncio.to_thread(func, *args, **kwargs)


def _format_examples_table(examples: List[Example]) -> str:
    """Format examples as a markdown table."""
    if not examples:
        return "No examples found."

    lines = [
        "| Rank | File | Score | Stars | Reason |",
        "|------|------|-------|-------|--------|",
    ]

    for i, ex in enumerate(examples, 1):
        file_path = f"{ex.repo}/{ex.path}"
        if len(file_path) > 60:
            file_path = file_path[:57] + "..."
        reason = ex.reason if len(ex.reason) < 40 else ex.reason[:37] + "..."
        lines.append(
            f"| {i} | {file_path} | {ex.score:.1f} | {ex.repo_stars:,} | {reason} |"
        )

    return "\n".join(lines)


class FindExamplesTool:
    """Tool for finding examples and tutorials for libraries."""

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute find_examples operation."""
        library = params.get("library")
        if not library:
            return {
                "formatted": "Error: 'library' parameter is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

        org = params.get("org", "huggingface")
        repo_scope = params.get("repo_scope")
        max_results = params.get("max_results", 10)

        try:
            examples = await _async_call(
                find_examples,
                library=library,
                org=org,
                repo_scope=repo_scope,
                max_results=max_results,
            )

            if not examples:
                return {
                    "formatted": f"No examples found for '{library}' in {org}",
                    "totalResults": 0,
                    "resultsShared": 0,
                }

            table = _format_examples_table(examples)
            response = f"**Found {len(examples)} examples for '{library}' in {org}:**\n\n{table}"

            # Add URLs and suggest using read_file
            response += "\n\n**Top examples (use read_file to view):**\n"
            for i, ex in enumerate(examples[:3], 1):
                response += f"{i}. [{ex.repo}/{ex.path}]({ex.url})\n"
                response += f"   Use: read_file(repo='{ex.repo}', path='{ex.path}')\n"

            return {
                "formatted": response,
                "totalResults": len(examples),
                "resultsShared": len(examples),
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
FIND_EXAMPLES_TOOL_SPEC = {
    "name": "find_examples",
    "description": (
        "Find examples, guides, and tutorials for a library using deterministic queries and heuristics.\n\n"
        "Uses best practices retrieval without semantic search:\n"
        "- Prefers README.md, docs/**, examples/**, notebooks/**, tests/**\n"
        "- Prefers files with if __name__ == '__main__', 'quickstart', 'tutorial', 'usage'\n"
        "- Prefers repos with higher stars and more recent updates\n\n"
        "Returns a ranked list of canonical example files.\n\n"
        "Examples:\n"
        "- Find transformers examples: {'library': 'transformers', 'org': 'huggingface', 'max_results': 5}\n"
        "- Find torch examples in specific repo: {'library': 'torch', 'org': 'pytorch', 'repo_scope': 'examples'}\n\n"
        "Use read_file tool to view the content of returned files.\n\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "library": {
                "type": "string",
                "description": "Library name to search for (e.g., 'transformers', 'torch', 'react')",
            },
            "org": {
                "type": "string",
                "description": "GitHub organization to search in (default: 'huggingface')",
            },
            "repo_scope": {
                "type": "string",
                "description": "Optional specific repository to search within",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10)",
            },
        },
        "required": ["library"],
    },
}


async def find_examples_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router."""
    try:
        tool = FindExamplesTool()
        result = await tool.execute(arguments)
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error executing find_examples: {str(e)}", False
