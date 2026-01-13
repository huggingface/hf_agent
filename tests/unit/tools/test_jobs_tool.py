"""
Unit tests for hf_jobs tool.
Based on real usage:
- {"operation": "run", "script": "print('Hello')", "hardware_flavor": "cpu-basic", "timeout": "5m"}
- {"operation": "run", "script": "<DPO training script>", "dependencies": ["trl", "torch"], "hardware_flavor": "a100-large", "timeout": "4h"}
"""

import base64
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.jobs_tool import (
    HfJobsTool,
    _build_uv_command,
    _filter_uv_install_output,
    _resolve_uv_command,
    _wrap_inline_script,
)


class TestRunPythonJobBuildsUvCommand:
    """Test UV command construction for Python jobs."""

    def test_build_uv_command_with_deps(self):
        """Test UV command building with dependencies."""
        command = _build_uv_command(
            script="train.py",
            with_deps=["trl", "torch", "transformers"],
            python="3.12",
        )

        assert command[0] == "uv"
        assert command[1] == "run"
        assert "--with" in command
        assert "trl" in command
        assert "torch" in command
        assert "transformers" in command
        assert "-p" in command
        assert "3.12" in command
        assert "train.py" in command

    def test_wrap_inline_script_base64_encodes(self):
        """Test inline script wrapping with base64 encoding."""
        script = "print('Hello from HF Jobs!')\nimport torch"
        wrapped = _wrap_inline_script(
            script=script,
            with_deps=["torch"],
        )

        # Should contain base64 encoding
        assert "base64" in wrapped
        assert "echo" in wrapped
        assert "uv run" in wrapped

        # Verify base64 decodes back to original
        encoded = script.encode("utf-8")
        b64 = base64.b64encode(encoded).decode("utf-8")
        assert b64 in wrapped

    def test_resolve_uv_command_inline_script(self):
        """Test command resolution for inline scripts (contains newline)."""
        script = "from trl import DPOTrainer\nprint('training')"
        command = _resolve_uv_command(
            script=script,
            with_deps=["trl"],
        )

        # Should wrap in shell command
        assert command[0] == "/bin/sh"
        assert command[1] == "-lc"
        assert "base64" in command[2]

    def test_resolve_uv_command_url(self):
        """Test command resolution for URL scripts."""
        script = "https://example.com/train.py"
        command = _resolve_uv_command(script=script, with_deps=["trl"])

        # Should use URL directly
        assert "uv" in command
        assert "run" in command
        assert script in command

    def test_resolve_uv_command_file_path(self):
        """Test command resolution for file path scripts."""
        script = "train.py"
        command = _resolve_uv_command(script=script, with_deps=["trl"])

        # Should use file path directly
        assert "uv" in command
        assert "run" in command
        assert script in command


class TestFilterUvInstallOutput:
    """Test UV installation log filtering."""

    def test_filter_uv_install_output_truncates(self, sample_uv_install_logs):
        """
        Test that installation details are replaced with summary.
        Should keep "Installed X packages in Y s" line and user output.
        """
        filtered = _filter_uv_install_output(sample_uv_install_logs)

        # Should have truncation message
        assert "[installs truncated]" in filtered

        # Should keep the summary line
        assert any("Installed 42 packages" in line for line in filtered)

        # Should keep user output
        assert any("Loading model" in line for line in filtered)
        assert any("Training complete" in line for line in filtered)

        # Should NOT have individual package installs
        assert not any("+ torch==" in line for line in filtered)
        assert not any("+ transformers==" in line for line in filtered)

    def test_filter_uv_install_output_handles_empty(self):
        """Test empty logs handling."""
        assert _filter_uv_install_output([]) == []
        assert _filter_uv_install_output(None) is None

    def test_filter_uv_install_output_no_match(self):
        """Test logs without install pattern - should return unchanged."""
        logs = ["Starting job", "Running script", "Done"]
        filtered = _filter_uv_install_output(logs)

        assert filtered == logs

    def test_filter_uv_install_output_milliseconds(self):
        """Test pattern matching with milliseconds."""
        logs = [
            "+ package==1.0.0",
            "Installed 5 packages in 123ms",
            "User output here",
        ]
        filtered = _filter_uv_install_output(logs)

        assert "[installs truncated]" in filtered
        assert any("123ms" in line for line in filtered)

    def test_filter_uv_install_output_decimal_seconds(self):
        """Test pattern matching with decimal seconds."""
        logs = [
            "+ package==1.0.0",
            "Installed 10 packages in 2.5s",
            "User output here",
        ]
        filtered = _filter_uv_install_output(logs)

        assert "[installs truncated]" in filtered


class TestListJobsFiltersByStatus:
    """Test job listing with status filtering."""

    @pytest.fixture
    def jobs_tool(self):
        """Create a HfJobsTool with mocked api."""
        with patch.dict(os.environ, {"HF_TOKEN": "test-token"}):
            tool = HfJobsTool(hf_token="test-token", namespace="test")
            return tool

    @pytest.fixture
    def mock_running_job(self):
        """Create a mock running job."""
        job = MagicMock()
        job.id = "job-running-123"
        job.status = MagicMock(stage="RUNNING", message="In progress")
        job.command = ["python", "train.py"]
        job.created_at = datetime.now()
        job.docker_image = "python:3.12"
        job.space_id = None
        job.flavor = "cpu-basic"
        job.owner = MagicMock(name="user")
        return job

    @pytest.fixture
    def mock_completed_job(self):
        """Create a mock completed job."""
        job = MagicMock()
        job.id = "job-completed-456"
        job.status = MagicMock(stage="COMPLETED", message="Done")
        job.command = ["python", "old.py"]
        job.created_at = datetime.now()
        job.docker_image = "python:3.12"
        job.space_id = None
        job.flavor = "cpu-basic"
        job.owner = MagicMock(name="user")
        return job

    async def test_list_jobs_default_shows_running(
        self, jobs_tool, mock_running_job, mock_completed_job
    ):
        """Default ps shows only RUNNING jobs."""
        with patch(
            "agent.tools.jobs_tool._async_call", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = [mock_running_job, mock_completed_job]

            result = await jobs_tool._list_jobs({})

            # Should only show running job
            assert "job-running-123" in result["formatted"]
            assert "job-completed-456" not in result["formatted"]

    async def test_list_jobs_all_shows_everything(
        self, jobs_tool, mock_running_job, mock_completed_job
    ):
        """ps with all=True shows all jobs."""
        with patch(
            "agent.tools.jobs_tool._async_call", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = [mock_running_job, mock_completed_job]

            result = await jobs_tool._list_jobs({"all": True})

            # Should show both jobs
            assert "job-running-123" in result["formatted"]
            assert "job-completed-456" in result["formatted"]


class TestOperationValidation:
    """Test operation parameter validation."""

    @pytest.fixture
    def jobs_tool(self):
        """Create a HfJobsTool with mocked api."""
        with patch.dict(os.environ, {"HF_TOKEN": "test-token"}):
            tool = HfJobsTool(hf_token="test-token", namespace="test")
            return tool

    async def test_missing_operation_returns_error(self, jobs_tool):
        """Test missing operation parameter."""
        result = await jobs_tool.execute({})

        assert result.get("isError", True)
        assert "operation" in result["formatted"].lower()

    async def test_invalid_operation_returns_error(self, jobs_tool):
        """Test invalid operation name."""
        result = await jobs_tool.execute({"operation": "invalid_op"})

        assert result.get("isError", True)
        assert "unknown" in result["formatted"].lower()
