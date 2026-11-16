# Troubleshooting

| Symptom | Check | Next step |
| --- | --- | --- |
| Dashboard says worker inactive | The separate `python -m app.worker` process and its terminal output | Start one worker from `services/api`; check that the configured database and data directory match the API. |
| `/ready` fails or tables are missing | `DATABASE_URL` and migration state | Stop services and run `alembic upgrade head` from `services/api`. |
| Ollama plan unavailable | Settings model name, `/api/v1/model/status`, and local Ollama process | Use the installed model's exact name or deterministic demo mode. NEXUS never downloads a model. |
| Plan is rejected | Step tool, arguments, dependencies and task capabilities | Edit the plan to refer only to selected files and granted tools. Model output does not grant permissions. |
| Task is waiting for approval | Cockpit approval scope and expiry | Inspect the exact action and approve or reject it. A changed plan needs a new approval. |
| Report needs recovery | Cockpit recovery inspection | Accept only an exact digest match, or confirm an absent file. A mismatch needs local operator inspection. |
| HTTPS fetch needs review | Journal and receipt | The request may have reached the remote target. NEXUS will not replay it; create a newly approved task if needed. |
| Report download fails | Artifact file and configured data directory | A 404 means unavailable; 409 means changed content or identity. Restore a trusted backup rather than bypassing the check. |
| Browser live updates disconnect | Cockpit reconnect status | The browser retries SSE and refreshes stored state. Reload if the loopback API has restarted. |
| 413, 422 or 429 API error | Response code, field list or `Retry-After` | Reduce the body, correct the named field or wait for the local rate limit window. |

Unexpected API errors return a correlation ID without internal exception text.
Use it to match the local server log. Do not paste goals, source text, tokens
or database contents into a public issue. For a reproducible local demo, run
`npm run test:e2e` from `apps/web` after installing the lockfile dependencies.
