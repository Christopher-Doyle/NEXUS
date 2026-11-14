# NEXUS development status

## Milestone

Milestone 1 foundation completed and pushed. Milestone 2 has a tested
task-to-plan vertical slice; workspace selection and input files remain open.

## Implemented

- React/Vite dashboard shell and API status display.
- FastAPI `/health` and `/ready` endpoints.
- SQLAlchemy models for the seven baseline entities and an initial Alembic migration.
- Python and JavaScript dependency locks; GitHub Actions CI definition.
- Persisted task creation, list, detail, deterministic planning and plan editing.
- Strict allowlisted plan arguments, 12-step limit, dependency validation,
  version conflict handling and a task state transition table.
- Task composer, recent-task list and editable plan review UI.

## Incomplete

Optional input file upload and owner-selected workspace folders are not yet
implemented. Ollama planning, tool execution, approvals, worker recovery,
live events, artifact delivery and the full UI remain incomplete.

## Checks

Both migrations applied locally. Four backend tests pass. Ruff and the web production build pass. npm audit
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

Commit and push the tested task-to-plan slice. Next, complete task workspace
and input file handling, then implement the bounded Ollama adapter.
