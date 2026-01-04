"""
GitHub Find Examples Tool - Discover examples, tutorials, and guides for any library

Uses intelligent heuristics to find the best learning resources on GitHub.
"""

import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from agent.tools.types import ToolResult


def _search_github_code(
    query: str, token: str, limit: int = 20
) -> List[Dict[str, Any]]:
    """Execute a GitHub code search query"""
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
            response = requests.get(
                "https://api.github.com/search/code",
                headers=headers,
                params=params,
                timeout=30,
            )

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
    """Fetch star count and update date for repositories"""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    metadata = {}
    for repo in repos:
        try:
            response = requests.get(
                f"https://api.github.com/repos/{repo}", headers=headers, timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                metadata[repo] = {
                    "stars": data.get("stargazers_count", 0),
                    "updated_at": data.get("updated_at", ""),
                }
        except Exception:
            continue

    return metadata


def _score_example(
    result: Dict[str, Any], metadata: Dict[str, Dict[str, Any]]
) -> tuple[float, str]:
    """Score an example based on multiple heuristics"""
    path = result["path"].lower()
    repo = result["repo"]
    score = 0.0
    reasons = []

    # Path-based scoring
    if "readme.md" in path:
        score += 100
        reasons.append("README file")
    elif "examples/" in path or "example/" in path:
        score += 90
        reasons.append("in examples/")
    elif "tutorials/" in path or "tutorial/" in path:
        score += 85
        reasons.append("in tutorials/")
    elif "docs/" in path or "doc/" in path:
        score += 80
        reasons.append("in docs/")
    elif "notebooks/" in path or "notebook/" in path:
        score += 70
        reasons.append("in notebooks/")

    # Extension scoring
    if path.endswith(".ipynb"):
        score += 15
    elif path.endswith(".md"):
        score += 20
    elif path.endswith(".py"):
        score += 10

    # Content keywords from text matches
    text_content = ""
    for match in result.get("text_matches", []):
        text_content += match.get("fragment", "").lower() + " "

    if 'if __name__ == "__main__"' in text_content:
        score += 50
        reasons.append("runnable example")
    if "quickstart" in text_content or "getting started" in text_content:
        score += 60
        reasons.append("quickstart guide")
    if "tutorial" in text_content:
        score += 50
        reasons.append("tutorial content")

    # Repository metadata scoring
    repo_meta = metadata.get(repo, {})
    stars = repo_meta.get("stars", 0)
    updated_at = repo_meta.get("updated_at", "")

    # Star-based score (logarithmic)
    if stars > 0:
        score += math.log10(stars + 1) * 10

    # Recency bonus (updated in last 6 months)
    if updated_at:
        try:
            updated_date = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            if datetime.now(updated_date.tzinfo) - updated_date < timedelta(days=180):
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

    # Size penalty for very large files
    if result["size"] > 100000:
        score *= 0.5
        reasons.append("large file")

    return score, ", ".join(reasons) if reasons else "matches library"


def find_examples(
    library: str,
    org: str = "huggingface",
    repo_scope: Optional[str] = None,
    max_results: int = 10,
) -> ToolResult:
    """
    Find examples, tutorials, and guides for a library using intelligent search.

    Args:
        library: Library name (e.g., "transformers", "torch", "react")
        org: GitHub organization to search in
        repo_scope: Optional specific repository name
        max_results: Maximum number of results (default 10)

    Returns:
        ToolResult with ranked examples
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {
            "formatted": "Error: GITHUB_TOKEN environment variable is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    # Build search queries
    all_results = []

    # Query 1: Search in example directories
    for path_pattern in ["examples/", "docs/", "tutorials/", "notebooks/"]:
        query_parts = [f"org:{org}", library, f"path:{path_pattern}"]
        if repo_scope:
            query_parts[0] = f"repo:{org}/{repo_scope}"
        query = " ".join(query_parts)
        all_results.extend(_search_github_code(query, token, limit=20))

    # Query 2: Search README files
    query_parts = [f"org:{org}", library, "filename:README"]
    if repo_scope:
        query_parts[0] = f"repo:{org}/{repo_scope}"
    query = " ".join(query_parts)
    all_results.extend(_search_github_code(query, token, limit=20))

    # Deduplicate
    seen = set()
    unique_results = []
    for result in all_results:
        key = (result["repo"], result["path"])
        if key not in seen:
            seen.add(key)
            unique_results.append(result)

    if not unique_results:
        return {
            "formatted": f"No examples found for '{library}' in {org}",
            "totalResults": 0,
            "resultsShared": 0,
        }

    # Fetch repo metadata
    repos = list(set(r["repo"] for r in unique_results))
    metadata = _fetch_repo_metadata(repos, token)

    # Score and rank
    scored = []
    for result in unique_results:
        score, reason = _score_example(result, metadata)
        repo_meta = metadata.get(result["repo"], {})
        scored.append(
            {
                "repo": result["repo"],
                "path": result["path"],
                "url": result["url"],
                "score": score,
                "reason": reason,
                "stars": repo_meta.get("stars", 0),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:max_results]

    # Format output
    lines = [f"**Found {len(top_results)} examples for '{library}' in {org}:**\n"]

    for i, ex in enumerate(top_results, 1):
        lines.append(f"{i}. **{ex['repo']}/{ex['path']}**")
        lines.append(f"   Score: {ex['score']:.1f} | ⭐ {ex['stars']:,} stars")
        lines.append(f"   Reason: {ex['reason']}")
        lines.append(f"   URL: {ex['url']}\n")

    return {
        "formatted": "\n".join(lines),
        "totalResults": len(top_results),
        "resultsShared": len(top_results),
    }


# Tool specification
GITHUB_FIND_EXAMPLES_TOOL_SPEC = {
    "name": "find_examples",
    "description": (
        "Find examples, tutorials, and guides for any library on GitHub using intelligent heuristic-based search.\n\n"
        "Uses multiple search strategies and ranks results by:\n"
        "- Path quality (examples/, docs/, tutorials/ directories)\n"
        "- Content keywords (quickstart, tutorial, runnable code)\n"
        "- Repository popularity (stars, recent updates)\n"
        "- File characteristics (size, extension, descriptive names)\n\n"
        "## Examples:\n\n"
        "**Find transformers examples in Hugging Face:**\n"
        "{'library': 'transformers', 'org': 'huggingface', 'max_results': 5}\n\n"
        "**Find PyTorch examples in specific repo:**\n"
        "{'library': 'torch', 'org': 'pytorch', 'repo_scope': 'examples', 'max_results': 10}\n\n"
        "**Find React quickstart guides:**\n"
        "{'library': 'react quickstart', 'org': 'facebook', 'max_results': 3}\n\n"
        "Returns ranked list with file paths, scores, star counts, and direct URLs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "library": {
                "type": "string",
                "description": "Library name to search for (e.g., 'transformers', 'torch', 'react'). Required.",
            },
            "org": {
                "type": "string",
                "description": "GitHub organization to search in. Default: 'huggingface'.",
            },
            "repo_scope": {
                "type": "string",
                "description": "Optional specific repository name within the org (e.g., 'transformers').",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return. Default: 10.",
            },
        },
        "required": ["library"],
    },
}


async def github_find_examples_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        result = find_examples(
            library=arguments["library"],
            org=arguments.get("org", "huggingface"),
            repo_scope=arguments.get("repo_scope"),
            max_results=arguments.get("max_results", 10),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error finding examples: {str(e)}", False
