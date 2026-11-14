# ADR 0002: Synchronous planning during the local MVP

Status: temporary

The design specification calls for a durable asynchronous planning operation.
The current implementation requests a bounded Ollama plan in a synchronous
API handler and returns the reviewed plan after completion. This keeps the
first demo path small but means `/plan` does not expose an intermediate
`planning` state to the browser. Planning must move to a durable job before
the v1 release; the state machine already models that state.
