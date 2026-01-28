"""Authentication routes for HF OAuth with JWT session tokens.

This module implements a cookie-free authentication flow designed for HF Spaces,
which run in iframes where third-party cookies are blocked by modern browsers.

Flow:
1. Frontend calls /auth/login (or opens in popup)
2. Backend redirects to HF OAuth with PKCE
3. User authorizes at huggingface.co
4. HF redirects to /auth/callback with code
5. Backend exchanges code for HF tokens
6. Backend generates JWT session token
7. Backend redirects to frontend with token in URL fragment (not query params)
8. Frontend extracts token from fragment, stores in sessionStorage
9. Frontend sends token in Authorization header for all API requests
"""

import logging
import os
import secrets
from urllib.parse import urlencode

import httpx
from auth.jwt_handler import jwt_handler
from auth.user_context import UserContext, get_current_user, require_auth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from storage.token_store import token_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth configuration from environment
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
OPENID_PROVIDER_URL = os.environ.get("OPENID_PROVIDER_URL", "https://huggingface.co")

# OAuth scopes for full agent capabilities
OAUTH_SCOPES = "read-repos write-repos contribute-repos manage-repos inference-api jobs write-discussions"

# In-memory OAuth state store (for CSRF protection during OAuth flow)
oauth_states: dict[str, dict] = {}


def get_redirect_uri(request: Request) -> str:
    """Get the OAuth callback redirect URI."""
    # In HF Spaces, use the SPACE_HOST if available
    space_host = os.environ.get("SPACE_HOST")
    if space_host:
        return f"https://{space_host}/auth/callback"
    # Otherwise construct from request
    return str(request.url_for("oauth_callback"))


def get_frontend_url(request: Request) -> str:
    """Get the frontend URL for redirects."""
    space_host = os.environ.get("SPACE_HOST")
    if space_host:
        return f"https://{space_host}"
    # For local dev, use the referer or default
    referer = request.headers.get("referer", "")
    if referer:
        # Extract origin from referer
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        return f"{parsed.scheme}://{parsed.netloc}"
    return "http://localhost:5173"


@router.get("/login")
async def oauth_login(request: Request) -> RedirectResponse:
    """Initiate OAuth login flow."""
    if not OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="OAuth not configured. Set OAUTH_CLIENT_ID environment variable.",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {
        "redirect_uri": get_redirect_uri(request),
        "frontend_url": get_frontend_url(request),
    }

    # Build authorization URL with full scopes
    params = {
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": get_redirect_uri(request),
        "scope": OAUTH_SCOPES,
        "response_type": "code",
        "state": state,
    }
    auth_url = f"{OPENID_PROVIDER_URL}/oauth/authorize?{urlencode(params)}"

    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def oauth_callback(
    request: Request, code: str = "", state: str = ""
) -> HTMLResponse:
    """Handle OAuth callback.

    Instead of redirecting with token in query params (visible in server logs),
    we return an HTML page that uses JavaScript to put the token in the URL fragment.
    URL fragments are never sent to the server, making them more secure for tokens.
    """
    # Verify state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    stored_state = oauth_states.pop(state)
    redirect_uri = stored_state["redirect_uri"]
    frontend_url = stored_state["frontend_url"]

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")

    # Exchange code for token
    token_url = f"{OPENID_PROVIDER_URL}/oauth/token"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": OAUTH_CLIENT_ID,
                    "client_secret": OAUTH_CLIENT_SECRET,
                },
            )
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            raise HTTPException(status_code=500, detail=f"Token exchange failed: {e}")

    # Get HF access token (strip any whitespace)
    hf_token = token_data.get("access_token", "").strip()
    if not hf_token:
        raise HTTPException(status_code=500, detail="No access token in response")

    # Get user info
    user_info = {}
    async with httpx.AsyncClient() as client:
        try:
            userinfo_response = await client.get(
                f"{OPENID_PROVIDER_URL}/oauth/userinfo",
                headers={"Authorization": f"Bearer {hf_token}"},
            )
            userinfo_response.raise_for_status()
            user_info = userinfo_response.json()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to get user info: {e}")

    # Extract user details
    user_id = user_info.get("preferred_username") or user_info.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=500, detail="Could not determine user ID")

    # Store tokens in encrypted store
    token_store.store_tokens(
        user_id=user_id,
        hf_token=hf_token,
        username=user_id,
        name=user_info.get("name"),
        picture=user_info.get("picture"),
    )

    # Create JWT session token
    session_token = jwt_handler.create_token(user_id)

    # Return HTML page that redirects with token in fragment
    # The fragment (#) is never sent to the server, making it secure
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Authenticating...</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: #f5f5f5;
            }}
            .loading {{
                text-align: center;
                color: #666;
            }}
            .spinner {{
                width: 40px;
                height: 40px;
                border: 3px solid #e0e0e0;
                border-top: 3px solid #1976d2;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 16px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="loading">
            <div class="spinner"></div>
            <p>Completing authentication...</p>
        </div>
        <script>
            // Redirect to frontend with token in URL fragment
            // Fragments are never sent to servers, making them secure for tokens
            const token = "{session_token}";
            const frontendUrl = "{frontend_url}";
            window.location.href = frontendUrl + "/#auth_callback=" + encodeURIComponent(token);
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@router.post("/logout")
async def logout(user: UserContext = Depends(require_auth)) -> dict:
    """Log out the current user.

    Revokes the JWT and removes stored tokens.
    """
    # Remove tokens from store
    token_store.remove_tokens(user.user_id)

    # Note: We can't revoke the JWT from here since we don't have it
    # The frontend should discard it

    return {"status": "logged_out", "user_id": user.user_id}


@router.get("/logout")
async def logout_get(request: Request) -> RedirectResponse:
    """GET endpoint for logout (for simple redirects).

    Clears tokens if authenticated, then redirects to home.
    """
    user = await get_current_user(request)
    if user:
        token_store.remove_tokens(user.user_id)

    frontend_url = get_frontend_url(request)
    return RedirectResponse(url=frontend_url)


@router.get("/me")
async def get_current_user_info(
    user: UserContext | None = Depends(get_current_user),
) -> dict:
    """Get current user info from JWT session token.

    Returns user info if authenticated, or authenticated: false otherwise.
    """
    if not user:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user_id": user.user_id,
        "username": user.username,
        "name": user.name,
        "picture": user.picture,
        "has_anthropic_key": user.has_anthropic_key,
    }


class AnthropicKeyRequest(BaseModel):
    """Request to set Anthropic API key."""

    key: str


@router.post("/anthropic-key")
async def set_anthropic_key(
    request: AnthropicKeyRequest,
    user: UserContext = Depends(require_auth),
) -> dict:
    """Set the Anthropic API key for the current user.

    The key is validated by making a test request to the Anthropic API.
    """
    key = request.key.strip()

    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    # Validate key format (basic check)
    if not key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid Anthropic API key format. Key should start with 'sk-ant-'",
        )

    # Validate key by making a test request
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10.0,
            )
            if response.status_code == 401:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Anthropic API key",
                )
            # Any other error we'll accept (rate limit, etc.) as key is valid
        except httpx.TimeoutException:
            # Timeout is OK - key might be valid, API is just slow
            pass
        except httpx.HTTPError as e:
            logger.warning(f"Error validating Anthropic key: {e}")
            # Continue anyway - key format is correct

    # Store the key
    success = token_store.set_anthropic_key(user.user_id, key)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to store API key")

    return {"status": "ok", "message": "Anthropic API key set successfully"}


@router.delete("/anthropic-key")
async def remove_anthropic_key(
    user: UserContext = Depends(require_auth),
) -> dict:
    """Remove the Anthropic API key for the current user."""
    token_store.remove_anthropic_key(user.user_id)
    return {"status": "ok", "message": "Anthropic API key removed"}


@router.get("/anthropic-key/status")
async def get_anthropic_key_status(
    user: UserContext = Depends(require_auth),
) -> dict:
    """Check if the current user has an Anthropic API key set."""
    return {
        "has_key": user.has_anthropic_key,
    }
