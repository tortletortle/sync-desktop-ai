import math, random
from sage import Action

class Adaptive:
    def __init__(self, seed=0, ttl=3):
        self.r=random.Random(seed); self.ttl=ttl; self.pending={}; self.stats={}
    def choose(self, s, task, now):
        self.pending={k:v for k,v in self.pending.items() if v>=now}
        if not s.authorized:
            self.pending.clear(); return Action.QUIET, None
        key=(s.need>=.65,s.interruption>=.5,s.confidence>=.75,task in self.pending)
        if not s.idle and s.need>=.75 and s.interruption>=.75:
            self.pending.setdefault(task,now+self.ttl)
            return Action.DEFER,None
        arms=[Action.QUIET,Action.HINT,Action.HELP]
        if self.r.random()<.08: a=self.r.choice(arms)
        else:
            prior=[0,.55*s.need*s.confidence-.32*s.interruption-.1,s.need*s.confidence-.95*s.interruption-.2]
            def score(i):
                n,total=self.stats.get((key,arms[i]),(0,0)); return (total+4*prior[i])/(n+4)
            a=arms[max(range(3),key=score)]
        if a!=Action.QUIET: self.pending.pop(task,None)
        return a,(key,a)
    def feedback(self, token, reward):
        if token is None or not math.isfinite(reward): return
        n,total=self.stats.get(token,(0,0)); self.stats[token]=(n+1,total+max(-1,min(1,reward)))
