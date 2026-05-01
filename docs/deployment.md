# Background sessions deployment

This codebase runs as **two HF Space tiers** for the background-sessions feature:

1. **Main Space** — current FastAPI/React app, hosts UI and interactive sessions. Started with `MODE=main` (the default).
2. **Worker Space(s)** — same Docker image, `MODE=worker` env var. Run agent loops for backgrounded sessions. No public HTTP routes.

Both rely on a **MongoDB replica set** (Atlas, or self-hosted with `--replSet`). Change streams require this; the app falls back to 500 ms polling on a single-node deployment, but production should be a replica set.

## Deploy ordering

When shipping a new release that touches the agent loop:

1. **Roll Workers first.** Each Worker reads `pending_submissions` and claims dormant sessions; deploying them ahead of Main means Main never processes a request against an old-protocol Worker.
2. **Then roll Main.** Main's `lifespan` startup runs `MongoSessionStore.init()`, which:
   - Backfills `lease={holder_id: null, expires_at: 0}` on sessions with `last_active_at > now-1h` (recoverable)
   - Flips older sessions' `runtime_state` to `"idle"` (still recoverable, never `"ended"`)
3. The lifespan shutdown sweep on the OLD Main releases active-turn leases via `release_session_to_background(reason="main_shutdown")`. Workers pick them up within ~30 s (TTL).

## Pre-deploy blast-radius check

Run before deploying:

```js
db.sessions.aggregate([
  { $match: { runtime_state: "processing" } },
  { $count: "active_turns_at_deploy" },
])
```

Capture as a baseline metric. Each active turn at deploy time will see a `migrating` event then a brief (~30 s) handover window. Sessions with no in-flight work see no user-visible event.

## Required env vars

| Var | Default | Effect |
| --- | --- | --- |
| `MODE` | `main` | `worker` flips to the worker-loop entrypoint |
| `MONGODB_URI` | unset | Required for the control plane; without it falls back to `NoopSessionStore` (CLI compatibility) |
| `GRACE_PERIOD_SECONDS` | `180` | SSE-drop grace before background migration |
| `IDLE_EVICTION_SECONDS` | `1800` | Worker idle eviction TTL |

## Local development

To run a 2-process stack locally for a "close laptop, come back" drill:

```bash
# 1) Start a Mongo replica set in Docker
docker run -d --name mongo-rs -p 27017:27017 mongo:7 --replSet rs0
# Initiate the replica set (one-time)
docker exec mongo-rs mongosh --eval 'rs.initiate()'
docker exec mongo-rs mongosh --eval 'rs.status()' | grep PRIMARY

# 2) Start Main
MODE=main MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0 \
  uvicorn backend.main:app --host 0.0.0.0 --port 7860

# 3) In another terminal, start Worker(s)
MODE=worker MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0 \
  python -m backend.worker

# 4) Run Drill 1 (manually): create a session, close the tab,
# wait > GRACE_PERIOD_SECONDS, reopen, observe the migrating event
# in the SSE stream and verify lease.holder_id flipped to worker:* in db.sessions.
```

### Chaos test (verifies change-stream resume token)

```bash
# Mid-drill, briefly pause the Mongo container:
docker pause mongo-rs && sleep 5 && docker unpause mongo-rs
# SSE should reconnect via resume token without losing events.
```

## Observability

Grep production logs for:

- `lease_claim`, `lease_release` — lease churn
- `requeue_claimed count=N` with N>0 — handover happened
- `migrating_emitted reason=...` — sessions moving to background
- `replay_event_count` with high counts — long-session replay scan
- `pending_submission_lag` (DEBUG) — Mongo or change-stream backpressure

## Acceptance drills (run post-deploy)

### Drill 1 — close laptop, come back

1. `POST /api/session` → `session_id`. `db.sessions.findOne({_id})` shows `lease.holder_id` matching `main:*`.
2. `POST /api/chat/{session_id}` with a long-running message (HF Job). SSE streams initial events.
3. Close the browser tab. Wait `GRACE_PERIOD_SECONDS + ~10s`. `db.sessions.findOne({_id})` shows `lease.holder_id` matching `worker:*`. A `migrating` event was emitted at handover.
4. Reopen the browser, `GET /api/sessions`, then `GET /api/events/{session_id}?after=<lastSeq>`. SSE replays all missed events including any `approval_required`.
5. `POST /api/approve` for any pending tool. Worker resumes the turn within ≤2 s (change-stream) or ≤500 ms × 1 (polling fallback).

**Pass**: all 5 succeed end-to-end, including across a deliberate `docker restart` of Main between steps 2 and 3.

### Drill 2 — Main restart with active turn

1. Start a session on Main, send a message that triggers a long-running tool call.
2. Force-restart Main. Lifespan shutdown sweep emits `migrating` for each in-flight session and calls `release_lease`.
3. Within 30 s a Worker claims the lease (`lease.holder_id` flips to `worker:*`).
4. Fresh Main comes back; user opens new tab, hits `GET /api/events/{id}?after=<seq>`. No `interrupted` event from the restart itself.

**Pass**: single uninterrupted user-visible turn across the restart.
