# Security boundary and current limits

NEXUS binds the API and dev server to loopback. Mutations require an accepted
local Host and Origin plus `X-Nexus-Intent: local`; this is a local browser
boundary, not remote user authentication. No remote deployment is supported.

The worker executes registered `read_file` and `write_report` operations only.
It validates the tool grant, typed arguments and argument hash at dispatch.
Reads resolve the canonical path under the task workspace, reject symlink
escapes, and cap Markdown/text files at 64 KiB. Uploaded text inputs are
bounded to five files. Approved folders must exactly match the operator's
`APPROVED_WORKSPACES` setting. Network access is not implemented.

Report writes require an unexpired approval tied to the task, plan version,
step and argument hash. The worker uses exclusive creation for the output file
and records its SHA-256 digest. Downloads recheck the artifact path and digest.
After an uncertain interrupted write, the worker marks the step for review
instead of repeating it. A separate worker process should be run only once
until cross-process leasing is implemented.

Source documents and model responses are untrusted. The deterministic report
quotes source text as evidence; it does not follow instructions found there.
Ollama is restricted to a configured loopback HTTP origin. No paid API or
telemetry is required.
