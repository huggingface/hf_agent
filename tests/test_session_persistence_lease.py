"""Lease + pending-submission control plane tests for ``MongoSessionStore``.

Uses ``mongomock-motor`` to simulate Mongo's atomic ``findOneAndUpdate``
semantics without requiring a real replica set. Change-stream paths are
tested separately (or skipped here) because ``mongomock`` does not implement
``watch()``.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta

import pytest

mongomock_motor = pytest.importorskip(
    "mongomock_motor",
    reason="mongomock-motor is required for the lease control-plane tests",
)

from agent.core.session_persistence import (  # noqa: E402
    MongoSessionStore,
    NoopSessionStore,
    make_holder_id,
)


def _make_store() -> MongoSessionStore:
    """Build a ``MongoSessionStore`` wired to an in-memory mongomock client."""
    client = mongomock_motor.AsyncMongoMockClient()
    store = MongoSessionStore.__new__(MongoSessionStore)
    store.uri = "mongodb://mock"
    store.db_name = "test"
    store.client = client
    store.db = client["test"]
    store.enabled = True
    return store


async def _seed_session(store: MongoSessionStore, session_id: str = "s1") -> None:
    await store.db.sessions.insert_one(
        {
            "_id": session_id,
            "session_id": session_id,
            "user_id": "u1",
            "status": "active",
            "runtime_state": "idle",
            "last_active_at": datetime.now(UTC),
        }
    )


# ── Lease ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_lease_exactly_once_concurrent():
    store = _make_store()
    await _seed_session(store)

    results = await asyncio.gather(
        *[store.claim_lease("s1", f"holder-{i}", ttl_s=30) for i in range(10)]
    )
    winners = [r for r in results if r is not None]
    assert len(winners) == 1, f"expected exactly 1 winner, got {len(winners)}"
    assert winners[0]["lease"]["holder_id"].startswith("holder-")


@pytest.mark.asyncio
async def test_renew_lease_wrong_holder_returns_none():
    store = _make_store()
    await _seed_session(store)
    claimed = await store.claim_lease("s1", "holder-A", ttl_s=30)
    assert claimed is not None

    result = await store.renew_lease("s1", "holder-B", ttl_s=30)
    assert result is None


@pytest.mark.asyncio
async def test_renew_lease_correct_holder_extends_ttl():
    store = _make_store()
    await _seed_session(store)
    claimed = await store.claim_lease("s1", "holder-A", ttl_s=30)
    assert claimed is not None
    initial_expiry = claimed["lease"]["expires_at"]

    # Sleep briefly so wall-clock advances enough to detect the bump.
    await asyncio.sleep(0.01)
    renewed = await store.renew_lease("s1", "holder-A", ttl_s=30)
    assert renewed is not None
    assert renewed["lease"]["expires_at"] > initial_expiry


@pytest.mark.asyncio
async def test_release_lease_idempotent():
    store = _make_store()
    await _seed_session(store)
    await store.claim_lease("s1", "holder-A", ttl_s=30)

    await store.release_lease("s1", "holder-A")
    # Second release is a no-op (lease.expires_at already in the past, or
    # owned by no-one) — must not raise.
    await store.release_lease("s1", "holder-A")


@pytest.mark.asyncio
async def test_claim_lease_succeeds_after_expiry():
    """A new holder can claim once the previous lease expires."""
    store = _make_store()
    await _seed_session(store)
    first = await store.claim_lease("s1", "holder-A", ttl_s=30)
    assert first is not None

    # Force-expire the lease to simulate the clock crossing expires_at.
    await store.db.sessions.update_one(
        {"_id": "s1"},
        {"$set": {"lease.expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
    )
    second = await store.claim_lease("s1", "holder-B", ttl_s=30)
    assert second is not None
    assert second["lease"]["holder_id"] == "holder-B"


# ── Pending submissions ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pending_submissions_fifo_claim():
    store = _make_store()
    await _seed_session(store)

    for marker in ("first", "second", "third"):
        await store.enqueue_pending_submission("s1", op_type=marker, payload={})
        # Force distinct created_at timestamps so FIFO is observable.
        await asyncio.sleep(0.005)

    claimed = []
    for _ in range(3):
        doc = await store.claim_pending_submission("s1", "holder-A")
        assert doc is not None
        claimed.append(doc["op_type"])
    assert claimed == ["first", "second", "third"]

    # No more pending after exhausting the queue.
    assert await store.claim_pending_submission("s1", "holder-A") is None


@pytest.mark.asyncio
async def test_requeue_claimed_for_preserves_created_at_and_order():
    store = _make_store()
    await _seed_session(store)

    for marker in ("first", "second", "third"):
        await store.enqueue_pending_submission("s1", op_type=marker, payload={})
        await asyncio.sleep(0.005)

    original_created_at: dict[str, datetime] = {}
    for _ in range(3):
        doc = await store.claim_pending_submission("s1", "holder-A")
        assert doc is not None
        original_created_at[doc["op_type"]] = doc["created_at"]

    requeued = await store.requeue_claimed_for("holder-A")
    assert requeued == 3

    re_claimed: list[str] = []
    for _ in range(3):
        doc = await store.claim_pending_submission("s1", "holder-B")
        assert doc is not None
        # ``created_at`` must be untouched across handover.
        assert doc["created_at"] == original_created_at[doc["op_type"]]
        # ``claimed_at`` must have been unset by requeue and re-set by the
        # second claim.
        assert "claimed_at" in doc
        re_claimed.append(doc["op_type"])
    assert re_claimed == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_requeue_claimed_for_with_session_id_only_flips_that_session():
    """P0 #2: ``session_id=`` arg scopes the requeue to one session.

    Other sessions held by the same holder must remain ``claimed`` so a
    transient lease loss on session A doesn't cause double-execution on
    session B.
    """
    store = _make_store()
    await _seed_session(store, "sess-A")
    await _seed_session(store, "sess-B")

    # Two pending submissions per session, claimed by the same holder.
    for _ in range(2):
        await store.enqueue_pending_submission("sess-A", "op", {})
        await store.claim_pending_submission("sess-A", "holder-X")
        await store.enqueue_pending_submission("sess-B", "op", {})
        await store.claim_pending_submission("sess-B", "holder-X")

    n = await store.requeue_claimed_for("holder-X", session_id="sess-A")
    assert n == 2

    # Session A's submissions are now pending again.
    a_pending = await store.db.pending_submissions.count_documents(
        {"session_id": "sess-A", "status": "pending"}
    )
    assert a_pending == 2
    # Session B's submissions are still claimed by holder-X.
    b_claimed = await store.db.pending_submissions.count_documents(
        {"session_id": "sess-B", "status": "claimed", "claimed_by": "holder-X"}
    )
    assert b_claimed == 2


@pytest.mark.asyncio
async def test_requeue_claimed_for_no_session_id_flips_all_for_holder():
    """``requeue_claimed_for(holder)`` (no session_id) keeps existing
    behaviour: every claimed submission for that holder is flipped.
    """
    store = _make_store()
    await _seed_session(store, "sess-A")
    await _seed_session(store, "sess-B")

    for _ in range(2):
        await store.enqueue_pending_submission("sess-A", "op", {})
        await store.claim_pending_submission("sess-A", "holder-X")
        await store.enqueue_pending_submission("sess-B", "op", {})
        await store.claim_pending_submission("sess-B", "holder-X")

    n = await store.requeue_claimed_for("holder-X")
    assert n == 4

    still_claimed = await store.db.pending_submissions.count_documents(
        {"status": "claimed", "claimed_by": "holder-X"}
    )
    assert still_claimed == 0


@pytest.mark.asyncio
async def test_renew_lease_propagates_pymongo_error():
    """P1 #1: ``renew_lease`` must NOT swallow ``PyMongoError`` — the
    heartbeat loop relies on the exception to distinguish transient flaps
    from real lease theft.
    """
    from unittest.mock import AsyncMock

    from pymongo.errors import PyMongoError

    store = _make_store()
    await _seed_session(store)
    await store.claim_lease("s1", "holder-A", ttl_s=30)

    store.db.sessions = AsyncMock()
    store.db.sessions.find_one_and_update = AsyncMock(
        side_effect=PyMongoError("transient")
    )

    with pytest.raises(PyMongoError):
        await store.renew_lease("s1", "holder-A", ttl_s=30)


@pytest.mark.asyncio
async def test_release_lease_clears_holder_id_and_blocks_renew():
    """P1 #2: After ``release_lease``, a stale heartbeat tick that calls
    ``renew_lease`` with the old holder must NOT match the CAS filter.
    """
    store = _make_store()
    await _seed_session(store)
    claimed = await store.claim_lease("s1", "holder-A", ttl_s=30)
    assert claimed is not None

    await store.release_lease("s1", "holder-A")

    # holder_id is cleared on the doc.
    doc = await store.db.sessions.find_one({"_id": "s1"})
    assert doc is not None
    assert doc["lease"]["holder_id"] is None

    # A renew attempt by the (now-former) holder no longer matches.
    result = await store.renew_lease("s1", "holder-A", ttl_s=30)
    assert result is None


@pytest.mark.asyncio
async def test_mark_submission_done_marks_status_done():
    store = _make_store()
    await _seed_session(store)
    sub_id = await store.enqueue_pending_submission("s1", op_type="x", payload={})
    claimed = await store.claim_pending_submission("s1", "holder-A")
    assert claimed is not None

    await store.mark_submission_done(sub_id)
    doc = await store.db.pending_submissions.find_one({"_id": claimed["_id"]})
    assert doc is not None
    assert doc["status"] == "done"
    assert "completed_at" in doc


# ── Backfill on init() ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_backfills_empty_lease_for_recent_sessions():
    store = _make_store()
    now = datetime.now(UTC)
    await store.db.sessions.insert_many(
        [
            {
                "_id": "recent",
                "status": "active",
                "runtime_state": "active",
                "last_active_at": now - timedelta(minutes=30),
            },
            {
                "_id": "old",
                "status": "active",
                "runtime_state": "active",
                "last_active_at": now - timedelta(hours=2),
            },
        ]
    )

    await store._backfill_lease_state()

    recent = await store.db.sessions.find_one({"_id": "recent"})
    old = await store.db.sessions.find_one({"_id": "old"})
    assert recent is not None and old is not None
    assert recent.get("lease") is not None
    assert recent["lease"]["holder_id"] is None
    assert "lease" not in old
    assert old["runtime_state"] == "idle"


@pytest.mark.asyncio
async def test_init_backfill_idempotent():
    store = _make_store()
    now = datetime.now(UTC)
    await store.db.sessions.insert_one(
        {
            "_id": "recent",
            "status": "active",
            "runtime_state": "active",
            "last_active_at": now - timedelta(minutes=10),
        }
    )

    await store._backfill_lease_state()
    after_first = await store.db.sessions.find_one({"_id": "recent"})
    assert after_first is not None
    first_lease = dict(after_first["lease"])

    await store._backfill_lease_state()
    after_second = await store.db.sessions.find_one({"_id": "recent"})
    assert after_second is not None
    # Second run finds no docs matching ``lease: {$exists: false}`` so the
    # lease sub-doc is unchanged.
    assert after_second["lease"] == first_lease


# ── Holder ID format ──────────────────────────────────────────────────────


def test_make_holder_id_format():
    holder = make_holder_id("main")
    assert re.match(r"^main:[\w.\-]+:[0-9a-f]{8}$", holder), holder
    holder_w = make_holder_id("worker")
    assert holder_w.startswith("worker:")


# ── No-op store still satisfies the lease surface ────────────────────────


@pytest.mark.asyncio
async def test_noop_store_lease_methods_are_safe():
    store = NoopSessionStore()
    assert await store.claim_lease("s1", "h1") is None
    assert await store.renew_lease("s1", "h1") is None
    assert await store.release_lease("s1", "h1") is None
    assert await store.enqueue_pending_submission("s1", "x", {}) == ""
    assert await store.claim_pending_submission("s1", "h1") is None
    assert await store.requeue_claimed_for("h1") == 0
    assert await store.poll_pending_submissions_after("s1", None) == []
