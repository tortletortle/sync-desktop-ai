"""Crash-recoverable deferred-task lifecycle backed by SQLite."""
from dataclasses import replace

from sqlite_task_store import SQLiteTaskStore
from temporal_engine import DeferredTask, Status


class PersistentTemporalTaskEngine:
    """Atomic SQLite-backed task lifecycle.

    now is UTC epoch seconds, not time.monotonic(). Use int(time.time()).
    Persisted deadlines survive process and machine restarts. A backwards wall-clock
    adjustment fails closed; concurrent writers must refresh and retry.
    """

    def __init__(self, store: SQLiteTaskStore, max_pending: int = 100):
        if isinstance(max_pending, bool) or not isinstance(max_pending, int) or max_pending < 1:
            raise ValueError("max_pending must be a positive integer")
        self.store = store
        self.max_pending = max_pending
        self.tasks = {}
        self._revision = 0
        self._last_now = -1
        self.refresh()

    def refresh(self):
        """Reload the active snapshot after a concurrent-writer conflict."""
        active, revision, last_now = self.store.load_state()
        if len(active) > self.max_pending:
            raise OverflowError("persisted active tasks exceed configured capacity")
        self.tasks = {task.task_id: task for task in active}
        self._revision = revision
        self._last_now = last_now
        return list(active)

    def _clock(self, now):
        if isinstance(now, bool) or not isinstance(now, int) or now < 0:
            raise ValueError("now must be a non-negative UTC epoch-second integer")
        if now < self._last_now:
            raise ValueError("now moved backwards; persistent deadlines require UTC epoch seconds")

    def _commit(self, now, *, inserts=(), updates=()):
        self._revision = self.store.commit(
            self._revision, now, inserts=inserts, updates=updates
        )
        self._last_now = now

    def schedule(self, task_id: str, now: int, delay: int, ttl: int) -> DeferredTask:
        self._clock(now)
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id must be a non-empty opaque string")
        for value, label in ((delay, "delay"), (ttl, "ttl")):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(label + " must be an integer")
        if delay < 0 or ttl <= 0:
            raise ValueError("delay must be non-negative and ttl must be positive")

        existing = self.store.get_task(task_id)
        if existing is not None:
            # A task ID is an idempotency key for its entire lifetime, including
            # terminal states. Never resurrect a completed/cancelled task.
            self.refresh()
            self._clock(now)
            self._commit(now)
            return existing

        if len(self.tasks) >= self.max_pending:
            raise OverflowError("pending task capacity reached")
        task = DeferredTask(task_id, now, now + delay, now + delay + ttl)
        self._commit(now, inserts=(task,))
        self.tasks[task_id] = task
        return task

    def cancel(self, task_id: str, reason: str, now: int) -> bool:
        self._clock(now)
        if not isinstance(reason, str) or not reason:
            raise ValueError("reason must be a non-empty string")
        task = self.tasks.get(task_id)
        if task is None:
            self._commit(now)
            return False
        updated = replace(task, status=Status.CANCELLED, reason=reason)
        self._commit(now, updates=(updated,))
        self.tasks.pop(task_id, None)
        return True

    def resolve(self, task_id: str, now: int) -> bool:
        self._clock(now)
        task = self.tasks.get(task_id)
        if task is None:
            self._commit(now)
            return False
        updated = replace(
            task, status=Status.RESOLVED, reason="condition no longer exists"
        )
        self._commit(now, updates=(updated,))
        self.tasks.pop(task_id, None)
        return True

    def poll(self, now: int, *, authorized: bool, dnd: bool,
             condition_exists: dict, safe_to_interrupt: bool) -> list:
        self._clock(now)
        if not isinstance(authorized, bool) or not isinstance(dnd, bool):
            raise ValueError("authorized and dnd must be booleans")
        if not isinstance(safe_to_interrupt, bool):
            raise ValueError("safe_to_interrupt must be boolean")

        ready = []
        active_after = {}
        updates = []
        for task in self.tasks.values():
            updated = replace(task)
            if not authorized or dnd:
                updated.status = Status.CANCELLED
                updated.reason = "permission revoked" if not authorized else "do not disturb"
            elif now >= task.expires_at:
                updated.status = Status.EXPIRED
                updated.reason = "ttl elapsed"
            elif condition_exists.get(task.task_id) is False:
                updated.status = Status.RESOLVED
                updated.reason = "condition cleared"
            elif (now >= task.due_at and safe_to_interrupt
                  and condition_exists.get(task.task_id) is True and not task.offered):
                updated.status = Status.READY
                updated.offered = True
                ready.append(task.task_id)

            if updated.status in (Status.PENDING, Status.READY):
                active_after[updated.task_id] = updated
            if updated != task:
                updates.append(updated)

        # One SQLite transaction covers every transition caused by this poll.
        self._commit(now, updates=updates)
        self.tasks = active_after
        return ready
