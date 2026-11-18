# Local security review — 2026-11-18

This review covers the current loopback, single-owner development build. It
does not certify remote deployment or production security. Evidence is the
code, backend tests, process-kill tests and browser suite at this checkpoint.

| Severity | Finding | Current disposition |
| --- | --- | --- |
| High if exposed remotely | There is no remote user authentication. Host, Origin and intent checks are designed only for a loopback browser and local processes. | API and Vite bind to loopback in documented commands and E2E; remote deployment remains unsupported. Do not expose either port publicly. |
| Medium | Uploaded task inputs were stored under `workspaces/<task-id>` but deletion cleaned only legacy `inputs/<task-id>`. | Fixed. Deletion stages and removes both locations; an API test creates an upload, deletes its task and confirms the owned directory is gone. External selected folders remain untouched. |
| Medium | Read and download path checks could be followed by a changed file before open. Windows alternate streams, device and UNC spellings were not all rejected before resolution. | Fixed for reads and downloads using canonical containment, conservative syntax checks and opened-file identity checks. Platform-neutral path and file-swap tests pass; Linux CI runs symlink cases unavailable on this Windows host. |
| Medium | A stalled tool could exceed its declared timeout indefinitely. | Fixed in the production worker. A supervisor terminates the child after the registered timeout, records `ToolTimeout`, and leaves uncertain writes for exact-file reconciliation. Tests cover read, cancellation, and writes before and after file creation. |
| Medium | Raw OS exception text in journal entries could reveal local paths; downloaded Markdown could contain active HTML from source text. | Fixed. Filesystem exceptions use a generic journal error, and report goal, source paths and quoted evidence escape HTML. Tests cover both. |
| Medium | Outbound fetch could reach internal services through private DNS answers, redirects or hostname changes; an unapproved task must not request a URL. | Mitigated in code: `fetch_url` requires a per-task grant and exact approval. HTTPS port 443, all DNS answers, pinned TCP/TLS identity, same-origin redirects, 64 KiB body limit and a 15-second supervised timeout are tested with mocked transport. One owner-approved request to `https://example.com/` completed with exactly one outbound call after approval. |
| Medium | App-owned report directories are checked before writes, but another process running as the same OS user could redirect a directory between validation and file creation. | Mitigated on POSIX by no-follow, directory-relative exclusive creation and identity checks. Windows still has a checked-path fallback. A hostile same-user process can move directories or alter local data; full resistance requires process isolation. |
| Medium | Task evidence and model planning data live in local SQLite. Manual or age-based deletion removes logical records and owned files, but SQLite WAL pages, backups and filesystem snapshots are not securely erased. | Open. An opt-in 30/90/365 day policy now prunes terminal tasks in bounded batches. Add an operator-controlled compaction/backup policy before claiming secure erasure. |
| Low | Mutation and planning rate limits are in process and reset on restart. | Open. Suitable only as a local resource guard; a remote deployment would need durable limits. Mutating request bodies are now capped at 512 KiB, including streamed bodies. |
| High in development tooling | `picomatch@4.0.7` in Vite/Vitest and their transitive packages is affected by [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), a ReDoS issue in repeated extglob patterns. | Owner-approved 30-day exception, strictly scoped to trusted local development tooling until end of 2026-12-18 UTC. The full audit still runs; CI rejects every other high/critical issue. Production audit remains mandatory. Not patched. |

### Temporary dependency exception — owner-approved 2026-11-18

The owner accepted a narrowly scoped, **temporary** exception for
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)
only in the current Vite/Vitest development dependency chain. It expires at
the end of **2026-12-18 UTC**, and must be reviewed for each release candidate
and removed as soon as a compatible fixed version becomes available.

The CI policy in `apps/web/scripts/audit-dependencies.mjs` runs and prints the
**full npm audit JSON**, allows this exact high-severity advisory only with
unchanged development-only package names, versions and install paths, and fails
for other high/critical findings or a changed dependency tree. CI also runs a
separate production-dependency audit. No untrusted glob expressions may be
passed to developer tooling. This is not an assertion that the vulnerability
is fixed, not an approval for remote deployment, and not a standing waiver.

### Owner acceptance — strictly local single-owner filesystem threat model

On 2026-11-18 the owner accepted the documented residual same-user
report-directory replacement race **only** for local-only, single-owner use,
where no hostile process operates with the same OS-user privileges. Existing
POSIX directory-handle mitigations and Windows path checks remain in place.
This does **not** provide isolation from malware or other same-user processes;
if that threat model changes, the risk acceptance no longer applies and the
release requires a new security assessment. SQLite deletion remains logical,
not secure erasure; the owner has not approved any claim of secure deletion.

Trust boundaries checked: task capability grants and plan argument hashes;
approval scope and expiry; source text treated as data; local Ollama origin and
typed plan validation; SQLite foreign keys and serialized state decisions;
artifact path, size and digest verification; journal and API error redaction;
retry keys, lease recovery, write reconciliation and process timeouts. The
model can propose a plan, but a human still reviews it before execution.

Manual assistive technology review remains a release gate. Isolated loopback
sequential and four-client smoke measurements are recorded
in the development status, along with a 40-task supervised worker sample. An
automated keyboard focus and submission path passed for the
task form. A separately cloned checkout installed lockfile
dependencies, applied seven migrations and passed backend, frontend and
browser checks. An installed local Ollama model completed a reviewable plan,
supervised execution and report approval in the opt-in browser test. Model
read paths are checked against selected inputs before review. Automated
WCAG A/AA checks pass on the five tested core views.
