# Agent Notes

## Local Dev Servers

- Frontend: from `frontend/`, run `npm ci` if dependencies are missing, then `npm run dev`.
- Backend: from `backend/`, run `uv run uvicorn main:app --host ::1 --port 7860`.
- Frontend URL: http://localhost:5173/
- Backend health check: `curl -g http://[::1]:7860/api`
- Frontend proxy health check: `curl http://localhost:5173/api`

Notes:

- Vite proxies `/api` and `/auth` to `http://localhost:7860`.
- If `127.0.0.1:7860` is already owned by another local process, binding the backend to `::1` lets the Vite proxy resolve `localhost` cleanly.
- Prefer `npm ci` over `npm install` for setup, since `npm install` may rewrite `frontend/package-lock.json` metadata depending on npm version.
- Production defaults to the Bedrock Claude model. For local development with a personal Anthropic key, set `ANTHROPIC_API_KEY` and `ML_INTERN_CLAUDE_MODEL_ID=anthropic/claude-opus-4-6` before starting the backend. Other models are selected through the app's model switcher.

## GitHub CLI

- For multiline PR descriptions, prefer `gh pr edit <number> --body-file <file>` over inline `--body` so shell quoting, `$` env-var names, backticks, and newlines are preserved correctly.

## Background sessions deployment (bg-sessions-mongo-control-plane)

This codebase runs as **two HF Space tiers**:

1. **Main Space** — current FastAPI/React app, hosts UI + interactive sessions. Started with `MODE=main` (default).
2. **Worker Space(s)** — same Docker image, `MODE=worker` env var. Run agent loops for backgrounded sessions. No public HTTP routes.

Both rely on a **MongoDB replica set** (Atlas or self-hosted with `--replSet`). Change streams require this; the app falls back to 500 ms polling if the deployment is single-node, but production should be a replica set.

### Deploy ordering

When shipping a new release that touches the agent loop:

1. **Roll Workers first.** Each Worker reads `pending_submissions` and claims dormant sessions; deploying them ahead of Main means Main never processes a request against an old-protocol Worker.
2. **Then roll Main.** Main's `lifespan` startup runs `MongoSessionStore.init()` which:
   - Backfills `lease={holder_id: null, expires_at: 0}` on sessions with `last_active_at > now-1h` (recoverable)
   - Flips older sessions' `runtime_state` to `"idle"` (still recoverable, never `"ended"`)
3. The lifespan shutdown sweep on the OLD Main releases active-turn leases via `release_session_to_background(reason="main_shutdown")`. Workers pick them up within ~30 s (TTL).

### Blast radius (TBD pre-launch)

Run before deploying:
```
db.sessions.aggregate([
  {$match: {runtime_state: "processing"}},
  {$count: "active_turns_at_deploy"}
])
```
Capture as a baseline metric. Each active turn at deploy time will see a `migrating` event then a brief (~30 s) handover window. Sessions with no in-flight work see no user-visible event.

### Required env vars

| Var | Default | Effect |
|---|---|---|
| `MODE` | `main` | `worker` flips to worker-loop entrypoint |
| `MONGODB_URI` | unset | Required for the control plane; without it falls back to NoopSessionStore (CLI compatibility) |
| `GRACE_PERIOD_SECONDS` | `180` | SSE-drop grace before background migration |
| `IDLE_EVICTION_SECONDS` | `1800` | Worker idle eviction TTL |

### Local development

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

Chaos test (verifies change-stream resume token):
```bash
# Mid-drill, briefly pause the Mongo container:
docker pause mongo-rs && sleep 5 && docker unpause mongo-rs
# SSE should reconnect via resume token without losing events.
```

### Observability

Grep production logs for:
- `lease_claim`, `lease_release` — lease churn
- `requeue_claimed count=N` with N>0 — handover happened
- `migrating_emitted reason=...` — sessions moving to background
- `replay_event_count` with high counts — long-session replay scan
- `pending_submission_lag` (DEBUG) — Mongo or change-stream backpressure
