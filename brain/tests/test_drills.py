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
    outer = [p for p in sc.posts.values() if p.job not in INNER and p.job != HCB_ROLE_MARKSMAN]   # (1.3: the marksman goes his own way, no token)
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

# ------------------------------------------------------------------ what the half-hour run found (soak_30min.py), each as a drill of its own
# four men to the far side of a long wall with one gap two metres wide: all through, nobody gives up, the gap is never "shut" by those who jostled in it
sc = Scene(); sc.walls = [(-40., 25., -8., 25.), (-6., 25., 40., 25.)]
sc.cj['pos'] = [9., 30., 1.]
team = [sc.our(x, 23.5, SQ + k, weapon=M4) for k, x in enumerate((-12., -10., -4., -2.))]; sc.walk_posts = True
g = sc.ped(9., 70., pedtype=GANG, weapon=AK, face=(0., -1.))
failed, t_all = 0, None
for k in range(450):
    if k % 9 == 0: sc.shot(g, (9., 30., 1.), dst=1)
    sc.step(1)
    failed += sum(1 for p in sc.posts.values() if p.phase == HCB_PH_FAILED)
    if t_all is None and all(sc.peds[w]['pos'][1] > 25.5 for w in team): t_all = k / 10.
assert t_all is not None and t_all < 40 and failed == 0, ('all four through the gap, nobody gave his post up', t_all, failed, [[round(x, 1) for x in sc.peds[w]['pos'][:2]] for w in team])
passed('A gap two metres wide in a long wall, four men from both sides of it: all are through after %.0f s and nobody gives up - men who hold each other up wait a moment (a jam is not an obstacle), and a way is called impossible only by walls the map has seen, never by the marks of men who did not get through' % t_all)

# the commander's place "a step to CJ's right" lies beyond a wall CJ stands beside: it is pulled in to CJ's side
sc = Scene(); sc.walls = [(-20., -1.6, 20., -1.6)]                      # a wall 1.6 m to CJ's right (he faces +x)
team = team8(sc); sc.step(60)
lead = next(p for p in sc.posts.values() if p.job == HCB_ROLE_LEAD)
assert lead.at.y > -1.5 and d2((lead.at.x, lead.at.y), sc.cj['pos']) < 2.0 and lead.phase != HCB_PH_FAILED, ('on CJ\'s side of the wall', (lead.at.x, lead.at.y), lead.phase)
passed('The commander\'s place beyond a wall CJ stands beside is pulled in to CJ\'s side of it (he does not stand 8 s with "no way")')

# two men are never left standing on one spot: "near enough" is not enough when another of ours is within 0.6 m
sc = Scene(); team = team8(sc); sc.step(40)
a_, b_ = team[1], team[3]                                              # the two bodyguards
sc.peds[b_]['pos'] = [sc.peds[a_]['pos'][0] + 0.2, sc.peds[a_]['pos'][1] + 0.1, 1.]
sc.step(40)
assert d2(sc.peds[a_]['pos'], sc.peds[b_]['pos']) > 0.6, ('they step apart to their own places', d2(sc.peds[a_]['pos'], sc.peds[b_]['pos']))
pts = [(p.at.x, p.at.y) for p in sc.posts.values()]
assert all(d2(pts[i], pts[j]) >= 0.79 for i in range(len(pts)) for j in range(i)), 'and no two places are nearer than shoulder width'
passed('Two of ours on one spot: each walks on to his own place (within a step of it is "there" only with nobody on top of him), and no two places are given nearer than 0.8 m')

# a man far outside the brain's map with a wall across the straight way: the game's path network takes him (move 4), not a failure
sc = Scene(); sc.walls = [(-50., -30., -50., 30.)]
team = [sc.our(-58., 0., SQ, weapon=M4)]; sc.walk_posts = True
net, failed, t_in = 0, 0, None
for k in range(400):
    sc.step(1); p = sc.posts[team[0]]
    net += p.move == 4; failed += p.phase == HCB_PH_FAILED
    if t_in is None and d2(sc.peds[team[0]]['pos'], sc.cj['pos']) < 3.: t_in = k / 10.
assert net > 0 and failed == 0 and t_in is not None, ('by the path network to where the map has him, then on - no "failed"', net, failed, t_in)
passed('A man 58 m off, outside the brain\'s map, with a wall across the straight way: after two tries he is sent by the game\'s own path network (move 4, the script walks him) and it is not counted against him; he is at CJ\'s side after %.0f s' % t_in)

# "no way" only by the walls the map has seen: marks left by men who did not get through make a way longer, never impossible
sc = Scene(); sc.walls = [(-40., 10., -1., 10.), (1., 10., 40., 10.)]   # a wall right across the map with one gap two metres wide
team = team8(sc); sc.step(100)                                          # (the whole map is known)
frm, to = (0.5, 6.5, 1.), (0.5, 14.5, 1.)
way0 = hcb_py.nav_way(sc.brain, frm, to, sc.time)
for x in (-0.5, 0.5):
    LIB.hcb_nav_mark(sc.brain.mem, vec(x, 9.5, 1.), vec(x, 10.5, 1.), sc.time, 30000)
    for dx in (-1., 1.): LIB.hcb_nav_mark(sc.brain.mem, vec(x, 9.5, 1.), vec(x + dx, 10.5, 1.), sc.time, 30000)
way1 = hcb_py.nav_way(sc.brain, frm, to, sc.time)
assert way0 and way1 and all(abs(x) < 1.5 for x, y, z in way1 if 9. < y < 11.), ('the gap is marked "nobody got through" on every side - and it is still the way', way0, way1)
passed('Marks on the map ("I did not get through here") never make a way impossible: with the only gap in a wall marked on every side the way still goes through it')

# a man held up by another of ours who is walking in front of him waits - he is not "stuck" and marks nothing
sc = Scene(); team = team8(sc); sc.step(30)
sc.cj['pos'] = [0., 30., 1.]; sc.step(8)                                # CJ is 30 m on: everybody walks after him
jj = {p.job: p for p in sc.posts.values()}
front, rear = jj[HCB_ROLE_LEAD].who, jj[HCB_ROLE_CLOSE2].who
fp = sc.peds[front]['pos']; sc.peds[rear]['pos'] = [fp[0], fp[1] - 1.2, 1.]   # one of them is a step behind another
sc.stuck_men = {front, rear}                                            # the man in front is held (a door, a car) - and so is the one behind him
waits, failed = 0, 0
for k in range(40):
    sc.step(1); p = sc.posts[rear]
    waits += p.why == HCB_WHY2_WAIT_TURN and p.act == HCB_ACT_HOLD
    failed += p.why == HCB_WHY2_NO_PROGRESS
assert waits >= 2 and not failed, ('the man behind waits his turn; it is never "no progress" for him', waits, failed)
passed('A jam: the man behind one of ours who is held up waits (it is not his failure and he marks nothing on the map) for as long as the one in front is still on the move')

# two men within a step of both their places, on one spot: each goes on to his own place
sc = Scene(); team = team8(sc); sc.step(20)
susp = sc.ped(25, 0, pedtype=GANG, weapon=AK, face=(-1., 0.)); sc.step(20)        # a suspect: the bodyguard steps out 1.5 m towards him, the commander is 0.85 m from that
jj = {p.job: p for p in sc.posts.values()}
A_, B_ = jj[HCB_ROLE_CLOSE], jj[HCB_ROLE_CLOSE2]
la, ca = (A_.at.x, A_.at.y), (B_.at.x, B_.at.y)
assert 1.2 < d2(la, ca) < 1.8, (la, ca)                                 # (their places are 1.7 m apart: the middle is "near enough" for both)
mid = [(la[0] + ca[0]) / 2, (la[1] + ca[1]) / 2, 1.]
sc.peds[A_.who]['pos'] = list(mid); sc.peds[B_.who]['pos'] = [mid[0] + 0.05, mid[1], 1.]
sc.step(30)
gap_ = d2(sc.peds[A_.who]['pos'], sc.peds[B_.who]['pos'])
assert gap_ > 0.6, ('both were within a step of their places on ONE spot: each walks on to his own', gap_)
passed('Two men on one spot, each within a step of his own place: they do not stay there - each goes on to his place (%.1f m apart)' % gap_)

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_drills_tests.txt').write_text(text)
print(text)
