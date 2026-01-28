"""Database client for the private ML Agent DB Space.

This module provides a client interface to the separate database Space,
keeping user secrets and sessions isolated from the main application.
"""

import base64
import json
import logging
import os
from typing import Optional

import httpx
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Database Space configuration
DB_SPACE_URL = os.environ.get("DB_SPACE_URL", "https://smolagents-ml-agent-db.hf.space")
DB_API_KEY = os.environ.get("DB_API_KEY", "dev-key-change-me")

# Encryption key for secrets (encryption happens client-side)
_cipher: Optional[Fernet] = None


def get_cipher() -> Fernet:
    """Get Fernet cipher for encrypting secrets."""
    global _cipher
    if _cipher is None:
        key = os.environ.get("ENCRYPTION_KEY")
        if not key:
            logger.warning("ENCRYPTION_KEY not set, using ephemeral key (dev only)")
            key = Fernet.generate_key().decode()
        _cipher = Fernet(key.encode() if isinstance(key, str) else key)
    return _cipher


def _get_headers() -> dict:
    """Get headers for DB API requests."""
    return {"X-API-Key": DB_API_KEY}


async def _request(method: str, path: str, **kwargs) -> dict:
    """Make a request to the DB Space."""
    url = f"{DB_SPACE_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, headers=_get_headers(), **kwargs)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def _request_sync(method: str, path: str, **kwargs) -> dict:
    """Make a synchronous request to the DB Space."""
    url = f"{DB_SPACE_URL}{path}"
    with httpx.Client(timeout=30.0) as client:
        response = client.request(method, url, headers=_get_headers(), **kwargs)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


# User operations
def upsert_user(
    hf_user_id: str, username: str, name: str = None, picture: str = None
) -> None:
    """Create or update a user."""
    _request_sync(
        "PUT",
        f"/users/{hf_user_id}",
        json={
            "hf_user_id": hf_user_id,
            "username": username,
            "name": name,
            "picture": picture,
        },
    )


def get_user(hf_user_id: str) -> dict | None:
    """Get user by HF user ID."""
    return _request_sync("GET", f"/users/{hf_user_id}")


# Secrets operations (encrypted client-side)
def store_user_secrets(hf_user_id: str, secrets: dict[str, str]) -> None:
    """Store encrypted user secrets."""
    cipher = get_cipher()
    encrypted = cipher.encrypt(json.dumps(secrets).encode())
    encoded = base64.b64encode(encrypted).decode()

    _request_sync(
        "PUT",
        f"/secrets/{hf_user_id}",
        json={
            "encrypted_secrets": encoded,
        },
    )


def get_user_secrets(hf_user_id: str) -> dict[str, str]:
    """Get decrypted user secrets."""
    result = _request_sync("GET", f"/secrets/{hf_user_id}")
    if not result or not result.get("encrypted_secrets"):
        return {}

    cipher = get_cipher()
    try:
        encrypted = base64.b64decode(result["encrypted_secrets"])
        decrypted = cipher.decrypt(encrypted)
        return json.loads(decrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt secrets for {hf_user_id}: {e}")
        return {}


def delete_user_secrets(hf_user_id: str) -> bool:
    """Delete user secrets."""
    result = _request_sync("DELETE", f"/secrets/{hf_user_id}")
    return result.get("deleted", False) if result else False


# Session operations
def save_session(
    session_id: str,
    hf_user_id: str,
    title: str | None = None,
    messages: list[dict] | None = None,
    config_snapshot: dict | None = None,
) -> None:
    """Save or update a session."""
    _request_sync(
        "PUT",
        f"/sessions/{session_id}",
        json={
            "session_id": session_id,
            "hf_user_id": hf_user_id,
            "title": title,
            "messages": messages,
            "config_snapshot": config_snapshot,
        },
    )


def get_session(session_id: str) -> dict | None:
    """Get a session by ID."""
    return _request_sync("GET", f"/sessions/{session_id}")


def list_user_sessions(hf_user_id: str, include_archived: bool = False) -> list[dict]:
    """List all sessions for a user."""
    params = {"include_archived": str(include_archived).lower()}
    result = _request_sync("GET", f"/users/{hf_user_id}/sessions", params=params)
    return result if result else []


def archive_session(session_id: str) -> bool:
    """Archive a session."""
    result = _request_sync("POST", f"/sessions/{session_id}/archive")
    return result.get("archived", False) if result else False


def delete_session(session_id: str) -> bool:
    """Delete a session."""
    result = _request_sync("DELETE", f"/sessions/{session_id}")
    return result.get("deleted", False) if result else False


# Async versions for use in async contexts
async def upsert_user_async(
    hf_user_id: str, username: str, name: str = None, picture: str = None
) -> None:
    """Create or update a user (async)."""
    await _request(
        "PUT",
        f"/users/{hf_user_id}",
        json={
            "hf_user_id": hf_user_id,
            "username": username,
            "name": name,
            "picture": picture,
        },
    )


async def save_session_async(
    session_id: str,
    hf_user_id: str,
    title: str | None = None,
    messages: list[dict] | None = None,
    config_snapshot: dict | None = None,
) -> None:
    """Save or update a session (async)."""
    await _request(
        "PUT",
        f"/sessions/{session_id}",
        json={
            "session_id": session_id,
            "hf_user_id": hf_user_id,
            "title": title,
            "messages": messages,
            "config_snapshot": config_snapshot,
        },
    )
