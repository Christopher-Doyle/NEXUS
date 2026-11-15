# NEXUS development status

## Milestone and measured progress

Milestone 1 is complete. Milestones 2-6 have a working local demo path and
remain open for broader requirements. Milestone 7 is underway; Milestone 8
is not release-ready.

The design specification has 10 P0 IDs: NX-F01 through NX-F07 and NX-N01
through NX-N03. Seven have verified baseline behavior (NX-F01, F02, F03, F04,
F07, N01, N03), so functional P0 progress is **7/10 = 70%**. F05, F06 and N02
are partially implemented and need their remaining acceptance checks. This
number does not imply a 60% complete release or passing security gates.

## Implemented

- FastAPI and React/Vite local application with six explicit database migrations.
- Task creation with constraints, bounded text attachments or an approved local
  folder; deterministic plan generation, editing, version checks and state transitions.
- Optional Ollama planning with structured JSON, local endpoint restriction,
  configurable bounded timeout, capped generation, one repair attempt and
  availability check. The installed `qwen3.5:9b` model produced a validated
  synthetic two-step plan in a direct adapter check.
- Separate worker process with three allowlisted tools: bounded text read,
  bounded search of selected local files, and approval-gated Markdown report write.
- Explicit registry declares each tool's version, input and output schema,
  permission, risk, timeout, output limit, retry and idempotency behavior.
  Worker responses are schema-checked and size-bounded before persistence.
- Execution records, idempotency hashes, approval scope hashes, append-only
  events, SSE replay, artifact metadata and verified download.
- Exported Markdown reports include numbered source citations, line ranges
  and content hashes. A mismatched stored read receipt blocks the write.
- Worker heartbeat with a 10-second liveness window and dashboard status.
- A configurable one-hour default task dispatch deadline is stored with each
  started task. Expired queued, paused and approval-waiting tasks fail before
  another tool action; approval and report-write boundaries recheck it.
- Dashboard, task composer, plan review, execution cockpit and persisted task
  history with search, status filtering and pagination. The cockpit includes a
  timeline, approval controls, journal and artifact links.
- Paginated artifact library with links to the source task and verified downloads.
- Confirmed deletion of inactive tasks removes their database journal,
  execution records, NEXUS-owned inputs and artifacts. External approved
  workspaces are excluded from cleanup.
- Local settings page persists the chosen Ollama model, planning timeout and
  task dispatch deadline. Operator-approved workspace paths and the loopback
  endpoint remain environment-only.
- Local mutation rate limits and redacted, correlated 500 responses. Planning
  has a separate request bucket; the limiter is in-process and resets on restart.

## Incomplete

- No outbound network fetch tool or general document parsers. Network access
  remains unused and off in the web client.
- SQLite scheduling uses an immediate transaction and active step leases.
  Two Windows processes completed a shared 12-task queue with one execution
  per task. The new deadline stops future tool dispatch, but does not kill an
  in-flight read or write. Pause/cancel during reads and cancellation at the
  report write boundary are covered by tests.
- Tool timeouts are declared but not yet enforced as hard process deadlines.
- The primary approved and rejected workflows pass isolated Playwright tests
  from a fresh migrated database. Accessibility, a clean-clone installation
  outside CI and the browser Ollama flow remain unverified.
- Error handling and logging need a full security review. There is no
  automatic retention schedule or task export UI yet.
- The supplied PDF expresses an MIT licence intention, but no licence has been
  added without an explicit owner decision.

## Checks executed

- `uv run alembic upgrade head`: six migrations applied locally.
- `python -m pytest -q`: 37 backend tests passed, two symlink tests skipped on
  this Windows host, one dependency deprecation warning.
- `ruff check app tests`: passed.
- `npm run build`: passed.
- `npm test`: three frontend API tests passed.
- `npm run test:e2e`: two browser tests passed with installed Chrome, fresh
  temporary SQLite database, API, worker and web client.
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
- Report export test: source citations include line ranges and verified read
  hashes; a tampered read receipt prevents an artifact. Browser E2E checks
  the downloaded report contains its citation section.
- Artifact and deletion-directory symlink redirection is rejected in code.
  The real symlink tests are skipped locally because directory symlinks are
  unavailable here; Linux CI will exercise them.
- Retention test: exact confirmation and inactive-state checks; deletion of
  task records, inputs and artifacts leaves the selected external workspace intact.
- Settings test: preferences persist and a newly started task receives the
  configured deadline.
- API error tests: local mutation rate limiting returns `Retry-After`; an
  unexpected failure returns a correlation ID without exposing exception text.

Remote CI passed all three jobs for the isolated browser demo (`7e52681`).
Ollama is installed with
two local models. A real `qwen3.5:9b` readiness check passed and a direct
adapter call returned a validated read/write plan. The first 30-second call
and a 90-second call without generation controls timed out; the bounded
no-thinking call completed in about four seconds. An API/browser Ollama
journey has not yet been verified.

## Version control

Latest pushed commit before this checkpoint: `7e52681` (isolated browser
demo and P0 traceability). Citation export: commit and push pending.

## Known risks

Local Host, Origin and explicit intent checks protect mutations in the
single-owner development setup; they are not remote authentication. The
worker stops uncertain writes
for manual review but has no UI to resolve them. The report quotes local source
text without treating it as instructions or making unsupported claims.

## Exact next task

Verify and push citation export in CI. Then complete the remaining P0
acceptance checks, starting with worker recovery and manual resolution.
