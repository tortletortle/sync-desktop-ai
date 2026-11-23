# SYNC V0.7

Experimental Python decision core for a desktop AI companion. This is not yet a desktop application: there is no Electron client, screen capture, production memory layer, notification delivery, or tool execution.

## Run

- Python 3.10+
- No third-party Python dependencies

Run the synthetic proxy benchmark:

    python bench.py

Run all deterministic unit tests:

    python -m unittest discover -v

## Deferred-task engine

The original in-memory engine remains available as TemporalTaskEngine. For crash-recoverable scheduling, use PersistentTemporalTaskEngine with SQLiteTaskStore:

    import time
    from pathlib import Path
    from sqlite_task_store import SQLiteTaskStore
    from persistent_task_engine import PersistentTemporalTaskEngine

    store = SQLiteTaskStore(Path.home() / ".sync" / "tasks.sqlite3")
    engine = PersistentTemporalTaskEngine(store)
    now = int(time.time())  # UTC epoch seconds for persistent deadlines
    engine.schedule("opaque-task-id", now, delay=60, ttl=3600)

The persistent engine commits each lifecycle operation atomically, restores active tasks on startup, remembers READY/offered state, and uses a revision check to reject stale concurrent writers. Call engine.refresh() after TaskStoreConflict before retrying. Task IDs must be short opaque ASCII tokens; cancellation reasons are allowlisted stable codes. Never store screen text, prompts, filenames, window titles, or other sensitive content in task IDs or reason fields.

Clock contract: the persistent engine accepts non-decreasing UTC epoch seconds, not time.monotonic(). This allows deadlines to survive process and machine restarts. If the system clock moves backwards, operations fail closed until the clock catches up or an operator resolves the condition.

## Evidence limits

bench.py and experiment.py use synthetic outcomes. They are not evidence of real user benefit, calibrated risk, or superiority to an LLM. The adaptive policy remains experimental. No desktop telemetry or user study has been conducted.
