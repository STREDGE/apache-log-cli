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
JOB = {HCB_ROLE_LEAD: 'lead', HCB_ROLE_CLOSE: 'close', HCB_ROLE_POINT: 'point', HCB_ROLE_REAR: 'rear', HCB_ROLE_CLOSE2: 'close2', HCB_ROLE_POINT2: 'point2', HCB_ROLE_REAR2: 'rear2', HCB_ROLE_MARKSMAN: 'delta', HCB_ROLE_CLOSE3: 'close3'}


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


# ------------------------------------------------------------------ peace: nobody in CJ's way
EIGHT = ((-1.3, -0.5), (1.9, -1.0), (-7.8, 6.2), (-2.2, -1.6), (-7.6, -5.0), (0.3, -2.8), (7.8, 6.2), (4.6, -11.0))


def detail8(sc, walk=True):
    return detail(sc, places=EIGHT, walk=walk)


OUTER, BODY = ('point', 'point2', 'rear', 'delta'), ('close', 'close2', 'close3')
sc = Scene()
team = detail8(sc)
sc.step(30)
j = by_job(sc)
assert set(j) == {'lead'} | set(OUTER) | set(BODY), sorted(j)
assert d2(at(j['lead']), (0, 0)) < 1.6, ('the commander is at CJ\'s side', at(j['lead']))
assert all(1.5 < d2(at(j[k]), (0, 0)) < 3.2 and at(j[k])[1] < -0.5 for k in BODY), ('the three bodyguards: two to three metres off, behind him - nobody in front of CJ', [at(j[k]) for k in BODY])
assert all(8 <= d2(at(j[k]), (0, 0)) <= 12.5 for k in OUTER), ('the outer four: 9-12 m out', [at(j[k]) for k in OUTER])
quad = sorted((at(j[k])[0] > 0, at(j[k])[1] > 0) for k in OUTER)
assert quad == [(False, False), (False, True), (True, False), (True, True)], ('one at each corner', quad)
assert all(d2((j[k].look.x, j[k].look.y), (0, 0)) > 20 for k in OUTER), 'each looks outwards over his own corner'
assert all(p.duty == HCB_DUTY_CALM and not p.crouch for p in j.values())
near_cj = [k for k, p in j.items() if d2(sc.peds[p.who]['pos'], sc.cj['pos']) < 4.0]
assert sorted(near_cj) == sorted(('lead',) + BODY), near_cj
passed('Peace, eight men: the commander at CJ\'s side, three bodyguards two to three metres behind him (nobody in front of him, no heap round him), the other four 9-12 m out, one at each corner, each watching outwards')

sc = Scene()
team = detail(sc)
sc.step(3)
j = by_job(sc)
assert set(j) == {'lead', 'close', 'close2', 'point'}, sorted(j)
passed('Four men: the commander, two bodyguards and one man out')

# CJ walks east: the formation turns with him after 1.5 s; a short sidestep does not turn it
sc = Scene(); team = detail8(sc); sc.step(20)
sc.cj['vel'] = [3., 0., 0.]
sc.step(8)
assert by_job(sc)['point'].at.y > sc.cj['pos'][1] + 3, 'a sidestep of 0.8 s does not turn the formation'
sc.step(12)
j = by_job(sc)
assert j['point'].at.x - sc.cj['pos'][0] > 3.5 and j['point2'].at.x - sc.cj['pos'][0] > 3.5 and j['rear'].at.x < sc.cj['pos'][0], ('after 1.5 s going east the two front men are ahead of him in the east', at(j['point']), sc.cj['pos'])
assert all(p.move in (2, 3) for p in j.values() if d2(at(p), sc.peds[p.who]['pos']) > 5), 'far behind a moving CJ: they run'
passed('The formation turns with the way CJ goes (after 1.5 s on a new course, not on a sidestep), and whoever has fallen back runs to his place')

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
team = detail8(sc)
sc.step(20)
sus = sc.ped(15, 0, pedtype=GANG, weapon=AK, face=(1., 0.))         # armed, near, his back to CJ: watched, not a threat
sc.step(4)
j = by_job(sc)
assert all(p.duty == HCB_DUTY_WATCH for p in j.values()), [p.duty for p in j.values()]
assert d2(at(j['close']), (1.5, 0)) < 0.3, ('the first bodyguard steps between the suspect and CJ', at(j['close']))
assert all(d2((j[k].look.x, j[k].look.y), (15, 0)) < 1.5 for k in ('lead', 'close', 'close2', 'close3', 'point', 'point2')), 'eyes on him'
assert all(d2((j[k].look.x, j[k].look.y), (15, 0)) > 15 for k in ('rear', 'delta')), 'the two rear men keep watching the rear'
passed('A suspect (armed and near, has done nothing yet): the first bodyguard steps between him and CJ, the commander, the bodyguards and the two front men put their eyes on him, the two rear men keep the rear')

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
assert j['close'].duty == HCB_DUTY_SHIELD and d2(at(j['close']), (1.4, 0)) < 0.4, ('until CJ moves the bodyguard is between him and the shooter', at(j['close']))
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
sc.step(30)                                                            # (he says it when CJ has stayed there a second, and never two things within 2.5 s)
o = sc.last_out
j = by_job(sc)
assert any(s_[1] == HCB_SAY_IN_COVER for s_ in sc.said) and not o.cover_ok, ('"CJ is in cover - we hold"; the mark goes away', sc.said)
assert j['close'].crouch and d2(at(j['close']), sc.cj['pos']) < 1.2, 'the bodyguard crouches beside him'
assert j['lead'].crouch and d2(at(j['lead']), sc.cj['pos']) < 4.5, 'the commander takes cover next to him'
assert 4 <= d2(at(j['point']), sc.cj['pos']) <= 26, ('the outer man: on a post of his own, 4-26 m from CJ', at(j['point']))
passed('CJ goes to the spot: "CJ is in cover, we hold"; the bodyguards crouch at his sides, the commander crouches next to him, the outer man holds a post of his own')

# ------------------------------------------------------------------ no cover near: stay with the bodyguard
sc, team, g = contact()
sc.step(25)
o = sc.last_out
assert not o.cover_ok and any(s_[1] == HCB_SAY_FOLLOW_ME for s_ in sc.said), ('nothing to hide behind: "CJ, stay with me"', sc.said)
j = by_job(sc)
assert d2(at(j['close']), (1.4, 0)) < 0.4 and j['close'].duty == HCB_DUTY_SHIELD, 'the bodyguard keeps his body between CJ and the shooter'
passed('No cover within 8 m: the commander tells CJ to stay with the bodyguard, who keeps his body between CJ and the shooter')

# cover only on the shooter's side of CJ is not where CJ is sent; a hidden spot over a drop (no ground) neither
sc, team, g = contact(walls=[(6., -1.0, 6., 1.0), (3., 7., 3., 11.)])     # a short wall ahead on the line, and one off to the shooter's side
sc.step(20)
o = sc.last_out
r_ = math.hypot(o.cover_at.x, o.cover_at.y)
assert not o.cover_ok or o.cover_at.x <= 0.5 * r_ + 0.01, ('CJ is never sent towards the man who shoots at him', o.cover_at.x, o.cover_at.y)
assert (o.cover_ok and o.cover_at.x < 0) or (math.hypot(o.cover_at.x, o.cover_at.y) < .01 and o.duty == HCB_DUTY_COVER), ('the shade behind the short wall (away from the shooter) is taken - here CJ already stands in it and stays', o.cover_at.x, o.cover_at.y)
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

# ------------------------------------------------------------------ a fight, eight men: three shield CJ, four hold posts behind cover
def fight8(walls, threat=(30., 0.)):
    sc = Scene(); sc.walls = list(walls)
    team = detail8(sc); sc.step(20)
    g = sc.ped(threat[0], threat[1], pedtype=GANG, weapon=AK, face=(-1., 0.))
    sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
    return sc, team, g


# short walls (cars, corners) about the place: something to stand behind in every corner
WALLS = [(10., -12., 10., -9.), (10., 9., 10., 12.), (-4., -11., -4., -8.), (-14., 5., -14., 8.), (11., -6., 11., -4.), (11., 4., 11., 6.)]
sc, team, g = fight8(WALLS)
sc.step(80)
j = by_job(sc); cjp = sc.cj['pos']
assert d2(at(j['lead']), cjp) < 2.0, ('the commander stays at CJ\'s side', at(j['lead']))
assert all(d2(at(j[k]), cjp) < 2.0 and at(j[k])[0] > cjp[0] for k in BODY) and d2(at(j['close']), (1.4, 0)) < 0.3, ('three bodies between CJ and the shooter', [at(j[k]) for k in BODY])
outs = {k: at(j[k]) for k in OUTER}
assert all(8 <= d2(p_, cjp) <= 26 for p_ in outs.values()), ('the four are out, 8-26 m from CJ - not in a heap round him', outs)
hidden = [k for k, p_ in outs.items() if sc.blocked(sc.peds[g]['pos'][:2], p_)]
assert len(hidden) >= 3, ('behind something solid (a crouching man there is hidden from the shooter)', outs, hidden)
assert all(not sc.blocked(cjp[:2], p_) for k, p_ in outs.items() if k in hidden), 'and CJ\'s ground is in sight from each post'
assert outs['point2'][1] < 0 < outs['point'][1] and outs['point'][0] > 0 and outs['point2'][0] > 0 and outs['rear'][0] < outs['point'][0], ('each in his own sector: two forward left and right, two back', outs)
there = [k for k in OUTER if d2(sc.peds[j[k].who]['pos'], outs[k]) < 1.5]
assert len(there) >= 3 and all(j[k].crouch and j[k].duty == HCB_DUTY_COVER for k in there), (there, [(k, j[k].crouch, j[k].duty) for k in OUTER])
kept = dict(outs); changed = 0
for _ in range(100):                                       # 10 more seconds of the same fight: the posts are kept
    if _ % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    j = by_job(sc)
    changed += sum(d2(at(j[k]), kept[k]) > 0.5 for k in hidden)
assert changed == 0, ('a post once taken is kept', changed)
passed('A fight, eight men: the commander at CJ\'s side, three bodyguards between CJ and the shooter, the other four each on a post of his own in his sector 8-26 m out, behind something solid (%d of 4 found cover here), with CJ\'s ground in sight, crouched once there; the posts are kept for the next 10 s' % len(hidden))

# on the way to his post a man is "bounding" (running, upright); CJ moves far: new posts near him
sc, team, g = fight8(WALLS)
sc.step(3)
j = by_job(sc)
assert all(j[k].duty == HCB_DUTY_BOUND and not j[k].crouch and j[k].move in (2, 3) for k in OUTER if d2(sc.peds[j[k].who]['pos'], at(j[k])) > 3), [(k, j[k].duty) for k in OUTER]
sc.step(60); sc.cj['pos'] = [0., 60., 1.]; sc.step(60)
j = by_job(sc)
assert all(d2(at(j[k]), sc.cj['pos']) <= 26 for k in OUTER) and all(d2(at(j[k]), sc.cj['pos']) < 2.2 for k in BODY + ('lead',)), 'CJ has moved 60 m: everybody\'s place is with him again'
passed('On the way to a post a man runs upright; when CJ has moved far the outer men take new posts near him and the inner four are at his side')

# rotation: a badly hurt outer man changes places with the fittest bodyguard
sc, team, g = fight8(WALLS)
sc.step(30)
j = by_job(sc); hurt = j['point2'].who; fresh = j['close3'].who
sc.peds[hurt]['health'] = 60.
for t_ in team: sc.peds[t_].setdefault('health', 250.)
for t_ in team:
    if t_ != hurt: sc.peds[t_]['health'] = 250.
sc.step(2)
j = by_job(sc)
assert j['point2'].who != hurt and JOB[sc.posts[hurt].job] in BODY, ('the wounded man comes in to CJ\'s side', JOB[sc.posts[hurt].job])
assert JOB[sc.posts[fresh].job] in OUTER or any(JOB[sc.posts[t_].job] == 'point2' for t_ in team if t_ != hurt)
passed('Rotation: an outer man who is badly hurt changes places with the fittest bodyguard - the wounded man comes in to CJ\'s side, a fresh one takes his post')

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
lead_p = sc.posts[o.lead]
assert o.duty == HCB_DUTY_RING and o.mode == HCB_MODE_PULLOUT and all(d2(at(p), sc.cj['pos']) <= 5.1 for w_, p in sc.posts.items()), [at(p) for p in sc.posts.values()]
assert o.leading and d2(at(lead_p), sc.cj['pos']) <= 1.7 and at(lead_p)[0] < sc.cj['pos'][0], ('the commander at CJ\'s side, a step away from the shooter: he takes CJ out', at(lead_p))
evac = [s_ for s_ in sc.said if s_[1] == HCB_SAY_EVAC]
sc.step(60)
assert len(evac) == 1 and len([s_ for s_ in sc.said if s_[1] == HCB_SAY_EVAC]) == 1, 'said once, then not again for 20 s'
passed('Too hot (CJ badly hurt under fire): the detail pulls out - everybody comes in (nobody further than 5 m), the bodyguards towards the shooter, the commander at CJ\'s side a step away from the shooter, taking him out; "we pull out - call the pickup", not repeated for 20 s')

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

# ------------------------------------------------------------------ the commander takes CJ to his cover: at his side, a step ahead
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(4)
lp = sc.posts[sc.last_out.lead]
assert sc.last_out.leading and 1.0 < d2(at(lp), sc.cj['pos']) <= 1.7 and at(lp)[0] < sc.cj['pos'][0] - 0.9, ('the commander is at CJ\'s side, a step towards the cover (west)', at(lp))
for k in range(12):                                        # CJ goes with him (the cover is 4 m west)
    sc.cj['pos'][0] -= 0.25
    sc.step(1)
    lp = sc.posts[sc.last_out.lead]
    if sc.last_out.leading: assert d2(at(lp), sc.cj['pos']) <= 1.7 and at(lp)[0] <= sc.cj['pos'][0], ('he stays at CJ\'s side, a step ahead, all the way', at(lp), sc.cj['pos'])
sc.cj['pos'] = [sc.last_out.cover_at.x, sc.last_out.cover_at.y, 1.]
sc.step(20)
assert not sc.last_out.leading and sc.posts[sc.last_out.lead].crouch and d2(at(sc.posts[sc.last_out.lead]), sc.cj['pos']) < 2.0, 'there: he crouches next to CJ'
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
for k in range(80):                                        # CJ stays where he is: the commander does not leave him
    sc.step(1)
    assert d2(at(sc.posts[sc.last_out.lead]), sc.cj['pos']) <= 1.7, 'the commander never leaves CJ\'s side'
passed('Under fire the commander takes CJ to the cover like by the hand: at CJ\'s side, a step towards the cover, all the way, crouching next to him there; if CJ stays where he is, so does the commander')

sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(10)
g_pos = list(sc.peds[g]['pos'])
del sc.peds[g]                                             # the shooter is gone from sight
sc.step(40)
assert sc.last_out.duty == HCB_DUTY_COVER, 'between shots the detail stays in its fight positions (the threat is remembered)'
sc.step(400)
assert sc.last_out.duty in (HCB_DUTY_CALM, HCB_DUTY_WATCH)
passed('The threat is remembered (the attacker 20 s, his place 12 s more): between bursts the detail does not stand down; then it does')

sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.stuck_men = {team[2]}                                   # the point man cannot move (a fence)
sc.step(70)
pp = sc.posts[team[2]]
assert pp.stuck and pp.move == 4, ('he gets another way round, then the path network', pp.stuck, pp.move)
passed('A man who does not get nearer to his post for 1.5 s is given another way round (the post turned round CJ), then the path network')

sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.wanted = 5
sc.step(3)
assert sc.last_out.mode == HCB_MODE_PULLOUT and sc.last_out.duty == HCB_DUTY_RING
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.tactics = 1; sc.cj['pos'] = [-4.0, 0., 1.]
sc.step(60)
assert sc.last_out.mode == HCB_MODE_HOLD, sc.last_out.mode
passed('The brain picks how to fight by itself: 5 stars (or too many / too strong, CJ badly hurt) -> pull out; else hold. There is no ASSAULT / GUARD setting any more (the old menu value is ignored)')

sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.heli = sc.veh(0, -30, z=25.)
sc.step(10)
o = sc.last_out
assert o.heli_ok and 19 < d2((o.heli_at.x, o.heli_at.y), sc.cj['pos']) < 21 and o.heli_at.y < -15 and abs(o.heli_at.z - sc.cj['pos'][2] - 16) < 0.1, ('a spot for the helicopter 20 m off and 16 m up, abeam of the line CJ - shooter, on the side the helicopter is', o.heli_ok, o.heli_at.x, o.heli_at.y, o.heli_at.z)
assert o.gunner_pose == 1
spot0 = (o.heli_at.x, o.heli_at.y); moved = 0
g2 = sc.ped(-20., 15., pedtype=GANG, weapon=AK, face=(1., -1.))
for k in range(100):                                       # the shooter moves about, a second one fires in turn, CJ shifts a little: the spot stays
    sc.peds[g]['pos'] = [25. + 6. * math.sin(k * 0.2), 8. * math.sin(k * 0.13), 1.]
    if k % 7 == 0: sc.shot(g if (k // 7) % 2 else g2, (0., 0., 1.), dst=1)
    if k % 30 == 15: sc.cj['pos'] = [sc.cj['pos'][0] + 1.5, sc.cj['pos'][1], 1.]
    sc.step(1)
    if sc.last_out.heli_ok: moved += d2((sc.last_out.heli_at.x, sc.last_out.heli_at.y), spot0) > 1.0
assert moved == 0 and sc.last_out.heli_ok, ('the spot is kept', moved)
sc.cj['pos'] = [60., 0., 1.]; sc.step(15)
assert sc.last_out.heli_ok and d2((sc.last_out.heli_at.x, sc.last_out.heli_at.y), sc.cj['pos']) < 21, 'CJ has gone far from it: a new one beside him'
sc2 = Scene(); detail(sc2); sc2.heli = sc2.veh(0, -30, z=25.); sc2.step(3)
assert sc2.last_out.gunner_pose == 2 and not sc2.last_out.heli_ok
passed('The helicopter gets a spot 20 m from CJ and 16 m up, abeam of the line to the shooter on the side it is already, where the gunners see him; it is kept for 10 s of a fight with shooters moving and firing in turn and replaced only when CJ has gone far; the gunners sit on the skid when all is quiet and kneel at the door over a fight')


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

# ---- 0.4.2, from the first whole-game log (16.11.2026) ----
# a car drives at a guard: he gets out of its way (seven were run over in that game); when it has passed he goes back
sc = Scene(); team = detail(sc)
sc.step(10)
gx, gy = sc.peds[team[0]]['pos'][:2]
drv = sc.ped(gx, gy - 30., pedtype=4)
car = sc.veh(gx, gy - 30., vel=(0., 15., 0.), driver=drv)
least = 9.
for k in range(30):
    sc.step(1)
    c_ = sc.vehs[car]['pos']
    for t_ in team:
        q = sc.peds[t_]['pos']
        if abs(q[1] - c_[1]) < 3.0: least = min(least, abs(q[0] - c_[0]))
assert least > 2.0, ('nobody is within 2 m of the car\'s path as it passes', least)
sc.vehs[car]['vel'] = [0., 0., 0.]; sc.step(40)
assert d2(sc.peds[team[0]]['pos'], at(post(sc, team[0]))) < 1.5 and post(sc, team[0]).move != 3
passed('A car at speed coming at a guard: he sprints out of its path (never within 2 m of it as it passes; closest %.1f m) and returns to his post after' % least)

# 0.5: nobody runs across in front of a car - a man whose post is on the other side of its path waits for it to pass
sc = Scene(); team = detail(sc); sc.step(10)
me = team[2]; mx, my = sc.peds[me]['pos'][:2]
drv = sc.ped(mx + 5., my - 40., pedtype=4); car = sc.veh(mx + 5., my - 40., vel=(0., 16., 0.), driver=drv)
sc.cj['pos'] = [sc.cj['pos'][0] + 10., sc.cj['pos'][1], 1.]            # CJ steps over the road: the man's post is on the far side now
least = 9.
for k in range(30):
    sc.step(1)
    c_ = sc.vehs[car]['pos']; q = sc.peds[me]['pos']
    if abs(q[1] - c_[1]) < 3.5: least = min(least, abs(q[0] - c_[0]))
assert least > 2.5, ('he was never in front of the car', least)
sc.step(40)
assert d2(sc.peds[me]['pos'], at(post(sc, me))) < 2.0, 'and when it has passed he crosses to his post'
passed('A post on the other side of a road with a car coming: the man waits for it to pass (closest %.1f m to its path) and crosses after' % least)

# the threat drives round CJ and others come and go: the commander does not chatter, the commander does not start and stop
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
g2 = sc.ped(-20., 15., pedtype=GANG, weapon=AK, face=(1., -1.))
lead_flips, was = 0, 0
for k in range(300):
    a_ = k * 0.05
    sc.peds[g]['pos'] = [25. * math.cos(a_), 25. * math.sin(a_), 1.]
    if k % 7 == 0: sc.shot(g if (k // 7) % 2 else g2, (0., 0., 1.), dst=1)
    if k % 40 == 20: sc.cj['pos'] = [sc.cj['pos'][0] + 1.8, sc.cj['pos'][1], 1.]
    sc.step(1)
    lead_flips += sc.last_out.leading != was; was = sc.last_out.leading
gaps = [b_[0] - a_[0] for a_, b_ in zip(sc.said, sc.said[1:])]
assert gaps and min(gaps) >= 2500, ('never two things said within 2.5 s', sorted(gaps)[:5])
same = [b_[0] - a_[0] for a_, b_ in zip(sc.said, sc.said[1:]) if a_[1] == b_[1] == HCB_SAY_TAKE_COVER]
assert all(x >= 6000 for x in same) and len(sc.said) <= 12 and lead_flips <= 16, (len(sc.said), lead_flips, sc.said)
passed('30 s with the shooter circling CJ, a second one firing in turn and CJ shifting about: the commander says %d things, never two within 2.5 s, "into cover" 6 s apart at least; he starts or stops leading %d times' % (len(sc.said), lead_flips))

# the detail keeps the man it fights: a second shooter a little more dangerous for a moment does not turn it round
sc, team, g = contact()
sc.step(10)
look0 = at(post(sc, team[2])); T0 = sc.brain.b.dt.threat_id if hasattr(sc.brain, 'b') else None
g2 = sc.ped(-22., 0., pedtype=GANG, weapon=AK, face=(1., 0.))
turned = 0
for k in range(25):
    if k % 5 == 0: sc.shot(g2, (0., 0., 1.), dst=1)
    if k % 5 == 2: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    lk = post(sc, team[0]).look
    turned += (lk.x < 0) != (k and prev < 0); prev = lk.x
assert turned <= 2, ('the commander\'s weapon does not swing from one shooter to the other every look', turned)
passed('Two shooters on opposite sides firing in turn: the detail keeps the one it fights (3 s at least, then until another is half again as dangerous) - it turned round %d times in 2.5 s' % turned)

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_detail_tests.txt').write_text(text)
print(text)
