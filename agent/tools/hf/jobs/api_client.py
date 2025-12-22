"""
Jobs API Client

Ported from: hf-mcp-server/packages/mcp/src/jobs/api-client.ts
"""
from typing import Optional, Dict, Any, List
from agent.tools.hf.base import HfApiCall


class JobsApiClient(HfApiCall):
    """API client for HuggingFace Jobs API"""

    def __init__(self, hf_token: Optional[str] = None, namespace: Optional[str] = None):
        super().__init__('https://huggingface.co/api', hf_token)
        self.namespace_cache = namespace

    async def get_namespace(self, namespace: Optional[str] = None) -> str:
        """
        Get the namespace (username or org) for the current user
        Uses cached value or /api/whoami-v2 endpoint as fallback
        """
        if namespace:
            return namespace

        if self.namespace_cache:
            return self.namespace_cache

        # Fetch from whoami endpoint
        whoami = await self.fetch_from_api('https://huggingface.co/api/whoami-v2')
        self.namespace_cache = whoami['name']
        return self.namespace_cache

    async def run_job(self, job_spec: Dict[str, Any], namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a job
        POST /api/jobs/{namespace}
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/jobs/{ns}'

        result = await self.fetch_from_api(url, method='POST', json=job_spec)
        return result

    async def list_jobs(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all jobs for a namespace
        GET /api/jobs/{namespace}
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/jobs/{ns}'

        return await self.fetch_from_api(url)

    async def get_job(self, job_id: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed information about a specific job
        GET /api/jobs/{namespace}/{jobId}
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/jobs/{ns}/{job_id}'

        return await self.fetch_from_api(url)

    async def cancel_job(self, job_id: str, namespace: Optional[str] = None) -> None:
        """
        Cancel a running job
        POST /api/jobs/{namespace}/{jobId}/cancel
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/jobs/{ns}/{job_id}/cancel'

        await self.fetch_from_api(url, method='POST')

    def get_logs_url(self, job_id: str, namespace: str) -> str:
        """Get logs URL for a job (for SSE streaming)"""
        return f'https://huggingface.co/api/jobs/{namespace}/{job_id}/logs'

    async def create_scheduled_job(
        self,
        spec: Dict[str, Any],
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a scheduled job
        POST /api/scheduled-jobs/{namespace}
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/scheduled-jobs/{ns}'

        return await self.fetch_from_api(url, method='POST', json=spec)

    async def list_scheduled_jobs(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all scheduled jobs
        GET /api/scheduled-jobs/{namespace}
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/scheduled-jobs/{ns}'

        return await self.fetch_from_api(url)

    async def get_scheduled_job(
        self,
        scheduled_job_id: str,
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get details of a scheduled job
        GET /api/scheduled-jobs/{namespace}/{scheduledJobId}
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/scheduled-jobs/{ns}/{scheduled_job_id}'

        return await self.fetch_from_api(url)

    async def delete_scheduled_job(
        self,
        scheduled_job_id: str,
        namespace: Optional[str] = None
    ) -> None:
        """
        Delete a scheduled job
        DELETE /api/scheduled-jobs/{namespace}/{scheduledJobId}
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/scheduled-jobs/{ns}/{scheduled_job_id}'

        await self.fetch_from_api(url, method='DELETE')

    async def suspend_scheduled_job(
        self,
        scheduled_job_id: str,
        namespace: Optional[str] = None
    ) -> None:
        """
        Suspend a scheduled job
        POST /api/scheduled-jobs/{namespace}/{scheduledJobId}/suspend
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/scheduled-jobs/{ns}/{scheduled_job_id}/suspend'

        await self.fetch_from_api(url, method='POST')

    async def resume_scheduled_job(
        self,
        scheduled_job_id: str,
        namespace: Optional[str] = None
    ) -> None:
        """
        Resume a suspended scheduled job
        POST /api/scheduled-jobs/{namespace}/{scheduledJobId}/resume
        """
        ns = await self.get_namespace(namespace)
        url = f'https://huggingface.co/api/scheduled-jobs/{ns}/{scheduled_job_id}/resume'

        await self.fetch_from_api(url, method='POST')
