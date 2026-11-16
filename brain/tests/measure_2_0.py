"""2.0: the numbers the plan is judged by, measured on the host build of the core in a simulated street (NOT in the game).
    python3 brain/tests/measure_2_0.py
Eight guards, low walls around, the mod walking the men (the simulation moves a man to the next point of his way at his pace and
stops him at walls). Three minutes: CJ walks a block with stops (60 s), stands (60 s), is attacked by two gunmen (60 s).
One sample a second for every guard - the same counts as mods/hcbrain_summary.txt makes in the game."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

SQ, M4, AK, GANG = HCB_ROLE_SQUAD, 31, 30, 7
EIGHT = ((1.2, -0.8), (-1.8, 3.5), (-9., 11.), (-1.6, -2.2), (-12., -8.), (12., -8.), (9., 11.), (16., -7.))
LOW = [(10., -13., 10., -9.), (10., 9., 10., 13.), (-6., -14., -6., -10.), (-6., 10., -6., 14.), (13., -5., 13., -3.), (13., 3., 13., 5.), (-9., -17., -9., -13.), (-9., 13., -9., 17.),
       (30., -6., 30., 6.), (44., 8., 52., 8.), (44., -8., 52., -8.)]
sc = Scene(); sc.low_walls = list(LOW); sc.walls = [(20., 14., 40., 14.), (20., -14., 40., -14.)]
team = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(EIGHT)]
sc.walk_posts = True
n = dict(samples=0, still=0, far8=0, far20=0, stuck=0, failed=0, calm=0, sprint=0, changes=0, near=0, near_n=0, sees=0, sees_n=0)
last_act, gang = {}, []
ROUTE = [(40., 0.), (40., 30.), (0., 30.), (0., 0.)]
leg = 0

for sec in range(180):
    for tick in range(10):
        cj = sc.cj
        if sec < 60 and sec % 15 < 11:                              # walking the block, a stop of 4 s in every 15
            tx, ty = ROUTE[leg]; dx, dy = tx - cj['pos'][0], ty - cj['pos'][1]; d = math.hypot(dx, dy)
            if d < 1.: leg = (leg + 1) % 4
            cj['vel'] = [2.5 * dx / max(d, .01), 2.5 * dy / max(d, .01), 0.]
        else:
            cj['vel'] = [0., 0., 0.]
        if sec == 120 and tick == 0:
            gang = [sc.ped(cj['pos'][0] + 34, cj['pos'][1] + 3, pedtype=GANG, weapon=AK), sc.ped(cj['pos'][0] + 30, cj['pos'][1] - 9, pedtype=GANG, weapon=AK)]
        if sec >= 120 and tick == 0 and sec % 2 == 0:
            for g in gang: sc.shot(g, (cj['pos'][0], cj['pos'][1], 1.), dst=1)
        sc.step(1)
    out, cjp, still = sc.last_out, sc.cj['pos'], math.hypot(*sc.cj['vel'][:2]) < .5
    near = 0
    for who, p in sc.posts.items():
        me = sc.peds[who]['pos']; d = math.dist(me[:2], (p.at.x, p.at.y))
        n['samples'] += 1
        if still: n['still'] += 1; n['far8'] += d > 8; n['far20'] += d > 20
        n['stuck'] += p.stuck; n['failed'] += p.phase == HCB_PH_FAILED
        if out.alert < HCB_ALERT_THREAT: n['calm'] += 1; n['sprint'] += p.act == HCB_ACT_SPRINT
        if who in last_act and last_act[who] != p.act: n['changes'] += 1
        last_act[who] = p.act
        near += math.dist(me[:2], cjp[:2]) < 4.
        if sec >= 135 and p.job in (HCB_ROLE_POINT, HCB_ROLE_POINT2, HCB_ROLE_REAR, HCB_ROLE_REAR2) and d < 1.5:
            n['sees_n'] += 1
            n['sees'] += (not sc.blocked(me, cjp, low_too=False)) and any(not sc.blocked(me, sc.peds[g]['pos'], low_too=False) for g in gang)
    if out.umode == HCB_UMODE_PROTECT and len(sc.posts) >= 7: n['near'] += near; n['near_n'] += 1
pc = lambda a, b: '%d %%' % round(100. * a / b) if b else '-'
text = '\n'.join([
    'Simulated street, 180 s, eight guards, the mod walking them (host build of the core; NOT the game):',
    'guard farther than 8 m from his post while CJ stands: %s   (0.9 in the game: 65 %%; goal 15 %% or less)' % pc(n['far8'], n['still']),
    'guard farther than 20 m from his post while CJ stands: %s   (0.9 in the game: 45 %%)' % pc(n['far20'], n['still']),
    'STUCK: %s   (0.9 in the game: 21 %%; goal 5 %% or less)' % pc(n['stuck'], n['samples']),
    'gave his post up for a while (FAILED): %s' % pc(n['failed'], n['samples']),
    'sprinting with no threat: %s   (0.9 in the game: 50 %%; goal 10 %% or less)' % pc(n['sprint'], n['calm']),
    'changes of action per guard per minute: %.1f   (goal 6 or less)' % (n['changes'] * 60. / n['samples']),
    'guards within 4 m of CJ in PROTECT, average: %.1f   (0.9 in the game: 6 of 8; goal 3)' % (n['near'] / max(1, n['near_n'])),
    'an outer man at his place sees both CJ and an attacker: %s   (goal 80 %% or more)' % pc(n['sees'], n['sees_n'])])
(hcb_py.OUT / 'brain_measure_2_0.txt').write_text(text + '\n'); print(text)
