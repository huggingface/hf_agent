"""DuckDB-based storage with HF Dataset persistence.

Provides fast in-memory queries with periodic sync to HF Dataset (parquet).
On startup, recovers recent sessions from HF Dataset.

Architecture:
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │    Routes    │───▶│ DuckDBStorage│───▶│  HF Syncer   │
    └──────────────┘    │  (in-memory) │    │  (background)│
                        └──────────────┘    └──────────────┘
                              │                    │
                              ▼                    ▼
                        ┌────────────┐      ┌─────────────┐
                        │  DuckDB    │      │ HF Dataset  │
                        │  :memory:  │      │ (parquet)   │
                        └────────────┘      └─────────────┘

HF Dataset Structure:
    smolagents/hf-agent-sessions/
    ├── sessions/
    │   ├── 2026-01/
    │   │   ├── batch_abc123.parquet
    │   │   └── ...
    │   └── ...
    └── metadata/
        └── schema_version.json
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from uuid import uuid4

import duckdb
from huggingface_hub import HfApi
from huggingface_hub.utils import HfHubHTTPError

from .hf_storage import PersistedSession, SessionIndexEntry

logger = logging.getLogger(__name__)

# Schema version for migrations
SCHEMA_VERSION = 1

# How far back to recover sessions on startup
RECOVERY_DAYS = 90


@dataclass
class DirtySession:
    """Tracks a session that needs to be synced."""

    session: PersistedSession
    marked_at: datetime


class DuckDBStorage:
    """DuckDB-based storage with HF Dataset persistence.

    Features:
    - Fast in-memory queries (<10ms for most operations)
    - Dirty-flag tracking for efficient sync
    - Background sync to HF Dataset (parquet format)
    - Recovery from HF Dataset on startup
    - User isolation enforced at query level
    """

    def __init__(
        self,
        hf_repo_id: str,
        hf_token: Optional[str] = None,
        sync_interval: int = 30,
        recovery_days: int = RECOVERY_DAYS,
    ):
        """Initialize DuckDB storage.

        Args:
            hf_repo_id: HF Dataset repo ID for persistence
            hf_token: HF token for authentication
            sync_interval: Seconds between background syncs
            recovery_days: How many days of history to recover on startup
        """
        self.hf_repo_id = hf_repo_id
        self.hf_token = hf_token
        self.sync_interval = sync_interval
        self.recovery_days = recovery_days

        # DuckDB connection (in-memory)
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

        # HF API
        self.api = HfApi(token=hf_token)

        # Background sync
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()

        # Rate limit handling
        self._consecutive_failures = 0
        self._max_backoff_seconds = 300

    async def start(self) -> None:
        """Start the storage layer.

        Creates schema, recovers from HF, and starts background sync.
        """
        if self._running:
            return

        # Create in-memory database
        self.conn = duckdb.connect(":memory:")
        self._create_schema()

        # Recover from HF Dataset
        await self._recover_from_hf()

        # Start background sync
        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("DuckDB storage started")

    async def stop(self) -> None:
        """Stop the storage layer and flush pending changes."""
        self._running = False

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # Final flush (best effort - don't fail shutdown on sync errors)
        try:
            await self._sync_to_hf()
        except Exception as e:
            logger.warning(f"Final sync failed during shutdown: {e}")

        if self.conn:
            self.conn.close()
            self.conn = None

        logger.info("DuckDB storage stopped")

    def _create_schema(self) -> None:
        """Create the sessions table schema."""
        if not self.conn:
            return

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                title VARCHAR DEFAULT 'Untitled',
                model_name VARCHAR,
                status VARCHAR DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                message_count INTEGER DEFAULT 0,
                last_message_preview VARCHAR(200),
                messages_json TEXT,
                context_summary TEXT,
                metadata JSON,
                version INTEGER DEFAULT 1,
                is_dirty BOOLEAN DEFAULT TRUE
            )
        """)

        # Index for user session lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_status
            ON sessions(user_id, status, updated_at DESC)
        """)

        # Index for dirty session sync (DuckDB doesn't support partial indexes)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_dirty
            ON sessions(is_dirty)
        """)

        logger.debug("DuckDB schema created")

    async def _recover_from_hf(self) -> None:
        """Load recent sessions from HF Dataset on startup."""
        if not self.conn or not self.hf_token:
            logger.warning("Skipping HF recovery (no token or connection)")
            return

        try:
            # List parquet files in the sessions directory
            files = await asyncio.to_thread(
                self.api.list_repo_files,
                repo_id=self.hf_repo_id,
                repo_type="dataset",
            )

            parquet_files = [
                f for f in files if f.startswith("sessions/") and f.endswith(".parquet")
            ]

            if not parquet_files:
                logger.info("No parquet files found, trying JSON fallback")
                await self._recover_from_json()
                return

            logger.info(f"Found {len(parquet_files)} parquet files for recovery")

            # Download and load parquet files
            recovered = 0
            for parquet_file in parquet_files:
                try:
                    local_path = await asyncio.to_thread(
                        self.api.hf_hub_download,
                        repo_id=self.hf_repo_id,
                        filename=parquet_file,
                        repo_type="dataset",
                    )

                    # Load parquet into DuckDB
                    self.conn.execute(
                        f"""
                        INSERT OR REPLACE INTO sessions
                        SELECT
                            session_id,
                            user_id,
                            title,
                            model_name,
                            status,
                            created_at,
                            updated_at,
                            message_count,
                            last_message_preview,
                            messages_json,
                            context_summary,
                            metadata,
                            version,
                            FALSE as is_dirty
                        FROM read_parquet('{local_path}')
                        WHERE status != 'deleted'
                        """
                    )
                    recovered += 1
                except Exception as e:
                    logger.debug(f"Failed to load {parquet_file}: {e}")

            count = self.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            logger.info(f"Recovered {count} sessions from {recovered} parquet files")

        except duckdb.IOException as e:
            # No parquet files yet, try JSON fallback
            logger.info(f"No parquet files found, trying JSON fallback: {e}")
            await self._recover_from_json()
        except Exception as e:
            logger.warning(f"Recovery from HF failed (starting fresh): {e}")

    async def _recover_from_json(self) -> None:
        """Fallback: recover from existing JSON session files."""
        if not self.conn:
            return

        try:
            # List session files
            files = await asyncio.to_thread(
                self.api.list_repo_files,
                repo_id=self.hf_repo_id,
                repo_type="dataset",
            )

            session_files = [f for f in files if f.startswith("sessions/") and f.endswith(".json")]
            logger.info(f"Found {len(session_files)} JSON session files for recovery")

            recovered = 0
            for session_file in session_files[:500]:  # Limit initial recovery
                try:
                    local_path = await asyncio.to_thread(
                        self.api.hf_hub_download,
                        repo_id=self.hf_repo_id,
                        filename=session_file,
                        repo_type="dataset",
                    )
                    with open(local_path, "r") as f:
                        session = PersistedSession.from_json(f.read())

                    # Insert into DuckDB
                    self._insert_session(session, is_dirty=False)
                    recovered += 1
                except Exception as e:
                    logger.debug(f"Failed to recover {session_file}: {e}")

            logger.info(f"Recovered {recovered} sessions from JSON files")

        except Exception as e:
            logger.warning(f"JSON recovery failed: {e}")

    def _insert_session(self, session: PersistedSession, is_dirty: bool = True) -> None:
        """Insert or replace a session in DuckDB."""
        if not self.conn:
            return

        self.conn.execute(
            """
            INSERT OR REPLACE INTO sessions (
                session_id, user_id, title, model_name, status,
                created_at, updated_at, message_count, last_message_preview,
                messages_json, context_summary, metadata, version, is_dirty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session.session_id,
                session.user_id,
                session.title,
                session.model_name,
                session.status,
                session.created_at,
                session.updated_at,
                session.message_count,
                session.last_message_preview,
                session.messages_json,
                session.context_summary,
                session.metadata,
                session.version,
                is_dirty,
            ],
        )

    async def mark_dirty(self, session: PersistedSession) -> None:
        """Mark a session as needing sync.

        Args:
            session: The session to persist
        """
        async with self._lock:
            self._insert_session(session, is_dirty=True)
        logger.debug(f"Marked session {session.session_id} dirty")

    async def list_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[SessionIndexEntry]:
        """List sessions for a user.

        Args:
            user_id: User ID (required for isolation)
            limit: Maximum sessions to return
            offset: Pagination offset
            include_archived: Include archived sessions

        Returns:
            List of session index entries
        """
        if not self.conn:
            return []

        status_filter = "('active', 'archived')" if include_archived else "('active')"

        result = self.conn.execute(
            f"""
            SELECT
                session_id, title, created_at, updated_at,
                status, message_count, last_message_preview
            FROM sessions
            WHERE user_id = ?
            AND status IN {status_filter}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            [user_id, limit, offset],
        ).fetchall()

        return [
            SessionIndexEntry(
                session_id=row[0],
                title=row[1],
                created_at=str(row[2]) if row[2] else "",
                updated_at=str(row[3]) if row[3] else "",
                status=row[4],
                message_count=row[5] or 0,
                last_message_preview=row[6] or "",
            )
            for row in result
        ]

    async def load_session(
        self, session_id: str, user_id: Optional[str] = None
    ) -> Optional[PersistedSession]:
        """Load a session by ID.

        Args:
            session_id: Session ID
            user_id: User ID for ownership verification (if provided)

        Returns:
            PersistedSession if found and accessible
        """
        if not self.conn:
            return None

        # Build query with optional user filter
        if user_id:
            query = """
                SELECT session_id, user_id, title, model_name, status,
                       created_at, updated_at, message_count, last_message_preview,
                       messages_json, context_summary, metadata, version
                FROM sessions
                WHERE session_id = ? AND user_id = ?
            """
            result = self.conn.execute(query, [session_id, user_id]).fetchone()
        else:
            query = """
                SELECT session_id, user_id, title, model_name, status,
                       created_at, updated_at, message_count, last_message_preview,
                       messages_json, context_summary, metadata, version
                FROM sessions
                WHERE session_id = ?
            """
            result = self.conn.execute(query, [session_id]).fetchone()

        if not result:
            return None

        return PersistedSession(
            session_id=result[0],
            user_id=result[1],
            title=result[2] or "Untitled",
            model_name=result[3] or "unknown",
            status=result[4] or "active",
            created_at=str(result[5]) if result[5] else "",
            updated_at=str(result[6]) if result[6] else "",
            message_count=result[7] or 0,
            last_message_preview=result[8] or "",
            messages_json=result[9] or "[]",
            context_summary=result[10],
            metadata=result[11] or "{}",
            version=result[12] or 1,
        )

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Soft-delete a session (mark as deleted).

        Args:
            session_id: Session to delete
            user_id: Owner user ID (required for authorization)

        Returns:
            True if deleted, False if not found or not authorized
        """
        if not self.conn:
            return False

        # Verify ownership and update
        result = self.conn.execute(
            """
            UPDATE sessions
            SET status = 'deleted',
                updated_at = NOW(),
                version = version + 1,
                is_dirty = TRUE
            WHERE session_id = ? AND user_id = ?
            RETURNING session_id
            """,
            [session_id, user_id],
        ).fetchone()

        return result is not None

    async def _sync_loop(self) -> None:
        """Background loop for periodic syncing to HF."""
        while self._running:
            try:
                await asyncio.sleep(self._calculate_sync_interval())
                await self._sync_to_hf()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                self._consecutive_failures += 1

    def _calculate_sync_interval(self) -> float:
        """Calculate sync interval with exponential backoff on failures."""
        if self._consecutive_failures == 0:
            return self.sync_interval

        backoff = min(
            self.sync_interval * (2**self._consecutive_failures),
            self._max_backoff_seconds,
        )
        return backoff

    async def _sync_to_hf(self) -> None:
        """Sync dirty sessions to HF Dataset as parquet."""
        if not self.conn or not self.hf_token:
            return

        async with self._lock:
            # Check for dirty records
            dirty_count = self.conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE is_dirty = TRUE"
            ).fetchone()[0]

            if dirty_count == 0:
                return

            logger.info(f"Syncing {dirty_count} dirty sessions to HF")

            try:
                # Export dirty records to parquet
                now = datetime.now(timezone.utc)
                batch_id = str(uuid4())[:8]
                parquet_filename = f"batch_{now:%Y%m%d_%H%M%S}_{batch_id}.parquet"

                with tempfile.TemporaryDirectory() as tmpdir:
                    local_parquet = Path(tmpdir) / parquet_filename

                    # Export to parquet (all columns except is_dirty)
                    self.conn.execute(
                        f"""
                        COPY (
                            SELECT
                                session_id, user_id, title, model_name, status,
                                created_at, updated_at, message_count, last_message_preview,
                                messages_json, context_summary, metadata, version
                            FROM sessions
                            WHERE is_dirty = TRUE
                        ) TO '{local_parquet}' (FORMAT PARQUET)
                        """
                    )

                    # Upload to HF
                    remote_path = f"sessions/{now:%Y-%m}/{parquet_filename}"
                    await asyncio.to_thread(
                        self.api.upload_file,
                        path_or_fileobj=str(local_parquet),
                        path_in_repo=remote_path,
                        repo_id=self.hf_repo_id,
                        repo_type="dataset",
                    )

                # Mark as synced
                self.conn.execute("UPDATE sessions SET is_dirty = FALSE WHERE is_dirty = TRUE")
                self._consecutive_failures = 0
                logger.info(f"Synced {dirty_count} sessions to {remote_path}")

            except HfHubHTTPError as e:
                if hasattr(e, "response") and e.response.status_code == 429:
                    logger.warning("Rate limited during sync, will retry")
                else:
                    logger.error(f"HF sync error: {e}")
                self._consecutive_failures += 1
                raise
            except Exception as e:
                logger.error(f"Failed to sync to HF: {e}")
                self._consecutive_failures += 1
                raise

    async def force_sync(self) -> None:
        """Force an immediate sync of all dirty sessions."""
        await self._sync_to_hf()

    @property
    def dirty_count(self) -> int:
        """Get count of dirty sessions waiting for sync."""
        if not self.conn:
            return 0
        return self.conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE is_dirty = TRUE"
        ).fetchone()[0]

    async def get_session_count(self, user_id: Optional[str] = None) -> int:
        """Get total session count.

        Args:
            user_id: Filter by user (optional)

        Returns:
            Session count
        """
        if not self.conn:
            return 0

        if user_id:
            return self.conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE user_id = ? AND status != 'deleted'",
                [user_id],
            ).fetchone()[0]
        else:
            return self.conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE status != 'deleted'"
            ).fetchone()[0]
