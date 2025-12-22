"""
Base API client for Hugging Face API

Ported from: hf-mcp-server/packages/mcp/src/hf-api-call.ts
"""
import os
from typing import Optional, Dict, Any, TypeVar, Generic
import httpx


TResponse = TypeVar('TResponse')


class HfApiError(Exception):
    """Error from Hugging Face API"""

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        status_text: Optional[str] = None,
        response_body: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.status = status
        self.status_text = status_text
        self.response_body = response_body


class HfApiCall(Generic[TResponse]):
    """Base class for making authenticated API calls to Hugging Face"""

    def __init__(
        self,
        api_url: str,
        hf_token: Optional[str] = None,
        api_timeout: Optional[float] = None
    ):
        self.api_url = api_url
        self.hf_token = hf_token or os.getenv('HF_TOKEN')
        self.api_timeout = api_timeout or float(os.getenv('HF_API_TIMEOUT', '12.5'))

    async def fetch_from_api(
        self,
        url: str,
        method: str = "GET",
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[Any]:
        """Fetch data from API with auth and error handling"""
        headers = {
            "Accept": "application/json",
            **kwargs.pop("headers", {})
        }

        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        async with httpx.AsyncClient(timeout=self.api_timeout) as client:
            if method == "GET":
                response = await client.get(url, headers=headers, **kwargs)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json, **kwargs)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers, **kwargs)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=json, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if not response.is_success:
                raise HfApiError(
                    message=f"API request failed: {response.status_code} {response.reason_phrase}",
                    status=response.status_code,
                    status_text=response.reason_phrase,
                    response_body=response.text
                )

            # Handle empty responses (DELETE often returns empty)
            if not response.text:
                return None

            return response.json()
