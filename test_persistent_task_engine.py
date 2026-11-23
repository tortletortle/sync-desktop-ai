import tempfile
import unittest
from pathlib import Path

from persistent_task_engine import PersistentTemporalTaskEngine
from sqlite_task_store import SQLiteTaskStore, TaskStoreConflict
from temporal_engine import DeferredTask, Status


class PersistentEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "tasks.sqlite3"
        self.store = SQLiteTaskStore(self.path)
        self.engine = PersistentTemporalTaskEngine(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def reopen(self, max_pending=100):
        return PersistentTemporalTaskEngine(SQLiteTaskStore(self.path), max_pending)

    def test_pending_and_ready_survive_restart_without_redelivery(self):
        self.engine.schedule("opaque-a", 100, 5, 20)
        self.assertEqual(
            self.engine.poll(
                105, authorized=True, dnd=False,
                condition_exists={"opaque-a": True}, safe_to_interrupt=True
            ),
            ["opaque-a"],
        )
        restarted = self.reopen()
        self.assertIn("opaque-a", restarted.tasks)
        self.assertEqual(
            restarted.poll(
                106, authorized=True, dnd=False,
                condition_exists={"opaque-a": True}, safe_to_interrupt=True
            ),
            [],
        )
        persisted = self.store.get_task("opaque-a")
        self.assertEqual(persisted.status, Status.READY)
        self.assertTrue(persisted.offered)

    def test_duplicate_schedule_does_not_reset_deadline(self):
        first = self.engine.schedule("opaque-a", 100, 10, 20)
        second = self.engine.schedule("opaque-a", 101, 0, 1)
        self.assertEqual(first.due_at, second.due_at)
        self.assertEqual(first.expires_at, second.expires_at)

    def test_terminal_task_id_is_not_resurrected(self):
        self.engine.schedule("opaque-a", 100, 0, 20)
        self.assertTrue(self.engine.cancel("opaque-a", "user cancelled", 101))
        returned = self.engine.schedule("opaque-a", 102, 0, 20)
        self.assertEqual(returned.status, Status.CANCELLED)
        self.assertNotIn("opaque-a", self.engine.tasks)
        self.assertEqual(self.store.get_task("opaque-a").status, Status.CANCELLED)

    def test_permission_revocation_is_persisted(self):
        self.engine.schedule("opaque-a", 100, 0, 20)
        self.engine.poll(
            101, authorized=False, dnd=False,
            condition_exists={"opaque-a": True}, safe_to_interrupt=True
        )
        restarted = self.reopen()
        self.assertNotIn("opaque-a", restarted.tasks)
        self.assertEqual(self.store.get_task("opaque-a").status, Status.CANCELLED)
        self.assertEqual(self.store.get_task("opaque-a").reason, "permission revoked")

    def test_do_not_disturb_cancels_persisted_tasks(self):
        self.engine.schedule("opaque-a", 100, 0, 20)
        self.engine.poll(
            101, authorized=True, dnd=True,
            condition_exists={"opaque-a": True}, safe_to_interrupt=True
        )
        self.assertEqual(self.store.get_task("opaque-a").reason, "do not disturb")
        self.assertEqual(self.reopen().tasks, {})

    def test_expiry_is_persisted(self):
        self.engine.schedule("opaque-a", 100, 1, 2)
        self.engine.poll(
            103, authorized=True, dnd=False,
            condition_exists={"opaque-a": True}, safe_to_interrupt=True
        )
        self.assertEqual(self.store.get_task("opaque-a").status, Status.EXPIRED)
        self.assertEqual(self.reopen().tasks, {})

    def test_unsafe_interruption_remains_pending_after_restart(self):
        self.engine.schedule("opaque-a", 100, 1, 20)
        self.assertEqual(
            self.engine.poll(
                105, authorized=True, dnd=False,
                condition_exists={"opaque-a": True}, safe_to_interrupt=False
            ),
            [],
        )
        restarted = self.reopen()
        self.assertEqual(
            restarted.poll(
                106, authorized=True, dnd=False,
                condition_exists={"opaque-a": True}, safe_to_interrupt=True
            ),
            ["opaque-a"],
        )

    def test_persisted_clock_rejects_regression_after_restart(self):
        self.engine.schedule("opaque-a", 100, 0, 20)
        restarted = self.reopen()
        with self.assertRaises(ValueError):
            restarted.cancel("opaque-a", "late clock", 99)

    def test_stale_writer_must_refresh_before_retry(self):
        second = self.reopen()
        self.engine.schedule("a", 100, 0, 20)
        with self.assertRaises(TaskStoreConflict):
            second.schedule("b", 100, 0, 20)
        second.refresh()
        second.schedule("b", 101, 0, 20)
        self.assertEqual(set(second.tasks), {"a", "b"})

    def test_legacy_store_write_invalidates_engine_revision(self):
        self.store.save(DeferredTask("external", 100, 100, 110))
        with self.assertRaises(TaskStoreConflict):
            self.engine.schedule("local", 101, 0, 20)
        self.engine.refresh()
        self.assertIn("external", self.engine.tasks)

    def test_failed_batch_rolls_back_all_rows_and_revision(self):
        missing = DeferredTask(
            "missing", 100, 100, 110, Status.CANCELLED, False, "test"
        )
        with self.assertRaises(TaskStoreConflict):
            self.store.commit(
                0, 100,
                inserts=(DeferredTask("new", 100, 100, 110),),
                updates=(missing,),
            )
        self.assertIsNone(self.store.get_task("new"))
        active, revision, last_now = self.store.load_state()
        self.assertEqual(active, [])
        self.assertEqual(revision, 0)
        self.assertEqual(last_now, -1)

    def test_capacity_is_enforced_after_restart(self):
        limited = PersistentTemporalTaskEngine(self.store, max_pending=1)
        limited.schedule("a", 100, 0, 20)
        restarted = self.reopen(max_pending=1)
        with self.assertRaises(OverflowError):
            restarted.schedule("b", 101, 0, 20)

    def test_invalid_time_and_task_parameters_fail_closed(self):
        with self.assertRaises(ValueError):
            self.engine.schedule("a", True, 0, 10)
        with self.assertRaises(ValueError):
            self.engine.schedule("a", 100, -1, 10)
        with self.assertRaises(ValueError):
            self.engine.schedule("a", 100, 0, 0)


if __name__ == "__main__":
    unittest.main()
