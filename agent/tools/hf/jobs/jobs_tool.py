"""
Hugging Face Jobs Tool - Manage compute jobs on Hugging Face

Ported from: hf-mcp-server/packages/mcp/src/jobs/jobs-tool.ts
"""
import json
from typing import Optional, Dict, Any, List, Literal
from agent.tools.hf.types import ToolResult
from agent.tools.hf.base import HfApiError
from agent.tools.hf.jobs.api_client import JobsApiClient
from agent.tools.hf.jobs.job_utils import create_job_spec
from agent.tools.hf.jobs.uv_utils import resolve_uv_command, UV_DEFAULT_IMAGE
from agent.tools.hf.utilities import (
    format_jobs_table,
    format_scheduled_jobs_table,
    format_job_details,
    format_scheduled_job_details,
)


# Hardware flavors
CPU_FLAVORS = ['cpu-basic', 'cpu-upgrade', 'cpu-performance', 'cpu-xl']
GPU_FLAVORS = [
    'sprx8', 'zero-a10g', 't4-small', 't4-medium', 'l4x1', 'l4x4',
    'l40sx1', 'l40sx4', 'l40sx8', 'a10g-small', 'a10g-large',
    'a10g-largex2', 'a10g-largex4', 'a100-large', 'h100', 'h100x8'
]
SPECIALIZED_FLAVORS = ['inf2x6']
ALL_FLAVORS = CPU_FLAVORS + GPU_FLAVORS + SPECIALIZED_FLAVORS

# Operation names
OperationType = Literal[
    "run", "uv", "ps", "logs", "inspect", "cancel",
    "scheduled run", "scheduled uv", "scheduled ps",
    "scheduled inspect", "scheduled delete", "scheduled suspend", "scheduled resume"
]

# Constants
DEFAULT_LOG_WAIT_SECONDS = 10


class HfJobsTool:
    """Tool for managing Hugging Face compute jobs"""

    def __init__(self, hf_token: Optional[str] = None, namespace: Optional[str] = None):
        self.hf_token = hf_token
        self.client = JobsApiClient(hf_token, namespace)

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the specified operation"""
        operation = params.get('operation')
        args = params.get('args', {})

        # If no operation provided, return usage instructions
        if not operation:
            return self._show_help()

        # Normalize operation name
        operation = operation.lower()

        # Check if help is requested
        if args.get('help'):
            return self._show_operation_help(operation)

        try:
            # Route to appropriate handler
            if operation == "run":
                return await self._run_job(args)
            elif operation == "uv":
                return await self._run_uv_job(args)
            elif operation == "ps":
                return await self._list_jobs(args)
            elif operation == "logs":
                return await self._get_logs(args)
            elif operation == "inspect":
                return await self._inspect_job(args)
            elif operation == "cancel":
                return await self._cancel_job(args)
            elif operation == "scheduled run":
                return await self._scheduled_run(args)
            elif operation == "scheduled uv":
                return await self._scheduled_uv(args)
            elif operation == "scheduled ps":
                return await self._list_scheduled_jobs(args)
            elif operation == "scheduled inspect":
                return await self._inspect_scheduled_job(args)
            elif operation == "scheduled delete":
                return await self._delete_scheduled_job(args)
            elif operation == "scheduled suspend":
                return await self._suspend_scheduled_job(args)
            elif operation == "scheduled resume":
                return await self._resume_scheduled_job(args)
            else:
                return {
                    "formatted": f'Unknown operation: "{operation}"\n\n'
                                'Available operations:\n'
                                '- run, uv, ps, logs, inspect, cancel\n'
                                '- scheduled run, scheduled uv, scheduled ps, scheduled inspect, '
                                'scheduled delete, scheduled suspend, scheduled resume\n\n'
                                'Call this tool with no operation for full usage instructions.',
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True
                }

        except HfApiError as e:
            error_message = f"API Error: {e.message}"
            if e.response_body:
                try:
                    parsed = json.loads(e.response_body)
                    formatted_body = json.dumps(parsed, indent=2)
                    error_message += f"\n\nServer response:\n{formatted_body}"
                except Exception:
                    if len(e.response_body) < 500:
                        error_message += f"\n\nServer response: {e.response_body}"

            return {
                "formatted": error_message,
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }
        except Exception as e:
            return {
                "formatted": f"Error executing {operation}: {str(e)}",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

    def _show_help(self) -> ToolResult:
        """Show usage instructions when tool is called with no arguments"""
        cpu_flavors_list = ', '.join(CPU_FLAVORS)
        gpu_flavors_list = ', '.join(GPU_FLAVORS)
        specialized_flavors_list = ', '.join(SPECIALIZED_FLAVORS)

        hardware_section = f"**CPU:** {cpu_flavors_list}\n"
        if GPU_FLAVORS:
            hardware_section += f"**GPU:** {gpu_flavors_list}\n"
        if SPECIALIZED_FLAVORS:
            hardware_section += f"**Specialized:** {specialized_flavors_list}"

        usage_text = f"""# HuggingFace Jobs API

Manage compute jobs on Hugging Face infrastructure.

## Available Commands

### Job Management
- **run** - Run a job with a Docker image
- **uv** - Run a Python script with UV (inline dependencies)
- **ps** - List jobs
- **logs** - Fetch job logs
- **inspect** - Get detailed job information
- **cancel** - Cancel a running job

### Scheduled Jobs
- **scheduled run** - Create a scheduled job
- **scheduled uv** - Create a scheduled UV job
- **scheduled ps** - List scheduled jobs
- **scheduled inspect** - Get scheduled job details
- **scheduled delete** - Delete a scheduled job
- **scheduled suspend** - Pause a scheduled job
- **scheduled resume** - Resume a suspended job

## Examples

### Run a simple job
Call this tool with:
```json
{{
  "operation": "run",
  "args": {{
    "image": "python:3.12",
    "command": ["python", "-c", "print('Hello from HF Jobs!')"],
    "flavor": "cpu-basic"
  }}
}}
```

### Run a Python script with UV
Call this tool with:
```json
{{
  "operation": "uv",
  "args": {{
    "script": "import random\\nprint(42 + random.randint(1, 5))"
  }}
}}
```

## Hardware Flavors

{hardware_section}

## Command Format Guidelines

**Array format (default):**
- Recommended for every command—JSON keeps arguments intact (URLs with `&`, spaces, etc.)
- Use `["/bin/sh", "-lc", "..."]` when you need shell operators like `&&`, `|`, or redirections
- Works with any language: Python, bash, node, npm, uv, etc.

**String format (simple cases only):**
- Still accepted for backwards compatibility, parsed with POSIX shell semantics
- Rejects shell operators and can mis-handle characters such as `&`; switch to arrays when things turn complex
- `$HF_TOKEN` stays literal—forward it via `secrets: {{ "HF_TOKEN": "$HF_TOKEN" }}`

### Show command-specific help
Call this tool with:
```json
{{"operation": "<operation>", "args": {{"help": true}}}}
```

## Tips

- Jobs default to non-detached mode (tail logs for up to {DEFAULT_LOG_WAIT_SECONDS}s or until completion). Set `detach: true` to return immediately.
- Prefer array commands to avoid shell parsing surprises
- To access private Hub assets, include `secrets: {{ "HF_TOKEN": "$HF_TOKEN" }}` to inject your auth token.
"""
        return {
            "formatted": usage_text,
            "totalResults": 1,
            "resultsShared": 1
        }

    def _show_operation_help(self, operation: str) -> ToolResult:
        """Show help for a specific operation"""
        help_text = f"Help for operation: {operation}\n\nCall with appropriate arguments. Use the main help for examples."
        return {
            "formatted": help_text,
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _run_job(self, args: Dict[str, Any]) -> ToolResult:
        """Create and run a job"""
        # Create job spec from args
        job_spec = create_job_spec({
            'image': args.get('image', 'python:3.12'),
            'command': args.get('command'),
            'flavor': args.get('flavor', 'cpu-basic'),
            'env': args.get('env'),
            'secrets': args.get('secrets'),
            'timeout': args.get('timeout', '30m'),
            'hfToken': self.hf_token,
        })

        # Submit job
        job = await self.client.run_job(job_spec, args.get('namespace'))

        job_url = f"https://huggingface.co/jobs/{job['owner']['name']}/{job['id']}"

        # If detached, return immediately
        if args.get('detach', False):
            response = f"""Job started successfully!

**Job ID:** {job['id']}
**Status:** {job['status']['stage']}
**View at:** {job_url}

To check logs, call this tool with `{{"operation": "logs", "args": {{"job_id": "{job['id']}"}}}}`
To inspect, call this tool with `{{"operation": "inspect", "args": {{"job_id": "{job['id']}"}}}}`"""
            return {
                "formatted": response,
                "totalResults": 1,
                "resultsShared": 1
            }

        # Not detached - return job info and link to logs
        response = f"""Job started: {job['id']}

**Status:** {job['status']['stage']}
**View logs at:** {job_url}

Note: Logs are being collected. Check the job page for real-time logs.
"""
        return {
            "formatted": response,
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _run_uv_job(self, args: Dict[str, Any]) -> ToolResult:
        """Run job with UV package manager"""
        # UV jobs use a standard UV image
        image = UV_DEFAULT_IMAGE

        # Build UV command
        command = resolve_uv_command(args)

        # Convert to run args
        run_args = {
            'image': image,
            'command': command,
            'flavor': args.get('flavor', 'cpu-basic'),
            'env': args.get('env'),
            'secrets': args.get('secrets'),
            'timeout': args.get('timeout', '30m'),
            'detach': args.get('detach', False),
            'namespace': args.get('namespace'),
        }

        return await self._run_job(run_args)

    async def _list_jobs(self, args: Dict[str, Any]) -> ToolResult:
        """List user's jobs"""
        # Fetch all jobs from API
        all_jobs = await self.client.list_jobs(args.get('namespace'))

        # Filter jobs
        jobs = all_jobs

        # Default: show only running jobs unless --all is specified
        if not args.get('all', False):
            jobs = [job for job in jobs if job['status']['stage'] == 'RUNNING']

        # Apply status filter if specified
        if args.get('status'):
            status_filter = args['status'].upper()
            jobs = [job for job in jobs if status_filter in job['status']['stage'].upper()]

        # Format as markdown table
        table = format_jobs_table(jobs)

        if len(jobs) == 0:
            if args.get('all', False):
                return {
                    "formatted": "No jobs found.",
                    "totalResults": 0,
                    "resultsShared": 0
                }
            return {
                "formatted": 'No running jobs found. Use `{"args": {"all": true}}` to show all jobs.',
                "totalResults": 0,
                "resultsShared": 0
            }

        response = f"**Jobs ({len(jobs)} of {len(all_jobs)} total):**\n\n{table}"
        return {
            "formatted": response,
            "totalResults": len(all_jobs),
            "resultsShared": len(jobs)
        }

    async def _get_logs(self, args: Dict[str, Any]) -> ToolResult:
        """Get logs for a job"""
        job_id = args.get('job_id')
        if not job_id:
            return {
                "formatted": "job_id is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

        # Get namespace for the logs URL
        namespace = await self.client.get_namespace(args.get('namespace'))
        job_url = f"https://huggingface.co/jobs/{namespace}/{job_id}"

        # For now, direct users to the web interface for logs
        # Full SSE streaming implementation would be more complex
        response = f"""**Logs for job {job_id}**

View real-time logs at: {job_url}

Note: Full log streaming support is coming soon. Please use the web interface for now.
"""
        return {
            "formatted": response,
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _inspect_job(self, args: Dict[str, Any]) -> ToolResult:
        """Get detailed information about one or more jobs"""
        job_id = args.get('job_id')
        if not job_id:
            return {
                "formatted": "job_id is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

        job_ids = job_id if isinstance(job_id, list) else [job_id]

        # Fetch all jobs
        jobs = []
        for jid in job_ids:
            try:
                job = await self.client.get_job(jid, args.get('namespace'))
                jobs.append(job)
            except Exception as e:
                raise Exception(f"Failed to fetch job {jid}: {str(e)}")

        formatted_details = format_job_details(jobs)
        response = f"**Job Details** ({len(jobs)} job{'s' if len(jobs) > 1 else ''}):\n\n{formatted_details}"

        return {
            "formatted": response,
            "totalResults": len(jobs),
            "resultsShared": len(jobs)
        }

    async def _cancel_job(self, args: Dict[str, Any]) -> ToolResult:
        """Cancel a running job"""
        job_id = args.get('job_id')
        if not job_id:
            return {
                "formatted": "job_id is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

        await self.client.cancel_job(job_id, args.get('namespace'))

        response = f"""✓ Job {job_id} has been cancelled.

To verify, call this tool with `{{"operation": "inspect", "args": {{"job_id": "{job_id}"}}}}`"""

        return {
            "formatted": response,
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _scheduled_run(self, args: Dict[str, Any]) -> ToolResult:
        """Create a scheduled job"""
        # Create job spec
        job_spec = create_job_spec({
            'image': args.get('image', 'python:3.12'),
            'command': args.get('command'),
            'flavor': args.get('flavor', 'cpu-basic'),
            'env': args.get('env'),
            'secrets': args.get('secrets'),
            'timeout': args.get('timeout', '30m'),
            'hfToken': self.hf_token,
        })

        # Create scheduled job spec
        scheduled_spec = {
            'schedule': args.get('schedule'),
            'suspend': args.get('suspend', False),
            'jobSpec': job_spec,
        }

        # Submit scheduled job
        scheduled_job = await self.client.create_scheduled_job(scheduled_spec, args.get('namespace'))

        response = f"""✓ Scheduled job created successfully!

**Scheduled Job ID:** {scheduled_job['id']}
**Schedule:** {scheduled_job['schedule']}
**Suspended:** {'Yes' if scheduled_job.get('suspend') else 'No'}
**Next Run:** {scheduled_job.get('nextRun', 'N/A')}

To inspect, call this tool with `{{"operation": "scheduled inspect", "args": {{"scheduled_job_id": "{scheduled_job['id']}"}}}}`
To list all, call this tool with `{{"operation": "scheduled ps"}}`"""

        return {
            "formatted": response,
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _scheduled_uv(self, args: Dict[str, Any]) -> ToolResult:
        """Create a scheduled UV job"""
        # For UV, use standard UV image
        image = UV_DEFAULT_IMAGE

        # Build UV command
        command = resolve_uv_command(args)

        # Convert to scheduled run args
        scheduled_run_args = {
            'schedule': args.get('schedule'),
            'suspend': args.get('suspend', False),
            'image': image,
            'command': command,
            'flavor': args.get('flavor', 'cpu-basic'),
            'env': args.get('env'),
            'secrets': args.get('secrets'),
            'timeout': args.get('timeout', '30m'),
            'namespace': args.get('namespace'),
        }

        return await self._scheduled_run(scheduled_run_args)

    async def _list_scheduled_jobs(self, args: Dict[str, Any]) -> ToolResult:
        """List scheduled jobs"""
        # Fetch all scheduled jobs
        all_jobs = await self.client.list_scheduled_jobs(args.get('namespace'))

        # Filter jobs
        jobs = all_jobs

        # Default: hide suspended jobs unless --all is specified
        if not args.get('all', False):
            jobs = [job for job in jobs if not job.get('suspend', False)]

        # Format as markdown table
        table = format_scheduled_jobs_table(jobs)

        if len(jobs) == 0:
            if args.get('all', False):
                return {
                    "formatted": "No scheduled jobs found.",
                    "totalResults": 0,
                    "resultsShared": 0
                }
            return {
                "formatted": 'No active scheduled jobs found. Use `{"args": {"all": true}}` to show suspended jobs.',
                "totalResults": 0,
                "resultsShared": 0
            }

        response = f"**Scheduled Jobs ({len(jobs)} of {len(all_jobs)} total):**\n\n{table}"
        return {
            "formatted": response,
            "totalResults": len(all_jobs),
            "resultsShared": len(jobs)
        }

    async def _inspect_scheduled_job(self, args: Dict[str, Any]) -> ToolResult:
        """Get details of a scheduled job"""
        scheduled_job_id = args.get('scheduled_job_id')
        if not scheduled_job_id:
            return {
                "formatted": "scheduled_job_id is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

        job = await self.client.get_scheduled_job(scheduled_job_id, args.get('namespace'))
        formatted_details = format_scheduled_job_details(job)

        return {
            "formatted": f"**Scheduled Job Details:**\n\n{formatted_details}",
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _delete_scheduled_job(self, args: Dict[str, Any]) -> ToolResult:
        """Delete a scheduled job"""
        scheduled_job_id = args.get('scheduled_job_id')
        if not scheduled_job_id:
            return {
                "formatted": "scheduled_job_id is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

        await self.client.delete_scheduled_job(scheduled_job_id, args.get('namespace'))

        return {
            "formatted": f"✓ Scheduled job {scheduled_job_id} has been deleted.",
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _suspend_scheduled_job(self, args: Dict[str, Any]) -> ToolResult:
        """Suspend a scheduled job"""
        scheduled_job_id = args.get('scheduled_job_id')
        if not scheduled_job_id:
            return {
                "formatted": "scheduled_job_id is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

        await self.client.suspend_scheduled_job(scheduled_job_id, args.get('namespace'))

        response = f"""✓ Scheduled job {scheduled_job_id} has been suspended.

To resume, call this tool with `{{"operation": "scheduled resume", "args": {{"scheduled_job_id": "{scheduled_job_id}"}}}}`"""

        return {
            "formatted": response,
            "totalResults": 1,
            "resultsShared": 1
        }

    async def _resume_scheduled_job(self, args: Dict[str, Any]) -> ToolResult:
        """Resume a suspended scheduled job"""
        scheduled_job_id = args.get('scheduled_job_id')
        if not scheduled_job_id:
            return {
                "formatted": "scheduled_job_id is required",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True
            }

        await self.client.resume_scheduled_job(scheduled_job_id, args.get('namespace'))

        response = f"""✓ Scheduled job {scheduled_job_id} has been resumed.

To inspect, call this tool with `{{"operation": "scheduled inspect", "args": {{"scheduled_job_id": "{scheduled_job_id}"}}}}`"""

        return {
            "formatted": response,
            "totalResults": 1,
            "resultsShared": 1
        }


# Tool specification for agent registration
HF_JOBS_TOOL_SPEC = {
    "name": "hf_jobs",
    "description": (
        "Manage Hugging Face CPU/GPU compute jobs. Run commands in Docker containers, "
        "execute Python scripts with UV. List, schedule and monitor jobs/logs. "
        "Call this tool with no operation for full usage instructions and examples."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "run", "uv", "ps", "logs", "inspect", "cancel",
                    "scheduled run", "scheduled uv", "scheduled ps",
                    "scheduled inspect", "scheduled delete", "scheduled suspend", "scheduled resume"
                ],
                "description": (
                    "Operation to execute. Valid values: run, uv, ps, logs, inspect, cancel, "
                    "scheduled run, scheduled uv, scheduled ps, scheduled inspect, scheduled delete, "
                    "scheduled suspend, scheduled resume"
                )
            },
            "args": {
                "type": "object",
                "description": "Operation-specific arguments as a JSON object",
                "additionalProperties": True
            }
        }
    }
}


async def hf_jobs_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        tool = HfJobsTool()
        result = await tool.execute(arguments)
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error executing HF Jobs tool: {str(e)}", False
