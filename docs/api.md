# API implemented so far

The API is local only and binds to `127.0.0.1` by default. Mutating requests
require `X-Nexus-Intent: local`; browser requests must have a permitted local
Origin. This is a single-owner development boundary, not a remote access
authentication scheme.

| Method | Route | Behaviour |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| GET | `/ready` | Database connection check |
| POST | `/api/v1/tasks` | Create a draft task |
| GET | `/api/v1/tasks` | List tasks with bounded pagination, `q` goal search and `state` filter |
| GET | `/api/v1/tasks/{id}` | Read a task and its steps |
| POST | `/api/v1/tasks/{id}/plan` | Generate the deterministic demo plan |
| PATCH | `/api/v1/tasks/{id}/steps` | Replace a plan with a matching version |
| GET | `/api/v1/model/status` | Check configured local Ollama model |
| GET | `/api/v1/worker/status` | Recent worker heartbeat and active process count |
| POST | `/api/v1/tasks/{id}/start` | Queue a reviewed plan |
| POST | `/api/v1/tasks/{id}/pause` | Pause after the current step |
| POST | `/api/v1/tasks/{id}/resume` | Resume a paused task |
| POST | `/api/v1/tasks/{id}/cancel` | Cancel an active task |
| GET | `/api/v1/tasks/{id}/events` | SSE event stream with cursor replay |
| GET | `/api/v1/tasks/{id}/journal` | Bounded event history |
| GET | `/api/v1/tasks/{id}/artifacts` | Artifact metadata |
| GET | `/api/v1/artifacts` | Paginated artifact library |
| GET | `/api/v1/approvals` | Pending approvals |
| POST | `/api/v1/approvals/{id}/decision` | Decide an exact approval scope |
| GET | `/api/v1/artifacts/{id}` | Verified artifact download |

OpenAPI is available at `/docs` while the API runs. `POST /plan` accepts
`{"mode":"demo"}` or `{"mode":"ollama"}`. Ollama requires `OLLAMA_MODEL` in
the environment; no model is downloaded automatically. The worker must run in
a separate process for queued tasks to progress. API responses include a
correlation ID for HTTP and validation errors.

`search_local_docs` is a read-only plan tool. It searches only the task's
selected Markdown and text files, returning at most 20 line excerpts. A user
can add the step during plan review and provide the literal search text.
