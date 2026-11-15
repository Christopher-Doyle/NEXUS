# Local security review — 2026-11-16

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
| Medium | A local caller could set `network_access=true` despite no approved outbound tool. | Fixed. Task creation rejects the flag; settings and tool registry also keep outbound tools disabled. |
| Medium | App-owned report directories are checked before writes, but another process running as the same OS user could redirect a directory between validation and file creation. | Open. Exclusive creation and recovery prevent silent duplicate writes, but strong directory-handle isolation is still needed for this local race. |
| Medium | Task evidence and model planning data live in local SQLite. Deleting a task removes logical records and owned files, but SQLite WAL pages, backups and filesystem snapshots are not securely erased. | Open. Document the retention boundary and add an operator-controlled compaction/backup policy before claiming secure erasure. |
| Low | Mutation and planning rate limits are in process and reset on restart. | Open. Suitable only as a local resource guard; a remote deployment would need durable limits. Mutating request bodies are now capped at 512 KiB, including streamed bodies. |

Trust boundaries checked: task capability grants and plan argument hashes;
approval scope and expiry; source text treated as data; local Ollama origin and
typed plan validation; SQLite foreign keys and serialized state decisions;
artifact path, size and digest verification; journal and API error redaction;
retry keys, lease recovery, write reconciliation and process timeouts. The
model can propose a plan, but a human still reviews it before execution.

Manual assistive technology review and load/capacity measurements remain
release gates. An isolated loopback API latency smoke measurement is recorded
in the development status. An automated keyboard focus and submission path passed for the
task form. A separately cloned checkout installed lockfile
dependencies, applied seven migrations and passed backend, frontend and
browser checks. An installed local Ollama model completed a reviewable plan,
supervised execution and report approval in the opt-in browser test. Model
read paths are checked against selected inputs before review. Automated
WCAG A/AA checks pass on the five tested core views.
