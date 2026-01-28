"""JWT token handling for session authentication.

This module handles creation and verification of JWT session tokens.
These tokens are returned to the frontend after OAuth and used for all API calls.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pydantic import BaseModel


class TokenPayload(BaseModel):
    """JWT token payload."""

    user_id: str  # HF username
    exp: datetime
    iat: datetime
    jti: str  # Unique token ID


class JWTHandler:
    """Handles JWT session token creation and verification."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        token_lifetime_hours: int = 8,
    ):
        # Use provided secret or generate one (note: generated secret won't survive restarts)
        self.secret_key = (
            secret_key or os.environ.get("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
        )
        self.algorithm = algorithm
        self.token_lifetime = timedelta(hours=token_lifetime_hours)

        # Track revoked tokens (jti -> revocation time)
        self._revoked_tokens: dict[str, datetime] = {}

    def create_token(self, user_id: str) -> str:
        """Create a new JWT session token for a user.

        Args:
            user_id: The HF username

        Returns:
            Encoded JWT token string
        """
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "exp": now + self.token_lifetime,
            "iat": now,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify a JWT token and return its payload.

        Args:
            token: The JWT token string

        Returns:
            TokenPayload if valid, None if invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )

            # Check if token is revoked
            jti = payload.get("jti")
            if jti and jti in self._revoked_tokens:
                return None

            return TokenPayload(
                user_id=payload["user_id"],
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                jti=payload.get("jti", ""),
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def revoke_token(self, token: str) -> bool:
        """Revoke a token so it can no longer be used.

        Args:
            token: The JWT token to revoke

        Returns:
            True if revoked, False if token was invalid
        """
        payload = self.verify_token(token)
        if payload and payload.jti:
            self._revoked_tokens[payload.jti] = datetime.now(timezone.utc)
            return True
        return False

    def cleanup_revoked(self) -> int:
        """Remove expired tokens from the revoked list.

        Returns:
            Number of tokens cleaned up
        """
        now = datetime.now(timezone.utc)
        cutoff = now - self.token_lifetime

        to_remove = [
            jti
            for jti, revoked_at in self._revoked_tokens.items()
            if revoked_at < cutoff
        ]

        for jti in to_remove:
            del self._revoked_tokens[jti]

        return len(to_remove)


# Global JWT handler instance
jwt_handler = JWTHandler()
