"""SQLite persistence for TemporalTaskEngine; stores opaque task metadata only."""
import sqlite3
from pathlib import Path
from temporal_engine import DeferredTask, Status


class TaskStoreConflict(RuntimeError):
    """The persisted snapshot changed or a task transition lost a race."""


class SQLiteTaskStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("""CREATE TABLE IF NOT EXISTS deferred_tasks (
                task_id TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                due_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                status TEXT NOT NULL,
                offered INTEGER NOT NULL CHECK(offered IN (0,1)),
                reason TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_deferred_status_due ON deferred_tasks(status,due_at)")
            db.execute("""CREATE TABLE IF NOT EXISTS task_store_meta (
                id INTEGER PRIMARY KEY CHECK(id=1),
                revision INTEGER NOT NULL,
                last_now INTEGER NOT NULL
            )""")
            db.execute(
                "INSERT OR IGNORE INTO task_store_meta(id,revision,last_now) VALUES(1,0,-1)"
            )

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _row_to_task(row):
        return DeferredTask(
            row[0], row[1], row[2], row[3], Status(row[4]), bool(row[5]), row[6]
        )

    @staticmethod
    def _validate_task(task):
        if not isinstance(task, DeferredTask):
            raise ValueError("task must be a DeferredTask")
        if not isinstance(task.task_id, str) or not task.task_id:
            raise ValueError("task_id must be a non-empty opaque string")
        for value in (task.created_at, task.due_at, task.expires_at):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("task timestamps must be non-negative integers")
        if task.created_at > task.due_at or task.expires_at <= task.due_at:
            raise ValueError("invalid task timestamps")
        if not isinstance(task.status, Status):
            raise ValueError("invalid task status")
        if not isinstance(task.offered, bool):
            raise ValueError("offered must be boolean")

    def save(self, task: DeferredTask):
        """Legacy upsert API; bumps revision so active engines detect external writes."""
        self._validate_task(task)
        with self._connect() as db:
            db.execute("""INSERT INTO deferred_tasks
                (task_id,created_at,due_at,expires_at,status,offered,reason)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET
                created_at=excluded.created_at,due_at=excluded.due_at,
                expires_at=excluded.expires_at,status=excluded.status,
                offered=excluded.offered,reason=excluded.reason""",
                (task.task_id,task.created_at,task.due_at,task.expires_at,
                 task.status.value,int(task.offered),task.reason))
            db.execute("UPDATE task_store_meta SET revision=revision+1 WHERE id=1")

    def load_active(self):
        with self._connect() as db:
            rows = db.execute("""SELECT task_id,created_at,due_at,expires_at,status,offered,reason
                FROM deferred_tasks WHERE status IN (?,?) ORDER BY created_at,task_id""",
                (Status.PENDING.value, Status.READY.value)).fetchall()
        return [self._row_to_task(row) for row in rows]

    def load_state(self):
        """Return active tasks and revision/clock metadata from one read snapshot."""
        with self._connect() as db:
            meta = db.execute(
                "SELECT revision,last_now FROM task_store_meta WHERE id=1"
            ).fetchone()
            rows = db.execute("""SELECT task_id,created_at,due_at,expires_at,status,offered,reason
                FROM deferred_tasks WHERE status IN (?,?) ORDER BY created_at,task_id""",
                (Status.PENDING.value, Status.READY.value)).fetchall()
        if meta is None:
            raise RuntimeError("task store metadata is missing")
        return [self._row_to_task(row) for row in rows], int(meta[0]), int(meta[1])

    def get_task(self, task_id):
        """Read a task in any lifecycle state; terminal IDs remain idempotency keys."""
        with self._connect() as db:
            row = db.execute("""SELECT task_id,created_at,due_at,expires_at,status,offered,reason
                FROM deferred_tasks WHERE task_id=?""", (task_id,)).fetchone()
        return None if row is None else self._row_to_task(row)

    def commit(self, expected_revision, now, *, inserts=(), updates=()):
        """Atomically persist one engine operation with revision and state CAS checks."""
        if isinstance(now, bool) or not isinstance(now, int) or now < 0:
            raise ValueError("now must be a non-negative UTC epoch-second integer")
        inserts = tuple(inserts)
        updates = tuple(updates)
        all_ids = [task.task_id for task in inserts + updates]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("a task may appear only once in a commit")
        for task in inserts + updates:
            self._validate_task(task)
        for task in inserts:
            if task.status is not Status.PENDING or task.offered:
                raise ValueError("new tasks must start pending and unoffered")

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            meta = db.execute(
                "SELECT revision,last_now FROM task_store_meta WHERE id=1"
            ).fetchone()
            if meta is None:
                raise RuntimeError("task store metadata is missing")
            revision, last_now = int(meta[0]), int(meta[1])
            if revision != expected_revision:
                raise TaskStoreConflict(
                    "stale task-store revision; call refresh() before retrying"
                )
            if now < last_now:
                raise ValueError("clock moved backwards relative to persisted task-store time")

            for task in inserts:
                try:
                    db.execute("""INSERT INTO deferred_tasks
                        (task_id,created_at,due_at,expires_at,status,offered,reason)
                        VALUES(?,?,?,?,?,?,?)""",
                        (task.task_id, task.created_at, task.due_at, task.expires_at,
                         task.status.value, int(task.offered), task.reason))
                except sqlite3.IntegrityError as exc:
                    raise TaskStoreConflict("task_id already exists") from exc

            allowed = {
                Status.PENDING: {
                    Status.READY, Status.RESOLVED, Status.EXPIRED, Status.CANCELLED
                },
                Status.READY: {
                    Status.RESOLVED, Status.EXPIRED, Status.CANCELLED
                },
            }
            for task in updates:
                row = db.execute(
                    "SELECT status FROM deferred_tasks WHERE task_id=?",
                    (task.task_id,)
                ).fetchone()
                if row is None:
                    raise TaskStoreConflict("task disappeared before transition")
                old_status = Status(row[0])
                if task.status not in allowed.get(old_status, set()):
                    raise TaskStoreConflict("invalid or stale task lifecycle transition")
                cursor = db.execute("""UPDATE deferred_tasks
                    SET created_at=?,due_at=?,expires_at=?,status=?,offered=?,reason=?
                    WHERE task_id=? AND status=?""",
                    (task.created_at, task.due_at, task.expires_at, task.status.value,
                     int(task.offered), task.reason, task.task_id, old_status.value))
                if cursor.rowcount != 1:
                    raise TaskStoreConflict("task transition lost a race")

            next_revision = revision + 1
            cursor = db.execute("""UPDATE task_store_meta
                SET revision=?,last_now=? WHERE id=1 AND revision=?""",
                (next_revision, now, revision))
            if cursor.rowcount != 1:
                raise TaskStoreConflict("task-store revision changed during commit")
        return next_revision

    def update_status(self, task_id, status: Status, reason=None, offered=None):
        offered_value = None if offered is None else int(offered)
        with self._connect() as db:
            cursor = db.execute("""UPDATE deferred_tasks
                SET status=?,reason=?,offered=COALESCE(?,offered)
                WHERE task_id=? AND status IN (?,?)""",
                (status.value, reason, offered_value, task_id,
                 Status.PENDING.value, Status.READY.value))
            if cursor.rowcount == 1:
                db.execute("UPDATE task_store_meta SET revision=revision+1 WHERE id=1")
                return True
            return False

    def close_checkpoint(self):
        with self._connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
