"""Authentication routes for HF OAuth."""

import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth configuration from environment
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
OPENID_PROVIDER_URL = os.environ.get("OPENID_PROVIDER_URL", "https://huggingface.co")

# In-memory session store (replace with proper session management in production)
oauth_states: dict[str, dict] = {}


def get_redirect_uri(request: Request) -> str:
    """Get the OAuth callback redirect URI."""
    # In HF Spaces, use the SPACE_HOST if available
    space_host = os.environ.get("SPACE_HOST")
    if space_host:
        return f"https://{space_host}/auth/callback"
    # Otherwise construct from request
    return str(request.url_for("oauth_callback"))


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
    oauth_states[state] = {"redirect_uri": get_redirect_uri(request)}

    # Build authorization URL
    params = {
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": get_redirect_uri(request),
        "scope": "openid profile",
        "response_type": "code",
        "state": state,
    }
    auth_url = f"{OPENID_PROVIDER_URL}/oauth/authorize?{urlencode(params)}"

    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def oauth_callback(
    request: Request, code: str = "", state: str = ""
) -> RedirectResponse:
    """Handle OAuth callback."""
    # Verify state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    stored_state = oauth_states.pop(state)
    redirect_uri = stored_state["redirect_uri"]

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
            raise HTTPException(status_code=500, detail=f"Token exchange failed: {e}")

    # Get user info
    access_token = token_data.get("access_token")
    if access_token:
        async with httpx.AsyncClient() as client:
            try:
                userinfo_response = await client.get(
                    f"{OPENID_PROVIDER_URL}/oauth/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                userinfo_response.raise_for_status()
                user_info = userinfo_response.json()
            except httpx.HTTPError:
                user_info = {}
    else:
        user_info = {}

    # For now, redirect to home with token in query params
    # In production, use secure cookies or session storage
    redirect_params = {
        "access_token": access_token,
        "username": user_info.get("preferred_username", ""),
    }

    return RedirectResponse(url=f"/?{urlencode(redirect_params)}")


@router.get("/logout")
async def logout() -> RedirectResponse:
    """Log out the user."""
    return RedirectResponse(url="/")


@router.get("/me")
async def get_current_user(request: Request) -> dict:
    """Get current user info from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"authenticated": False}

    token = auth_header.split(" ")[1]

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{OPENID_PROVIDER_URL}/oauth/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            user_info = response.json()
            return {
                "authenticated": True,
                "username": user_info.get("preferred_username"),
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
            }
        except httpx.HTTPError:
            return {"authenticated": False}
