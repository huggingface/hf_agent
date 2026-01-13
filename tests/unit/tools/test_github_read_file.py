"""
Unit tests for github_read_file tool.
Based on real usage: {"repo": "huggingface/trl", "path": "trl/scripts/dpo.py"}
"""

import base64
import json
from unittest.mock import MagicMock, patch

from agent.tools.github_read_file import _convert_ipynb_to_markdown, read_file


class TestReadPythonFileWithTruncation:
    """Test reading Python files with automatic truncation."""

    def test_read_python_file_with_line_truncation(
        self, mock_github_token, sample_python_file_content
    ):
        """
        Reading a 500+ line file should truncate to 300 lines.
        Based on real usage: reading trl/scripts/dpo.py
        """
        # Encode content as base64 (GitHub API format)
        content_b64 = base64.b64encode(sample_python_file_content.encode()).decode()

        with patch("agent.tools.github_read_file.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "type": "file",
                "content": content_b64,
                "encoding": "base64",
                "name": "dpo.py",
                "path": "trl/scripts/dpo.py",
            }
            mock_get.return_value = response

            result = read_file(repo="huggingface/trl", path="trl/scripts/dpo.py")

            # Verify no error
            assert not result.get("isError", False)
            assert result["totalResults"] == 1

            # Verify truncation message present
            formatted = result["formatted"]
            assert "lines" in formatted.lower()
            assert "300" in formatted  # Shows line range
            assert "line_start" in formatted or "line_end" in formatted

    def test_read_file_with_explicit_line_range(
        self, mock_github_token, sample_python_file_content
    ):
        """Test reading specific line range."""
        content_b64 = base64.b64encode(sample_python_file_content.encode()).decode()

        with patch("agent.tools.github_read_file.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "type": "file",
                "content": content_b64,
                "encoding": "base64",
            }
            mock_get.return_value = response

            result = read_file(
                repo="huggingface/trl",
                path="trl/scripts/dpo.py",
                line_start=50,
                line_end=100,
            )

            assert not result.get("isError", False)
            # Should show the specific range
            formatted = result["formatted"]
            assert "trl/scripts/dpo.py" in formatted


class TestJupyterNotebookConversion:
    """Test Jupyter notebook to markdown conversion."""

    def test_read_jupyter_notebook_converts_to_markdown(
        self, mock_github_token, sample_jupyter_notebook
    ):
        """
        Reading .ipynb file should convert to markdown.
        Outputs should be cleared for LLM readability.
        """
        notebook_json = json.dumps(sample_jupyter_notebook)
        content_b64 = base64.b64encode(notebook_json.encode()).decode()

        with patch("agent.tools.github_read_file.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "type": "file",
                "content": content_b64,
                "encoding": "base64",
            }
            mock_get.return_value = response

            result = read_file(
                repo="huggingface/trl",
                path="notebooks/dpo_training.ipynb",
            )

            assert not result.get("isError", False)
            formatted = result["formatted"]

            # Should contain markdown heading
            assert "DPO Training Tutorial" in formatted
            # Should contain code
            assert "DPOConfig" in formatted or "trl" in formatted.lower()

    def test_ipynb_conversion_preserves_code_cells(self, sample_jupyter_notebook):
        """Test that code cells are preserved in conversion."""
        notebook_json = json.dumps(sample_jupyter_notebook)
        markdown = _convert_ipynb_to_markdown(notebook_json)

        # Code should be preserved
        assert "DPOConfig" in markdown
        assert "print" in markdown

    def test_ipynb_conversion_handles_invalid_json(self):
        """Test graceful handling of invalid notebook JSON."""
        invalid_json = "not valid json {"
        result = _convert_ipynb_to_markdown(invalid_json)

        # Should return original content on error
        assert result == invalid_json


class TestErrorHandling:
    """Test error handling for various scenarios."""

    def test_file_not_found_returns_error(self, mock_github_token):
        """Test 404 handling."""
        with patch("agent.tools.github_read_file.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 404
            mock_get.return_value = response

            result = read_file(repo="huggingface/trl", path="nonexistent.py")

            assert result.get("isError", True)
            assert "not found" in result["formatted"].lower()

    def test_invalid_repo_format_returns_error(self, mock_github_token):
        """Test invalid repo format (missing /)."""
        result = read_file(repo="invalid-repo-no-slash", path="file.py")

        assert result.get("isError", True)
        assert "owner/repo" in result["formatted"].lower()

    def test_missing_github_token_returns_error(self):
        """Test missing GITHUB_TOKEN."""
        with patch.dict("os.environ", {}, clear=True):
            result = read_file(repo="huggingface/trl", path="file.py")

            assert result.get("isError", True)
            assert "GITHUB_TOKEN" in result["formatted"]
