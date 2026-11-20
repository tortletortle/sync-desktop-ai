import unittest
from adaptive import Adaptive
from sage import Context, Action
class Test(unittest.TestCase):
    def test_permission(self):
        a=Adaptive(); a.choose(Context(1,1,1),1,0); self.assertTrue(a.pending); self.assertEqual(a.choose(Context(1,0,1,False),1,1)[0],Action.QUIET); self.assertFalse(a.pending)
    def test_expiry(self):
        a=Adaptive(); self.assertEqual(a.choose(Context(1,1,1),1,0)[0],Action.DEFER); a.choose(Context(0,0,1),2,4); self.assertNotIn(1,a.pending)
    def test_feedback(self):
        a=Adaptive(); _,token=a.choose(Context(1,0,1),1,0); a.feedback(token,.5); self.assertEqual(a.stats[token],(1,.5))
if __name__=='__main__': unittest.main()
