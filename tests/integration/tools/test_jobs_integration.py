"""
Integration tests for HF Jobs tool.
Requires: HF_TOKEN environment variable.

WARNING: These tests run real jobs on HF infrastructure.
Only cpu-basic jobs are used to minimize cost.
"""

import os

import pytest

from agent.tools.jobs_tool import HfJobsTool

# Skip all tests if no HF token
pytestmark = pytest.mark.skipif(
    not os.environ.get("HF_TOKEN"), reason="HF_TOKEN not set"
)


@pytest.fixture
def jobs_tool():
    """Create HfJobsTool with environment token."""
    return HfJobsTool(
        hf_token=os.environ.get("HF_TOKEN"),
        namespace=os.environ.get("HF_NAMESPACE", ""),
    )


class TestRunSimpleCpuJob:
    """Test running simple CPU jobs."""

    @pytest.mark.asyncio
    async def test_run_simple_cpu_job(self, jobs_tool):
        """
        Run a minimal Python job on cpu-basic.
        Should complete and show "hello" in logs.
        """
        result = await jobs_tool.execute(
            {
                "operation": "run",
                "script": "print('hello from integration test')",
                "hardware_flavor": "cpu-basic",
                "timeout": "5m",
            }
        )

        # Job should complete (might fail due to timeout in tests, but should run)
        assert result["totalResults"] > 0

        # Check for job ID in response
        assert "Job ID" in result["formatted"] or "job" in result["formatted"].lower()

        # If completed successfully, should have hello in logs
        if "COMPLETED" in result["formatted"]:
            assert "hello" in result["formatted"].lower()


class TestListAndInspectJobs:
    """Test job listing and inspection."""

    @pytest.mark.asyncio
    async def test_list_jobs(self, jobs_tool):
        """Test listing all jobs."""
        result = await jobs_tool.execute(
            {
                "operation": "ps",
                "all": True,
            }
        )

        # Should not error (may have 0 jobs)
        assert not result.get("isError", False)

    @pytest.mark.asyncio
    async def test_list_and_inspect_job(self, jobs_tool):
        """
        List jobs and inspect one if available.
        """
        # List all jobs
        list_result = await jobs_tool.execute(
            {
                "operation": "ps",
                "all": True,
            }
        )

        assert not list_result.get("isError", False)

        # If there are jobs, try to inspect one
        if list_result["totalResults"] > 0:
            # Extract a job ID from the formatted output
            import re

            job_ids = re.findall(r"[a-f0-9]{24}", list_result["formatted"])

            if job_ids:
                inspect_result = await jobs_tool.execute(
                    {
                        "operation": "inspect",
                        "job_id": job_ids[0],
                    }
                )

                assert not inspect_result.get("isError", False)
                assert (
                    "status" in inspect_result["formatted"].lower()
                    or "Job" in inspect_result["formatted"]
                )


class TestScheduledJobs:
    """Test scheduled job operations."""

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs(self, jobs_tool):
        """Test listing scheduled jobs."""
        result = await jobs_tool.execute(
            {
                "operation": "scheduled ps",
                "all": True,
            }
        )

        # Should not error
        assert not result.get("isError", False)
