# Local development

Requires Python 3.12+, Node.js 22+, uv, and npm. No paid service is required.

From `services/api`:

```powershell
uv sync --extra dev
New-Item -ItemType Directory -Force data
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

From `apps/web` in another terminal:

```powershell
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The API docs are at
`http://127.0.0.1:8765/docs`. Run checks with `uv run pytest -q`,
`uv run ruff check app tests`, and `npm run build`.
