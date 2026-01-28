"""User context for authenticated requests.

Provides UserContext dataclass and FastAPI dependency for extracting
authenticated user information from JWT session tokens.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from auth.jwt_handler import jwt_handler
from fastapi import Depends, HTTPException, Request, status
from storage.token_store import token_store

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """Context for an authenticated user request.

    Contains user identity and tokens needed for HF API operations.
    """

    user_id: str  # HF username
    hf_token: str  # HF OAuth access token
    username: str  # Display username
    name: Optional[str] = None  # Display name
    picture: Optional[str] = None  # Profile picture URL
    anthropic_key: Optional[str] = None  # Optional Anthropic API key

    @property
    def has_anthropic_key(self) -> bool:
        """Check if user has an Anthropic API key set."""
        return bool(self.anthropic_key)


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(request: Request) -> Optional[UserContext]:
    """Get the current authenticated user from the request.

    This is a soft authentication check - returns None if not authenticated
    rather than raising an exception.

    Args:
        request: The FastAPI request

    Returns:
        UserContext if authenticated, None otherwise
    """
    token = _extract_bearer_token(request)
    if not token:
        return None

    # Verify JWT
    payload = jwt_handler.verify_token(token)
    if not payload:
        return None

    # Get user's tokens from store
    tokens = token_store.get_tokens(payload.user_id)
    if not tokens:
        return None

    return UserContext(
        user_id=payload.user_id,
        hf_token=tokens.hf_token,
        username=tokens.username,
        name=tokens.name,
        picture=tokens.picture,
        anthropic_key=tokens.anthropic_key,
    )


async def require_auth(request: Request) -> UserContext:
    """Require authentication for a request.

    This is a hard authentication check - raises HTTPException if not authenticated.

    Args:
        request: The FastAPI request

    Returns:
        UserContext for the authenticated user

    Raises:
        HTTPException: 401 if not authenticated
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_anthropic_key(
    user: UserContext = Depends(require_auth),
) -> UserContext:
    """Require authentication AND an Anthropic API key.

    Args:
        user: The authenticated user context

    Returns:
        UserContext with Anthropic key

    Raises:
        HTTPException: 401 if not authenticated, 403 if no Anthropic key
    """
    if not user.has_anthropic_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anthropic API key required. Please set your API key first.",
        )
    return user


def get_optional_user(request: Request) -> Optional[UserContext]:
    """Synchronous version for cases where async isn't available."""
    token = _extract_bearer_token(request)
    if not token:
        return None

    payload = jwt_handler.verify_token(token)
    if not payload:
        return None

    tokens = token_store.get_tokens(payload.user_id)
    if not tokens:
        return None

    return UserContext(
        user_id=payload.user_id,
        hf_token=tokens.hf_token,
        username=tokens.username,
        name=tokens.name,
        picture=tokens.picture,
        anthropic_key=tokens.anthropic_key,
    )
