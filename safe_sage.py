"""Experimental constrained policy; risk proxy is not a calibrated probability."""
from collections import deque
from sage import Action
from adaptive import Adaptive
import math

class SafeSAGE:
    def __init__(self, seed=0, budget=3, window=20):
        if budget<0 or window<=0: raise ValueError("invalid budget")
        self.agent=Adaptive(seed); self.budget=budget; self.window=window
        self.sent=deque(); self.last=-1; self.last_task={}
    def choose(self,s,task,now,*,dnd=False,resolved=False):
        if now<self.last: raise ValueError("nonmonotonic clock")
        self.last=now
        while self.sent and self.sent[0]<=now-self.window: self.sent.popleft()
        self.last_task={k:v for k,v in self.last_task.items() if v>now-self.window}
        if not s.authorized or dnd:
            self.agent.pending.clear(); return Action.QUIET,None
        if resolved:
            self.agent.pending.pop(task,None); return Action.QUIET,None
        if not all(math.isfinite(v) and 0<=v<=1 for v in (s.need,s.confidence,s.interruption)):
            return Action.QUIET,None
        if len(self.sent)>=self.budget or task in self.last_task:
            return Action.QUIET,None
        a,token=self.agent.choose(s,task,now)
        if a in (Action.HINT,Action.HELP):
            if s.confidence<.65 or s.need*s.confidence<.35 or s.interruption>(.35 if a==Action.HELP else .6):
                return Action.QUIET,None
            self.sent.append(now); self.last_task[task]=now
        return a,token
    def feedback(self,token,reward):
        self.agent.feedback(token,reward)
