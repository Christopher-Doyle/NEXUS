# NEXUS development status

## Milestone

Milestone 1 foundation completed and pushed. Milestone 2 has a tested
task-to-plan vertical slice; workspace selection and input files remain open.
Milestone 3 has a tested Ollama adapter but has not been exercised with a
running local model.

## Implemented

- React/Vite dashboard shell and API status display.
- FastAPI `/health` and `/ready` endpoints.
- SQLAlchemy models for the seven baseline entities and an initial Alembic migration.
- Python and JavaScript dependency locks; GitHub Actions CI definition.
- Persisted task creation, list, detail, deterministic planning and plan editing.
- Strict allowlisted plan arguments, 12-step limit, dependency validation,
  version conflict handling and a task state transition table.
- Task composer, recent-task list and editable plan review UI.
- Configurable Ollama endpoint/model, bounded structured planning, one JSON
  repair attempt, offline error messaging and model availability check.

## Incomplete

Optional input file upload and owner-selected workspace folders are not yet
implemented. Live Ollama integration has only mock tests. Tool execution, approvals, worker recovery,
live events, artifact delivery and the full UI remain incomplete.

## Checks

Both migrations applied locally. Seven backend tests pass. Ruff and the web production build pass. npm audit
reported zero vulnerabilities after updating Vitest. CI has not run remotely.

## Version control

Latest pushed commit: eb8460d (foundation). Milestone 2 commit pending.

## Known issues and security

The API requires a local Host, accepted Origin and explicit intent header for
mutations. This boundary is intended only for a local single-owner setup. The
demo planner always uses synthetic fixture names and does not yet execute.
Dependency licences and CI results have not yet been reviewed. No secrets or
user data are included.

## Next task

Fix the final lint issue, commit and push the Ollama adapter. Next implement
the local demo tool policy, approvals and separate worker so the plan can run.
