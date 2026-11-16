# Local operations, backup and deletion

## Back up a consistent local instance

Stop the web client, API and worker first so no task or approval is in flight.
With the default configuration, copy the entire `services/api/data` directory
to a private backup location. This includes `nexus.db` and NEXUS-owned
`artifacts`, `workspaces` and legacy `inputs`. Preserve the directory layout.
If `DATABASE_URL` or `DATA_DIR` has been changed, include both the configured
database file and the complete configured data directory. An external folder
listed in `APPROVED_WORKSPACES` is not NEXUS-owned; back it up separately if
you need it. Keep the backup local and access-controlled because the database
can contain goals, source text, fetched content and URLs.

To restore, stop all processes, set aside the current data directory, copy
the backup into the configured locations, run `alembic upgrade head` from
`services/api`, then start the API and one worker. Check `/ready`, the worker
status on the dashboard, task history and one verified artifact download.
Restoring a backup can restore older task, approval and retention state;
inspect pending approvals before resuming a task.

## Delete or retain records

Delete an inactive task in History by confirming its ID. The application
removes its task rows and NEXUS-owned task directories. Alternatively, choose
30, 90 or 365 days in Settings. The worker checks at startup and about hourly
and prunes at most 20 eligible terminal tasks per pass. Zero disables this
automatic cleanup. Active tasks must be cancelled before manual deletion.

Deletion is logical. SQLite free pages, WAL files, old backups and filesystem
snapshots may retain bytes. Review and remove old backups according to your
own retention policy. NEXUS does not claim secure erasure. Do not manually
delete one task directory while its database records remain; that breaks
artifact integrity and recovery inspection.

If cleanup reports a staged directory under `data/deleting`, stop the worker
and inspect it before operator cleanup. The database transaction may already
have committed. See [security limits](security.md) for the same-user report
directory race and local-only trust boundary.
