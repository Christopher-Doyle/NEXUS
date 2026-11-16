# Local development

Requires Python 3.12+, Node.js 22+, uv, and npm. No paid service is required.

From `services/api`:

```powershell
uv sync --extra dev
New-Item -ItemType Directory -Force data
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

In a second terminal, also from `services/api`, run the single worker process:

```powershell
uv run python -m app.worker
```

From `apps/web` in another terminal:

```powershell
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The API docs are at
`http://127.0.0.1:8765/docs`. Run checks with `uv run pytest -q`,
`uv run ruff check app tests`, and `npm run build`.

The default demo uses two synthetic files in `fixtures/demo`. You may attach
up to five `.md` or `.txt` files in the task form. To allow a folder instead,
set `APPROVED_WORKSPACES` in `.env` to an exact absolute local path; separate
multiple paths with semicolons. Writes always go to `DATA_DIR/artifacts` and
require approval in the cockpit. Set `OLLAMA_MODEL` to an installed local model
to enable Ollama planning; demo mode needs no model.
`OLLAMA_TIMEOUT_SECONDS` bounds a planning request (default: 90 seconds).
The optional adapter has been verified locally with `qwen3.5:9b`. It disables
thinking for structured plans and caps generation at 1024 tokens. The model
must already be installed; NEXUS does not download one.
`TASK_TIMEOUT_SECONDS` sets the task dispatch deadline (default: 3600 seconds).
The Settings page can override the model name, both timeouts and terminal-task
retention in SQLite. Retention is off by default; enabling it removes old
task records and NEXUS-owned files when the local worker checks for cleanup.
`APPROVED_WORKSPACES`, `DATA_DIR`, and `OLLAMA_ENDPOINT` remain operator-only
environment settings. Run `alembic upgrade head` before using the updated UI.

Public HTTPS text fetch is an optional task capability. Select it on the task
form, add a `fetch_url` plan step with a full `https://` URL, and approve the
exact step in the cockpit. The worker validates every DNS address as public,
pins the validated IP for TLS, allows only same-origin redirects and caps
response text at 64 KiB. Fetch failures or uncertain interrupted attempts
stop for review; the worker does not replay them automatically. Do not put
credentials in URLs: URLs and fetched text are stored in local task records.
The ordinary demo and browser suite make no real public network requests.

## Reproducible browser demo

After `uv sync --extra dev` in `services/api` and `npm ci` in `apps/web`, run
`npm run test:e2e` from `apps/web`. It needs an installed Google Chrome and
does not download a browser. The runner creates an isolated temporary SQLite
database, migrates it, starts the API, worker and web client on loopback,
executes approved and rejected synthetic workflows, then stops services and
removes its own test data. Ports 8765 and 5173 must be available. Set
`NEXUS_PYTHON` to a Python executable if the API virtual environment is not
at `services/api/.venv`.
The browser suite includes automated WCAG A/AA checks through the reviewed
open-source `@axe-core/playwright` development dependency. Automated checks
do not replace keyboard and assistive technology review.

To exercise Ollama planning and execution through the browser with an already installed
model, set `NEXUS_E2E_OLLAMA_MODEL` to its local name before running
`npm run test:e2e`. The regular suite leaves the model unset and skips this
optional case. The runner never downloads a model.

For a small loopback API latency sample, run `uv run python scripts/measure_local.py`
from `services/api`. It migrates an isolated temporary database, starts an API
process on a free loopback port, and reports median, p95 and maximum times for
100 `/health`, 100 `/ready`, 100 `/ready` requests across four clients and 10
synthetic task-creation requests. This is a
single-process smoke measurement, not a load or release capacity benchmark.
