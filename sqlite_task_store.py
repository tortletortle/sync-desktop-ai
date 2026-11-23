"""SQLite persistence for TemporalTaskEngine; stores opaque task metadata only."""
import sqlite3
from pathlib import Path
from temporal_engine import DeferredTask, Status

class SQLiteTaskStore:
    def __init__(self, path):
        self.path=str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
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

    def _connect(self):
        db=sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def save(self, task: DeferredTask):
        if not task.task_id or task.expires_at <= task.due_at or task.created_at > task.due_at:
            raise ValueError("invalid task record")
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

    def load_active(self):
        with self._connect() as db:
            rows=db.execute("""SELECT task_id,created_at,due_at,expires_at,status,offered,reason
                FROM deferred_tasks WHERE status IN (?,?) ORDER BY created_at,task_id""",
                (Status.PENDING.value,Status.READY.value)).fetchall()
        return [DeferredTask(row[0],row[1],row[2],row[3],Status(row[4]),bool(row[5]),row[6]) for row in rows]

    def update_status(self, task_id, status: Status, reason=None, offered=None):
        with self._connect() as db:
            row=db.execute("SELECT status,offered FROM deferred_tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None or Status(row[0]) not in (Status.PENDING,Status.READY):
                return False
            db.execute("""UPDATE deferred_tasks SET status=?,reason=?,offered=?
                WHERE task_id=?""",
                (status.value,reason,row[1] if offered is None else int(offered),task_id))
            return True

    def close_checkpoint(self):
        with self._connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
