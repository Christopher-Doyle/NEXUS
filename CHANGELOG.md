# Changelog

This file tracks development checkpoints. NEXUS has not had a stable release.

## Unreleased — 2026-11-16

- Checked in the generated OpenAPI contract with a CI drift check, added
  field paths to validation responses and documented SSE reconnection.
- Added an opt-in HTTPS text fetch tool with public-address DNS checks,
  address-pinned TLS, same-origin redirects, response bounds and exact-step
  approval. Local SSRF and workflow tests use mocked connections; a real
  public fetch remains unverified.
- Added a supervised worker that terminates tools at their registered process
  deadlines and records recoverable outcomes for uncertain report writes.
- Rejected ambiguous Windows and POSIX path syntax; verified opened-file
  identity for reads and artifact downloads; fixed deletion of uploaded inputs.
- Added automated WCAG A/AA browser checks and corrected plan reorder labels.
- Added exact report citations, durable execution receipts, report recovery,
  local settings, confirmed task deletion and reproducible browser workflows.
- Redacted filesystem errors in journals, escaped untrusted report HTML and
  rejected requests for unavailable network tools.
- Added per-task JSON history export from the History page, covering task
  metadata, bounded journal, execution receipts and artifact metadata.
- Verified the installed local Ollama model through browser plan review,
  supervised execution and report approval. Plans now use the task's exact
  selected filenames and reject invented read paths before review.
- Capped mutation request bodies at 512 KiB before parsing and fixed a
  report test that assumed a particular checkout line-ending convention.
- Verified task-form keyboard focus order and Enter submission in the browser
  suite.
- Added a reproducible isolated loopback API latency smoke script.
- Added opt-in 30, 90 or 365 day retention for terminal tasks, with the local
  worker pruning old records and NEXUS-owned files in bounded batches.

See [development status](docs/DEVELOPMENT_STATUS.md) for test evidence and
remaining release gates.
