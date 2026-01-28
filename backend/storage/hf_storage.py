"""HF Dataset storage for session persistence.

Implements batched sync to HF Datasets with dirty-flag tracking.
Sessions are stored as individual JSON files, with per-user index files.

Dataset Structure:
    datasets/{repo_id}/
    ├── sessions/
    │   ├── {session_id_1}.json
    │   └── ...
    └── index/
        └── users/
            ├── {user_id_1}.jsonl
            └── ...
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional, Literal

from huggingface_hub import HfApi, CommitOperationAdd
from huggingface_hub.utils import HfHubHTTPError

logger = logging.getLogger(__name__)


@dataclass
class PersistedSession:
    """Session data structure for HF Dataset storage."""

    session_id: str
    user_id: str
    version: int  # Optimistic concurrency
    created_at: str  # ISO8601
    updated_at: str  # ISO8601
    title: str
    model_name: str
    status: Literal["active", "archived", "deleted"]
    messages_json: str  # JSON array of messages
    context_summary: Optional[str] = None  # Compacted summary
    metadata: str = "{}"  # Extensible JSON
    message_count: int = 0
    last_message_preview: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PersistedSession":
        """Create from dictionary."""
        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PersistedSession":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SessionIndexEntry:
    """Entry in the user's session index file."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    status: Literal["active", "archived", "deleted"]
    message_count: int
    last_message_preview: str

    def to_jsonl(self) -> str:
        """Serialize to JSONL line."""
        return json.dumps(asdict(self))

    @classmethod
    def from_jsonl(cls, line: str) -> "SessionIndexEntry":
        """Deserialize from JSONL line."""
        return cls(**json.loads(line))


@dataclass
class DirtySession:
    """Tracks a session that needs to be synced."""

    session: PersistedSession
    index_entry: SessionIndexEntry
    marked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HFStorageManager:
    """Manages session persistence to HF Datasets.

    Features:
    - Dirty-flag tracking for batched commits
    - Global background sync (every 30-60s)
    - Single commit for all dirty sessions + index updates
    - Rate-limit handling with exponential backoff
    """

    def __init__(
        self,
        repo_id: str,
        hf_token: Optional[str] = None,
        sync_interval_seconds: int = 30,
        max_files_per_commit: int = 50,
    ):
        """Initialize the storage manager.

        Args:
            repo_id: HF Dataset repo ID (e.g., "smolagents/hf-agent-sessions")
            hf_token: HF token for authentication (uses env var if not provided)
            sync_interval_seconds: Interval between sync attempts
            max_files_per_commit: Maximum files per commit (HF recommendation)
        """
        self.repo_id = repo_id
        self.api = HfApi(token=hf_token)
        self.sync_interval = sync_interval_seconds
        self.max_files_per_commit = max_files_per_commit

        # Dirty tracking
        self._dirty_sessions: dict[str, DirtySession] = {}
        self._lock = asyncio.Lock()

        # Background sync task
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False

        # Rate limit handling
        self._consecutive_failures = 0
        self._max_backoff_seconds = 300  # 5 minutes max

    async def start(self) -> None:
        """Start the background sync task."""
        if self._running:
            return

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info(f"HF Storage started for {self.repo_id}")

    async def stop(self) -> None:
        """Stop the background sync task and flush pending changes."""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._sync_dirty_sessions()
        logger.info("HF Storage stopped")

    async def _sync_loop(self) -> None:
        """Background loop for periodic syncing."""
        while self._running:
            try:
                await asyncio.sleep(self._calculate_sync_interval())
                await self._sync_dirty_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                self._consecutive_failures += 1

    def _calculate_sync_interval(self) -> float:
        """Calculate sync interval with exponential backoff on failures."""
        if self._consecutive_failures == 0:
            return self.sync_interval

        # Exponential backoff: base * 2^failures, capped at max
        backoff = min(
            self.sync_interval * (2 ** self._consecutive_failures),
            self._max_backoff_seconds,
        )
        logger.info(f"Sync backoff: {backoff}s (failures: {self._consecutive_failures})")
        return backoff

    async def mark_dirty(self, session: PersistedSession) -> None:
        """Mark a session as needing sync.

        Args:
            session: The session to mark dirty
        """
        async with self._lock:
            index_entry = SessionIndexEntry(
                session_id=session.session_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                status=session.status,
                message_count=session.message_count,
                last_message_preview=session.last_message_preview,
            )
            self._dirty_sessions[session.session_id] = DirtySession(
                session=session,
                index_entry=index_entry,
            )

    async def _sync_dirty_sessions(self) -> None:
        """Sync all dirty sessions to HF Dataset in a single commit."""
        async with self._lock:
            if not self._dirty_sessions:
                return

            # Take a snapshot of dirty sessions
            to_sync = dict(self._dirty_sessions)
            self._dirty_sessions.clear()

        if not to_sync:
            return

        logger.info(f"Syncing {len(to_sync)} dirty sessions to {self.repo_id}")

        try:
            # Build commit operations
            operations = []

            # Group by user for index updates
            user_sessions: dict[str, list[SessionIndexEntry]] = {}

            for session_id, dirty in to_sync.items():
                # Session file
                session_path = f"sessions/{session_id}.json"
                operations.append(
                    CommitOperationAdd(
                        path_in_repo=session_path,
                        path_or_fileobj=dirty.session.to_json().encode("utf-8"),
                    )
                )

                # Group for index
                user_id = dirty.session.user_id
                if user_id not in user_sessions:
                    user_sessions[user_id] = []
                user_sessions[user_id].append(dirty.index_entry)

            # User index files (we need to merge with existing)
            for user_id, entries in user_sessions.items():
                index_content = await self._build_user_index(user_id, entries)
                index_path = f"index/users/{user_id}.jsonl"
                operations.append(
                    CommitOperationAdd(
                        path_in_repo=index_path,
                        path_or_fileobj=index_content.encode("utf-8"),
                    )
                )

            # Batch commits if needed
            for i in range(0, len(operations), self.max_files_per_commit):
                batch = operations[i : i + self.max_files_per_commit]
                await self._commit_with_retry(batch)

            self._consecutive_failures = 0
            logger.info(f"Successfully synced {len(to_sync)} sessions")

        except Exception as e:
            # Put sessions back in dirty queue
            async with self._lock:
                for session_id, dirty in to_sync.items():
                    if session_id not in self._dirty_sessions:
                        self._dirty_sessions[session_id] = dirty

            self._consecutive_failures += 1
            logger.error(f"Failed to sync sessions: {e}")
            raise

    async def _build_user_index(
        self, user_id: str, new_entries: list[SessionIndexEntry]
    ) -> str:
        """Build the user's session index, merging with existing.

        Args:
            user_id: User ID
            new_entries: New/updated index entries

        Returns:
            JSONL content for the index file
        """
        # Fetch existing index
        existing: dict[str, SessionIndexEntry] = {}
        try:
            index_path = f"index/users/{user_id}.jsonl"
            # Force download to get latest version (bypass cache)
            content = await asyncio.to_thread(
                self.api.hf_hub_download,
                repo_id=self.repo_id,
                filename=index_path,
                repo_type="dataset",
                force_download=True,
            )
            with open(content, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = SessionIndexEntry.from_jsonl(line)
                        existing[entry.session_id] = entry
        except HfHubHTTPError:
            # Index doesn't exist yet
            pass
        except Exception as e:
            logger.warning(f"Error fetching user index for {user_id}: {e}")

        # Merge new entries
        for entry in new_entries:
            existing[entry.session_id] = entry

        # Build JSONL
        lines = [entry.to_jsonl() for entry in existing.values()]
        return "\n".join(lines)

    async def _commit_with_retry(
        self,
        operations: list[CommitOperationAdd],
        max_retries: int = 3,
    ) -> None:
        """Commit operations with retry on rate limits.

        Args:
            operations: Commit operations
            max_retries: Maximum retry attempts
        """
        for attempt in range(max_retries):
            try:
                await asyncio.to_thread(
                    self.api.create_commit,
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    operations=operations,
                    commit_message=f"Sync {len(operations)} session files",
                )
                return
            except HfHubHTTPError as e:
                if e.response.status_code == 429:
                    # Rate limited
                    wait_time = 2 ** attempt * 5  # 5s, 10s, 20s
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise

        raise Exception(f"Failed to commit after {max_retries} retries")

    async def load_session(self, session_id: str) -> Optional[PersistedSession]:
        """Load a session from HF Dataset.

        Args:
            session_id: Session ID to load

        Returns:
            PersistedSession if found, None otherwise
        """
        try:
            session_path = f"sessions/{session_id}.json"
            # Force download to get latest version (bypass cache)
            local_path = await asyncio.to_thread(
                self.api.hf_hub_download,
                repo_id=self.repo_id,
                filename=session_path,
                repo_type="dataset",
                force_download=True,
            )
            with open(local_path, "r") as f:
                return PersistedSession.from_json(f.read())
        except HfHubHTTPError:
            return None
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None

    async def load_user_sessions(self, user_id: str) -> list[SessionIndexEntry]:
        """Load session index for a user.

        Args:
            user_id: User ID

        Returns:
            List of session index entries
        """
        try:
            index_path = f"index/users/{user_id}.jsonl"
            # Force download to get latest version (bypass cache)
            local_path = await asyncio.to_thread(
                self.api.hf_hub_download,
                repo_id=self.repo_id,
                filename=index_path,
                repo_type="dataset",
                force_download=True,
            )
            entries = []
            with open(local_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(SessionIndexEntry.from_jsonl(line))
            return entries
        except HfHubHTTPError:
            return []
        except Exception as e:
            logger.error(f"Error loading user sessions for {user_id}: {e}")
            return []

    async def force_sync(self) -> None:
        """Force an immediate sync of all dirty sessions."""
        await self._sync_dirty_sessions()

    @property
    def dirty_count(self) -> int:
        """Get count of dirty sessions waiting for sync."""
        return len(self._dirty_sessions)
