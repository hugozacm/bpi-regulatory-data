# Frontend / backend connection

> Historical or alternate implementation guide. For the active public pilot, controls, quality gate and current run commands, use [README.md](README.md), [CONNECTED_FRONTEND.md](CONNECTED_FRONTEND.md) and [CURRENT_WORKFLOW.md](CURRENT_WORKFLOW.md). Counts and disconnected-hosting statements below describe that earlier stage, not the live Site.

## Honest status

The Python WSGI API, browser adapter and operator job controls are implemented for local verification. A Python hosting account/endpoint is not yet connected, so the public Site still uses its static snapshot. Connecting the API does not implement missing historical financial mappings.

## API contract

| Route | Access | Purpose |
|---|---|---|
| GET /api/health | Public | Health and processing-enabled flag |
| GET /api/status | Public | Allowlisted snapshot metadata, no private source paths |
| GET /api/dataset | Public | Paginated current interim snapshot with inclusive start/end filters |
| GET /api/export | Public | Filtered current-snapshot CSV |
| POST /api/jobs | Operator bearer key | JSON `{ "start": "20240331", "end": "20241231" }` |
| GET /api/jobs/{id} | Operator bearer key | Persisted job state |
| GET /api/jobs/{id}/result | Operator bearer key | Upstream research-draft CSV, not a certified/publicly promoted release |

Operator key must contain at least 32 characters and be supplied through private environment configuration. No key is embedded in source, frontend configuration, URLs or browser storage. Enter it only into the operator password field in the trusted interface. Do not paste keys into chat.

One job at a time, at least 60 seconds between starts, at most 12 quarters, 30-minute subprocess limit. Fixed script/arguments, no shell or arbitrary paths. Requests outside verified mapping bounds (currently 2023 Q1–2026 Q2) are rejected before launching a job. Source-access failures are BLOCKED; a completed upstream build is COMPLETED_REVIEW_REQUIRED, never historical MVP completion. Jobs download missing supported inputs through the existing builder. NIC browser handoff may still be required.

Job files/logs are private under outputs/api_jobs. They are not exposed through generic filesystem routes. Restarted RUNNING/QUEUED jobs are reported as INTERRUPTED; submit again to reuse cached sources. Do not restart or redeploy during an active build; this minimal coordinator is not a distributed queue.

## Local verification

Set `REGDATA_ALLOWED_ORIGINS` to `http://127.0.0.1:8765` and optionally set `REGDATA_OPERATOR_KEY` privately. Run:

```powershell
.\.venv\Scripts\python.exe src\backend_api.py
.\.venv\Scripts\python.exe src\serve_frontend.py
```

The API development runner listens only on 127.0.0.1:8767. In the local Dataset explorer, expand “Backend connection & operator processing”, enter http://127.0.0.1:8767 and connect. Snapshot browsing works without an operator key. Source files/data must exist locally for browsing. Job integration tests use explicit test fixtures, not live official acquisition.

## Hosting handoff

`Dockerfile.backend` uses a non-root user and Gunicorn with exactly one worker/four threads. Build context excludes downloaded data, secrets and private outputs. It has not yet been built or deployed in this environment. It requires a Linux container host with HTTPS termination, outbound official-source access, sufficient memory/disk, and persistent storage mounted at /app/research and /app/outputs. Seed the interim package separately if public snapshot browsing is required. Do not put raw archives or private logs in web-accessible storage.

Set the operator key privately and set `REGDATA_ALLOWED_ORIGINS` to exactly https://bpi-regulatory-research-hugo.amusedvine18.chatgpt.site (comma-separated exact origins if adding local verification). CORS is not authentication; public reads are intentionally public, processing remains operator-authenticated. Add host-level request/body/rate limits and monitoring before wider use. TLS termination is required; the WSGI application is HTTP behind the proxy.

After a hosted /api/health check succeeds, set `frontend/backend-config.json` api_url to the actual HTTPS backend origin, rebuild the public demo and republish. Alternatively an operator can connect a verified backend address temporarily from the UI. Never configure the Site with localhost: it would refer to each visitor's own machine. The current empty api_url intentionally leaves static demo mode enabled.

## Remaining work

- Connect a hosting integration, review its resource plan/cost, deploy and verify HTTPS/CORS against the actual Site.
- Test real hosted acquisition, review-required result download, persisted cache and restart behaviour.
- Finish historical mappings/ownership and expand job eligibility only when verified.
- Add a durable external job queue, separate operator identities, aggregate rate limits, row-level progress and independent acceptance checks before production use.
