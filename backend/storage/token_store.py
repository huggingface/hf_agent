"""Encrypted in-memory token storage.

Stores HF OAuth tokens and optional Anthropic API keys for authenticated users.
Tokens are encrypted at rest using Fernet symmetric encryption.
"""

import os
import secrets
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


@dataclass
class UserTokens:
    """Tokens associated with a user session."""

    hf_token: str  # HF OAuth access token
    anthropic_key: Optional[str] = None  # User-provided Anthropic API key
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # User info from OAuth
    username: str = ""
    name: Optional[str] = None
    picture: Optional[str] = None


class TokenStore:
    """Encrypted in-memory storage for user tokens.

    Security features:
    - Tokens encrypted with Fernet (AES-128-CBC)
    - Automatic expiry of old tokens
    - No persistence to disk
    """

    def __init__(
        self,
        encryption_key: Optional[str] = None,
        token_lifetime_hours: int = 8,
    ):
        # Use provided key or generate one
        key = encryption_key or os.environ.get("TOKEN_ENCRYPTION_KEY")
        if key:
            # Ensure key is valid Fernet format (32 url-safe base64 bytes)
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        else:
            # Generate a new key (note: won't survive restarts)
            self._fernet = Fernet(Fernet.generate_key())

        self._token_lifetime = timedelta(hours=token_lifetime_hours)

        # user_id -> encrypted UserTokens data
        self._store: dict[str, bytes] = {}

    def _encrypt(self, data: str) -> bytes:
        """Encrypt a string."""
        return self._fernet.encrypt(data.encode())

    def _decrypt(self, data: bytes) -> str:
        """Decrypt bytes to string."""
        return self._fernet.decrypt(data).decode()

    def _serialize_tokens(self, tokens: UserTokens) -> str:
        """Serialize UserTokens to a string."""
        import json
        return json.dumps({
            "hf_token": tokens.hf_token,
            "anthropic_key": tokens.anthropic_key,
            "created_at": tokens.created_at.isoformat(),
            "last_accessed": tokens.last_accessed.isoformat(),
            "username": tokens.username,
            "name": tokens.name,
            "picture": tokens.picture,
        })

    def _deserialize_tokens(self, data: str) -> UserTokens:
        """Deserialize string to UserTokens."""
        import json
        d = json.loads(data)
        return UserTokens(
            hf_token=d["hf_token"],
            anthropic_key=d.get("anthropic_key"),
            created_at=datetime.fromisoformat(d["created_at"]),
            last_accessed=datetime.fromisoformat(d["last_accessed"]),
            username=d.get("username", ""),
            name=d.get("name"),
            picture=d.get("picture"),
        )

    def store_tokens(
        self,
        user_id: str,
        hf_token: str,
        username: str = "",
        name: Optional[str] = None,
        picture: Optional[str] = None,
        anthropic_key: Optional[str] = None,
    ) -> None:
        """Store tokens for a user.

        Args:
            user_id: The user identifier (HF username)
            hf_token: HF OAuth access token
            username: Display username
            name: Display name
            picture: Profile picture URL
            anthropic_key: Optional Anthropic API key
        """
        tokens = UserTokens(
            hf_token=hf_token,
            anthropic_key=anthropic_key,
            username=username,
            name=name,
            picture=picture,
        )
        encrypted = self._encrypt(self._serialize_tokens(tokens))
        self._store[user_id] = encrypted
        logger.info(f"Stored tokens for user {user_id}")

    def get_tokens(self, user_id: str) -> Optional[UserTokens]:
        """Get tokens for a user.

        Args:
            user_id: The user identifier

        Returns:
            UserTokens if found and not expired, None otherwise
        """
        encrypted = self._store.get(user_id)
        if not encrypted:
            return None

        try:
            tokens = self._deserialize_tokens(self._decrypt(encrypted))

            # Check if expired
            if datetime.now(timezone.utc) - tokens.created_at > self._token_lifetime:
                self.remove_tokens(user_id)
                return None

            # Update last accessed
            tokens.last_accessed = datetime.now(timezone.utc)
            self._store[user_id] = self._encrypt(self._serialize_tokens(tokens))

            return tokens
        except Exception as e:
            logger.error(f"Error retrieving tokens for {user_id}: {e}")
            return None

    def get_hf_token(self, user_id: str) -> Optional[str]:
        """Get just the HF token for a user."""
        tokens = self.get_tokens(user_id)
        return tokens.hf_token if tokens else None

    def get_anthropic_key(self, user_id: str) -> Optional[str]:
        """Get the Anthropic API key for a user."""
        tokens = self.get_tokens(user_id)
        return tokens.anthropic_key if tokens else None

    def set_anthropic_key(self, user_id: str, key: str) -> bool:
        """Set or update the Anthropic API key for a user.

        Args:
            user_id: The user identifier
            key: The Anthropic API key

        Returns:
            True if successful, False if user not found
        """
        tokens = self.get_tokens(user_id)
        if not tokens:
            return False

        tokens.anthropic_key = key
        self._store[user_id] = self._encrypt(self._serialize_tokens(tokens))
        logger.info(f"Set Anthropic key for user {user_id}")
        return True

    def remove_anthropic_key(self, user_id: str) -> bool:
        """Remove the Anthropic API key for a user."""
        tokens = self.get_tokens(user_id)
        if not tokens:
            return False

        tokens.anthropic_key = None
        self._store[user_id] = self._encrypt(self._serialize_tokens(tokens))
        return True

    def remove_tokens(self, user_id: str) -> bool:
        """Remove all tokens for a user.

        Args:
            user_id: The user identifier

        Returns:
            True if removed, False if not found
        """
        if user_id in self._store:
            del self._store[user_id]
            logger.info(f"Removed tokens for user {user_id}")
            return True
        return False

    def has_tokens(self, user_id: str) -> bool:
        """Check if a user has stored tokens."""
        return user_id in self._store

    def cleanup_expired(self) -> int:
        """Remove expired tokens.

        Returns:
            Number of tokens cleaned up
        """
        now = datetime.now(timezone.utc)
        to_remove = []

        for user_id, encrypted in self._store.items():
            try:
                tokens = self._deserialize_tokens(self._decrypt(encrypted))
                if now - tokens.created_at > self._token_lifetime:
                    to_remove.append(user_id)
            except Exception:
                to_remove.append(user_id)

        for user_id in to_remove:
            del self._store[user_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} expired token entries")

        return len(to_remove)

    @property
    def active_user_count(self) -> int:
        """Get count of users with stored tokens."""
        return len(self._store)


# Global token store instance
token_store = TokenStore()
