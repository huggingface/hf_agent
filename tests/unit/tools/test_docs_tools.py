"""
Unit tests for docs_tools.
Based on real usage: {"endpoint": "trl"}, {"url": "https://huggingface.co/docs/trl/dpo_trainer"}
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

from agent.tools.docs_tools import (
    _extract_all_tags,
    _format_parameters,
    _generate_curl_example,
    _parse_sidebar_navigation,
    _search_openapi_by_tag,
    explore_hf_docs_handler,
    hf_docs_fetch_handler,
    search_openapi_handler,
)


class TestExploreTrlDocsParsesSidebar:
    """Test sidebar navigation parsing."""

    def test_parse_sidebar_extracts_all_links(self, trl_docs_sidebar_html):
        """
        Parse TRL docs sidebar and extract navigation links.
        Should find all trainer pages.
        """
        nav_data = _parse_sidebar_navigation(trl_docs_sidebar_html)

        assert len(nav_data) > 0

        # Extract titles
        titles = [item["title"] for item in nav_data]

        assert "DPOTrainer" in titles
        assert "SFTTrainer" in titles
        assert "Installation" in titles

        # Verify URLs are absolute
        for item in nav_data:
            assert item["url"].startswith("https://")

    async def test_explore_hf_docs_returns_structure(
        self, mock_hf_token, trl_docs_sidebar_html, dpo_trainer_docs_markdown
    ):
        """
        Test full explore_hf_docs flow with mocked HTTP.
        """
        with patch("agent.tools.docs_tools.httpx.AsyncClient") as mock_client_class:
            # Create mock response for HTML page
            mock_html_response = MagicMock()
            mock_html_response.text = trl_docs_sidebar_html
            mock_html_response.raise_for_status = MagicMock()

            # Create mock response for MD glimpses
            mock_md_response = MagicMock()
            mock_md_response.text = dpo_trainer_docs_markdown
            mock_md_response.raise_for_status = MagicMock()

            # Create async mock client
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[mock_html_response] + [mock_md_response] * 10
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            result, success = await explore_hf_docs_handler({"endpoint": "trl"})

            assert success
            assert "trl" in result.lower()


class TestFetchDocsAddsMdExtension:
    """Test documentation fetching."""

    async def test_fetch_docs_adds_md_extension(
        self, mock_hf_token, dpo_trainer_docs_markdown
    ):
        """
        URL without .md extension should have it added automatically.
        """
        with patch("agent.tools.docs_tools.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.text = dpo_trainer_docs_markdown
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            result, success = await hf_docs_fetch_handler(
                {"url": "https://huggingface.co/docs/trl/dpo_trainer"}
            )

            assert success
            assert "DPOTrainer" in result
            assert "beta" in result.lower()

            # Verify .md was added to URL
            call_args = mock_client.get.call_args
            url_called = call_args[0][0]
            assert url_called.endswith(".md")

    async def test_fetch_docs_preserves_existing_md_extension(
        self, mock_hf_token, dpo_trainer_docs_markdown
    ):
        """URL already with .md should not get double extension."""
        with patch("agent.tools.docs_tools.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.text = dpo_trainer_docs_markdown
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            result, success = await hf_docs_fetch_handler(
                {"url": "https://huggingface.co/docs/trl/dpo_trainer.md"}
            )

            assert success

            # Should not have .md.md
            call_args = mock_client.get.call_args
            url_called = call_args[0][0]
            assert not url_called.endswith(".md.md")


class TestSearchOpenapiByTag:
    """Test OpenAPI endpoint search."""

    def test_search_openapi_by_tag_finds_endpoints(self, sample_openapi_spec):
        """Search for 'repos' tag should return repo endpoints."""
        results = _search_openapi_by_tag(sample_openapi_spec, "repos")

        assert len(results) == 2  # GET and POST

        # Check GET endpoint
        get_endpoint = next(r for r in results if r["method"] == "GET")
        assert "/api/repos/{repo_id}" in get_endpoint["path"]
        assert get_endpoint["operationId"] == "get_repo"

        # Check POST endpoint
        post_endpoint = next(r for r in results if r["method"] == "POST")
        assert "/api/repos" in post_endpoint["path"]

    def test_extract_all_tags(self, sample_openapi_spec):
        """Test tag extraction from OpenAPI spec."""
        tags = _extract_all_tags(sample_openapi_spec)

        assert "repos" in tags
        assert "models" in tags
        assert len(tags) == 2

    def test_generate_curl_example(self, sample_openapi_spec):
        """Test curl example generation."""
        results = _search_openapi_by_tag(sample_openapi_spec, "repos")
        get_endpoint = next(r for r in results if r["method"] == "GET")

        curl = _generate_curl_example(get_endpoint)

        assert "curl" in curl
        assert "-X GET" in curl
        assert "$HF_TOKEN" in curl
        assert "huggingface.co" in curl

    def test_format_parameters(self, sample_openapi_spec):
        """Test parameter formatting."""
        results = _search_openapi_by_tag(sample_openapi_spec, "repos")
        get_endpoint = next(r for r in results if r["method"] == "GET")

        formatted = _format_parameters(get_endpoint["parameters"])

        assert "repo_id" in formatted
        assert "required" in formatted.lower()
        assert "Path" in formatted

    async def test_search_openapi_handler_with_tag(self, sample_openapi_spec):
        """Test the full handler flow."""
        with patch(
            "agent.tools.docs_tools._fetch_openapi_spec", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_openapi_spec

            result, success = await search_openapi_handler({"tag": "repos"})

            assert success
            assert "repos" in result.lower()
            assert "curl" in result.lower()


class TestErrorHandling:
    """Test error handling."""

    async def test_explore_docs_missing_endpoint(self, mock_hf_token):
        """Test missing endpoint parameter."""
        result, success = await explore_hf_docs_handler({})

        assert not success
        assert "endpoint" in result.lower() or "error" in result.lower()

    async def test_fetch_docs_missing_url(self, mock_hf_token):
        """Test missing URL parameter."""
        result, success = await hf_docs_fetch_handler({})

        assert not success
        assert "url" in result.lower() or "error" in result.lower()

    async def test_search_openapi_missing_tag(self):
        """Test missing tag parameter."""
        result, success = await search_openapi_handler({})

        assert not success
        assert "tag" in result.lower() or "error" in result.lower()

    async def test_fetch_docs_missing_hf_token(self):
        """Test missing HF_TOKEN."""
        with patch.dict(os.environ, {}, clear=True):
            result, success = await hf_docs_fetch_handler(
                {"url": "https://huggingface.co/docs/trl/dpo_trainer"}
            )

            assert not success
            assert "HF_TOKEN" in result
