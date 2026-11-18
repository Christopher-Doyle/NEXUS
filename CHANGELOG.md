# Changelog

This file tracks development checkpoints and versioned releases.

## 1.0.0 — 2026-11-18

- Initial local-only, single-user release; baseline requirements NX-F01–NX-F07 and NX-N01–NX-N03 are implemented and verified. NEXUS is an approval-gated workflow console, not an unrestricted computer agent.
- Owner-reported desktop Narrator/keyboard and 400px browser-emulation checks passed. Real local Ollama planning and supervised execution were verified.
- The owner accepted documented same-user filesystem limitations for trusted local use and approved a strictly scoped development-only picomatch advisory exception through 2026-12-18. Neither claim constitutes a security fix.
- Release publication is gated on a clean GitHub Actions CI run from this exact release candidate.


- Added the owner-approved MIT licence and Semantic Versioning policy; stable
  `v1.0.0` remains gated on manual release checks and final CI.
- Applied a time-limited, strict development-tool audit policy for the single
  `picomatch` GHSA-fc5q-39xc-vjpf advisory, with a separate production audit.
- Recorded owner acceptance of the documented same-user filesystem limitation
  exclusively for local single-owner use.

- Added a browser-persisted optional light appearance with a mobile automated
  accessibility and contrast check; dark remains the default.
- Recorded the newly reported unpatched `picomatch` ReDoS advisory in
  development tooling; the approved exact-advisory audit policy retains full audit output, with all other high/critical findings blocked and the production audit required.
- Verified one owner-approved public HTTPS request to `https://example.com/`
  through an isolated NEXUS task after exact approval, with one outbound call
  and no private inputs.
- Added bounded, keyboard-accessible comparison of two verified report
  artifacts, with added/removed line labels and a browser accessibility check.
- Added persisted concise/detailed Ollama planning styles using fixed reviewed
  prompt variants and the existing plan validation boundary.
- Added a bounded sustained loopback readiness sample to the isolated
  performance script and recorded the measured one-host result.
- Added an isolated supervised-worker measurement: 40 synthetic local reads
  completed with 40 single-attempt receipts on Windows.
- Displayed API validation field paths and correlated server-error references
  in the web client.
- Added an isolated backup/restore verification script and CI gate covering
  migration, SQLite integrity, verified artifact download and recovery of an
  interrupted read lease.
- Updated README capability and launch descriptions to match the tested
  application and its open release gates.
- Hardened POSIX report creation with a pinned no-follow directory handle,
  exclusive relative file creation and directory identity checks.
- Added a code-level read-only search provider interface while retaining the
  single allowlisted, selected-file Markdown/text scanner in production.
- Paginated task journals by event cursor, so cockpit and JSON history export
  can include events beyond the first 500.
- Added a compact mobile navigation menu with expanded-state semantics and
  a browser navigation check.
- Added local user, troubleshooting, backup/restore and release-checklist
  guides, plus contribution and security reporting guidance.
- Added an in-app, bounded preview of integrity-checked Markdown reports in
  the artifact library, with separate download and source-task navigation.
- Checked in the generated OpenAPI contract with a CI drift check, added
  field paths to validation responses and documented SSE reconnection.
- Added an opt-in HTTPS text fetch tool with public-address DNS checks,
  address-pinned TLS, same-origin redirects, response bounds and exact-step
  approval. Automated SSRF and workflow tests use mocked connections.
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
