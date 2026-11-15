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
| DELETE | `/api/v1/tasks/{id}` | Confirmed deletion of an inactive task and its NEXUS-owned files |
| POST | `/api/v1/tasks/{id}/plan` | Generate the deterministic demo plan |
| PATCH | `/api/v1/tasks/{id}/steps` | Replace a plan with a matching version |
| GET | `/api/v1/model/status` | Check configured local Ollama model |
| GET/PATCH | `/api/v1/settings` | Read and update local model and timeout preferences |
| GET | `/api/v1/worker/status` | Recent worker heartbeat and active process count |
| POST | `/api/v1/tasks/{id}/start` | Queue a reviewed plan |
| POST | `/api/v1/tasks/{id}/pause` | Pause after the current step |
| POST | `/api/v1/tasks/{id}/resume` | Resume a paused task |
| POST | `/api/v1/tasks/{id}/cancel` | Cancel an active task |
| GET | `/api/v1/tasks/{id}/events` | SSE event stream with cursor replay |
| GET | `/api/v1/tasks/{id}/journal` | Bounded event history |
| GET | `/api/v1/tasks/{id}/executions` | Bounded tool receipts with version, timing, hashes and safe result metadata |
| GET | `/api/v1/tasks/{id}/recovery` | Inspect an uncertain report write and compare its exact expected digest |
| POST | `/api/v1/tasks/{id}/recovery` | Accept a matching existing report or acknowledge that no report exists |
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
Mutation rate limits return 429 and `Retry-After`. Unexpected errors return a
generic 500 body with a correlation ID; exception text is not sent to the client.

Started tasks include `deadline_at`. `TASK_TIMEOUT_SECONDS` defaults to 3600
and may be set from 60 to 86400. The deadline prevents new tool dispatch and
approval after expiry; it does not interrupt an in-flight operation.
The separate registry timeout kills a stalled worker child. Execution receipts
record `ToolTimeout`; the journal emits `tool_timeout`. A report timeout
requires recovery inspection before the file is accepted or confirmed absent.

`search_local_docs` is a read-only plan tool. It searches only the task's
selected Markdown and text files, returning at most 20 line excerpts. A user
can add the step during plan review and provide the literal search text.

`DELETE /tasks/{id}` requires `{"confirm_id":"<same task ID>"}` and returns
204. Active tasks must be cancelled before deletion. Selected external
workspaces are not deleted.

`PATCH /settings` accepts `ollama_model`, `ollama_timeout_seconds` (10–180),
and `task_timeout_seconds` (60–86400). Values persist in SQLite. Workspace
grants and the Ollama endpoint remain operator environment settings.

Execution receipts persist the registered tool version at dispatch. The
`/executions` response omits source file contents and validates stored result
schemas before returning metadata. Historical receipts remain tied to the
version that produced them.

Recovery applies only to a failed task with a `needs_review` report step and
execution. The POST body contains `step_id`, `expected_sha256` from the GET
inspection, and `decision` (`accept_existing` or `confirm_absent`). A matching
file is checked against the report rebuilt from verified read receipts before
an artifact record is restored. A missing file can be acknowledged without
retrying the write. Mismatched or redirected files cannot be accepted.
When a report is accepted, unfinished dependent steps are queued if the task
deadline has not expired. An expired task stays failed with its verified
artifact available for download.
