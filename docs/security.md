# Security boundary and current limits

NEXUS binds the API and dev server to loopback. Mutations require an accepted
local Host and Origin plus `X-Nexus-Intent: local`; this is a local browser
boundary, not remote user authentication. No remote deployment is supported.

The worker executes registered `read_file`, `search_local_docs`, and
`write_report` operations only.
It validates the tool grant, typed arguments and argument hash at dispatch.
The registry also validates the output shape and serialized size before an
execution result is persisted. Registered timeouts are not yet hard process
deadlines.
Started tasks have a persisted dispatch deadline, one hour by default. The
worker fails expired tasks before scheduling another tool, and an approval or
report write rechecks the deadline. A tool already in progress may finish.
Reads resolve the canonical path under the task workspace, reject symlink
escapes, and cap Markdown/text files at 64 KiB. Uploaded text inputs are
bounded to five files. Approved folders must exactly match the operator's
`APPROVED_WORKSPACES` setting. Search examines only those selected files and
returns at most 20 line excerpts. Network access is not implemented.

Report writes require an unexpired approval tied to the task, plan version,
step and argument hash. The worker uses exclusive creation for the output file
and records its SHA-256 digest. Artifact directories reject symlink redirection.
Downloads recheck the artifact path and digest.
The worker acquires a SQLite write lock before the final report action and
rechecks task state and approval. A cancellation acknowledged before that
boundary prevents the write; a cancellation requested during the write waits
for the result and returns a conflict if the task has completed.
After an uncertain interrupted write, the worker marks the step for review
instead of repeating it. A 12-task test with two separate Windows worker
processes completed without duplicate executions. One worker remains the
recommended development setup while broader recovery behavior is verified.

Source documents and model responses are untrusted. The deterministic report
quotes source text as evidence; it does not follow instructions found there.
Ollama is restricted to a configured loopback HTTP origin. No paid API or
telemetry is required.
