"""Deterministic deferred-task lifecycle. No UI action is executed here."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

class Status(str, Enum):
    PENDING="pending"
    READY="ready"
    RESOLVED="resolved"
    EXPIRED="expired"
    CANCELLED="cancelled"

@dataclass
class DeferredTask:
    task_id: str
    created_at: int
    due_at: int
    expires_at: int
    status: Status = Status.PENDING
    offered: bool = False
    reason: Optional[str] = None

class TemporalTaskEngine:
    def __init__(self, max_pending: int = 100):
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        self.max_pending=max_pending
        self.tasks: Dict[str, DeferredTask]={}
        self._last_now=-1

    def _clock(self, now: int):
        if not isinstance(now,int) or now < self._last_now:
            raise ValueError("now must be a monotonic integer")
        self._last_now=now

    def schedule(self, task_id: str, now: int, delay: int, ttl: int) -> DeferredTask:
        self._clock(now)
        if not task_id or delay < 0 or ttl <= 0:
            raise ValueError("invalid task id, delay, or ttl")
        if task_id in self.tasks and self.tasks[task_id].status in (Status.PENDING,Status.READY):
            return self.tasks[task_id]  # idempotent; do not reset deadline
        active=sum(t.status in (Status.PENDING,Status.READY) for t in self.tasks.values())
        if active >= self.max_pending:
            raise OverflowError("pending task capacity reached")
        task=DeferredTask(task_id,now,now+delay,now+delay+ttl)
        self.tasks[task_id]=task
        return task

    def cancel(self, task_id: str, reason: str, now: int) -> bool:
        self._clock(now)
        task=self.tasks.get(task_id)
        if task is None or task.status not in (Status.PENDING,Status.READY):
            return False
        task.status=Status.CANCELLED; task.reason=reason
        return True

    def resolve(self, task_id: str, now: int) -> bool:
        self._clock(now)
        task=self.tasks.get(task_id)
        if task is None or task.status not in (Status.PENDING,Status.READY):
            return False
        task.status=Status.RESOLVED; task.reason="condition no longer exists"
        return True

    def poll(self, now: int, *, authorized: bool, dnd: bool,
             condition_exists: Dict[str,bool], safe_to_interrupt: bool) -> list[str]:
        self._clock(now)
        ready=[]
        if not authorized or dnd:
            for task in self.tasks.values():
                if task.status in (Status.PENDING,Status.READY):
                    task.status=Status.CANCELLED
                    task.reason="permission revoked" if not authorized else "do not disturb"
            return ready
        for task in self.tasks.values():
            if task.status not in (Status.PENDING,Status.READY):
                continue
            if now >= task.expires_at:
                task.status=Status.EXPIRED; task.reason="ttl elapsed"; continue
            if condition_exists.get(task.task_id) is False:
                task.status=Status.RESOLVED; task.reason="condition cleared"; continue
            if now >= task.due_at and safe_to_interrupt and condition_exists.get(task.task_id) is True and not task.offered:
                task.status=Status.READY
                task.offered=True
                ready.append(task.task_id)
        return ready
