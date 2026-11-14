# API implemented so far

The API is local only and binds to `127.0.0.1` by default. Mutating requests
require `X-Nexus-Intent: local`; browser requests must have a permitted local
Origin. This is a single-owner development boundary, not a remote access
authentication scheme.

| Method | Route | Behaviour |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| GET | `/ready` | Database connection check |
| POST | `/api/v1/tasks` | Create a draft task |
| GET | `/api/v1/tasks` | List tasks, bounded pagination |
| GET | `/api/v1/tasks/{id}` | Read a task and its steps |
| POST | `/api/v1/tasks/{id}/plan` | Generate the deterministic demo plan |
| PATCH | `/api/v1/tasks/{id}/steps` | Replace a plan with a matching version |

OpenAPI is available at `/docs` while the API runs. Only the deterministic
demo planner is currently available. Task execution, approval, events, and
artifacts are not yet exposed.
