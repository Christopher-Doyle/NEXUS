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
set `APPROVED_WORKSPACES` in `.env` to an exact absolute path; separate
multiple paths with semicolons. Writes always go to `DATA_DIR/artifacts` and
require approval in the cockpit. Set `OLLAMA_MODEL` to an installed local model
to enable Ollama planning; demo mode needs no model.
`OLLAMA_TIMEOUT_SECONDS` bounds a planning request (default: 90 seconds).
The optional adapter has been verified locally with `qwen3.5:9b`. It disables
thinking for structured plans and caps generation at 1024 tokens. The model
must already be installed; NEXUS does not download one.
`TASK_TIMEOUT_SECONDS` sets the task dispatch deadline (default: 3600 seconds).
The Settings page can override the model name and both timeouts in SQLite.
`APPROVED_WORKSPACES`, `DATA_DIR`, and `OLLAMA_ENDPOINT` remain operator-only
environment settings. Run `alembic upgrade head` before using the updated UI.
