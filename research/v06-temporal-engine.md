# SYNC V0.6 — Temporal Task Engine

## Scope
A deterministic, in-memory lifecycle engine for deferred assistance. It schedules and re-evaluates a task; it does not capture the screen, infer task state, show notifications, or execute tools.

## Lifecycle
PENDING → READY when due, the underlying condition is still present, permission remains granted, DND is off, and the caller says interruption is safe.
PENDING/READY → RESOLVED when the condition clears.
PENDING/READY → EXPIRED when TTL elapses.
PENDING/READY → CANCELLED when permission is revoked, DND is enabled, or explicitly cancelled.

## Safety properties
- Monotonic integer clock; backwards time is rejected.
- Duplicate scheduling is idempotent and cannot extend the original deadline.
- Explicit capacity limit prevents unbounded pending-task growth.
- Permission revocation and DND cancel all active tasks.
- READY is only a recommendation for the host app; it does not execute an action.

## Verification
Run: `python -m unittest -v`
The 10 deterministic tests cover due scheduling, resolution, expiry, permission revocation, DND, idempotence, clock regression, capacity, cancellation idempotence, and unsafe interruption deferral.

## Known limitations
State is in-memory and lost on process restart. The caller supplies condition truth and interruption safety; no real desktop integration exists. Task IDs must be opaque and should not contain sensitive screen content. A production version needs SQLite persistence, crash recovery, audit events, and a permission-change event source.
