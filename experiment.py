import random, statistics, math
from sage import Context, Action, decide
from adaptive import Adaptive

def trial(seed, regime):
    r=random.Random(seed); agent=Adaptive(seed+10000); scores=[0.,0.,0.]; bad=[0,0,0]; hits=[0,0,0]; counts=[0,0,0]; task=0
    pref=r.uniform(.55,1.45)
    for t in range(1000):
        if t%5==0: task+=1; need=r.random(); authorized=r.random()>.1
        cost=r.random(); conf=r.uniform(.5,1); s=Context(need,cost,conf,authorized,cost<.25)
        p=need*conf if regime=='aligned' else min(1,max(0,.15+.65*need+.15*(t%5==4)))
        useful=r.random()<p
        a,token=agent.choose(s,task,t)
        arms=[Action.HELP if authorized and need>.7 else Action.QUIET,decide(s),a]
        for i,x in enumerate(arms):
            active=x in (Action.HELP,Action.HINT); strength=1 if x==Action.HELP else .55
            reward=strength*(int(useful)-pref*cost)-.08 if active else 0
            scores[i]+=reward; bad[i]+=active and not useful; hits[i]+=active and useful; counts[i]+=active
            if i==2: agent.feedback(token,reward)
    return [x/1000 for x in scores],bad,hits,counts
if __name__=='__main__':
    for regime in ['aligned','alternate']:
        rows=[trial(s,regime) for s in range(100)]
        print(regime)
        for i,name in enumerate(['rule','sage','adaptive']):
            print(name, 'reward',round(statistics.mean(x[0][i] for x in rows),5),'unwanted',sum(x[1][i] for x in rows),'useful',sum(x[2][i] for x in rows))
        d=[x[0][2]-x[0][1] for x in rows]; m=statistics.mean(d); e=1.984*statistics.stdev(d)/math.sqrt(len(d)); print('paired adaptive-sage',round(m,5), '95% CI',round(m-e,5),round(m+e,5))
