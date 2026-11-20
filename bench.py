import random, statistics
from sage import Context, Action, decide, Life

def run(seed):
    r=random.Random(seed); totals={k:[0,0,0,0] for k in ['random','rule','sage']}
    for _ in range(1000):
        need=r.random(); cost=r.random(); confidence=r.uniform(.5,1); auth=r.random()>.1; idle=cost<.25
        s=Context(need,cost,confidence,auth,idle)
        # Synthetic latent outcome, not evidence of real user benefit.
        useful=r.random()<need*confidence
        actions={'random':r.choice(list(Action)) if auth else Action.QUIET,'rule':Action.HELP if auth and need>.7 else Action.QUIET,'sage':decide(s)}
        for name,a in actions.items():
            active=a in (Action.HINT,Action.HELP); strength=1 if a==Action.HELP else .55
            t=totals[name]; t[0]+=active and useful; t[1]+=active and not useful; t[2]+=active; t[3]+=strength*(int(useful)-cost) if active else 0
    return totals
if __name__=='__main__':
    assert decide(Context(1,0,1,False))==Action.QUIET
    assert decide(Context(1,0,1))==Action.HELP
    assert decide(Context(0,1,1))==Action.QUIET
    l=Life(10); assert l.tick(True)=='sleep' and l.energy==18
    runs=[run(i) for i in range(20)]
    for k in runs[0]:
        h,f,n,u=[sum(x[k][j] for x in runs) for j in range(4)]
        print(f'{k}: useful={h}, unwanted={f}, active={n}, useful_rate={h/max(n,1):.3f}, score/event={u/20000:.4f}')
