# Local user guide

NEXUS is a single-owner local application. Follow [local setup](development.md)
to start the API, worker and web client. Keep the API and web client on their
documented loopback addresses; this is not a multi-user server.

## Create and run a task

1. Open the dashboard and choose **Create task**. Enter a goal, constraints
   and optional success criterion. The default demo uses synthetic local text.
   You can instead attach up to five small `.md` or `.txt` files, or select an
   operator-approved local folder.
2. Generate a deterministic demo plan or, if an installed local model is
   configured, an Ollama plan. Review every tool, argument, dependency and
   requested capability. Edit the plan before starting it.
3. Start the plan. The cockpit shows step state, events and tool receipts.
   A report write stops for approval. An HTTPS fetch needs a separate task
   grant and an exact approval; check the URL before approving.
4. Use **Pause** to stop dispatch after the current step, or **Cancel** to
   prevent later actions. An in-flight action may finish first. If a report
   write was interrupted, use the cockpit recovery inspection to accept only
   an exact matching report or confirm that the file is absent.
5. Open **Artifacts** to preview a verified report and download it. Open
   **History** to find tasks and export a bounded JSON history snapshot.

The report quotes and cites source excerpts; it does not verify their claims.
The model proposes steps but cannot add permissions. If a model proposes an
unknown file or tool, correct the plan or use the deterministic demo.

## Settings and data

Settings can change the installed Ollama model name, a concise or detailed
planning style, planning and task
timeouts, and retention of completed, failed and cancelled tasks. Retention
is off by default. A 30, 90 or 365 day period lets the worker remove eligible
task records and NEXUS-owned files in batches. **Delete** in History requires
the inactive task's exact ID. Neither cleanup path removes an external folder
selected for reading.

Task history export contains metadata, the bounded journal, receipts and
artifact records. It is not a full backup and does not include report bytes.
See [operations and backup](operations.md) for a complete local backup.

Public HTTPS fetch is optional and off per task by default. Only public port
443 text targets are supported, with bounded redirects and response size.
Avoid credential-bearing URLs: URLs and fetched text are kept in local task
data. A request with an uncertain outcome is not replayed automatically.

For errors, use the correlation ID returned by the API and follow the
[troubleshooting guide](troubleshooting.md).
