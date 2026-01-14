"""
Documentation search tools for the HF Agent
Tools for exploring and fetching HuggingFace documentation and API specifications
"""

import asyncio
import os
from typing import Any

import httpx
from bs4 import BeautifulSoup
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import MultifieldParser, OrGroup

# Cache for OpenAPI spec to avoid repeated fetches
_openapi_spec_cache: dict[str, Any] | None = None

# Simple in-memory caches for docs and search indexes
_DOCS_CACHE: dict[str, list[dict[str, str]]] = {}
_INDEX_CACHE: dict[str, tuple[Any, MultifieldParser]] = {}
_CACHE_LOCK = asyncio.Lock()

# Result limiting defaults
DEFAULT_MAX_RESULTS = 20
MAX_RESULTS_CAP = 50

# Gradio documentation endpoints (hosted separately from HF docs)
GRADIO_LLMS_TXT_URL = "https://gradio.app/llms.txt"
GRADIO_EMBEDDING_SEARCH_URL = "https://playground-worker.pages.dev/api/prompt"

# High-level endpoints that bundle related documentation sections
COMPOSITE_ENDPOINTS: dict[str, list[str]] = {
    "optimum": [
        "optimum",
        "optimum-habana",
        "optimum-neuron",
        "optimum-intel",
        "optimum-executorch",
        "optimum-tpu",
    ],
    "courses": [
        "llm-course",
        "robotics-course",
        "mcp-course",
        "smol-course",
        "agents-course",
        "deep-rl-course",
        "computer-vision-course",
        "audio-course",
        "ml-games-course",
        "diffusion-course",
        "ml-for-3d-course",
        "cookbook",
    ],
}


def _expand_endpoint(endpoint: str) -> list[str]:
    return COMPOSITE_ENDPOINTS.get(endpoint, [endpoint])


# ---------------------------------------------------------------------------
# Gradio documentation helpers (uses gradio.app instead of HF docs)
# ---------------------------------------------------------------------------


async def _fetch_gradio_full_docs() -> str:
    """Fetch Gradio's full documentation from llms.txt"""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(GRADIO_LLMS_TXT_URL)
        response.raise_for_status()
    return response.text


async def _search_gradio_docs(query: str) -> str:
    """
    Run embedding search on Gradio's documentation via their API.
    Returns the most relevant content for the query.
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.post(
            GRADIO_EMBEDDING_SEARCH_URL,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://gradio-docs-mcp.up.railway.app",
            },
            json={
                "prompt_to_embed": query,
                "SYSTEM_PROMPT": "$INSERT_GUIDES_DOCS_DEMOS",
                "FALLBACK_PROMPT": "No results found",
            },
        )
        response.raise_for_status()
        result = response.json()
    return result.get("SYS_PROMPT", "No results found")


def _format_gradio_results(content: str, query: str | None = None) -> str:
    """Format Gradio documentation results"""
    header = "# Gradio Documentation\n\n"
    if query:
        header += f"Search query: '{query}'\n\n"
    header += "Source: https://gradio.app/docs\n\n---\n\n"
    return header + content


async def _fetch_html_page(hf_token: str, endpoint: str) -> str:
    """Fetch the HTML page for a given endpoint"""
    base_url = "https://huggingface.co/docs"
    url = f"{base_url}/{endpoint}"
    headers = {"Authorization": f"Bearer {hf_token}"}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()

    return response.text


def _parse_sidebar_navigation(html_content: str) -> list[dict[str, str]]:
    """Parse the sidebar navigation and extract all links"""
    soup = BeautifulSoup(html_content, "html.parser")
    sidebar = soup.find("nav", class_=lambda x: x and "flex-auto" in x)

    if not sidebar:
        raise ValueError("Could not find navigation sidebar")

    links = sidebar.find_all("a", href=True)
    nav_data = []

    for link in links:
        title = link.get_text(strip=True)
        href = link["href"]

        # Make URL absolute
        page_url = f"https://huggingface.co{href}" if href.startswith("/") else href
        nav_data.append({"title": title, "url": page_url})

    return nav_data


async def _fetch_single_glimpse(
    client: httpx.AsyncClient, hf_token: str, item: dict[str, str]
) -> dict[str, str]:
    """Fetch a short glimpse for a single page"""
    md_url = f"{item['url']}.md"
    headers = {"Authorization": f"Bearer {hf_token}"}

    try:
        response = await client.get(md_url, headers=headers)
        response.raise_for_status()

        content = response.text.strip()
        snippet_length = 200
        glimpse = content[:snippet_length].strip()
        if len(content) > snippet_length:
            glimpse += "..."

        return {
            "title": item["title"],
            "url": item["url"],
            "md_url": md_url,
            "glimpse": glimpse,
            "content": content,
        }
    except Exception as e:
        return {
            "title": item["title"],
            "url": item["url"],
            "md_url": md_url,
            "glimpse": f"[Could not fetch glimpse: {str(e)[:50]}]",
            "content": "",
        }


async def _fetch_all_glimpses(
    hf_token: str, nav_data: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Fetch glimpses for all pages in parallel"""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        result_items = await asyncio.gather(
            *[_fetch_single_glimpse(client, hf_token, item) for item in nav_data]
        )

    return list(result_items)


async def _load_single_endpoint(hf_token: str, endpoint: str) -> list[dict[str, str]]:
    """Fetch docs for a single endpoint."""
    html_content = await _fetch_html_page(hf_token, endpoint)
    nav_data = _parse_sidebar_navigation(html_content)
    if not nav_data:
        raise ValueError(f"No navigation links found for endpoint '{endpoint}'")

    docs = await _fetch_all_glimpses(hf_token, nav_data)
    for doc in docs:
        doc["section"] = endpoint
    return docs


async def _get_docs(hf_token: str, endpoint: str) -> list[dict[str, str]]:
    """Return docs for a single endpoint or expanded composite."""
    async with _CACHE_LOCK:
        cached = _DOCS_CACHE.get(endpoint)
    if cached is not None:
        return cached

    docs: list[dict[str, str]] = []
    for member in _expand_endpoint(endpoint):
        async with _CACHE_LOCK:
            member_cached = _DOCS_CACHE.get(member)
        if member_cached is None:
            member_cached = await _load_single_endpoint(hf_token, member)
            async with _CACHE_LOCK:
                _DOCS_CACHE[member] = member_cached
        docs.extend(member_cached)

    async with _CACHE_LOCK:
        _DOCS_CACHE[endpoint] = docs
    return docs


async def _ensure_index(
    endpoint: str, docs: list[dict[str, str]]
) -> tuple[Any, MultifieldParser]:
    async with _CACHE_LOCK:
        cached = _INDEX_CACHE.get(endpoint)
    if cached is not None:
        return cached

    analyzer = StemmingAnalyzer()
    schema = Schema(
        title=TEXT(stored=True, analyzer=analyzer),
        url=ID(stored=True, unique=True),
        md_url=ID(stored=True),
        section=ID(stored=True),
        glimpse=TEXT(stored=True, analyzer=analyzer),
        content=TEXT(stored=False, analyzer=analyzer),
    )
    storage = RamStorage()
    index = storage.create_index(schema)
    writer = index.writer()
    for doc in docs:
        writer.add_document(
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            md_url=doc.get("md_url", ""),
            section=doc.get("section", endpoint),
            glimpse=doc.get("glimpse", ""),
            content=doc.get("content", ""),
        )
    writer.commit()

    parser = MultifieldParser(
        ["title", "content"],
        schema=schema,
        fieldboosts={"title": 2.0, "content": 1.0},
        group=OrGroup,
    )

    async with _CACHE_LOCK:
        _INDEX_CACHE[endpoint] = (index, parser)
    return index, parser


async def _search_docs(
    endpoint: str,
    docs: list[dict[str, str]],
    query: str,
    limit: int | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Run a Whoosh search over documentation entries.

    Returns (results, fallback_message). If fallback_message is not None, the caller
    should surface fallback information to the user.
    """
    index, parser = await _ensure_index(endpoint, docs)

    try:
        query_obj = parser.parse(query)
    except Exception:
        return (
            [],
            "Query contained unsupported syntax; showing default ordering instead.",
        )

    with index.searcher() as searcher:
        whoosh_results = searcher.search(query_obj, limit=limit or None)
        matches: list[dict[str, Any]] = []
        for hit in whoosh_results:
            matches.append(
                {
                    "title": hit["title"],
                    "url": hit["url"],
                    "md_url": hit.get("md_url", ""),
                    "section": hit.get("section", endpoint),
                    "glimpse": hit["glimpse"],
                    "score": round(hit.score, 2),
                }
            )

    if not matches:
        return [], "No strong matches found; showing default ordering instead."

    return matches, None


def _format_exploration_results(
    endpoint: str,
    result_items: list[dict[str, str]],
    total_items: int,
    query: str | None = None,
    fallback_message: str | None = None,
) -> str:
    """Format the exploration results as a readable string"""
    base_url = "https://huggingface.co/docs"
    url = f"{base_url}/{endpoint}"
    result = f"Documentation structure for: {url}\n\n"

    if query:
        result += (
            f"Query: '{query}' → showing {len(result_items)} result(s)"
            f" out of {total_items} pages"
        )
        if fallback_message:
            result += f" ({fallback_message})"
        result += "\n\n"
    else:
        result += (
            f"Found {len(result_items)} page(s) (total available: {total_items}).\n\n"
        )

    for i, item in enumerate(result_items, 1):
        result += f"{i}. **{item['title']}**\n"
        result += f"   URL: {item['url']}\n"
        result += f"   Section: {item.get('section', endpoint)}\n"
        if query and "score" in item:
            result += f"   Relevance score: {item['score']:.2f}\n"
        result += f"   Glimpse: {item['glimpse']}\n\n"

    return result


async def explore_hf_docs(
    hf_token: str,
    endpoint: str,
    query: str | None = None,
    max_results: int | None = None,
) -> str:
    """Main function to explore documentation structure"""
    cached_items = await _get_docs(hf_token, endpoint)

    total_count = len(cached_items)
    if max_results is None:
        limit = DEFAULT_MAX_RESULTS
        limit_note = f"Showing top {DEFAULT_MAX_RESULTS} results (set max_results to adjust)."
    else:
        limit = max_results if max_results > 0 else None
        limit_note = None
        if limit is None:
            return "Error: max_results must be greater than zero."

    if limit > MAX_RESULTS_CAP:
        limit_note = (
            f"Requested {limit} results but showing top {MAX_RESULTS_CAP} (maximum allowed)."
        )
        limit = MAX_RESULTS_CAP

    selected_items: list[dict[str, Any]]
    fallback_message: str | None = None

    if query:
        search_results, fallback_message = await _search_docs(
            endpoint,
            cached_items,
            query,
            limit,
        )

        if search_results:
            selected_items = search_results
        else:
            selected_items = cached_items[:limit] if limit else cached_items
    else:
        selected_items = cached_items[:limit] if limit else cached_items

    if not selected_items:
        return f"No documentation entries available for endpoint '{endpoint}'."

    note = None
    if fallback_message or limit_note:
        pieces = []
        if fallback_message:
            pieces.append(fallback_message)
        if limit_note:
            pieces.append(limit_note)
        note = "; ".join(pieces)

    result = _format_exploration_results(
        endpoint,
        selected_items,
        total_items=total_count,
        query=query,
        fallback_message=note,
    )

    return result


async def explore_hf_docs_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """
    Explore the documentation structure for a given endpoint by parsing the sidebar navigation

    Args:
        arguments: Dictionary with 'endpoint' parameter (e.g., 'trl', 'transformers', etc.)

    Returns:
        Tuple of (structured_navigation_with_glimpses, success)
    """
    endpoint = arguments.get("endpoint", "")
    query = arguments.get("query")
    max_results = arguments.get("max_results")

    if not endpoint:
        return "Error: No endpoint provided", False

    endpoint = endpoint.lstrip("/")

    # Special handling for Gradio docs (hosted at gradio.app, not HF docs)
    if endpoint.lower() == "gradio":
        try:
            clean_query = (
                query.strip() if isinstance(query, str) and query.strip() else None
            )
            if clean_query:
                # Use embedding search for specific queries
                content = await _search_gradio_docs(clean_query)
            else:
                # Fetch full docs when no query provided
                content = await _fetch_gradio_full_docs()
            return _format_gradio_results(content, query=clean_query), True
        except httpx.HTTPStatusError as e:
            return (
                f"HTTP error fetching Gradio docs: {e.response.status_code}",
                False,
            )
        except httpx.RequestError as e:
            return f"Request error fetching Gradio docs: {str(e)}", False
        except Exception as e:
            return f"Error fetching Gradio docs: {str(e)}", False

    # Standard HF docs flow for all other endpoints
    hf_token = os.environ.get("HF_TOKEN")

    if not hf_token:
        return "Error: HF_TOKEN environment variable not set", False

    try:
        try:
            max_results_int = int(max_results) if max_results is not None else None
        except (TypeError, ValueError):
            return "Error: max_results must be an integer", False

        if max_results_int is not None and max_results_int <= 0:
            return "Error: max_results must be greater than zero", False

        result = await explore_hf_docs(
            hf_token,
            endpoint,
            query=query.strip() if isinstance(query, str) and query.strip() else None,
            max_results=max_results_int,
        )
        return result, True

    except httpx.HTTPStatusError as e:
        return (
            f"HTTP error: {e.response.status_code} - {e.response.text[:200]}",
            False,
        )
    except httpx.RequestError as e:
        return f"Request error: {str(e)}", False
    except ValueError as e:
        return f"Error: {str(e)}", False
    except Exception as e:
        return f"Unexpected error: {str(e)}", False


async def _fetch_openapi_spec() -> dict[str, Any]:
    """Fetch and cache the HuggingFace OpenAPI specification"""
    global _openapi_spec_cache

    if _openapi_spec_cache is not None:
        return _openapi_spec_cache

    url = "https://huggingface.co/.well-known/openapi.json"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    spec = response.json()
    _openapi_spec_cache = spec

    return spec


def _extract_all_tags(spec: dict[str, Any]) -> list[str]:
    """Extract all unique tags from the OpenAPI spec"""
    tags = set()

    # Get tags from the tags section
    for tag_obj in spec.get("tags", []):
        if "name" in tag_obj:
            tags.add(tag_obj["name"])

    # Also get tags from paths (in case some aren't in the tags section)
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch", "head", "options"]:
                for tag in operation.get("tags", []):
                    tags.add(tag)

    return sorted(list(tags))


def _search_openapi_by_tag(spec: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    """Search for API endpoints with a specific tag"""
    results = []
    paths = spec.get("paths", {})
    servers = spec.get("servers", [])
    base_url = (
        servers[0].get("url", "https://huggingface.co")
        if servers
        else "https://huggingface.co"
    )

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method not in [
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "head",
                "options",
            ]:
                continue

            operation_tags = operation.get("tags", [])
            if tag in operation_tags:
                # Extract parameters
                parameters = operation.get("parameters", [])
                request_body = operation.get("requestBody", {})
                responses = operation.get("responses", {})

                results.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "operationId": operation.get("operationId", ""),
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "parameters": parameters,
                        "request_body": request_body,
                        "responses": responses,
                        "base_url": base_url,
                    }
                )

    return results


def _generate_curl_example(endpoint: dict[str, Any]) -> str:
    """Generate a curl command example for an endpoint"""
    method = endpoint["method"]
    path = endpoint["path"]
    base_url = endpoint["base_url"]

    # Build the full URL with example path parameters
    full_path = path
    for param in endpoint.get("parameters", []):
        if param.get("in") == "path" and param.get("required"):
            param_name = param["name"]
            example = param.get(
                "example", param.get("schema", {}).get("example", f"<{param_name}>")
            )
            full_path = full_path.replace(f"{{{param_name}}}", str(example))

    curl = f"curl -X {method} \\\n  '{base_url}{full_path}'"

    # Add query parameters if any
    query_params = [p for p in endpoint.get("parameters", []) if p.get("in") == "query"]
    if query_params and query_params[0].get("required"):
        param = query_params[0]
        example = param.get("example", param.get("schema", {}).get("example", "value"))
        curl += f"?{param['name']}={example}"

    # Add headers
    curl += " \\\n  -H 'Authorization: Bearer $HF_TOKEN'"

    # Add request body if applicable
    if method in ["POST", "PUT", "PATCH"] and endpoint.get("request_body"):
        content = endpoint["request_body"].get("content", {})
        if "application/json" in content:
            curl += " \\\n  -H 'Content-Type: application/json'"
            schema = content["application/json"].get("schema", {})
            example = schema.get("example", "{}")
            if isinstance(example, dict):
                import json

                example = json.dumps(example, indent=2)
            curl += f" \\\n  -d '{example}'"

    return curl


def _format_parameters(parameters: list[dict[str, Any]]) -> str:
    """Format parameter information from OpenAPI spec"""
    if not parameters:
        return ""

    # Group parameters by type
    path_params = [p for p in parameters if p.get("in") == "path"]
    query_params = [p for p in parameters if p.get("in") == "query"]
    header_params = [p for p in parameters if p.get("in") == "header"]

    output = []

    if path_params:
        output.append("**Path Parameters:**")
        for param in path_params:
            name = param.get("name", "")
            required = " (required)" if param.get("required") else " (optional)"
            description = param.get("description", "")
            param_type = param.get("schema", {}).get("type", "string")
            example = param.get("example") or param.get("schema", {}).get("example", "")

            output.append(f"- `{name}` ({param_type}){required}: {description}")
            if example:
                output.append(f"  Example: `{example}`")

    if query_params:
        if output:
            output.append("")
        output.append("**Query Parameters:**")
        for param in query_params:
            name = param.get("name", "")
            required = " (required)" if param.get("required") else " (optional)"
            description = param.get("description", "")
            param_type = param.get("schema", {}).get("type", "string")
            example = param.get("example") or param.get("schema", {}).get("example", "")

            output.append(f"- `{name}` ({param_type}){required}: {description}")
            if example:
                output.append(f"  Example: `{example}`")

    if header_params:
        if output:
            output.append("")
        output.append("**Header Parameters:**")
        for param in header_params:
            name = param.get("name", "")
            required = " (required)" if param.get("required") else " (optional)"
            description = param.get("description", "")

            output.append(f"- `{name}`{required}: {description}")

    return "\n".join(output)


def _format_response_info(responses: dict[str, Any]) -> str:
    """Format response information from OpenAPI spec"""
    if not responses:
        return "No response information available"

    output = []
    for status_code, response_obj in list(responses.items())[
        :3
    ]:  # Show first 3 status codes
        desc = response_obj.get("description", "")
        output.append(f"- **{status_code}**: {desc}")

        content = response_obj.get("content", {})
        if "application/json" in content:
            schema = content["application/json"].get("schema", {})
            if "type" in schema:
                output.append(f"  Returns: {schema.get('type', 'object')}")

    return "\n".join(output)


def _format_openapi_results(results: list[dict[str, Any]], tag: str) -> str:
    """Format OpenAPI search results as markdown with curl examples"""
    if not results:
        return f"No API endpoints found with tag '{tag}'"

    output = f"# API Endpoints for tag: `{tag}`\n\n"
    output += f"Found {len(results)} endpoint(s)\n\n"
    output += "---\n\n"

    for i, endpoint in enumerate(results, 1):
        output += f"## {i}. {endpoint['method']} {endpoint['path']}\n\n"

        if endpoint["summary"]:
            output += f"**Summary:** {endpoint['summary']}\n\n"

        if endpoint["description"]:
            desc = endpoint["description"][:300]
            if len(endpoint["description"]) > 300:
                desc += "..."
            output += f"**Description:** {desc}\n\n"

        # Parameters
        params_info = _format_parameters(endpoint.get("parameters", []))
        if params_info:
            output += params_info + "\n\n"

        # Curl example
        output += "**Usage:**\n```bash\n"
        output += _generate_curl_example(endpoint)
        output += "\n```\n\n"

        # Response info
        output += "**Returns:**\n"
        output += _format_response_info(endpoint["responses"])
        output += "\n\n"

        output += "---\n\n"

    return output


async def search_openapi_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """
    Search the HuggingFace OpenAPI specification by tag

    Args:
        arguments: Dictionary with 'tag' parameter

    Returns:
        Tuple of (search_results, success)
    """
    tag = arguments.get("tag", "")

    if not tag:
        return "Error: No tag provided", False

    try:
        # Fetch OpenAPI spec (cached after first fetch)
        spec = await _fetch_openapi_spec()

        # Search for endpoints with this tag
        results = _search_openapi_by_tag(spec, tag)

        # Format results
        formatted = _format_openapi_results(results, tag)

        return formatted, True

    except httpx.HTTPStatusError as e:
        return f"HTTP error fetching OpenAPI spec: {e.response.status_code}", False
    except httpx.RequestError as e:
        return f"Request error: {str(e)}", False
    except Exception as e:
        return f"Error searching OpenAPI spec: {str(e)}", False


async def hf_docs_fetch_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """
    Fetch full documentation content from a specific HF docs page

    Args:
        arguments: Dictionary with 'url' parameter (full URL to the doc page)

    Returns:
        Tuple of (full_markdown_content, success)
    """
    url = arguments.get("url", "")

    if not url:
        return "Error: No URL provided", False

    # Get HF token from environment
    hf_token = os.environ.get("HF_TOKEN")

    if not hf_token:
        return (
            "Error: HF_TOKEN environment variable not set",
            False,
        )

    # Add .md extension if not already present
    if not url.endswith(".md"):
        url = f"{url}.md"

    try:
        # Make request with auth
        headers = {"Authorization": f"Bearer {hf_token}"}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        content = response.text

        # Return the markdown content directly
        result = f"Documentation from: {url}\n\n{content}"

        return result, True

    except httpx.HTTPStatusError as e:
        return (
            f"HTTP error fetching {url}: {e.response.status_code} - {e.response.text[:200]}",
            False,
        )
    except httpx.RequestError as e:
        return f"Request error fetching {url}: {str(e)}", False
    except Exception as e:
        return f"Error fetching documentation: {str(e)}", False


# Tool specifications for documentation search

EXPLORE_HF_DOCS_TOOL_SPEC = {
    "name": "explore_hf_docs",
    "description": (
        "Explore Hugging Face documentation structure and discover available pages with 200-character previews. "
        "⚠️ MANDATORY: ALWAYS use this BEFORE implementing any ML task (training, fine-tuning, data processing, inference). "
        "Your training data may be outdated - current documentation is the source of truth. "
        "**Use when:** (1) Starting any implementation task, (2) User asks 'how to' questions, "
        "(3) Before writing training/processing code, (4) Researching library capabilities, "
        "(5) Verifying API syntax and parameters. "
        "**Pattern:** explore (discover structure) → fetch_hf_docs (get details) → implement with researched approach. "
        "Returns: Sidebar navigation with titles, URLs, and glimpses of all pages in the selected documentation. "
        "**Then:** Use fetch_hf_docs with specific URLs from results to get full content. "
        "**Critical for reliability:** Never implement based on internal knowledge without checking current docs first - APIs change frequently."
        " By default returns the top 20 results; set max_results (max 50) to adjust."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "enum": [
                    "hub",
                    "transformers",
                    "diffusers",
                    "datasets",
                    "gradio",
                    "trackio",
                    "smolagents",
                    "huggingface_hub",
                    "huggingface.js",
                    "transformers.js",
                    "inference-providers",
                    "inference-endpoints",
                    "peft",
                    "accelerate",
                    "optimum",
                    "tokenizers",
                    "courses",
                    "evaluate",
                    "tasks",
                    "dataset-viewer",
                    "trl",
                    "simulate",
                    "sagemaker",
                    "timm",
                    "safetensors",
                    "tgi",
                    "setfit",
                    "lerobot",
                    "autotrain",
                    "tei",
                    "bitsandbytes",
                    "sentence_transformers",
                    "chat-ui",
                    "leaderboards",
                    "lighteval",
                    "argilla",
                    "distilabel",
                    "microsoft-azure",
                    "kernels",
                    "google-cloud",
                ],
                "description": (
                    "The documentation endpoint to explore. Each endpoint corresponds to a major section of the Hugging Face documentation:\n\n"
                    "• courses — All Hugging Face courses (LLM, robotics, MCP, smol (llm training), agents, deep RL, computer vision, games, diffusion, 3D, audio) and the cookbook recipes. Probably the best place for examples.\n"
                    "• hub — Find answers to questions about models/datasets/spaces, auth, versioning, metadata.\n"
                    "• transformers — Core model library: architectures, configs, tokenizers, training & inference APIs.\n"
                    "• diffusers — Diffusion pipelines, schedulers, fine-tuning, training, and deployment patterns.\n"
                    "• datasets — Dataset loading, streaming, processing, Arrow format, Hub integration.\n"
                    "• gradio — UI components and demos for ML models. Uses Gradio's native API: without query returns full docs (llms.txt), with query uses embedding search for precise results.\n"
                    "• trackio — Experiment tracking, metrics logging, and run comparison.\n"
                    "• smolagents — Lightweight agent abstractions and tool-using patterns.\n"
                    "• huggingface_hub — Python client for Hub operations (auth, upload/download, repo management).\n"
                    "• huggingface.js — JS/TS client for Hub APIs in browser and Node.\n"
                    "• transformers.js — Run Transformer models in browser/Node via WebGPU/WASM.\n"
                    "• inference-providers — Unified interface for third-party inference backends.\n"
                    "• inference-endpoints — Managed, scalable model deployments on HF infrastructure.\n"
                    "• peft — Parameter-efficient fine-tuning methods (LoRA, adapters, etc.).\n"
                    "• accelerate — Hardware-agnostic, distributed and mixed-precision training orchestration.\n"
                    "• optimum — Hardware-aware optimization and model export tooling, including Habana, Neuron, Intel, ExecuTorch, and TPU variants.\n"
                    "• tokenizers — Fast tokenizer internals, training, and low-level APIs.\n"
                    "• evaluate — Metrics, evaluation workflows, and training-loop integration.\n"
                    "• tasks — Canonical task definitions and model categorization.\n"
                    "• dataset-viewer — Dataset preview, streaming views, and viewer internals.\n"
                    "• trl — RLHF, DPO, PPO, and SFT utilities for LLMs.\n"
                    "• simulate — Experimental simulation tools and workflows.\n"
                    "• sagemaker — Deploying Hugging Face models on AWS SageMaker.\n"
                    "• timm — Image model zoo and utilities via HF integrations.\n"
                    "• safetensors — Safe, fast tensor serialization format.\n"
                    "• tgi — High-throughput text generation server for LLMs.\n"
                    "• setfit — Few-shot text classification via sentence embeddings.\n"
                    "• lerobot — Robotics datasets, policies, and learning workflows.\n"
                    "• autotrain — No/low-code model training on Hugging Face.\n"
                    "• tei — Optimized inference server for embedding workloads.\n"
                    "• bitsandbytes — Quantization and memory-efficient optimizers.\n"
                    "• sentence_transformers — Embedding models, training recipes, similarity/search workflows.\n"
                    "• chat-ui — Reference chat interfaces for LLM deployment.\n"
                    "• leaderboards — Evaluation leaderboards and submission mechanics.\n"
                    "• lighteval — Lightweight, reproducible LLM evaluation framework.\n"
                    "• argilla — Data annotation, feedback, and human-in-the-loop workflows.\n"
                    "• distilabel — Synthetic data generation and distillation pipelines.\n"
                    "• microsoft-azure — Azure deployment and integration guides.\n"
                    "• kernels — Lightweight execution environments and notebook-style workflows.\n"
                    "• google-cloud — GCP deployment and serving workflows.\n"
                ),
            },
            "query": {
                "type": "string",
                "description": (
                    "Optional keyword query to rank and filter documentation pages. Fuzzy matching is used "
                    "against titles, URLs, and glimpses to surface the most relevant content."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": (
                    "Optional cap on number of results to return. Defaults to 20 when omitted and cannot exceed 50."
                ),
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["endpoint"],
    },
}

HF_DOCS_FETCH_TOOL_SPEC = {
    "name": "fetch_hf_docs",
    "description": (
        "Fetch full markdown content of a specific HF documentation page. "
        "⚠️ CRITICAL: Use this after explore_hf_docs to get detailed implementation guidance. "
        "**Use when:** (1) Found relevant page in explore_hf_docs results, (2) Need complete API documentation, "
        "(3) Need training method details (SFT/DPO/GRPO), (4) Need configuration examples, "
        "(5) Need parameter descriptions and usage patterns. "
        "**Pattern:** explore_hf_docs (find relevant page) → fetch_hf_docs (get full content) → implement using documented approach. "
        "Provide full URL from explore_hf_docs results (e.g., 'https://huggingface.co/docs/trl/sft_trainer'). "
        "Returns: Complete markdown documentation with examples, parameters, and usage patterns. "
        "**For training tasks:** ALWAYS fetch trainer docs (SFTConfig, DPOConfig, etc.) before creating training scripts. "
        "**Critical for reliability:** This ensures you use current APIs and best practices."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": (
                    "The full URL to the documentation page. "
                    "Example: 'https://huggingface.co/docs/trl/dpo_trainer' "
                    "The .md extension will be added automatically if not present."
                ),
            },
        },
        "required": ["url"],
    },
}


async def _get_api_search_tool_spec() -> dict[str, Any]:
    """
    Dynamically generate the OpenAPI tool spec with tag enum populated at runtime
    This must be called async to fetch the OpenAPI spec and extract tags
    """
    spec = await _fetch_openapi_spec()
    tags = _extract_all_tags(spec)

    return {
        "name": "search_hf_api_endpoints",
        "description": (
            "Search HuggingFace OpenAPI specification by tag to find API endpoints with curl examples. "
            "**Use when:** (1) Need to interact with HF Hub API directly, (2) Building scripts for repo operations, "
            "(3) Need authentication patterns, (4) Understanding API parameters and responses, "
            "(5) Need curl examples for HTTP requests. "
            "Returns: Endpoint paths, methods, parameters, curl examples with authentication, and response schemas. "
            "**Pattern:** search_hf_api_endpoints (find endpoint) → use curl pattern in implementation. "
            "Tags group related operations: repos, models, datasets, inference, spaces, etc. "
            "**Note:** Each result includes curl example with $HF_TOKEN placeholder for authentication. "
            "**For tool building:** This provides the API foundation for creating Hub interaction scripts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "enum": tags,
                    "description": (
                        "The API tag to search for. Each tag groups related API endpoints. "
                    ),
                },
            },
            "required": ["tag"],
        },
    }
