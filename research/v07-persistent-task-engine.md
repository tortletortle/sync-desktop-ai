# V0.7 — Transactional persistent task engine

## Implemented

- Added PersistentTemporalTaskEngine, retaining the original in-memory TemporalTaskEngine API for existing experiments.
- Added a metadata revision and persisted clock watermark to SQLite.
- Each schedule, poll, cancel, and resolve operation commits its state changes and clock watermark in one BEGIN IMMEDIATE transaction.
- Added optimistic revision checks. A stale engine instance receives TaskStoreConflict and must call refresh() before retrying.
- Added conditional lifecycle transitions so stale updates cannot overwrite terminal states.
- Preserved task IDs as idempotency keys across terminal states; a completed/cancelled ID cannot silently be reused.
- Restores PENDING and READY tasks, including READY/offered state, after restart.
- Restricts task IDs to short opaque ASCII tokens and cancellation reasons to allowlisted stable codes, reducing the chance that screen content is persisted in metadata.
- Persistent deadlines use UTC epoch seconds so they survive process and machine restarts. Backwards clock movement fails closed.
- Added a Python 3.10–3.12 GitHub Actions test workflow.

## Verification scope

Added deterministic tests for restart recovery, no duplicate READY delivery, idempotent scheduling, terminal-ID non-resurrection, permission revocation, DND, expiry, unsafe interruption, persisted clock regression, stale writers, transaction rollback, capacity, invalid inputs, and sensitive-text rejection.

The repository was edited through GitHub's file/Git APIs in this session; the Python test suite was not executed in a local runtime here. The Actions jobs were created but failed before any runner started (no job steps or logs were available). Do not describe these tests as passing until a runner executes them successfully.

## Guarantees and limitations

The transaction boundary covers SQLite state transitions, not UI notification delivery. Exactly-once external delivery is not claimed: the host must still make notification presentation idempotent using the task ID and reconcile delivery state if it later adds a notification adapter.

Revision checks prevent silent last-write-wins updates between engine instances, but they do not implement automatic retries or a distributed lease. Callers must refresh after conflicts. A single desktop process should own the engine.

The clock is a caller-supplied UTC epoch-second integer. Wall-clock rollback is rejected; no trusted time service or monotonic/UTC hybrid clock is implemented. Encryption at rest, database backup/restore, schema migration framework, audit-event history, cross-process notification delivery, and packaged Windows/macOS integration remain out of scope.

Task rows contain opaque IDs and fixed lifecycle reason codes only. Do not persist OCR output, screen text, application titles, prompts, or credentials in this table.
