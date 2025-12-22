"""
Tests for HF Jobs Tool

Tests the jobs tool implementation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.tools.hf.jobs.jobs_tool import HfJobsTool, hf_jobs_handler


@pytest.mark.asyncio
async def test_show_help():
    """Test that help message is shown when no operation specified"""
    tool = HfJobsTool()
    result = await tool.execute({})

    assert "HuggingFace Jobs API" in result["formatted"]
    assert "Available Commands" in result["formatted"]
    assert result["totalResults"] == 1
    assert not result.get("isError", False)


@pytest.mark.asyncio
async def test_show_operation_help():
    """Test operation-specific help"""
    tool = HfJobsTool()
    result = await tool.execute({"operation": "run", "args": {"help": True}})

    assert "Help for operation" in result["formatted"]
    assert result["totalResults"] == 1


@pytest.mark.asyncio
async def test_invalid_operation():
    """Test invalid operation handling"""
    tool = HfJobsTool()
    result = await tool.execute({"operation": "invalid_op"})

    assert result.get("isError") == True
    assert "Unknown operation" in result["formatted"]


@pytest.mark.asyncio
async def test_run_job_missing_command():
    """Test run job with missing required parameter"""
    tool = HfJobsTool()
    result = await tool.execute({
        "operation": "run",
        "args": {"image": "python:3.12"}
    })

    assert result.get("isError") == True
    assert "command parameter is required" in result["formatted"]


@pytest.mark.asyncio
async def test_list_jobs_mock():
    """Test list jobs with mock API"""
    tool = HfJobsTool()

    # Mock the API client
    with patch.object(tool.client, 'list_jobs', new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [
            {
                'id': 'test-job-1',
                'status': {'stage': 'RUNNING'},
                'command': ['echo', 'test'],
                'createdAt': '2024-01-01T00:00:00Z',
                'owner': {'name': 'test-user'}
            },
            {
                'id': 'test-job-2',
                'status': {'stage': 'COMPLETED'},
                'command': ['python', 'script.py'],
                'createdAt': '2024-01-01T01:00:00Z',
                'owner': {'name': 'test-user'}
            }
        ]

        # Test listing only running jobs (default)
        result = await tool.execute({"operation": "ps"})

        assert not result.get("isError", False)
        assert "test-job-1" in result["formatted"]
        assert "test-job-2" not in result["formatted"]  # COMPLETED jobs filtered out
        assert result["totalResults"] == 2
        assert result["resultsShared"] == 1

        # Test listing all jobs
        result = await tool.execute({"operation": "ps", "args": {"all": True}})

        assert not result.get("isError", False)
        assert "test-job-1" in result["formatted"]
        assert "test-job-2" in result["formatted"]
        assert result["totalResults"] == 2
        assert result["resultsShared"] == 2


@pytest.mark.asyncio
async def test_inspect_job_mock():
    """Test inspect job with mock API"""
    tool = HfJobsTool()

    with patch.object(tool.client, 'get_job', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {
            'id': 'test-job-1',
            'status': {'stage': 'RUNNING'},
            'command': ['echo', 'test'],
            'createdAt': '2024-01-01T00:00:00Z',
            'owner': {'name': 'test-user'},
            'flavor': 'cpu-basic'
        }

        result = await tool.execute({
            "operation": "inspect",
            "args": {"job_id": "test-job-1"}
        })

        assert not result.get("isError", False)
        assert "test-job-1" in result["formatted"]
        assert "Job Details" in result["formatted"]
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_job_mock():
    """Test cancel job with mock API"""
    tool = HfJobsTool()

    with patch.object(tool.client, 'cancel_job', new_callable=AsyncMock) as mock_cancel:
        mock_cancel.return_value = None

        result = await tool.execute({
            "operation": "cancel",
            "args": {"job_id": "test-job-1"}
        })

        assert not result.get("isError", False)
        assert "cancelled" in result["formatted"]
        assert "test-job-1" in result["formatted"]
        mock_cancel.assert_called_once()


@pytest.mark.asyncio
async def test_handler():
    """Test the handler function"""
    with patch('agent.tools.hf.jobs.jobs_tool.HfJobsTool') as MockTool:
        mock_tool_instance = MockTool.return_value
        mock_tool_instance.execute = AsyncMock(return_value={
            "formatted": "Test output",
            "totalResults": 1,
            "resultsShared": 1,
            "isError": False
        })

        output, success = await hf_jobs_handler({"operation": "ps"})

        assert success == True
        assert "Test output" in output


@pytest.mark.asyncio
async def test_handler_error():
    """Test handler with error"""
    with patch('agent.tools.hf.jobs.jobs_tool.HfJobsTool') as MockTool:
        MockTool.side_effect = Exception("Test error")

        output, success = await hf_jobs_handler({})

        assert success == False
        assert "Error" in output


@pytest.mark.asyncio
async def test_scheduled_jobs_mock():
    """Test scheduled jobs operations with mock API"""
    tool = HfJobsTool()

    # Test list scheduled jobs
    with patch.object(tool.client, 'list_scheduled_jobs', new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [
            {
                'id': 'sched-job-1',
                'schedule': '@daily',
                'suspend': False,
                'jobSpec': {
                    'command': ['python', 'backup.py'],
                    'dockerImage': 'python:3.12'
                },
                'nextRun': '2024-01-02T00:00:00Z'
            }
        ]

        result = await tool.execute({"operation": "scheduled ps"})

        assert not result.get("isError", False)
        assert "sched-job-1" in result["formatted"]
        assert "Scheduled Jobs" in result["formatted"]


def test_job_utils():
    """Test job utility functions"""
    from agent.tools.hf.jobs.job_utils import parse_timeout, parse_image_source, parse_command

    # Test timeout parsing
    assert parse_timeout("5m") == 300
    assert parse_timeout("2h") == 7200
    assert parse_timeout("30s") == 30
    assert parse_timeout("1d") == 86400

    # Test image source parsing
    result = parse_image_source("python:3.12")
    assert result["dockerImage"] == "python:3.12"
    assert result["spaceId"] is None

    result = parse_image_source("https://huggingface.co/spaces/user/space")
    assert result["dockerImage"] is None
    assert result["spaceId"] == "user/space"

    # Test command parsing
    result = parse_command(["python", "script.py"])
    assert result["command"] == ["python", "script.py"]

    result = parse_command("python script.py")
    assert result["command"] == ["python", "script.py"]


def test_uv_utils():
    """Test UV utility functions"""
    from agent.tools.hf.jobs.uv_utils import build_uv_command, resolve_uv_command

    # Test build UV command
    command = build_uv_command("script.py", {})
    assert command == ["uv", "run", "script.py"]

    command = build_uv_command("script.py", {
        "with_deps": ["requests", "numpy"],
        "python": "3.12"
    })
    assert "uv" in command
    assert "run" in command
    assert "--with" in command
    assert "requests" in command
    assert "-p" in command
    assert "3.12" in command

    # Test resolve UV command
    command = resolve_uv_command({"script": "https://example.com/script.py"})
    assert "https://example.com/script.py" in command

    command = resolve_uv_command({"script": "print('hello')"})
    assert command == ["uv", "run", "print('hello')"]
