# Version 1 requirement audit

Source: [design specification](design-spec.pdf), sections 02–13. This audit
distinguishes a tested P0 baseline from the complete v1 acceptance contract.
API `app/` and `test_*.py` paths below are relative to `services/api/`;
other paths are repository-relative. "Partial" means the documented v1
behavior or an acceptance check is still missing; it is not a release pass.

| ID | Expected behavior | Implementation files | Automated evidence | Manual evidence | Status and limitation |
| --- | --- | --- | --- | --- | --- |
| NX-F01 | Create a task with goal, constraints and bounded optional inputs. | `app/contracts.py`, `app/tasks.py`, `apps/web/src/main.tsx` | `test_tasks.py`; browser demo | Task form used in local browser | Complete for local text inputs; folder grants remain operator-configured. |
| NX-F02 | Produce and edit a numbered plan before execution. | `app/planning.py`, `app/ollama.py`, `app/tasks.py`, `apps/web/src/main.tsx` | `test_tasks.py`, `test_ollama.py`; browser plan review | Installed Ollama generated a reviewed plan | Complete for current allowlisted tools. |
| NX-F03 | Validate each tool against schema and declared permission. | `app/registry.py`, `app/tool_policy.py`, `app/worker.py` | `test_registry.py`, `test_tasks.py`, `test_network_policy.py`, `test_ollama.py` | Approval and denial shown in browser | Complete for four registered tools. |
| NX-F04 | Require approval for outbound requests and file writes. | `app/network_policy.py`, `app/operations.py`, `app/worker.py`, `app/tasks.py` | Exact approval, DNS/SSRF, redirect, size and timeout tests; browser approved/rejected runs | Report approval and rejected HTTPS approval verified in browser | **Partial:** outbound policy and approval are implemented with mocked network tests; a real approved public HTTPS fetch has not been verified. |
| NX-F05 | Show live states, logs and evidence. | `app/operations.py`, `apps/web/src/Cockpit.tsx`, `apps/web/src/Artifacts.tsx` | SSE and receipt tests; browser cockpit, report preview and axe checks | Local browser workflow and keyboard task-form path | **Partial:** report preview works; no version diff viewer or full assistive technology review. |
| NX-F06 | Persist journal and resume interrupted runs safely. | `app/models.py`, `app/worker.py`, `app/recovery.py` | `test_recovery.py`, `test_worker_process.py`, `test_timeout.py` | Recovery control visible in cockpit | Complete for local reads and reports; broader fault injection remains. |
| NX-F07 | Export Markdown report with local citations. | `app/tool_runner.py`, `app/operations.py` | Report provenance and artifact download tests; browser report download | Downloaded report checked in browser | Complete for local source readings; report claims remain evidence excerpts, not fact verification. |
| NX-F08 (P1) | Pluggable local read-only document search. | `app/search.py`, `app/registry.py`, `app/tool_runner.py` | Search scope, bounds and provider-dispatch tests | Search evidence shown in cockpit | Code-level read-only provider interface is implemented; only the reviewed local text provider is enabled. No runtime third-party loading. |
| NX-F09 (P1) | Prompt/model configuration and replayable fixtures. | `app/preferences.py`, `app/ollama.py`, `fixtures/demo`, `apps/web/src/Settings.tsx` | Settings and model tests; isolated browser demo | Installed local model and deterministic demo verified | Complete for local model choice and fixtures; prompt template is not user-editable. |
| NX-N01 | No default shell execution. | `app/registry.py`, `app/tool_policy.py` | Registry and policy tests | Tool list inspected | Complete; no shell tool registered. |
| NX-N02 | Stable idempotency key for external actions. | `app/tool_policy.py`, `app/models.py`, `app/worker.py` | Crash/write/recovery and expired network lease tests | Report recovery shown in cockpit | Network fetch stops for review after an uncertain outcome; it is never replayed automatically. |
| NX-N03 | Offline deterministic demo without an LLM. | `app/planning.py`, `fixtures/demo`, `apps/web/e2e/demo.spec.ts` | Browser approved and rejected workflows | Local browser demo verified | Complete. |

## Cross-cutting v1 acceptance

| Specification area | Current evidence | Status and next work |
| --- | --- | --- |
| Section 03 UX | Dashboard, task form, plan, cockpit, history, report preview, artifacts, Settings and a tested mobile menu; browser and axe checks | **Partial:** version diff viewer, optional light mode, and manual assistive technology review remain. Do not add fabricated metrics. |
| Section 06 data | Seven Alembic migrations; task, step, execution, approval, event, artifact and grant tables; clean checkout migration; `operations.md` backup, restore and purge runbook | **Partial:** backup and restore have not been exercised as a release acceptance check; deletion is logical, not secure erasure. |
| Section 07 API | Typed FastAPI contracts, checked-in OpenAPI schema with CI drift check, local intent/Host/Origin checks, bounded pagination, 413/422/429/500 responses, field paths for validation, SSE replay and cursor-paged journal | **Partial:** verify journal pagination on Linux CI; the web client guards display after 10,000 events. |
| Section 08 network | HTTPS-only `fetch_url` off by default per task; exact approval; public DNS/IP validation, pinned TLS connection, same-origin redirects, response and time bounds; negative SSRF tests and browser rejection | **Partial:** local policy and mocked workflow verified; a real approved public fetch remains unverified. No unrestricted networking is exposed. |
| Section 09 security | Local audit in `security-audit.md`; path, approval, timeout, redaction and request-size tests | **Partial:** same-user report directory replacement race and SQLite/WAL erasure limits remain documented. |
| Section 10 release tests | 100 backend tests passed locally with three Windows symlink skips; eight standard browser tests and installed-model workflow passed; clean checkout passed for the earlier baseline | **Partial:** manual assistive technology and sustained load checks remain. Linux CI passed through `91fd789`. |
| Sections 11–13 operations/release | Development, user, troubleshooting, operations, API and security guides; architecture/ADR, screenshots, changelog, contribution/security files, release checklist and checkpoint | **Partial:** release candidate and its manual gates are outstanding. A legal licence requires owner approval. |

No v1 stable release is declared by this matrix.
