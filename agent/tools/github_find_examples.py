"""
GitHub Find Examples Tool - Discover examples, tutorials, and guides for any library

Lists all files in a repository and performs deterministic keyword search.
"""

import os
from typing import Any, Dict, List

import requests
from thefuzz import fuzz

from agent.tools.types import ToolResult

# Global list of example-related keywords for fuzzy matching
EXAMPLE_PATTERNS = [
    # Core example patterns
    "examples",
    "example",
    "samples",
    "sample",
    "demos",
    "demo",
    # Tutorial/learning patterns
    "tutorials",
    "tutorial",
    "guides",
    "guide",
    "quickstart",
    "getting-started",
    "getting_started",
    "howto",
    "how-to",
    "walkthroughs",
    "walkthrough",
    # Cookbook/recipe patterns
    "cookbook",
    "cookbooks",
    "recipes",
    "recipe",
    # Notebook patterns (common in ML/data science)
    "notebooks",
    "notebook",
    "ipynb",
    # Starter/template patterns
    "starter",
    "starters",
    "templates",
    "template",
    "boilerplate",
    # Snippet/use-case patterns
    "snippets",
    "snippet",
    "use-cases",
    "usecases",
    "use_cases",
    # Showcase/playground patterns
    "showcase",
    "playground",
    "sandbox",
    # Script patterns
    "scripts",
]


def _get_repo_tree(org: str, repo: str, token: str) -> tuple[List[Dict[str, Any]], str]:
    """Get all files in a repository recursively. Returns (files, error_message)"""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    full_repo = f"{org}/{repo}"

    # Get default branch
    try:
        response = requests.get(
            f"https://api.github.com/repos/{full_repo}", headers=headers, timeout=10
        )
        if response.status_code == 404:
            return [], "not_found"
        if response.status_code != 200:
            return [], f"API error: {response.status_code}"

        repo_data = response.json()
        default_branch = repo_data.get("default_branch", "main")
    except Exception as e:
        return [], f"Error fetching repo: {str(e)}"

    # Get repository tree recursively
    try:
        response = requests.get(
            f"https://api.github.com/repos/{full_repo}/git/trees/{default_branch}",
            headers=headers,
            params={"recursive": "1"},
            timeout=30,
        )
        if response.status_code != 200:
            return [], f"Error fetching tree: {response.status_code}"

        data = response.json()
        tree = data.get("tree", [])

        # Filter to only include files (not directories)
        files = [
            {
                "path": item["path"],
                "ref": item["sha"],
                "size": item.get("size", 0),
                "url": f"https://github.com/{full_repo}/blob/{default_branch}/{item['path']}",
            }
            for item in tree
            if item["type"] == "blob"
        ]

        return files, ""
    except Exception as e:
        return [], f"Error processing tree: {str(e)}"


def _search_similar_repos(org: str, repo: str, token: str) -> List[Dict[str, Any]]:
    """Search for similar repository names in the organization"""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    # Search for repos in the org with similar name
    query = f"org:{org} {repo}"

    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 10},
            timeout=30,
        )

        if response.status_code != 200:
            return []

        data = response.json()
        items = data.get("items", [])

        return [
            {
                "name": item.get("name"),
                "full_name": item.get("full_name"),
                "description": item.get("description"),
                "stars": item.get("stargazers_count", 0),
                "url": item.get("html_url"),
            }
            for item in items
        ]
    except Exception:
        return []


def _score_against_example_patterns(file_path: str) -> int:
    """Score file against example patterns using token_set_ratio"""
    scores = []
    for pattern in EXAMPLE_PATTERNS:
        score = fuzz.token_set_ratio(pattern.lower(), file_path.lower())
        scores.append(score)
    return max(scores) if scores else 0


def _score_against_keyword(file_path: str, keyword: str) -> int:
    """Calculate fuzzy match score for a file path against a keyword"""
    # Use partial_ratio for substring matching (good for paths)
    # Also check token_set_ratio for word-level matching
    partial_score = fuzz.partial_ratio(keyword.lower(), file_path.lower())
    token_score = fuzz.token_set_ratio(keyword.lower(), file_path.lower())

    # Return the higher of the two
    return max(partial_score, token_score)


def _handle_repo_tree_errors(
    all_files: List[Dict[str, Any]],
    error: str,
    org: str,
    repo: str,
    token: str,
) -> ToolResult | None:
    """Handle errors from repo tree fetch. Returns ToolResult if error, None if OK."""
    if error == "not_found":
        similar_repos = _search_similar_repos(org, repo, token)

        if not similar_repos:
            return {
                "formatted": f"Repository '{org}/{repo}' not found and no similar repositories found.",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

        # Format similar repos
        lines = [f"**Repository '{org}/{repo}' not found. Similar repositories:**\n"]
        for i, r in enumerate(similar_repos, 1):
            lines.append(f"{i}. **{r['full_name']}** (⭐ {r['stars']:,} stars)")
            if r["description"]:
                desc = (
                    r["description"][:100] + "..."
                    if len(r["description"]) > 100
                    else r["description"]
                )
                lines.append(f"   {desc}")
            lines.append(f"   {r['url']}\n")

        return {
            "formatted": "\n".join(lines),
            "totalResults": len(similar_repos),
            "resultsShared": len(similar_repos),
            "isError": True,
        }

    if error:
        return {
            "formatted": f"Error accessing repository '{org}/{repo}': {error}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    if not all_files:
        return {
            "formatted": f"No files found in repository '{org}/{repo}'",
            "totalResults": 0,
            "resultsShared": 0,
        }

    return None


def find_examples(
    keyword: str = "",
    repo: str = "",
    org: str = "huggingface",
    max_results: int = 10,
    min_score: int = 80,
) -> ToolResult:
    """
    Find example files in a repository using fuzzy matching.

    Args:
        keyword: Keyword to fuzzy match against file paths (e.g., "grpo")
        repo: Repository name (e.g., "trl")
        org: GitHub organization (default: "huggingface")
        max_results: Maximum number of results (default 50)
        min_score: Minimum fuzzy match score (0-100, default 60)

    Returns:
        ToolResult with matching files, or similar repos if repo not found
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {
            "formatted": "Error: GITHUB_TOKEN environment variable is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    if not repo:
        return {
            "formatted": "Error: repo parameter is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    # Get all files in the repository
    all_files, error = _get_repo_tree(org, repo, token)

    # Handle errors (not found, API errors, empty repo)
    if error_result := _handle_repo_tree_errors(all_files, error, org, repo, token):
        return error_result

    # Step 1: Filter files by example patterns (score >= 60)
    example_threshold = 60
    example_files = []
    for file in all_files:
        example_score = _score_against_example_patterns(file["path"])
        if example_score >= example_threshold:
            example_files.append({**file, "example_score": example_score})

    if not example_files:
        return {
            "formatted": f"No example files found in {org}/{repo} (no files match example patterns with score >= {example_threshold}).",
            "totalResults": 0,
            "resultsShared": 0,
        }

    # Step 2: If keyword provided, score and filter by keyword
    if keyword:
        scored_files = []
        for file in example_files:
            keyword_score = _score_against_keyword(file["path"], keyword)
            if keyword_score >= min_score:
                scored_files.append({**file, "score": keyword_score})

        if not scored_files:
            return {
                "formatted": f"No files found in {org}/{repo} matching keyword '{keyword}' (min score: {min_score}) among {len(example_files)} example files.",
                "totalResults": 0,
                "resultsShared": 0,
            }
    else:
        # No keyword: use example pattern scores
        scored_files = [
            {**file, "score": file["example_score"]}
            for file in example_files
            if file["example_score"] >= min_score
        ]

        if not scored_files:
            return {
                "formatted": f"No example files found in {org}/{repo} with score >= {min_score}.",
                "totalResults": 0,
                "resultsShared": 0,
            }

    # Sort by score (descending) for best matches first
    scored_files.sort(key=lambda x: x["score"], reverse=True)

    # Limit results
    results = scored_files[:max_results]

    # Format output
    keyword_desc = f" matching '{keyword}'" if keyword else ""
    lines = [f"**Found {len(results)} example files in {org}/{repo}{keyword_desc}:**"]
    if len(scored_files) > max_results:
        lines[0] += f" (showing {max_results} of {len(scored_files)})"
    lines.append("")

    for i, file in enumerate(results, 1):
        lines.append(f"{i}. **{file['path']}**")
        lines.append(f"   Size: {file['size']:,} bytes | Ref: {file['ref'][:7]}")
        lines.append(f"   URL: {file['url']}")

        # Copyable parameters for read_file tool
        read_params = f"{{'repo': '{org}/{repo}', 'path': '{file['path']}'}}"
        lines.append(f"   To read, use: {read_params}")
        lines.append("")

    return {
        "formatted": "\n".join(lines),
        "totalResults": len(results),
        "resultsShared": len(results),
    }


# Tool specification
GITHUB_FIND_EXAMPLES_TOOL_SPEC = {
    "name": "github_find_examples",
    "description": (
        "Find example files in a GitHub repository using fuzzy matching.\n\n"
        "This tool uses fuzzy string matching to find files related to a keyword or common example patterns. "
        "It calculates similarity scores and returns the best matches.\n\n"
        "Global example keywords (always fuzzy matched): example, tutorial, demo, quickstart, guide, sample\n\n"
        "If the repository is not found, it returns similar repositories sorted by star count.\n\n"
        "Features:\n"
        "- Fuzzy matching using Levenshtein distance\n"
        "- Sorted by match score (best matches first)\n"
        "- Auto-suggests similar repos if target not found\n"
        "- Configurable minimum score threshold\n\n"
        "## Examples:\n\n"
        "**Find GRPO examples in TRL:**\n"
        "{'keyword': 'grpo', 'repo': 'trl', 'org': 'huggingface'}\n"
        "→ Matches: examples/scripts/grpo_agent.py, examples/scripts/gspo.py\n\n"
        "**Find tutorial files in transformers:**\n"
        "{'keyword': 'tutorial', 'repo': 'transformers', 'org': 'huggingface'}\n\n"
        "**Find any example files (no keyword):**\n"
        "{'repo': 'pytorch', 'org': 'pytorch'}\n"
        "→ Uses global example keywords for matching\n\n"
        "**Adjust minimum score:**\n"
        "{'keyword': 'bert', 'repo': 'transformers', 'org': 'huggingface', 'min_score': 70}\n\n"
        "Returns list of matching files with fuzzy match scores, paths, sizes, and URLs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Keyword to fuzzy match against file paths (e.g., 'grpo', 'bert'). Optional.",
            },
            "repo": {
                "type": "string",
                "description": "Repository name (e.g., 'trl', 'transformers'). Required.",
            },
            "org": {
                "type": "string",
                "description": "GitHub organization or username. Default: 'huggingface'.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return. Default: 50.",
            },
            "min_score": {
                "type": "integer",
                "description": "Minimum fuzzy match score (0-100). Default: 60.",
            },
        },
        "required": ["repo"],
    },
}


async def github_find_examples_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        result = find_examples(
            keyword=arguments.get("keyword", ""),
            repo=arguments["repo"],
            org=arguments.get("org", "huggingface"),
            max_results=arguments.get("max_results", 50),
            min_score=arguments.get("min_score", 60),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error finding examples: {str(e)}", False
