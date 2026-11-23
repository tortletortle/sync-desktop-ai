import unittest
from temporal_engine import TemporalTaskEngine, Status

class TemporalTests(unittest.TestCase):
    def test_schedule_and_due(self):
        e=TemporalTaskEngine(); e.schedule("a",0,3,10)
        self.assertEqual(e.poll(2,authorized=True,dnd=False,condition_exists={"a":True},safe_to_interrupt=True),[])
        self.assertEqual(e.poll(3,authorized=True,dnd=False,condition_exists={"a":True},safe_to_interrupt=True),["a"])
        self.assertEqual(e.tasks["a"].status,Status.READY)
    def test_ready_offered_once(self):
        e=TemporalTaskEngine(); e.schedule("a",0,0,10)
        args=dict(authorized=True,dnd=False,condition_exists={"a":True},safe_to_interrupt=True)
        self.assertEqual(e.poll(1,**args),["a"])
        self.assertEqual(e.poll(2,**args),[])
    def test_resolved_before_delivery(self):
        e=TemporalTaskEngine(); e.schedule("a",0,0,10)
        self.assertEqual(e.poll(1,authorized=True,dnd=False,condition_exists={"a":False},safe_to_interrupt=True),[])
        self.assertEqual(e.tasks["a"].status,Status.RESOLVED)
    def test_expiry(self):
        e=TemporalTaskEngine(); e.schedule("a",0,0,2)
        e.poll(2,authorized=True,dnd=False,condition_exists={"a":True},safe_to_interrupt=True)
        self.assertEqual(e.tasks["a"].status,Status.EXPIRED)
    def test_permission_revocation(self):
        e=TemporalTaskEngine(); e.schedule("a",0,1,10)
        e.poll(1,authorized=False,dnd=False,condition_exists={"a":True},safe_to_interrupt=True)
        self.assertEqual(e.tasks["a"].status,Status.CANCELLED)
    def test_dnd(self):
        e=TemporalTaskEngine(); e.schedule("a",0,1,10)
        e.poll(1,authorized=True,dnd=True,condition_exists={"a":True},safe_to_interrupt=True)
        self.assertEqual(e.tasks["a"].status,Status.CANCELLED)
    def test_duplicate_is_idempotent(self):
        e=TemporalTaskEngine(); a=e.schedule("a",0,5,10); b=e.schedule("a",1,0,1)
        self.assertEqual(a.due_at,b.due_at); self.assertEqual(b.expires_at,15)
    def test_clock_regression(self):
        e=TemporalTaskEngine(); e.schedule("a",5,1,10)
        with self.assertRaises(ValueError):
            e.poll(4,authorized=True,dnd=False,condition_exists={},safe_to_interrupt=False)
    def test_capacity(self):
        e=TemporalTaskEngine(max_pending=1); e.schedule("a",0,0,5)
        with self.assertRaises(OverflowError): e.schedule("b",1,0,5)
    def test_cancel_idempotent(self):
        e=TemporalTaskEngine(); e.schedule("a",0,0,5)
        self.assertTrue(e.cancel("a","user",1)); self.assertFalse(e.cancel("a","again",2))
    def test_unsafe_defers_delivery(self):
        e=TemporalTaskEngine(); e.schedule("a",0,0,5)
        self.assertEqual(e.poll(1,authorized=True,dnd=False,condition_exists={"a":True},safe_to_interrupt=False),[])
        self.assertEqual(e.tasks["a"].status,Status.PENDING)
if __name__=="__main__": unittest.main()
