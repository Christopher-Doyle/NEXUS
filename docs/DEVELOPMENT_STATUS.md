# NEXUS development status

## Milestone and measured progress

Milestone 1 is complete. Milestones 2-6 have a working local demo path and
remain open for broader requirements. Milestone 7 is underway; Milestone 8
is not release-ready.

The design specification has 10 P0 IDs: NX-F01 through NX-F07 and NX-N01
through NX-N03. All ten have verified baseline behavior, so functional P0
progress is **10/10 = 100%**. This number does not imply a release-ready
application or passing all security gates.

## Implemented

- FastAPI and React/Vite local application with seven explicit database migrations.
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
  Safe reads have at most three total attempts. Worker responses are
  schema-checked and size-bounded before persistence.
- Execution records, idempotency hashes, approval scope hashes, append-only
  events, SSE replay, artifact metadata and verified download.
- Persisted tool versions and a cockpit receipt view with attempts, timing,
  state, hashes, error codes and validated result metadata. Source text is
  omitted from receipt responses.
- Exported Markdown reports include numbered source citations, line ranges
  and content hashes. A mismatched stored read receipt blocks the write.
- Worker heartbeat with a 10-second liveness window and dashboard status.
- A configurable one-hour default task dispatch deadline is stored with each
  started task. Expired queued, paused and approval-waiting tasks fail before
  another tool action; approval and report-write boundaries recheck it.
- The production worker supervises each action in a killable child process.
  A tool's registered five-second timeout begins at the tool call. Timed-out
  reads fail with `ToolTimeout`; uncertain report writes stop for reconciliation,
  whether a file was created or not.
- Dashboard, task composer, plan review, execution cockpit and persisted task
  history with search, status filtering and pagination. The cockpit includes a
  timeline, approval controls, journal and artifact links.
- Paginated artifact library with links to the source task and verified downloads.
- Confirmed deletion of inactive tasks removes their database journal,
  execution records, NEXUS-owned inputs and artifacts. External approved
  workspaces are excluded from cleanup.
- Optional 30, 90 or 365 day retention prunes old terminal tasks and their
  NEXUS-owned files in batches of 20 when the worker runs. Default zero keeps
  records until manual deletion; the Settings page confirms enabling cleanup.
- Read paths reject drive, UNC, device, alternate-stream and control-character
  syntax across platforms. Local folder grants require absolute paths. Reads
  and artifact downloads compare the opened file identity with the validated
  path before consuming bytes. Deletion now covers actual uploaded workspace
  directories as well as legacy input directories.
- An uncertain report write has a recovery inspection and cockpit action.
  The operator can accept an on-disk file only when it exactly matches the
  report rebuilt from verified read receipts, or confirm that no file exists.
  Accepted reports requeue dependent steps if the task deadline is still valid.
- Local settings page persists the chosen Ollama model, planning timeout,
  task dispatch deadline and retention period. Operator-approved workspace paths and the loopback
  endpoint remain environment-only.
- Local mutation rate limits and redacted, correlated 500 responses. Planning
  has a separate request bucket; the limiter is in-process and resets on restart.
- Security review fixes reject unavailable network access, bound each task
  constraint, redact filesystem exceptions from journal errors and escape
  untrusted HTML in exported reports. Findings and open risks are tracked in
  [the local security review](security-audit.md).

## Incomplete

- No outbound network fetch tool or general document parsers. Network access
  remains unused and off in the web client.
- SQLite scheduling uses an immediate transaction and active step leases.
  Two Windows processes completed a shared 12-task queue with one execution
  per task. The task deadline stops future tool dispatch; the registered tool
  timeout kills a stalled action. Pause/cancel during reads and cancellation at the
  report write boundary are covered by tests.
- The supervisor has a 30-second startup bound before a tool reports its
  start. A child lost before that point still uses the durable lease recovery
  path; broader process fault injection remains a release gate.
- The primary approved and rejected workflows pass isolated Playwright tests
  from a fresh migrated database. Automated WCAG A/AA checks pass on the
  dashboard, task form, settings, plan review and completed cockpit. Manual
  assistive technology review remains unverified. Automated keyboard
  focus order and Enter submission pass for the task form. The separate
  clean-checkout setup and opt-in browser Ollama plan test passed.
- The local security review documents remaining limitations. There is no
  bulk task export UI or secure erasure of SQLite pages and backups yet.
- The supplied PDF expresses an MIT licence intention, but no licence has been
  added without an explicit owner decision.

## Checks executed

- Fresh-database E2E setup applied all seven migrations through
  `f6a916c64f20`.
- A separate local checkout succeeded. Offline installation found uncached
  packages; after approval, `uv sync --extra dev` and `npm ci` installed the
  lockfile dependencies. The clean frontend production build and all seven
  documented database migrations passed. The initial backend run found a
  line-ending assumption in a report assertion. After correcting it and
  updating the checkout to `13e1643`, 77 backend tests passed with three
  Windows symlink skips; Ruff, three frontend tests and six standard browser
  tests passed (one opt-in Ollama test skipped).
- `python -m pytest -q`: 80 passed, three symlink skips on this Windows host,
  one dependency deprecation warning.
- `ruff check app tests`: passed.
- `npm run build`: passed.
- `npm test`: three frontend API tests passed.
- `npm run test:e2e`: seven standard browser tests passed with installed Chrome, fresh
  temporary SQLite database, API, worker and web client. The mobile Settings
  path persists a deadline after reload without horizontal overflow at 390px.
  It also confirms and persists a 30-day retention choice after reload.
  Automated WCAG A/AA checks pass on five core views after correcting the
  plan reorder buttons' accessible names.
- A keyboard-only task-form path verified focus order through all fields and
  submitted with Enter to reach plan review.
- With `NEXUS_E2E_OLLAMA_MODEL=qwen3.5:9b`, all eight browser tests passed;
  the installed model generated a plan, the supervised worker executed it,
  the report write was approved and the task completed.
- The browser flow downloads a per-task JSON history export and checks its
  task state, journal, report execution receipt and artifact metadata.
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
- Expired read lease recovery stops with `RetryExhausted` after the third
  attempt, without dispatching another tool call.
- A spawned worker process was terminated inside an active read. After its
  lease expired, a second worker completed the same step on attempt two.
- Another worker process was terminated after creating a report file but
  before committing its artifact record. Recovery left one file and one
  execution and flagged the write for review without replaying it.
- Recovery API tests cover exact-match acceptance, stale digest rejection,
  absent-file acknowledgement, mismatched-file refusal, resumed dependent
  steps and deadline-guarded recovery. The real killed-write test reconciles
  its on-disk report to completion.
- Receipt API test verifies tool version, execution metadata and exclusion
  of read contents; browser E2E checks the receipt view.
- Platform-neutral path tests cover Windows and POSIX absolute paths,
  traversal, UNC and device syntax, alternate streams and control characters.
  A file-swap test rejects a changed selected file; an artifact-swap test
  rejects a changed download. Approved local folders still work. Deleting a
  draft task removes the uploaded input files actually created by the API.
  Linux CI exercises the redirected-upload-root test skipped on this Windows
  host.
- Artifact and deletion-directory symlink redirection is rejected in code.
  The real symlink tests are skipped locally because directory symlinks are
  unavailable here; Linux CI will exercise them.
- Retention test: exact confirmation and inactive-state checks; deletion of
  task records, inputs and artifacts leaves the selected external workspace intact.
- Age-based retention test: default zero preserves data; enabling 30 days
  removes an old completed task and its owned report while preserving a recent
  task, an old draft and the selected external workspace.
- Settings test: preferences persist and a newly started task receives the
  configured deadline.
- API error tests: local mutation rate limiting returns `Retry-After`; an
  unexpected failure returns a correlation ID without exposing exception text.
  Mutating bodies above 512 KiB return 413 with and without `Content-Length`.
- Timeout tests terminate stalled read and report child processes, preserve
  cancellation, and verify before-write and after-write reconciliation.
  The standard browser tests pass with the supervised production worker.
- Security tests cover Host, Origin and intent rejection, explicit network
  denial, bounded constraints, HTML escaping and journal path redaction.
- `scripts/measure_local.py` ran against an isolated migrated SQLite database
  and loopback API on Windows 11 / Python 3.13.16. For 100 sequential requests,
  `/health` median/p95/max was 1.09/1.38/4.16 ms and `/ready` was
  1.16/1.44/1.60 ms. Ten synthetic task creates measured 3.59/5.17/15.97 ms.
  These are one-host smoke timings, not throughput or capacity claims.

Remote CI passed all three jobs for the latency checkpoint (`e748d2a`).
Ollama is installed with
two local models. A real `qwen3.5:9b` readiness check passed and a direct
adapter call returned a validated read/write plan. The first 30-second call
and a 90-second call without generation controls timed out; the bounded
no-thinking call completed in about four seconds. The opt-in browser plan
journey passed in 22 seconds with the same installed model. Execution of a
model-generated plan now completes in the opt-in browser workflow after the
planner was constrained to the task's actual selected filenames. The first
full run exposed a hallucinated read path; that validation was added and the
next full run passed.

## Version control

Latest pushed commit before this checkpoint: `e748d2a` (loopback latency
measurement). Opt-in age-based retention is tested locally and pending commit.

## Known risks

Local Host, Origin and explicit intent checks protect mutations in the
single-owner development setup; they are not remote authentication. The
worker stops uncertain writes for operator reconciliation in the cockpit.
The report quotes and escapes local source text without treating it as
instructions or making unsupported claims. App-owned report writes still
have a same-user directory-swap race; SQLite deletion is not secure erasure.

## Exact next task

Commit and push opt-in retention, then verify remote CI. Continue with manual
assistive technology review and load/capacity testing before a stable release.
