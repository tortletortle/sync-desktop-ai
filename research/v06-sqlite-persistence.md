# V0.6.1 — SQLite task persistence

## Implemented
- SQLite database with WAL journal mode.
- Opaque task identifiers and lifecycle metadata only; no screen text or captured content.
- Active-task restoration for PENDING and READY records.
- READY/offered state survives restart to prevent re-offering the same notification.
- Terminal-state updates are idempotently rejected.
- Indexed status/due-time lookup.

## Verification
Seven deterministic tests passed in an isolated Python run: round-trip, READY/offered persistence, terminal filtering, status update, missing record, invalid record, and reopening the database.

## Important limitations
The store is a persistence component, not yet wired into TemporalTaskEngine. The engine and database can therefore diverge until a repository/service layer coordinates state transitions transactionally. No migration framework, encryption-at-rest, backup policy, or Windows packaged-app integration is implemented. The application must keep task IDs opaque and never persist raw screen text in this table.
