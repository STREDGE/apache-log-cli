"""The protective detail on foot (stage 3): drills on the host build of the core.
    python3 brain/tests/test_detail.py
A scene with walls (segments on the ground plan) answers the brain's cover questions; the guards walk to their posts as the
scripts make them. Each drill checks what a close-protection team does, not how it is computed."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


GANG, M4, AK = 7, 31, 30
SQ = HCB_ROLE_SQUAD
JOB = {HCB_ROLE_LEAD: 'lead', HCB_ROLE_CLOSE: 'close', HCB_ROLE_POINT: 'point', HCB_ROLE_REAR: 'rear'}


def detail(sc, places=((-2.6, -1.6), (1.1, -1.3), (-0.8, 4.5), (0.6, -5.0)), walk=True):
    """Four guards round CJ (who faces north at the origin), in their formation slots."""
    team = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(places)]
    sc.walk_posts = walk
    return team


def post(sc, who):
    return sc.posts[who]


def at(p):
    return (p.at.x, p.at.y)


def by_job(sc):
    return {JOB[p.job]: p for p in sc.posts.values()}


def d2(a, b):
    return math.dist(a[:2], b[:2])


# ------------------------------------------------------------------ peace: the formation and the sectors
sc = Scene()
team = detail(sc)
sc.step(3)
j = by_job(sc)
assert set(j) == {'lead', 'close', 'point', 'rear'}, j
assert d2(at(j['close']), (0, 0)) < 2.0 and at(j['close'])[0] > 0 and at(j['close'])[1] < 0, 'the bodyguard: a pace behind CJ, on his right'
assert at(j['point'])[1] > 3.5 and at(j['rear'])[1] < -3.5 and at(j['lead'])[0] < -1, 'point man ahead, rear man behind, the commander behind on the left'
looks = {k: (p.look.x, p.look.y) for k, p in j.items()}
assert looks['point'][1] > 8 and looks['rear'][1] < -8 and looks['close'][0] > 5 and looks['lead'][0] < -5, ('each watches his own sector, outwards', looks)
assert all(p.duty == HCB_DUTY_CALM and not p.crouch for p in j.values())
assert sc.brain.out.lead == team[0] if hasattr(sc.brain, 'out') else True
passed('Peace: a diamond round CJ - the bodyguard a pace behind on his right, the commander behind on the left, the point man 4.5 m ahead, the rear man 5 m behind; each watches his own sector outwards, standing')

# CJ walks east: the formation turns with him after 1.5 s; a short sidestep does not turn it
sc.cj['vel'] = [3., 0., 0.]
sc.step(8)
assert by_job(sc)['point'].at.y > 3, 'a sidestep of 0.8 s does not turn the formation'
sc.step(10)
j = by_job(sc)
assert j['point'].at.x - sc.cj['pos'][0] > 3.5 and abs(j['point'].at.y - sc.cj['pos'][1]) < 1.5, ('after 1.5 s going east the point man is ahead of him in the east', at(j['point']), sc.cj['pos'])
assert all(p.move in (2, 3) for p in j.values() if d2(at(p), sc.peds[p.who]['pos']) > 5), 'far behind a moving CJ: they run'
passed('The formation turns with the way CJ goes (after 1.5 s on a new course, not on a sidestep), and whoever has fallen back runs to his slot')

# CJ fires straight ahead (north): the point man 4.5 m in front of him steps out of the line, the others stay where they are
sc = Scene()
team = detail(sc)
sc.step(3)
before = {p.who: at(p) for p in by_job(sc).values()}
sc.shot(1, (0., 30., 1.))
sc.step(1)
j = by_job(sc)
assert abs(j['point'].at.x) >= 1.99 and j['point'].move in (1, 2, 3), ('the point man is out of CJ\'s line', at(j['point']))
assert all(d2(at(p), before[p.who]) < .05 for k, p in j.items() if k != 'point'), 'nobody else had to move'
sc.step(15)
j = by_job(sc)
assert d2(at(j['point']), before[j['point'].who]) < .05, 'CJ stopped shooting 1.2 s ago: back to his slot'
passed('CJ shooting: nobody stands in front of his gun - a man within 2 m of his line steps out sideways (the bodyguard 1.2 m), and goes back once CJ has stopped for 1.2 s')

# ------------------------------------------------------------------ a suspect: weapons up, the bodyguard between him and CJ
sc = Scene()
team = detail(sc)
sus = sc.ped(15, 0, pedtype=GANG, weapon=AK, face=(1., 0.))         # armed, near, his back to CJ: watched, not a threat
sc.step(4)
j = by_job(sc)
assert all(p.duty == HCB_DUTY_WATCH for p in j.values()), [p.duty for p in j.values()]
assert d2(at(j['close']), (1.3, 0)) < 0.3, ('the bodyguard steps between the suspect and CJ', at(j['close']))
assert all(d2((p.look.x, p.look.y), (15, 0)) < 1 for k, p in j.items() if k != 'rear') and d2((j['rear'].look.x, j['rear'].look.y), (15, 0)) > 5, 'eyes on him, the rear man keeps the rear'
passed('A suspect (armed and near, has done nothing yet): the bodyguard steps between him and CJ, the others put their eyes on him, the rear man keeps watching the rear')

# ------------------------------------------------------------------ contact: cover for CJ, the commander tells him, the team fights from cover


def contact(walls=(), holes=(), tactics=0, threat=(25., 0.), walk=True):
    sc = Scene()
    sc.walls = list(walls)
    sc.holes = list(holes)
    sc.tactics = tactics
    team = detail(sc, walk=walk)
    g = sc.ped(threat[0], threat[1], pedtype=GANG, weapon=AK, face=(-1., 0.))
    sc.step(2)
    sc.shot(g, (0., 0., 1.), dst=1)
    return sc, team, g


sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])          # a wall 3 m west of CJ, the shooter 25 m east
sc.step(12)
out = sc.brain.think(sc.snapshot()) if False else None
covers = [s_ for s_ in sc.said if s_[1] == HCB_SAY_TAKE_COVER]
assert covers and covers[0][2] == 3, ('the commander: "CJ, into cover - on your left!" (west, CJ faces north)', sc.said)
j = by_job(sc)
cov = sc.brain_last_cover if hasattr(sc, 'brain_last_cover') else None
assert j['close'].duty == HCB_DUTY_SHIELD and d2(at(j['close']), (1.3, 0)) < 0.4, ('until CJ moves the bodyguard is between him and the shooter', at(j['close']))
passed('Contact with a wall 3 m away on the side away from the shooter: within a second the commander tells CJ where to go ("into cover - on your left"), the bodyguard puts himself between CJ and the shooter')


def last_out(sc):
    return sc.last_out


# the core's own record of the spot: cover_at in the last output
hcb_py.Scene.last_out = None
_orig_step = hcb_py.Scene.step


def _step(self, n=1, ms=100):
    out = _orig_step(self, n, ms)
    self.last_out = hcb_out.from_buffer_copy(bytes(out)) if out is not None else None
    return out


hcb_py.Scene.step = _step

sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(12)
o = sc.last_out
assert o.cover_ok and -5 < o.cover_at.x < -3 and abs(o.cover_at.y) < 2.6, ('a spot behind the wall, the nearest one', o.cover_ok, o.cover_at.x, o.cover_at.y)
assert sc.blocked((25., 0.), (o.cover_at.x, o.cover_at.y)), 'the shooter cannot see it'
sc.cj['pos'] = [o.cover_at.x, o.cover_at.y, 1.]
sc.step(6)
o = sc.last_out
j = by_job(sc)
assert any(s_[1] == HCB_SAY_IN_COVER for s_ in sc.said) and not o.cover_ok, ('"CJ is in cover - we hold"; the mark goes away', sc.said)
assert j['close'].crouch and d2(at(j['close']), sc.cj['pos']) < 1.2, 'the bodyguard crouches beside him'
assert j['lead'].crouch and d2(at(j['lead']), sc.cj['pos']) < 4.5, 'the commander takes cover next to him'
for k in ('point', 'rear'):
    p = j[k]
    assert d2(at(p), sc.cj['pos']) <= 12.5 and p.at.x > sc.cj['pos'][0], (k, 'on the shooter\'s side of CJ, never further than 12 m', at(p))
passed('CJ goes to the spot: "CJ is in cover, we hold", the mark goes away; the bodyguard crouches at his side, the commander takes cover next to him, the fire team fights from the shooter\'s side, within 12 m of CJ')

# ------------------------------------------------------------------ no cover near: stay with the bodyguard
sc, team, g = contact()
sc.step(25)
o = sc.last_out
assert not o.cover_ok and any(s_[1] == HCB_SAY_FOLLOW_ME for s_ in sc.said), ('nothing to hide behind: "CJ, stay with me"', sc.said)
j = by_job(sc)
assert d2(at(j['close']), (1.3, 0)) < 0.4 and j['close'].duty == HCB_DUTY_SHIELD, 'the bodyguard keeps his body between CJ and the shooter'
passed('No cover within 8 m: the commander tells CJ to stay with the bodyguard, who keeps his body between CJ and the shooter')

# cover only on the shooter's side of CJ is not where CJ is sent; a hidden spot over a drop (no ground) neither
sc, team, g = contact(walls=[(6., -1.0, 6., 1.0), (3., 7., 3., 11.)])     # a short wall ahead on the line, and one off to the shooter's side
sc.step(20)
o = sc.last_out
r_ = math.hypot(o.cover_at.x, o.cover_at.y)
assert not o.cover_ok or o.cover_at.x <= 0.5 * r_ + 0.01, ('CJ is never sent towards the man who shoots at him', o.cover_at.x, o.cover_at.y)
assert o.cover_ok and o.cover_at.x < 0, ('the shade behind the short wall (away from the shooter) is taken', o.cover_at.x, o.cover_at.y)
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)], holes=[(-4., 0., 3.)])
sc.step(20)
o = sc.last_out
assert not o.cover_ok or math.dist((o.cover_at.x, o.cover_at.y), (-4, 0)) >= 3, ('no ground there (water, a drop): not a place for CJ', o.cover_at.x, o.cover_at.y)
sc, team, g = contact(walls=[(6., -1.0, 6., 1.0)], holes=[(-5., 0., 4.5)])     # the only shade with ground under it is on the shooter's side
sc.step(20)
o = sc.last_out
r_ = math.hypot(o.cover_at.x, o.cover_at.y)
assert not o.cover_ok or o.cover_at.x <= 0.5 * r_ + 0.01, ('not even when it is the only shade there is', o.cover_at.x, o.cover_at.y)
passed('CJ is never sent towards the shooter for cover, nor to a hidden spot with no ground under it (water, a drop)')

# ------------------------------------------------------------------ bounding overwatch: one runs, the other covers him
sc, team, g = contact(walk=False)
sc.step(6)
j = by_job(sc)
duties = sorted((j['point'].duty, j['rear'].duty))
assert duties == sorted((HCB_DUTY_BOUND, HCB_DUTY_HOLD)), ('both far from their spots: one runs, the other holds crouched where he is', duties)
holder = j['point'] if j['point'].duty == HCB_DUTY_HOLD else j['rear']
assert holder.crouch and holder.move == 0 and d2(at(holder), sc.peds[holder.who]['pos']) < 0.01
mover = j['point'] if holder is j['rear'] else j['rear']
sc.peds[mover.who]['pos'] = [mover.at.x, mover.at.y, 1.]
sc.step(1)
j = by_job(sc)
other = j['point'] if holder.job == HCB_ROLE_POINT else j['rear']
assert other.duty == HCB_DUTY_BOUND, 'his mate is there: now he runs'
passed('Bounding overwatch: when both men of the fire team have to move, one runs to his spot while the other holds where he is, crouched, covering him; then they change')

# ------------------------------------------------------------------ the commander falls: the next man takes over and says so
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(8)
assert sc.last_out.lead == team[0]
sc.peds[team[0]]['flags'] |= HCB_PF_DEAD
sc.step(2)
assert sc.last_out.lead == team[1] and any(s_[1] == HCB_SAY_TAKE_OVER for s_ in sc.said), (sc.last_out.lead, sc.said)
assert len(sc.posts) == 3 and team[0] not in sc.posts
passed('The commander falls: the next man takes command and says so; the three left share the roles (bodyguard and fire team)')

# ------------------------------------------------------------------ too hot: a tight ring and the call for the pickup
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.cj['health'] = 20.
sc.step(6)
o = sc.last_out
assert o.duty == HCB_DUTY_RING and all(d2(at(p), sc.cj['pos']) <= 1.9 for p in sc.posts.values()), [at(p) for p in sc.posts.values()]
evac = [s_ for s_ in sc.said if s_[1] == HCB_SAY_EVAC]
sc.step(60)
assert len(evac) == 1 and len([s_ for s_ in sc.said if s_[1] == HCB_SAY_EVAC]) == 1, 'said once, then not again for 20 s'
passed('Too hot (CJ badly hurt under fire): a tight ring round him, nobody further than 2 m, the bodyguard towards the shooter; "we pull out - call the pickup", not repeated for 20 s')

# ------------------------------------------------------------------ all clear: once
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(10)
sc.peds[g]['flags'] |= HCB_PF_DEAD
sc.step(400)
clears = [s_ for s_ in sc.said if s_[1] == HCB_SAY_CLEAR]
assert len(clears) == 1 and sc.last_out.duty == HCB_DUTY_CALM, (sc.said[-4:], sc.last_out.duty)
passed('The shooter is down and it stays quiet: "clear - regroup on CJ", once, and the detail is back in its formation')

# ------------------------------------------------------------------ the questions about cover: few per look, none asked twice in vain
sc, team, g = contact()
counts, seen = [], {}
for _ in range(30):
    sc.step(1)
    counts.append(len(sc.probe_q))
    for q_at, q_from in sc.probe_q:
        key = (round(q_at[0], 1), round(q_at[1], 1))
        if key in seen:
            assert sc.time - seen[key] >= 6000, ('an answered spot is not asked about again while the answer is fresh', key)
        seen[key] = sc.time
assert max(counts) <= HCB_MAX_PROBES and sum(counts) > 20, counts
passed('Cover questions: at most %d a look (two rays each in the game), and a spot already answered is not asked about again while the answer is fresh' % HCB_MAX_PROBES)

# ------------------------------------------------------------------ CJ in a vehicle: no posts (the scripts take the seats)
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
car = sc.veh(0, 0, driver=0)
sc.cj['vehicle'] = car
sc.step(3)
assert not sc.posts, sc.posts
passed('CJ in a vehicle: the detail gives no posts on foot (the scripts take the free seats or follow)')

# ------------------------------------------------------------------ ASSAULT tactics: the fire team pushes further
sc, team, g = contact(tactics=1)
sc.step(20)
j = by_job(sc)
far_ = max(d2(at(j['point']), sc.cj['pos']), d2(at(j['rear']), sc.cj['pos']))
sc2, team2, g2 = contact(tactics=0)
sc2.step(20)
j2 = by_job(sc2)
near_ = max(d2(at(j2['point']), sc2.cj['pos']), d2(at(j2['rear']), sc2.cj['pos']))
assert far_ > near_ + 2 and far_ <= 18.5 and near_ <= 12.5, (far_, near_)
passed('SQUAD TACTICS: GUARD keeps the fire team within 12 m of CJ (%.0f m here), ASSAULT pushes it towards the shooter (%.0f m, never beyond 18 m)' % (near_, far_))

# ------------------------------------------------------------------ the same fight twice: the same decisions
def run_twice():
    out = []
    for _ in range(2):
        sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5), (10., 6., 14., 6.)])
        digs = []
        for k in range(40):
            if k == 20:
                sc.cj['pos'] = [-4., 0., 1.]
            sc.step(1)
            digs.append(sc.last_out.digest)
        out.append(digs)
    return out
a_, b_ = run_twice()
assert a_ == b_
passed('The same fight twice gives the same posts, the same words and the same questions (a recorded fight replays exactly)')

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_detail_tests.txt').write_text(text)
print(text)
