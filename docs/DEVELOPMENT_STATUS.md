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

- FastAPI and React/Vite local application with three explicit database migrations.
- Task creation with constraints, bounded text attachments or an approved local
  folder; deterministic plan generation, editing, version checks and state transitions.
- Optional Ollama planning with structured JSON, local endpoint restriction,
  bounded timeouts, one repair attempt and availability check.
- Separate worker process with two registered tools: bounded text read and
  approval-gated Markdown report write.
- Execution records, idempotency hashes, approval scope hashes, append-only
  events, SSE replay, artifact metadata and verified download.
- Dashboard, task composer, plan review and execution cockpit with timeline,
  approval controls, journal and artifact links.

## Incomplete

- No outbound network fetch tool, search tool, general document parsers or
  settings UI. Network access remains unused and off in the web client.
- Worker has a single-process assumption, no cross-process lease claim, no
  bounded task wall-clock timeout and limited pause/cancel race coverage.
- SSE reconnect, frontend workflow, accessibility and a clean-clone demo still
  need browser-level verification. Real Ollama has only mock tests.
- Error handling and logging need a full security review. There is no rate
  limiting, input retention UI or export/delete UI yet.
- The supplied PDF expresses an MIT licence intention, but no licence has been
  added without an explicit owner decision.

## Checks executed

- `uv run alembic upgrade head`: three migrations applied locally.
- `python -m pytest -q`: 11 backend tests passed, one dependency deprecation warning.
- `ruff check app tests`: passed.
- `npm run build`: passed.
- `npm test`: two frontend API tests passed.
- `npm audit`: zero vulnerabilities after updating Vitest.

Remote CI and a real Ollama invocation have not been verified.

## Version control

Latest pushed commit before this checkpoint: `3f89d6b` (Ollama planner).
Current execution slice: commit and push pending.

## Known risks

Local Host, Origin and explicit intent checks protect mutations in the
single-owner development setup; they are not remote authentication. A second
worker process could claim the same task. The worker stops uncertain writes
for manual review but has no UI to resolve them. The report quotes local source
text without treating it as instructions or making unsupported claims.

## Exact next task

Commit and push the tested demo execution slice. Add a cross-process lease
claim and test duplicate execution, then run a browser end-to-end demo and
complete the remaining P0 acceptance checks.
