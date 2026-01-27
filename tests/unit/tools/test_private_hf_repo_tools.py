"""
Unit tests for private_hf_repo_tools.
Based on real usage:
- {"operation": "list_files", "args": {"repo_id": "facebook/MusicGen", "repo_type": "space"}}
- {"operation": "read_file", "args": {"repo_id": "facebook/MusicGen", "repo_type": "space", "path_in_repo": "app.py"}}
"""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.private_hf_repo_tools import PrivateHfRepoTool


@pytest.fixture
def repo_tool():
    """Create a PrivateHfRepoTool instance."""
    with patch.dict(os.environ, {"HF_TOKEN": "test-token"}):
        tool = PrivateHfRepoTool(hf_token="test-token")
        return tool


class TestUploadFileCreatesRepoIfMissing:
    """Test upload_file with auto repo creation."""

    async def test_upload_file_creates_repo_if_missing(self, repo_tool):
        """
        When repo doesn't exist and create_if_missing=True,
        should create repo then upload file.
        """
        with patch(
            "agent.tools.private_hf_repo_tools._async_call", new_callable=AsyncMock
        ) as mock_call:
            # First call: repo_exists returns False
            # Second call: repo_exists returns False (in _create_repo check)
            # Third call: create_repo returns URL
            # Fourth call: upload_file succeeds (returns None)
            mock_call.side_effect = [
                False,  # repo_exists in _upload_file
                False,  # repo_exists in _create_repo
                "https://huggingface.co/datasets/user/test-repo",  # create_repo
                None,  # upload_file
            ]

            result = await repo_tool._upload_file(
                {
                    "file_content": "print('hello')",
                    "path_in_repo": "scripts/hello.py",
                    "repo_id": "test-repo",
                    "repo_type": "dataset",
                    "create_if_missing": True,
                    "commit_message": "Add hello script",
                }
            )

            assert not result.get("isError", False)
            assert (
                "uploaded" in result["formatted"].lower()
                or "success" in result["formatted"].lower()
            )

    async def test_upload_file_fails_without_create_if_missing(self, repo_tool):
        """
        When repo doesn't exist and create_if_missing=False,
        should return error.
        """
        with patch(
            "agent.tools.private_hf_repo_tools._async_call", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = False  # repo_exists returns False

            result = await repo_tool._upload_file(
                {
                    "file_content": "print('hello')",
                    "path_in_repo": "scripts/hello.py",
                    "repo_id": "nonexistent-repo",
                    "repo_type": "dataset",
                    "create_if_missing": False,
                }
            )

            assert result.get("isError", True)
            assert "does not exist" in result["formatted"]


class TestReadFileHandlesBinaryGracefully:
    """Test read_file with binary content."""

    async def test_read_file_handles_binary_gracefully(self, repo_tool):
        """
        Reading binary file should return size info, not crash.
        """
        # Create a temporary binary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"\x00\x01\x02\x03\xff\xfe\xfd")
            temp_path = f.name

        try:
            with patch(
                "agent.tools.private_hf_repo_tools._async_call", new_callable=AsyncMock
            ) as mock_call:
                mock_call.return_value = temp_path  # hf_hub_download returns path

                result = await repo_tool._read_file(
                    {
                        "repo_id": "user/binary-repo",
                        "path_in_repo": "model.bin",
                        "repo_type": "dataset",
                    }
                )

                # Should handle gracefully - shows binary info
                assert (
                    "binary" in result["formatted"].lower()
                    or "bytes" in result["formatted"].lower()
                )
        finally:
            os.unlink(temp_path)

    async def test_read_file_text_content(self, repo_tool):
        """Test reading text file returns content."""
        # Create a temporary text file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
            f.write("from trl import DPOTrainer\nprint('hello')")
            temp_path = f.name

        try:
            with patch(
                "agent.tools.private_hf_repo_tools._async_call", new_callable=AsyncMock
            ) as mock_call:
                mock_call.return_value = temp_path

                result = await repo_tool._read_file(
                    {
                        "repo_id": "user/my-repo",
                        "path_in_repo": "script.py",
                        "repo_type": "dataset",
                    }
                )

                assert not result.get("isError", False)
                assert "DPOTrainer" in result["formatted"]
        finally:
            os.unlink(temp_path)


class TestListFiles:
    """Test list_files operation."""

    async def test_list_files_returns_all_files(self, repo_tool):
        """Test listing files in a repository."""
        files = [
            "README.md",
            "app.py",
            "requirements.txt",
            "demos/musicgen_app.py",
        ]

        with patch(
            "agent.tools.private_hf_repo_tools._async_call", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = files

            result = await repo_tool._list_files(
                {
                    "repo_id": "facebook/MusicGen",
                    "repo_type": "space",
                }
            )

            assert not result.get("isError", False)
            assert result["totalResults"] == 4
            assert "app.py" in result["formatted"]
            assert "musicgen_app.py" in result["formatted"]


class TestParameterValidation:
    """Test parameter validation."""

    async def test_upload_file_requires_content(self, repo_tool):
        """Test missing file_content parameter."""
        result = await repo_tool._upload_file(
            {
                "path_in_repo": "test.py",
                "repo_id": "test-repo",
            }
        )

        assert result.get("isError", True)
        assert "file_content" in result["formatted"]

    async def test_upload_file_requires_path(self, repo_tool):
        """Test missing path_in_repo parameter."""
        result = await repo_tool._upload_file(
            {
                "file_content": "content",
                "repo_id": "test-repo",
            }
        )

        assert result.get("isError", True)
        assert "path_in_repo" in result["formatted"]

    async def test_create_repo_requires_space_sdk_for_spaces(self, repo_tool):
        """Test that space creation requires space_sdk."""
        with patch(
            "agent.tools.private_hf_repo_tools._async_call", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = False  # repo doesn't exist

            result = await repo_tool._create_repo(
                {
                    "repo_id": "my-space",
                    "repo_type": "space",
                    # Missing space_sdk
                }
            )

            assert result.get("isError", True)
            assert "space_sdk" in result["formatted"]
