import tempfile, unittest
from pathlib import Path
from temporal_engine import DeferredTask, Status
from sqlite_task_store import SQLiteTaskStore

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=SQLiteTaskStore(Path(self.tmp.name)/"tasks.sqlite3")
    def tearDown(self): self.tmp.cleanup()
    def test_round_trip(self):
        t=DeferredTask("opaque-1",1,3,9,Status.PENDING,False,None)
        self.db.save(t); self.assertEqual(self.db.load_active(),[t])
    def test_ready_offered_persists(self):
        t=DeferredTask("a",1,2,8,Status.READY,True,None); self.db.save(t)
        loaded=self.db.load_active()[0]
        self.assertTrue(loaded.offered); self.assertEqual(loaded.status,Status.READY)
    def test_terminal_not_loaded(self):
        self.db.save(DeferredTask("a",1,2,8,Status.CANCELLED,False,"dnd"))
        self.assertEqual(self.db.load_active(),[])
    def test_status_update(self):
        self.db.save(DeferredTask("a",1,2,8))
        self.assertTrue(self.db.update_status("a",Status.CANCELLED,"permission_revoked"))
        self.assertFalse(self.db.update_status("a",Status.RESOLVED,"late"))
        self.assertEqual(self.db.load_active(),[])
    def test_missing_update(self):
        self.assertFalse(self.db.update_status("missing",Status.RESOLVED))
    def test_invalid_record(self):
        with self.assertRaises(ValueError):
            self.db.save(DeferredTask("bad",5,2,1))
    def test_restart_reopen(self):
        self.db.save(DeferredTask("persist",1,3,9))
        reopened=SQLiteTaskStore(Path(self.tmp.name)/"tasks.sqlite3")
        self.assertEqual(reopened.load_active()[0].task_id,"persist")
if __name__=="__main__": unittest.main()
