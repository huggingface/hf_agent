"""
Integration tests for GitHub tools.
Requires: GITHUB_TOKEN environment variable.
"""

import os

import pytest

from agent.tools.github_find_examples import find_examples
from agent.tools.github_list_repos import list_repos
from agent.tools.github_read_file import read_file

# Skip all tests if no GitHub token
pytestmark = pytest.mark.skipif(
    not os.environ.get("GITHUB_TOKEN"), reason="GITHUB_TOKEN not set"
)


class TestGitHubFindAndReadEndToEnd:
    """End-to-end test: find examples then read file."""

    def test_find_and_read_trl_example_end_to_end(self):
        """
        Real workflow:
        1. Find DPO examples in huggingface/trl
        2. Read the first result
        3. Verify valid Python code
        """
        # Step 1: Find examples
        find_result = find_examples(
            repo="trl",
            org="huggingface",
            keyword="dpo",
            max_results=5,
        )

        assert not find_result.get("isError", False), (
            f"Find failed: {find_result['formatted']}"
        )
        assert find_result["totalResults"] > 0, "No DPO examples found"

        # Extract path from results (look for .py file)
        formatted = find_result["formatted"]
        # Find a .py file path in the results
        import re

        paths = re.findall(r"path': '([^']+\.py)'", formatted)
        assert paths, "No Python files found in results"

        file_path = paths[0]

        # Step 2: Read the file
        read_result = read_file(
            repo="huggingface/trl",
            path=file_path,
        )

        assert not read_result.get("isError", False), (
            f"Read failed: {read_result['formatted']}"
        )

        # Step 3: Verify valid Python code indicators
        content = read_result["formatted"]
        # Should contain Python imports or function definitions
        assert any(
            keyword in content for keyword in ["import", "def ", "class ", "from "]
        ), "File doesn't appear to be valid Python"

    def test_find_examples_with_no_keyword(self):
        """Find all examples in TRL without keyword filter."""
        result = find_examples(
            repo="trl",
            org="huggingface",
            max_results=10,
        )

        assert not result.get("isError", False)
        assert result["totalResults"] > 0


class TestListHuggingFaceRepos:
    """Test listing repositories."""

    def test_list_huggingface_repos(self):
        """
        List repos from huggingface org.
        Should find major repos: transformers, datasets, trl.
        """
        result = list_repos(
            org="huggingface",
            sort_by="stars",
            max_results=20,
        )

        assert not result.get("isError", False), f"List failed: {result['formatted']}"
        assert result["totalResults"] > 0

        formatted = result["formatted"]

        # Should find major repos
        assert "transformers" in formatted.lower(), "transformers not found"
        # datasets or trl should be there too
        assert any(repo in formatted.lower() for repo in ["datasets", "trl"]), (
            "Neither datasets nor trl found"
        )


class TestReadSpecificFile:
    """Test reading specific files."""

    def test_read_transformers_readme(self):
        """Read README from transformers repo."""
        result = read_file(
            repo="huggingface/transformers",
            path="README.md",
        )

        assert not result.get("isError", False)
        assert "transformers" in result["formatted"].lower()

    def test_read_with_line_range(self):
        """Read specific line range from a file."""
        result = read_file(
            repo="huggingface/transformers",
            path="README.md",
            line_start=1,
            line_end=50,
        )

        assert not result.get("isError", False)
        # Should not have truncation message since we specified range
        # and it's within limits
