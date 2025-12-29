"""
Tools available to the search sub-agent
These tools are used by the search sub-agent spawned by search_docs_tool
"""

import os
from typing import Any

import httpx
from bs4 import BeautifulSoup


async def explore_docs_structure_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """
    Explore the documentation structure for a given endpoint by parsing the sidebar navigation

    Args:
        arguments: Dictionary with 'endpoint' parameter (e.g., 'trl', 'transformers', etc.)

    Returns:
        Tuple of (structured_navigation_with_glimpses, success)
    """
    endpoint = arguments.get("endpoint", "")

    if not endpoint:
        return "Error: No endpoint provided", False

    # Get HF token from environment
    hf_token = os.environ.get("HF_TOKEN")

    if not hf_token:
        return "Error: HF_TOKEN environment variable not set", False

    # Build the URL for the main page (without .md to get HTML with navigation)
    base_url = "https://huggingface.co/docs"
    endpoint = endpoint.lstrip("/")
    url = f"{base_url}/{endpoint}"

    try:
        headers = {"Authorization": f"Bearer {hf_token}"}

        # Fetch the main HTML page
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        html_content = response.text

        # Parse the sidebar navigation with BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Find the sidebar nav (contains flex-auto class)
        sidebar = soup.find("nav", class_=lambda x: x and "flex-auto" in x)

        if not sidebar:
            return (
                f"Error: Could not find navigation sidebar on {url}. "
                "The page structure might be different.",
                False,
            )

        # Extract all links from the sidebar
        links = sidebar.find_all("a", href=True)
        nav_data = []

        for link in links:
            title = link.get_text(strip=True)
            href = link["href"]

            # Make URL absolute
            if href.startswith("/"):
                page_url = f"https://huggingface.co{href}"
            else:
                page_url = href

            nav_data.append({"title": title, "url": page_url})

        if not nav_data:
            return f"No navigation links found in sidebar at {url}", False

        # Now fetch glimpses (first 200 chars) for each page
        result_items = []

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for item in nav_data[:20]:  # Limit to first 20 to avoid too many requests
                md_url = f"{item['url']}.md"

                try:
                    md_response = await client.get(md_url, headers=headers)
                    md_response.raise_for_status()

                    content = md_response.text
                    # Get first 200 characters as glimpse
                    glimpse = content[:200].strip()
                    if len(content) > 200:
                        glimpse += "..."

                    result_items.append(
                        {
                            "title": item["title"],
                            "url": item["url"],
                            "md_url": md_url,
                            "glimpse": glimpse,
                        }
                    )
                except Exception as e:
                    # If fetching glimpse fails, include without glimpse
                    result_items.append(
                        {
                            "title": item["title"],
                            "url": item["url"],
                            "md_url": f"{item['url']}.md",
                            "glimpse": f"[Could not fetch glimpse: {str(e)[:50]}]",
                        }
                    )

        # Format the results nicely
        result = f"Documentation structure for: {url}\n\n"
        result += f"Found {len(result_items)} pages:\n\n"

        for i, item in enumerate(result_items, 1):
            result += f"{i}. **{item['title']}**\n"
            result += f"   URL: {item['url']}\n"
            result += f"   Glimpse: {item['glimpse']}\n\n"

        return result, True

    except httpx.HTTPStatusError as e:
        return (
            f"HTTP error fetching {url}: {e.response.status_code} - {e.response.text[:200]}",
            False,
        )
    except httpx.RequestError as e:
        return f"Request error fetching {url}: {str(e)}", False
    except Exception as e:
        return f"Error exploring docs structure: {str(e)}", False


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


# Tool specifications for the search sub-agent

EXPLORE_DOCS_STRUCTURE_TOOL_SPEC = {
    "name": "explore_docs_structure",
    "description": (
        "Explore the structure of HF documentation by parsing the sidebar navigation. "
        "Provide an endpoint (e.g., 'trl', 'transformers', 'datasets') and get a list of all "
        "documentation pages with their titles, URLs, and a 200-character glimpse of each page. "
        "Use this to discover what documentation is available before fetching specific pages."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": (
                    "The documentation endpoint to explore (e.g., 'trl', 'transformers', 'hub'). "
                    "Do not include '/docs/' or leading slashes."
                ),
            },
        },
        "required": ["endpoint"],
    },
}

HF_DOCS_FETCH_TOOL_SPEC = {
    "name": "fetch_hf_docs",
    "description": (
        "Fetch the full content of a specific HF documentation page. "
        "Provide the full URL to the doc page (e.g., from explore_docs_structure results). "
        "Returns the complete markdown content of that page. "
        "Use explore_docs_structure first to discover available pages."
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
