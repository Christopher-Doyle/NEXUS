# Contributing

NEXUS is under active local development. Read the
[architecture](docs/architecture.md), [development setup](docs/development.md)
and [security boundary](docs/security.md) before changing tool or worker code.
Keep network access opt-in and approval-scoped; do not add arbitrary shell
execution, paid services or remote exposure as a convenience.

Run `uv run ruff check app tests scripts`,
`uv run python scripts/export_openapi.py --check` and `uv run pytest -q` from
`services/api`. Run `npm run build`, `npm test` and `npm run test:e2e` from
`apps/web`. Update the requirement matrix and development checkpoint with
tested behavior and limitations. Report security issues privately to the
repository owner rather than posting exploit details in a public issue.
