# Security boundary and current limits

NEXUS binds the API and dev server to loopback. Mutations require an accepted
local Host and Origin plus `X-Nexus-Intent: local`; this is a local browser
boundary, not remote user authentication. No remote deployment is supported.

The worker executes registered `read_file`, `search_local_docs`, `fetch_url`
and `write_report` operations only.
It validates the tool grant, typed arguments and argument hash at dispatch.
The registry also validates the output shape and serialized size before an
execution result is persisted. The production worker runs each action in a
killable child process and applies the registry timeout after the tool starts.
A timed-out local read fails with `ToolTimeout`; a timed-out report write
becomes `needs_review` and uses exact-file reconciliation. An uncertain HTTPS
request is never retried automatically and requires a new, explicitly
approved task if the owner chooses to try again.
Tool receipts retain the version used at dispatch. The receipt endpoint
revalidates stored result schemas and omits source file contents from API
responses; the local database still contains read text needed for reports.
Started tasks have a persisted dispatch deadline, one hour by default. The
worker fails expired tasks before scheduling another tool, and an approval or
report write rechecks the deadline. A tool already in progress can continue
until its separate registered tool timeout.
Reads resolve the canonical path under the task workspace, reject symlink
escapes, and cap Markdown/text files at 64 KiB. Uploaded text inputs are
bounded to five files. Approved folders must exactly match the operator's
`APPROVED_WORKSPACES` setting and use an absolute local path; UNC, device and
alternate-stream syntax is rejected. Relative read paths reject those forms,
traversal and control characters on both Windows and Linux. Reads compare the
opened file identity with the validated file before reading, so a path swap
between validation and open is denied. Search examines only those selected files and
returns at most 20 line excerpts. HTTPS fetch is off by default and requires
both a task capability and `network_access=true`, then a separate exact-scope
approval. The fetch policy allows public HTTPS port 443 only, rejects userinfo,
ambiguous URL syntax and non-public DNS answers, pins the TCP connection to a
validated address with the original TLS hostname, revalidates same-origin
redirects, and caps redirects, time and response bytes. Mocked policy and
approval tests pass. A real public fetch is awaiting explicit external-access
approval at this checkpoint.

Report writes require an unexpired approval tied to the task, plan version,
step and argument hash. The worker uses exclusive creation for the output file
and records its SHA-256 digest. Artifact directories reject symlink redirection.
Downloads recheck the artifact path, opened file identity, size and digest
before sending bytes. A redirected artifact root is rejected.
Report citations name each selected local or approved HTTPS source and its
line range and SHA-256 content
snapshot. Before writing, the worker recomputes the digest of each stored read
receipt and checks its provenance against the plan step. A changed source
file after the read does not alter that snapshot; citations are evidence
references, not a verification of the source's claims.
The worker acquires a SQLite write lock before the final report action and
rechecks task state and approval. A cancellation acknowledged before that
boundary prevents the write; a cancellation requested during the write waits
for the result and returns a conflict if the task has completed.
After an uncertain interrupted write, the worker marks the step for review
instead of repeating it. Expired read leases retry at most twice after the
initial attempt; exhaustion fails the task. A 12-task test with two separate
Windows worker processes completed without duplicate executions. One worker remains the
recommended development setup while broader recovery behavior is verified.
An additional test kills a worker after the report reaches disk but before
its database transaction commits. Recovery preserves the single file and
execution receipt and marks the step for review.
The recovery endpoint reconstructs the expected report from stored read
receipts and accepts an existing file only when its SHA-256 matches exactly.
It rejects stale inspection digests, mismatched content, redirected paths and
duplicate artifact records. An absent file may be acknowledged; it is never
silently rewritten. Dependent steps requeue only if the task deadline remains
valid; expired tasks stay failed.
The app-owned report directory is checked for redirection before a write,
but a separate process running as the same OS user could change that directory
between the check and file creation. Stronger OS-level directory-handle or
process isolation is still needed before treating local filesystem writes as
fully race resistant.

Source documents and model responses are untrusted. The deterministic report
quotes source text as evidence; it does not follow instructions found there.
The exported Markdown escapes HTML in the goal, source paths and quoted text.
Ollama is restricted to a configured loopback HTTP origin. No paid API or
telemetry is required.

Task deletion requires the exact task ID in the request and is available only
for inactive tasks. It removes task records, execution journals, and NEXUS-owned
input and artifact directories. The selected external workspace is never a
deletion target. Cleanup stages owned directories under the app data root;
failure after database deletion is reported for operator cleanup.
Uploaded inputs are stored under app-owned `workspaces/<task-id>` and are
removed with the task; legacy `inputs/<task-id>` directories are also cleaned.

The settings UI can change the local model name, two bounded timeouts and an
opt-in terminal-task retention period. The worker prunes at most 20 old
completed, failed or cancelled tasks per hourly check; default zero keeps
them until manual deletion. This is logical deletion, not secure erasure of
SQLite free pages, backups or filesystem snapshots.
It cannot expand workspace grants, enable network tools or change the loopback
endpoint. Those boundaries remain in the operator's environment configuration.
The HTTPS tool is a per-task opt-in capability; Settings cannot turn it on
globally or expand a task's grant after creation.

Mutating requests are limited in process to 120 per minute, with a separate
20-per-minute planning bucket. Responses include `Retry-After` when limited.
This is a local resource safeguard, not a distributed or durable security
boundary. Unexpected exceptions return a generic 500 with a correlation ID;
the local log records only the exception type and correlation ID.
Filesystem failures recorded in task journals use generic text rather than
raw OS exception paths. The severity-ranked review and residual risks are in
[the security audit](security-audit.md).
