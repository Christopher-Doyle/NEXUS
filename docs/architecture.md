# Architecture

NEXUS is a local-first, single-owner application. The React client uses a
versioned FastAPI service. The service owns state, permissions, and all data
changes. SQLite stores durable tasks, steps, approvals, execution records,
events, and artifact metadata. A separate worker process will execute only
registered tools after server-side policy checks. Ollama is optional; demo mode
uses deterministic fixtures.

The initial foundation includes the schema and service health routes. Task
orchestration and tool execution are not active yet.
