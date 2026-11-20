from dataclasses import dataclass
from enum import Enum
class Action(str, Enum):
    QUIET='quiet'; HINT='hint'; HELP='help'; DEFER='defer'
@dataclass(frozen=True)
class Context:
    need: float
    interruption: float
    confidence: float
    authorized: bool=True
    idle: bool=False

def decide(s: Context):
    if not s.authorized: return Action.QUIET
    b=s.need*s.confidence
    scores={Action.QUIET:0, Action.HINT:.55*b-.32*s.interruption-.10, Action.HELP:b-.95*s.interruption-.20, Action.DEFER:.35*b-.12 if not s.idle else -.2}
    return max(scores,key=scores.get)

@dataclass
class Life:
    energy: float=80
    curiosity: float=70
    def tick(self, idle: bool):
        if self.energy<25 or (idle and self.energy<60):
            action='sleep'; self.energy=min(100,self.energy+8)
        elif idle and self.curiosity>50:
            action='explore'; self.energy-=4; self.curiosity-=5
        else:
            action='read'; self.energy=max(0,self.energy-1); self.curiosity=min(100,self.curiosity+2)
        return action
