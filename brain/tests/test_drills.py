"""1.1: tokens (rifles per target, magazines one at a time, men on the move), corners and doorways - on the host build of the core.
    python3 brain/tests/test_drills.py"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


SQ, M4, AK, GANG = HCB_ROLE_SQUAD, 31, 30, 7
EIGHT = ((1.2, -0.8), (-1.8, 3.5), (-9., 11.), (-1.6, -2.2), (-12., -8.), (12., -8.), (9., 11.), (16., -7.))
INNER = (HCB_ROLE_LEAD, HCB_ROLE_CLOSE, HCB_ROLE_CLOSE2)


def d2(a, b):
    return math.dist(a[:2], b[:2])


def team8(sc, places=EIGHT):
    t = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(places)]
    sc.walk_posts = True
    return t


# ------------------------------------------------------------------ a token: no more than three of the outer men move at a time in a fight
sc = Scene(); team = team8(sc, tuple((x * .3, y * .3) for x, y in EIGHT)); sc.step(5)       # all eight in a heap round CJ when it starts
g = sc.ped(34, 0, pedtype=GANG, weapon=AK, face=(-1., 0.)); sc.step(2)
most, waited, arrived_all = 0, 0, None
for k in range(300):
    if k % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    outer = [p for p in sc.posts.values() if p.job not in INNER]
    moving = sum(1 for p in outer if p.phase == HCB_PH_MOVING and p.act not in (HCB_ACT_HOLD,))
    most = max(most, moving); waited += sum(1 for p in outer if p.why == HCB_WHY2_WAIT_TURN and p.phase == HCB_PH_CHOSEN)
    if arrived_all is None and k > 20 and all(p.phase >= HCB_PH_ARRIVED for p in outer): arrived_all = k / 10.
assert most <= 3 and waited > 0, ('never more than three of the outer men on the move; somebody waited for his turn', most, waited)
assert arrived_all is not None, 'and all of them are in place in the end'
passed('Token "movers": the fight starts with everybody in a heap - never more than three of the outer men run at once (the rest hold and wait their turn), and all are in place after %.0f s' % arrived_all)

# ------------------------------------------------------------------ a token: so many rifles on one man
def rifles(tune=None):
    sc = Scene()
    if tune: tune(sc.brain.cfg)
    team = team8(sc); sc.step(20)
    g = sc.ped(22, 0, pedtype=GANG, weapon=AK, face=(-1., 0.)); sc.step(2)
    worst = 0
    for k in range(120):
        if k % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
        sc.step(1)
        worst = max(worst, sum(1 for o in sc.orders.values() if o.fire and o.target == g))
    return worst
def two(c): c.shooters_per_target = 2
w3, w2 = rifles(), rifles(two)
assert w3 == 3 and w2 == 2, (w3, w2)
passed('Token "rifles": eight men and one shooter - three fire at him, the rest keep their sectors; with shooters_per_target = 2 in the settings, two')

# ------------------------------------------------------------------ a token: magazines are changed one man at a time
sc = Scene(); team = team8(sc); sc.step(20)
gs = [sc.ped(22, y, pedtype=GANG, weapon=AK, face=(-1., 0.)) for y in (-6., 0., 6.)]; sc.step(2)
sc.clips = {w: 30 for w in team}
both, turns, firing_meanwhile = 0, [], 0
for k in range(240):
    if k % 9 == 0:
        for g in gs: sc.shot(g, (0., 0., 1.), dst=1)
    if k == 40: sc.clips = {w: 3 for w in team}                       # everybody's magazine runs low at the same moment
    sc.step(1)
    rel = [o.who for o in sc.orders.values() if o.hold == HCB_HOLD_RELOAD]
    both = max(both, len(rel))
    if rel:
        if not turns or turns[-1] != rel[0]: turns.append(rel[0])
        firing_meanwhile += any(o.fire for o in sc.orders.values())
        sc.clips[rel[0]] = 30                                         # (the adapter changes his magazine)
assert both == 1 and len(set(turns)) >= 3 and firing_meanwhile > 0, ('one at a time, several men in turn, the others firing meanwhile', both, len(set(turns)), firing_meanwhile)
passed('Token "magazines": every magazine runs low at the same moment - the men change them one at a time (%d turns), the others fire on meanwhile' % len(turns))

# ------------------------------------------------------------------ a blind corner: stop short of it, look round it, go on - only when there is a threat
def corner_run(threat):
    sc = Scene(); sc.walls = [(-20., -10., 4., -10.), (4., -10., 4., -22.)]          # an L: the way from the south-west goes round its corner
    team = [sc.our(-6., -16., SQ, weapon=M4)]; sc.walk_posts = True
    if threat: g = sc.ped(0, 40, pedtype=GANG, weapon=AK, face=(0., -1.))
    stops, stood, looked, got = 0, 0, False, None
    for k in range(500):
        if threat and k % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
        before = list(sc.peds[team[0]]['pos']); sc.step(1); p = sc.posts[team[0]]
        if p.why == HCB_WHY2_CORNER and p.act == HCB_ACT_HOLD:
            stops += 1; stood += d2(before, sc.peds[team[0]]['pos']) < 0.05
            looked = looked or (d2((p.look.x, p.look.y), before) > 1.0 and sc.blocked(tuple(before[:2]), (p.look.x, p.look.y), low_too=False))   # his weapon on what lies beyond the corner (a point he cannot see yet)
        if got is None and d2(sc.peds[team[0]]['pos'], (p.at.x, p.at.y)) < 1.5 and p.at.y > -5: got = k / 10.
    return stops, stood, looked, got
stops, stood, looked, got = corner_run(True)
assert 6 <= stops <= 30 and stood >= stops - 3 and looked and got is not None, ('0.8 s short of the corner, standing, looking round it; then on', stops, stood, looked, got)
calm = corner_run(False)
assert calm[0] == 0 and calm[3] is not None, ('with nobody to fear he walks round the corner without stopping', calm)
passed('A blind corner under threat: the man stops short of it for %.1f s with his weapon on the way round it, then goes on and arrives; in peace he just walks round' % (stops / 10.))

# ------------------------------------------------------------------ a doorway: one man at a time, nobody stands in it
sc = Scene(); sc.walls = [(-20., -10., 0., -10.), (1., -10., 20., -10.)]              # a wall with a gap one metre wide
team = [sc.our(x, -16., SQ + k, weapon=M4) for k, x in enumerate((-2., 0.5, 3.))]; sc.walk_posts = True
g = sc.ped(0, 40, pedtype=GANG, weapon=AK, face=(0., -1.))
two_in, waited, stood_in, last_in = 0, 0, 0, {}
def in_gap(p): return -0.3 <= p[0] <= 1.3 and -10.8 <= p[1] <= -9.2
for k in range(400):
    if k % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    ins = [w for w in team if in_gap(sc.peds[w]['pos'])]
    two_in = max(two_in, len(ins)); waited += sum(1 for p in sc.posts.values() if p.why == HCB_WHY2_DOORWAY and p.act == HCB_ACT_HOLD)
    for w in team:
        last_in[w] = last_in.get(w, 0) + 1 if w in ins else 0
        stood_in = max(stood_in, last_in[w])
through = [w for w in team if sc.peds[w]['pos'][1] > -9.]
assert len(through) == 3 and two_in <= 1 and waited > 0 and stood_in <= 12, ('all three through, one at a time, somebody waited, nobody stood in it over a second', len(through), two_in, waited, stood_in)
passed('A doorway (a gap one metre wide) under threat: three men go through one at a time - the next one waits short of it - and nobody stands in it longer than %.1f s' % (stood_in / 10.))

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_drills_tests.txt').write_text(text)
print(text)
