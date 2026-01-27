"""
Integration tests for documentation tools.
Requires: HF_TOKEN environment variable.
"""

import os

import pytest

from agent.tools.docs_tools import explore_hf_docs_handler, hf_docs_fetch_handler

# Skip all tests if no HF token
pytestmark = pytest.mark.skipif(
    not os.environ.get("HF_TOKEN"), reason="HF_TOKEN not set"
)


class TestExploreAndFetchDocs:
    """End-to-end test: explore docs then fetch specific page."""

    @pytest.mark.asyncio
    async def test_explore_and_fetch_trl_docs(self):
        """
        Real workflow:
        1. Explore TRL documentation structure
        2. Fetch DPO trainer documentation
        3. Verify content contains DPOTrainer
        """
        # Step 1: Explore TRL docs
        explore_result, explore_success = await explore_hf_docs_handler(
            {"endpoint": "trl"}
        )

        assert explore_success, f"Explore failed: {explore_result}"
        assert "pages" in explore_result.lower() or "found" in explore_result.lower()

        # Should find DPO trainer page
        assert "dpo" in explore_result.lower(), "DPO trainer not found in navigation"

        # Step 2: Fetch DPO trainer docs
        fetch_result, fetch_success = await hf_docs_fetch_handler(
            {"url": "https://huggingface.co/docs/trl/dpo_trainer"}
        )

        assert fetch_success, f"Fetch failed: {fetch_result}"

        # Step 3: Verify content
        assert "DPOTrainer" in fetch_result or "dpo" in fetch_result.lower(), (
            "DPOTrainer not mentioned in documentation"
        )


class TestExploreVariousEndpoints:
    """Test exploring different documentation endpoints."""

    @pytest.mark.asyncio
    async def test_explore_transformers_docs(self):
        """Explore transformers documentation."""
        result, success = await explore_hf_docs_handler({"endpoint": "transformers"})

        assert success, f"Explore failed: {result}"
        # Should find key pages
        assert any(term in result.lower() for term in ["trainer", "model", "tokenizer"])

    @pytest.mark.asyncio
    async def test_explore_datasets_docs(self):
        """Explore datasets documentation."""
        result, success = await explore_hf_docs_handler({"endpoint": "datasets"})

        assert success, f"Explore failed: {result}"
        assert "dataset" in result.lower()
