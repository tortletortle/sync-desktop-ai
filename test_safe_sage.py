import unittest
from sage import Context, Action
from safe_sage import SafeSAGE
class Tests(unittest.TestCase):
    def test_permission(self):
        a=SafeSAGE(); self.assertEqual(a.choose(Context(1,0,1,False),1,0),(Action.QUIET,None))
    def test_dnd(self):
        a=SafeSAGE(); self.assertEqual(a.choose(Context(1,0,1),1,0,dnd=True),(Action.QUIET,None))
    def test_budget(self):
        a=SafeSAGE(budget=0); self.assertEqual(a.choose(Context(1,0,1),1,0),(Action.QUIET,None))
    def test_risk(self):
        a=SafeSAGE()
        for t in range(100):
            x,_=a.choose(Context(1,.7,1),t,t)
            self.assertNotIn(x,(Action.HINT,Action.HELP))
    def test_resolved(self):
        a=SafeSAGE(); self.assertEqual(a.choose(Context(1,0,1),1,0,resolved=True),(Action.QUIET,None))
    def test_rolling_budget(self):
        a=SafeSAGE(budget=2,window=10)
        times=[]
        for t in range(100):
            x,_=a.choose(Context(1,0,1),t,t)
            if x in (Action.HINT,Action.HELP): times.append(t)
            self.assertLessEqual(sum(t-10<v<=t for v in times),2)
        self.assertGreater(len(times),2)
    def test_repeat(self):
        a=SafeSAGE(budget=10,window=20)
        times=[t for t in range(20) if a.choose(Context(1,0,1),1,t)[0] in (Action.HINT,Action.HELP)]
        self.assertEqual(len(times),1)
if __name__=="__main__": unittest.main()
