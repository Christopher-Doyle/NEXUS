# NEXUS development status

## Milestone and measured progress

Milestone 1 is complete. Milestones 2-6 have a working local demo path and
remain open for broader requirements. Milestones 7-8 have not started.

The design specification has 10 P0 IDs: NX-F01 through NX-F07 and NX-N01
through NX-N03. Six have verified baseline behavior (NX-F01, F02, F03, F04,
N01, N03), so functional P0 progress is **6/10 = 60%**. F05, F06, F07 and N02
are partially implemented and need their remaining acceptance checks. This
number does not imply a 60% complete release or passing security gates.

## Implemented

- FastAPI and React/Vite local application with four explicit database migrations.
- Task creation with constraints, bounded text attachments or an approved local
  folder; deterministic plan generation, editing, version checks and state transitions.
- Optional Ollama planning with structured JSON, local endpoint restriction,
  bounded timeouts, one repair attempt and availability check.
- Separate worker process with three allowlisted tools: bounded text read,
  bounded search of selected local files, and approval-gated Markdown report write.
- Execution records, idempotency hashes, approval scope hashes, append-only
  events, SSE replay, artifact metadata and verified download.
- Worker heartbeat with a 10-second liveness window and dashboard status.
- Dashboard, task composer, plan review, execution cockpit and persisted task
  history with search, status filtering and pagination. The cockpit includes a
  timeline, approval controls, journal and artifact links.
- Paginated artifact library with links to the source task and verified downloads.

## Incomplete

- No outbound network fetch tool, general document parsers or
  settings UI. Network access remains unused and off in the web client.
- SQLite scheduling uses an immediate transaction and active step leases.
  Two Windows processes completed a shared 12-task queue with one execution
  per task. There is no bounded
  task wall-clock timeout. Pause/cancel during reads and cancellation at the
  report write boundary are covered by tests.
- The primary approved and rejected workflows passed a local browser smoke
  test. Accessibility, a clean-clone demo and real Ollama remain unverified.
- Error handling and logging need a full security review. There is no rate
  limiting, input retention UI or export/delete UI yet.
- The supplied PDF expresses an MIT licence intention, but no licence has been
  added without an explicit owner decision.

## Checks executed

- `uv run alembic upgrade head`: four migrations applied locally.
- `python -m pytest -q`: 28 backend tests passed, one symlink test skipped on
  this Windows host, one dependency deprecation warning.
- `ruff check app tests`: passed.
- `npm run build`: passed.
- `npm test`: two frontend API tests passed.
- `npm audit`: zero vulnerabilities after updating Vitest.
- Browser smoke test: task creation, plan review, approval, report artifact,
  persisted history after API restart, and rejection with no artifact passed.
  Four synthetic screenshots were captured and visually inspected.
- Threaded worker claim test: one read execution across simultaneous calls.
  Multi-process test: two workers, 12 tasks, 12 single-attempt executions.
  SSE test: `Last-Event-ID` replays the next event. Pause and cancel during
  an active read leave later steps pending. Local search tests cover scope,
  typed arguments and result bounds.
- Report cancellation race tests: a cancellation committed before the write
  boundary prevents output; a cancellation during a locked write waits and
  receives a conflict after the task completes.
- Artifact directory symlink redirection is rejected in code. The real symlink
  test is skipped locally because directory symlinks are unavailable here;
  Linux CI will exercise it.

Remote CI passed for the two-process worker test (`d6e2c01`). A
real Ollama invocation has not been verified.

## Version control

Latest pushed commit before this checkpoint: `d6e2c01` (two-process worker
test). Report cancellation serialization: commit and push pending.

## Known risks

Local Host, Origin and explicit intent checks protect mutations in the
single-owner development setup; they are not remote authentication. The
worker stops uncertain writes
for manual review but has no UI to resolve them. The report quotes local source
text without treating it as instructions or making unsupported claims.

## Exact next task

Commit and push report cancellation serialization. Then complete the
remaining P0 acceptance checks, especially full tool metadata, retention
controls, security review and reproducible browser tests.
