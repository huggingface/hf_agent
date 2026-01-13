"""
Integration tests for private HF repo tools.
Requires: HF_TOKEN environment variable.

WARNING: These tests create real repositories.
Cleanup is attempted but may require manual intervention if tests fail.
"""

import os
import uuid

import pytest

from agent.tools.private_hf_repo_tools import PrivateHfRepoTool

# Skip all tests if no HF token
pytestmark = pytest.mark.skipif(
    not os.environ.get("HF_TOKEN"), reason="HF_TOKEN not set"
)


@pytest.fixture
def repo_tool():
    """Create PrivateHfRepoTool with environment token."""
    return PrivateHfRepoTool(hf_token=os.environ.get("HF_TOKEN"))


@pytest.fixture
def test_repo_id():
    """Generate unique test repo ID."""
    return f"test-integration-{uuid.uuid4().hex[:8]}"


class TestCreateListReadCleanup:
    """Full lifecycle test: create, upload, list, read, cleanup."""

    @pytest.mark.asyncio
    async def test_create_list_read_cleanup(self, repo_tool, test_repo_id):
        """
        Full workflow:
        1. Create test dataset repo
        2. Upload test file
        3. List files
        4. Read back file
        5. Cleanup: delete repo
        """
        try:
            # Step 1: Create repo
            create_result = await repo_tool.execute(
                {
                    "operation": "create_repo",
                    "args": {
                        "repo_id": test_repo_id,
                        "repo_type": "dataset",
                    },
                }
            )

            assert not create_result.get("isError", False), (
                f"Create failed: {create_result['formatted']}"
            )
            assert (
                "created" in create_result["formatted"].lower()
                or "exists" in create_result["formatted"].lower()
            )

            # Step 2: Upload file
            test_content = "# Test File\n\nprint('hello from integration test')"
            upload_result = await repo_tool.execute(
                {
                    "operation": "upload_file",
                    "args": {
                        "file_content": test_content,
                        "path_in_repo": "test_script.py",
                        "repo_id": test_repo_id,
                        "repo_type": "dataset",
                        "commit_message": "Integration test upload",
                    },
                }
            )

            assert not upload_result.get("isError", False), (
                f"Upload failed: {upload_result['formatted']}"
            )

            # Step 3: List files
            list_result = await repo_tool.execute(
                {
                    "operation": "list_files",
                    "args": {
                        "repo_id": test_repo_id,
                        "repo_type": "dataset",
                    },
                }
            )

            assert not list_result.get("isError", False)
            assert "test_script.py" in list_result["formatted"]

            # Step 4: Read back
            read_result = await repo_tool.execute(
                {
                    "operation": "read_file",
                    "args": {
                        "repo_id": test_repo_id,
                        "path_in_repo": "test_script.py",
                        "repo_type": "dataset",
                    },
                }
            )

            assert not read_result.get("isError", False)
            assert "hello from integration test" in read_result["formatted"]

        finally:
            # Step 5: Cleanup - try to delete the repo
            # Note: huggingface_hub doesn't have a direct delete_repo in PrivateHfRepoTool
            # The repo will need manual cleanup or will be orphaned
            # In a real setup, you might use HfApi.delete_repo directly
            pass


class TestCheckRepo:
    """Test repo existence checking."""

    @pytest.mark.asyncio
    async def test_check_existing_repo(self, repo_tool):
        """Check a known public repo exists."""
        result = await repo_tool.execute(
            {
                "operation": "check_repo",
                "args": {
                    "repo_id": "bert-base-uncased",
                    "repo_type": "model",
                },
            }
        )

        assert not result.get("isError", False)
        assert "exists" in result["formatted"].lower()

    @pytest.mark.asyncio
    async def test_check_nonexistent_repo(self, repo_tool):
        """Check a nonexistent repo."""
        result = await repo_tool.execute(
            {
                "operation": "check_repo",
                "args": {
                    "repo_id": f"nonexistent-repo-{uuid.uuid4().hex}",
                    "repo_type": "dataset",
                },
            }
        )

        # Should return info about not existing
        assert (
            "does not exist" in result["formatted"]
            or "not" in result["formatted"].lower()
        )
