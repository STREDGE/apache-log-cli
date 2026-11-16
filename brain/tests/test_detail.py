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


OUTER, BODY = ('point', 'point2', 'rear', 'rear2'), ('close', 'close2')
sc = Scene()
team = detail8(sc)
sc.step(30)
j = by_job(sc)
assert set(j) == {'lead', 'delta'} | set(OUTER) | set(BODY), sorted(j)
assert d2(at(j['lead']), (0, 0)) < 1.6, ('the commander is at CJ\'s side', at(j['lead']))
assert at(j['lead'])[0] > 0.8 and at(j['lead'])[1] < 0, ('1.0: at his right shoulder, a step behind', at(j['lead']))
assert 3.0 < at(j['close'])[1] < 4.5 and at(j['close'])[0] < -1.2, ('one bodyguard ahead on the left, clear of CJ\'s way', at(j['close']))
assert at(j['close2'])[1] < -1.5 and at(j['close2'])[0] < -1.0 and j['close2'].look.y < -8, ('the other behind on the left, watching the rear', at(j['close2']))
assert all(abs(at(j[k])[0]) > 1.0 for k in BODY + ('lead',)), 'nobody on the line CJ walks'
assert all(15 <= d2(at(j[k]), (0, 0)) <= 33 for k in OUTER), ('1.5: the outer four 15-33 m out', [at(j[k]) for k in OUTER])
assert d2(at(j['delta']), (0, 0)) > 15, 'the marksman (on the ground while no high place is known): furthest out'
quad = sorted((at(j[k])[0] > 0, at(j[k])[1] > 0) for k in OUTER)
assert quad == [(False, False), (False, True), (True, False), (True, True)], ('a quarter each', quad)
assert all(d2((j[k].look.x, j[k].look.y), (0, 0)) > 30 for k in OUTER), 'each looks outwards over his own quarter'
assert all(p.duty == HCB_DUTY_CALM for p in j.values())
assert not any(j[k].crouch for k in BODY + ('lead',)), 'the three at CJ stand'
sc.step(120)
j = by_job(sc)
there = [k for k in OUTER if d2(at(j[k]), sc.peds[j[k].who]['pos']) < 1.5]
assert len(there) >= 3 and all(j[k].crouch for k in there), ('1.5: the outer men at their places are down', there, [(k, j[k].crouch) for k in OUTER])
near_cj = [k for k, p in j.items() if d2(sc.peds[p.who]['pos'], sc.cj['pos']) < 12.0]
assert sorted(near_cj) == sorted(('lead',) + BODY), ('1.5: within 12 m of CJ only the three', near_cj)
passed('Peace, eight men (1.5): THREE at CJ - the commander at his right shoulder, one bodyguard ahead on the left, one behind on the left watching the rear, nobody on the line he walks; the four outer men 15-33 m out, a quarter each, down at their places and watching outwards; nobody else within 12 m of CJ; the marksman furthest out')

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
east = [k for k in OUTER if j[k].at.x - sc.cj['pos'][0] > 3.5]
west = [k for k in OUTER if j[k].at.x < sc.cj['pos'][0]]
assert len(east) == 2 and len(west) == 2, ('after 1.5 s going east two of the outer men are ahead of him in the east (1.5: the quarters dealt out again, least way for all), two behind', {k: at(j[k]) for k in OUTER}, sc.cj['pos'])
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
assert all(d2(at(p), before[p.who]) < .05 for k, p in j.items() if k not in ('point', 'close')), 'nobody else had to move'
assert abs(j['close'].at.x) >= 1.99, 'the bodyguard ahead on the left steps further out of the line too'
sc.step(15)
j = by_job(sc)
assert d2(at(j['point']), before[j['point'].who]) < .3, 'CJ stopped shooting 1.2 s ago: back to his slot'
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
assert all(d2((j[k].look.x, j[k].look.y), (15, 0)) < 1.5 for k in ('lead', 'close', 'close2')), 'eyes on him'
on_him = [k for k in OUTER if d2((j[k].look.x, j[k].look.y), (15, 0)) < 1.5]
assert len(on_him) == 2, ('1.5: the two outer men in the quarters towards him put their eyes on him', on_him)
assert all(d2((j[k].look.x, j[k].look.y), (15, 0)) > 15 for k in set(OUTER) - set(on_him) | {'delta'}), 'the rear men keep watching the rear'
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
    sc = Scene(); sc.low_walls = list(walls)      # (1.0: things a crouching man is hidden behind and a standing one fires over)
    team = detail8(sc); sc.step(20)
    g = sc.ped(threat[0], threat[1], pedtype=GANG, weapon=AK, face=(-1., 0.))
    sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
    return sc, team, g


# short walls (cars, corners) about the place: something to stand behind in every corner
WALLS = [(10., -12., 10., -9.), (10., 9., 10., 12.), (-4., -11., -4., -8.), (-14., 5., -14., 8.), (11., -6., 11., -4.), (11., 4., 11., 6.),
         # (1.5: the outer men are 15-35 m out now - something to get down behind out there too, in each quarter)
         (15.5, 16., 15.5, 20.), (15.5, -20., 15.5, -16.), (-11., 17.5, -11., 21.), (-11., -21., -11., -17.5)]
sc, team, g = fight8(WALLS)
for _ in range(150):                                       # (1.1: the places are valued as the answers come in - a man may move ONCE to a place 20 % better after 4 s)
    if _ % 9 == 0 and _: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
j = by_job(sc); cjp = sc.cj['pos']
assert d2(at(j['lead']), cjp) < 2.0, ('the commander stays at CJ\'s side', at(j['lead']))
assert all(d2(at(j[k]), cjp) < 2.0 and at(j[k])[0] > cjp[0] for k in BODY) and d2(at(j['close']), (1.4, 0)) < 0.3, ('three bodies between CJ and the shooter', [at(j[k]) for k in BODY])
outs = {k: at(j[k]) for k in OUTER}
assert all(15 <= d2(p_, cjp) <= 35 for p_ in outs.values()), ('1.5: the four are out of sight, 15-35 m from CJ - not in a heap round him', outs)
hidden = [k for k, p_ in outs.items() if sc.blocked(sc.peds[g]['pos'][:2], p_)]
assert len(hidden) >= 3, ('behind something solid (a crouching man there is hidden from the shooter)', outs, hidden)
assert all(not sc.blocked(cjp[:2], p_) for k, p_ in outs.items() if k in hidden), 'and CJ\'s ground is in sight from each post'
fwd = sorted(outs.values(), key=lambda p_: -p_[0])
assert fwd[0][0] > 0 and fwd[1][0] > 0 and fwd[0][1] * fwd[1][1] < 0 and fwd[2][1] * fwd[3][1] < 0 and fwd[2][0] < min(fwd[0][0], fwd[1][0]), ('a quarter each: two forward left and right, two back left and right', outs)
there = [k for k in OUTER if d2(sc.peds[j[k].who]['pos'], outs[k]) < 1.5]
assert len(there) >= 3 and all(j[k].crouch and j[k].duty == HCB_DUTY_COVER for k in there), (there, [(k, j[k].crouch, j[k].duty) for k in OUTER])
kept = dict(outs); changed = 0
for _ in range(100):                                       # 10 more seconds of the same fight: the posts are kept
    if _ % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    j = by_job(sc)
    changed += sum(d2(at(j[k]), kept[k]) > 0.5 for k in hidden)
assert changed == 0, ('a post once taken is kept', changed)
passed('A fight, eight men: the commander at CJ\'s side, three bodyguards between CJ and the shooter, the other four each on a post of his own in his quarter 15-35 m out, behind something solid (%d of 4 found cover here), with CJ\'s ground in sight, crouched once there; the posts are kept for the next 10 s' % len(hidden))

# on the way to his post a man is "bounding" (running, upright); CJ moves far: new posts near him
sc, team, g = fight8(WALLS)
sc.step(3)
j = by_job(sc)
assert all(j[k].duty == HCB_DUTY_BOUND and not j[k].crouch and (j[k].move in (2, 3) or j[k].why == HCB_WHY2_WAIT_TURN) for k in OUTER if d2(sc.peds[j[k].who]['pos'], at(j[k])) > 3), [(k, j[k].duty, j[k].move, j[k].why) for k in OUTER]   # (1.1: no more than three on the move - the fourth waits his turn)
sc.step(60); sc.cj['pos'] = [0., 60., 1.]; sc.step(60)
j = by_job(sc)
assert all(d2(at(j[k]), sc.cj['pos']) <= 35 for k in OUTER) and all(d2(at(j[k]), sc.cj['pos']) < 2.2 for k in BODY + ('lead',)), 'CJ has moved 60 m: everybody\'s place is with him again'
passed('On the way to a post a man runs upright; when CJ has moved far the outer men take new posts near him and the inner four are at his side')

# rotation: a badly hurt outer man changes places with the fittest bodyguard
sc, team, g = fight8(WALLS)
sc.step(30)
j = by_job(sc); hurt = j['point2'].who; guards = {j['close'].who, j['close2'].who}
sc.peds[hurt]['health'] = 60.
for t_ in team: sc.peds[t_].setdefault('health', 250.)
for t_ in team:
    if t_ != hurt: sc.peds[t_]['health'] = 250.
sc.step(2)
j = by_job(sc)
assert j['point2'].who != hurt and JOB[sc.posts[hurt].job] in BODY, ('the wounded man comes in to CJ\'s side', JOB[sc.posts[hurt].job])
assert j['point2'].who in guards, 'one of the two bodyguards has taken his post'
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
assert o.duty == HCB_DUTY_RING and o.mode == HCB_MODE_PULLOUT, o.duty
dists = sorted(d2(at(p), sc.cj['pos']) for p in sc.posts.values())
# 0.9 (fifth log: six men of eight stood within 2-6 m of CJ): commander and bodyguards at his side; 1.5: the outer men 14-19 m off (out of sight)
assert all(x <= 5.1 for x in dists[:-1]) and 13.5 <= dists[-1] <= 19.5, dists
assert o.leading and d2(at(lead_p), sc.cj['pos']) <= 4.1 and at(lead_p)[0] < sc.cj['pos'][0], ('the commander goes ahead of CJ (1.3: 4 m at most), away from the shooter: he takes CJ out', at(lead_p))
evac = [s_ for s_ in sc.said if s_[1] == HCB_SAY_EVAC]
sc.step(60)
assert len(evac) == 1 and len([s_ for s_ in sc.said if s_[1] == HCB_SAY_EVAC]) == 1, 'said once, then not again for 20 s'
passed('Too hot (CJ badly hurt under fire): the detail pulls out - the commander and the bodyguards come in (5 m at most), the outer man holds 14-19 m off (1.5: out of sight), the bodyguards towards the shooter, the commander 4 m ahead of CJ away from the shooter, taking him out; "we pull out - call the pickup", not repeated for 20 s')

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
        key = (round(q_at[0], 1), round(q_at[1], 1), round(q_from[0]), round(q_from[1]))      # (1.1: a spot is asked about against each threat and against CJ - one question each)
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

# ------------------------------------------------------------------ the commander takes CJ to his cover himself (1.3)
# (the player: "why does the commander not lead me to cover - he stands in front of me and talks, no movement at all": his place
#  was 1.6 m from CJ towards the cover - one step, then waiting. Now he goes there, 4 m ahead of CJ, waits and waves him on.)
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(4)
lp = sc.posts[sc.last_out.lead]
assert sc.last_out.leading and d2(at(lp), sc.cj['pos']) > 2.0 and d2(at(lp), sc.cj['pos']) <= 4.1 and at(lp)[0] < sc.cj['pos'][0] - 1.5, ('the commander goes ahead of CJ towards the cover (west)', at(lp))
for k in range(12):                                        # CJ goes with him (the cover is 4 m west)
    sc.cj['pos'][0] -= 0.25; sc.cj['vel'] = [-2.5, 0., 0.]
    sc.step(1)
    lp = sc.posts[sc.last_out.lead]
    if sc.last_out.leading: assert d2(at(lp), sc.cj['pos']) <= 4.1 and at(lp)[0] <= sc.cj['pos'][0] + 0.1, ('he stays ahead of CJ, on the way to the cover, all the way', at(lp), sc.cj['pos'])
sc.cj['vel'] = [0., 0., 0.]
sc.cj['pos'] = [sc.last_out.cover_at.x, sc.last_out.cover_at.y, 1.]
sc.step(20)
assert not sc.last_out.leading and sc.posts[sc.last_out.lead].crouch and d2(at(sc.posts[sc.last_out.lead]), sc.cj['pos']) < 2.0, 'there: he crouches next to CJ'
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
waved, said, far = 0, [], 0
for k in range(140):                                       # CJ stays where he is
    sc.step(1)
    lp = sc.posts[sc.last_out.lead]
    waved += lp.sign == HCB_SIGN_COME
    far = max(far, d2(at(lp), sc.cj['pos']))
said = [s_ for s_ in sc.said if s_[1] in (HCB_SAY_TAKE_COVER, HCB_SAY_COVER_DIR)]
assert waved >= 10 and far <= 4.1, ('CJ does not come: the commander waits at his point, turned to CJ, and waves him on', waved, far)
assert len(said) <= 2, ('"follow me" is said once for a cover, not every 6 s', said)
assert d2(at(sc.posts[sc.last_out.lead]), sc.cj['pos']) <= 2.0 and sc.posts[sc.last_out.lead].sign == HCB_SIGN_NONE, 'after 10 s without a step of CJ\'s he is back at CJ\'s side, covering him where he is'
passed('1.3: under fire the commander goes to the cover himself, 4 m ahead of CJ, all the way; CJ there - he crouches next to him; CJ stays - he waits at his point, turned to CJ, and waves him on ("follow me" said once), and after 10 s he comes back to CJ\'s side')

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
sc.body = 0                                                # the script body (the fallback): the old way
sc.step(70)
pp = sc.posts[team[2]]
assert pp.stuck and pp.move == 4, ('he gets another way round, then the path network', pp.stuck, pp.move)
passed('Script body (fallback): a man who does not get nearer to his post for 1.5 s is given another way round (the post turned round CJ), then the path network')
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.stuck_men = {team[2]}
acts, whys, stucks, phases, places = [], [], [], [], []
for _ in range(160):
    sc.step(1); pp = sc.posts[team[2]]; acts.append(pp.act); whys.append(pp.why); stucks.append(pp.stuck); phases.append(pp.phase); places.append(at(pp))
assert HCB_ACT_SIDESTEP in acts[:25] and HCB_WHY2_NO_PROGRESS in whys[:25], ('1.5 s without getting nearer: he steps round and another way is looked for', acts[:25], whys[:25])
assert 1 in stucks[:60] and HCB_WHY2_NO_ROUTE in whys[:60], ('the fourth time: the game\'s path network', stucks[:60])
assert HCB_PH_FAILED in phases[:80], ('the sixth time the action has FAILED and says so', phases[:80])
k_ = phases.index(HCB_PH_FAILED)
assert any(d2(p_, places[k_]) > 2.0 for p_ in places[k_:]), 'and the squad gives him another place'
passed('1.0, a man who cannot get on: after 1.5 s with no progress he steps round it and a new way is planned (the reason is given: "no progress"); the fourth time the game\'s path network is asked ("no route"); the sixth time his action has failed and the squad may give him another place')

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

# ---- 1.5 (beta 6): the outer men out of CJ's sight ----
# a shooter appears behind CJ: the quarters turn round - nobody of the outer four crosses CJ's ground on the way (12 m), and they go down at their new places
sc = Scene(); team = detail8(sc); sc.step(120)
g = sc.ped(0., -30., pedtype=GANG, weapon=AK, face=(0., 1.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
closest = 99.
for k_ in range(200):
    if k_ % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    j = by_job(sc)
    closest = min([closest] + [d2(sc.peds[j[k].who]['pos'], sc.cj['pos']) for k in OUTER])
j = by_job(sc)
there = [k for k in OUTER if d2(sc.peds[j[k].who]['pos'], at(j[k])) < 1.5]
assert closest >= 12.0, ('nobody of the outer four came within 12 m of CJ while the quarters turned round', closest)
assert len(there) >= 3 and all(j[k].crouch for k in there), ('down at their new places', there)
front = [k for k in OUTER if at(j[k])[1] < -3]
assert len(front) >= 2, ('two of them in the quarters towards the shooter (south)', {k: at(j[k]) for k in OUTER})
passed('1.5: a shooter appears behind CJ - the four quarters turn round to him, each man going the least way and round CJ, not across his ground (the nearest anybody came: %.0f m); down at the new places, two of them towards the shooter' % closest)

# CJ walks: the outer men walk beside him in their quarters (no stopping in cover every few metres); he stands 4 s - they take places and get down
sc = Scene(); team = detail8(sc); sc.step(120)
sc.cj['vel'] = [0., 1.4, 0.]
acts = {k: [] for k in OUTER}; downs = 0; near = 0
for k_ in range(150):
    sc.step(1); j = by_job(sc)
    for k in OUTER:
        acts[k].append(j[k].act); downs += j[k].crouch
        near += d2(sc.peds[j[k].who]['pos'], sc.cj['pos']) < 12.
changes = sum(sum(1 for a, b_ in zip(v, v[1:]) if a != b_) for v in acts.values()) / 4. / 1.5     # (a minute is 600 looks; this is 150)
assert downs == 0 and near == 0, ('while CJ walks nobody of the four gets down, nobody comes within 12 m of him', downs, near)
assert changes <= 6, ('a steady walk beside CJ: at most 6 changes of action a minute', changes)
sc.cj['vel'] = [0., 0., 0.]; sc.step(100); j = by_job(sc)
there = [k for k in OUTER if d2(sc.peds[j[k].who]['pos'], at(j[k])) < 1.5]
assert len(there) >= 3 and all(j[k].crouch for k in there), ('CJ has stood 10 s: down at their places', there)
passed('1.5: CJ walks - the outer four walk beside him in their quarters (%.1f changes of action a minute, nobody down, nobody within 12 m); he stands - after 4 s each takes a place in his quarter and gets down' % changes)

# ---- 0.7 ----
import ctypes
# an open post is kept too: no cover anywhere - the outer men still take a place each and stay on it (they ran after a moving corner)
sc, team, g = fight8([])
sc.step(40)
j = by_job(sc); kept = {k: at(j[k]) for k in OUTER}; switches = {k: 0 for k in OUTER}
for k_ in range(100):
    sc.peds[g]['pos'] = [30. + 5. * math.sin(k_ * 0.2), 6. * math.sin(k_ * 0.13), 1.]      # the shooter shifts about
    if k_ % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    j = by_job(sc)
    for k in OUTER:
        if d2(at(j[k]), kept[k]) > 0.5: switches[k] += 1; kept[k] = at(j[k])
sc.step(40); j = by_job(sc)
there = sum(d2(sc.peds[j[k].who]['pos'], at(j[k])) < 1.5 for k in OUTER)
# (1.5: one move is allowed - when the shooter's shifting brings CJ into a man's line of fire, that place is no place any more)
assert max(switches.values()) <= 1 and there == 4 and all(15 <= d2(kept[k], sc.cj['pos']) <= 35 for k in OUTER), (switches, there, kept)
passed('No cover anywhere: each outer man still takes a place of his own and keeps it while the shooter shifts about for 10 s (all four on their posts; at most one move each - when CJ comes into his line of fire - none is running after a moving corner)')

# a man far off who has fired at CJ: "sniper - <dir>!"
sc, team, g = contact(threat=(0., 70.))
sc.peds[g]['weapon'] = 34
sc.step(30)
sn = [s_ for s_ in sc.said if s_[1] == HCB_SAY_SNIPER]
assert len(sn) == 1 and sn[0][2] == 0, ('"sniper - ahead" (he is 70 m north, CJ faces north), once', sc.said)
passed('A shooter 70 m off who has fired at CJ: the commander calls "sniper" with the direction, once in 20 s')

# the brain remembers where the detail was attacked: back there in peace the commander says so; the adapter can save and load the list
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(10)
at_, cnt_ = (hcb_vec * 16)(), (ctypes.c_uint16 * 16)()
assert hcb_py.LIB.hcb_places_changed(sc.brain.mem) == 1 and hcb_py.LIB.hcb_places_changed(sc.brain.mem) == 0
assert hcb_py.LIB.hcb_places_get(sc.brain.mem, at_, cnt_) == 1 and abs(at_[0].x) < 1 and cnt_[0] == 1
sc2 = Scene(); detail(sc2)
at_[0].x, at_[0].y = 20., 10.
hcb_py.LIB.hcb_places_set(sc2.brain.mem, at_, cnt_, 1)
sc2.step(30)
been = [s_ for s_ in sc2.said if s_[1] == HCB_SAY_BEEN_HERE]
assert len(been) == 1, sc2.said
sc3 = Scene(); detail(sc3); at_[0].x = 500.
hcb_py.LIB.hcb_places_set(sc3.brain.mem, at_, cnt_, 1); sc3.step(30)
assert not [s_ for s_ in sc3.said if s_[1] == HCB_SAY_BEEN_HERE]
passed('Memory of places: the spot of a fight is remembered (handed to the adapter to save); back within 45 m of one in peace the commander says "we were attacked here before", once; far from any - nothing')

# stealth: CJ creeps crouched in peace - so does the detail
sc = Scene(); team = detail8(sc); sc.step(20)
sc.cj['flags'] |= HCB_PF_DUCKING; sc.cj['vel'] = [0., 1.0, 0.]
sc.step(5)
assert all(p.crouch and p.move <= 1 for p in sc.posts.values()), [(p.crouch, p.move) for p in sc.posts.values()]
passed('Stealth: CJ crouches and creeps while all is quiet - everybody goes down and moves at a walk')

# a burning car: nobody is posted within 12 m of it
sc = Scene(); team = detail8(sc); sc.step(20)
j = by_job(sc); px, py = at(j['point'])
wreck = sc.veh(px + 2., py, flags=HCB_VF_BURNING, health=200.)
sc.step(3)
assert all(d2(at(p), (px + 2., py)) >= 12.0 for p in sc.posts.values() if p.job != HCB_ROLE_LEAD and d2(at(p), sc.cj['pos']) > 4), [at(p) for p in sc.posts.values()]
passed('A burning vehicle: no outer man is posted within 12 m of it (his post is moved straight out)')

# ---- 0.8: the rest of the plan ----
# a grenade lands among the detail: everybody within its radius sprints out of it, the commander calls it
sc = Scene(); team = detail8(sc); sc.step(20)
sc.dangers = [((3., -1., 1.), HCB_DG_GRENADE, 10.)]
sc.step(1)
near = [w_ for w_ in team if d2(sc.peds[w_]['pos'], (3., -1.)) < 10.]
assert near and all(d2(at(sc.posts[w_]), (3., -1.)) >= 12.9 and sc.posts[w_].move == 3 for w_ in near), [(at(sc.posts[w_]), sc.posts[w_].move) for w_ in near]
assert [s_ for s_ in sc.said if s_[1] == HCB_SAY_GRENADE and s_[2] == 1], ('"grenade - right!" (3 m east of CJ, who faces north)', sc.said)
sc.step(25)
assert all(d2(sc.peds[w_]['pos'], (3., -1.)) >= 9.9 for w_ in team), 'two and a half seconds later nobody is within 10 m of it'
sc.dangers = []; sc.step(40)
assert d2(sc.peds[sc.last_out.lead]['pos'], sc.cj['pos']) < 2.5, 'it is gone: back to their places'
passed('A grenade among the detail: every man within 10 m of it sprints straight out (13 m clear), the commander calls "grenade" with the side; when it is gone they come back')

# CJ in the water: nobody follows him in, the helicopter comes over him, the commander says so
sc = Scene(); team = detail8(sc); sc.heli = sc.veh(30, 30, z=25.); sc.step(20)
where = {w_: list(sc.peds[w_]['pos']) for w_ in team}
sc.cj['pos'] = [0., 40., 0.]; sc.in_water = 1
sc.step(20)
assert all(d2(sc.peds[w_]['pos'], where[w_]) < 0.5 and sc.posts[w_].move == 0 for w_ in team), 'each man stays where he stood (on the bank)'
o = sc.last_out
assert o.heli_ok and d2((o.heli_at.x, o.heli_at.y), sc.cj['pos']) < 0.5 and abs(o.heli_at.z - 12.) < 0.1 and [s_ for s_ in sc.said if s_[1] == HCB_SAY_WATER], (o.heli_ok, sc.said)
passed('CJ in the water: nobody follows him in (each man holds where he stands), the helicopter is sent over him 12 m up for the rope, the commander says so')

# a building: the detail holds the door CJ went in by
sc = Scene(); team = detail8(sc); sc.cj['pos'] = [10., 5., 1.]; sc.step(30)
sc.interior = 5; sc.cj['pos'] = [2000., 2000., 1000.]
sc.step(30)
j = by_job(sc)
assert d2(at(j['lead']), (10., 5.)) < 1.6 and all(d2(at(j[k]), (10., 5.)) <= 33 for k in j), ('everybody\'s place is round the door, not 2 km away', [at(p) for p in j.values()])
assert all(d2(sc.peds[w_]['pos'], (10., 5.)) < 35 for w_ in team) and sc.last_out.duty == HCB_DUTY_CALM
sc.interior = 0; sc.cj['pos'] = [10., 6., 1.]; sc.step(10)
assert d2(at(by_job(sc)['lead']), sc.cj['pos']) < 1.6, 'out again: with him as before'
passed('CJ goes into a building: the detail holds the door he went in by (the commander at the door, the outer men at the corners round it) until he is out again')

# CJ drives: the helicopter scouts 50 m ahead of him, and armed men on his way are called
sc = Scene(); team = detail8(sc); sc.heli = sc.veh(0, -40, z=25.); sc.step(5)
car = sc.veh(0, 0, vel=(0., 20., 0.)); sc.cj['vehicle'] = car; sc.cj['vel'] = [0., 20., 0.]
sc.step(3)
o = sc.last_out
assert o.heli_ok and o.heli_at.y - sc.cj['pos'][1] > 45 and abs(o.heli_at.x - sc.cj['pos'][0]) < 2, ('the spot is 50 m ahead on his way', o.heli_at.x, o.heli_at.y, sc.cj['pos'])
amb = sc.ped(sc.cj['pos'][0] + 5., sc.cj['pos'][1] + 80., pedtype=GANG, weapon=AK, face=(0., -1.))
sc.step(6)
assert [s_ for s_ in sc.said if s_[1] == HCB_SAY_AHEAD], sc.said
passed('CJ drives: the helicopter\'s spot is 50 m ahead of him along his way (it scouts the road), and armed men ahead on his way are called once')

# the game's own cover points are tried first
sc, team, g = contact(walls=[(-9., -2.5, -9., 2.5)])          # a wall 9 m west: further than the nearest ring of the brain's own search
sc.hints = [(-9., 0., 1.)]                                         # the game marks it as cover
sc.step(12)
o = sc.last_out
assert o.cover_ok and -11.5 < o.cover_at.x < -9 and abs(o.cover_at.y) < 2.6, ('the spot behind the thing the game calls cover', o.cover_ok, o.cover_at.x, o.cover_at.y)
passed('The game\'s own cover points (walls, corners, cars it marks near CJ) are tried first: CJ is taken behind one the brain\'s rings had not reached yet')


# ---- 0.9: the fifth whole-game log ----
# a blast still in the game's table: avoided like a grenade (the table's radius is not trusted: 6 to 14 m)
sc = Scene(); team = detail8(sc); sc.step(20)
sc.dangers = [((3., -1., 1.), HCB_DG_BLAST, 62.)]
sc.step(1)
near = [w_ for w_ in team if d2(sc.peds[w_]['pos'], (3., -1.)) < 10.]
assert near and all(d2(at(sc.posts[w_]), (3., -1.)) >= 12.9 and sc.posts[w_].move == 3 for w_ in near), [(d2(at(sc.posts[w_]), (3., -1.)), sc.posts[w_].move) for w_ in near]
sc = Scene(); team = detail8(sc); sc.step(20)
sc.dangers = [((3., -1., 1.), HCB_DG_BLAST, 1.5)]
sc.step(1)
near = [w_ for w_ in team if d2(sc.peds[w_]['pos'], (3., -1.)) < 6.]
assert near and all(d2(at(sc.posts[w_]), (3., -1.)) >= 8.9 for w_ in near), 'a small or unknown radius still means 6 m clear'
passed('A blast in the game\'s table: every man within its radius (kept between 6 and 14 m; a radius that is not believable counts as 10) sprints out of it - the old rule let blasts go as "gone off already"')

# a car on a collision course: called with its side, once in 2.5 s
sc = Scene(); team = detail8(sc); sc.step(20)
drv = sc.ped(-40., 0., pedtype=GANG, weapon=0)
sc.veh(-35., 0., vel=(14., 0., 0.), driver=drv)
for _ in range(14): sc.step(1)
cars = [s_ for s_ in sc.said if s_[1] == HCB_SAY_CAR]
assert cars and cars[0][2] == 3, ('"car - left!" (it comes from the west, CJ faces north)', sc.said)
assert len(cars) == 1, '1.3: once for a car'
sc = Scene(); team = detail8(sc); sc.step(20)
drv = sc.ped(-40., 0., pedtype=GANG, weapon=0)
sc.veh(-35., 0., vel=(0., 14., 0.), driver=drv)            # it drives past, not at CJ
sc.step(8)
assert not [s_ for s_ in sc.said if s_[1] == HCB_SAY_CAR], sc.said
passed('A car on a collision course with CJ is called with the side it comes from ("car - left!") - 1.3: once for a car, within 1.5 s of it; one that drives past is not')

# "into cover" is not repeated while CJ stands still: only if he has moved 3 m or after 15 s
sc, team, g = contact(walls=[(-3., -2.5, -3., 2.5)])
sc.step(60)
n1 = len([s_ for s_ in sc.said if s_[1] == HCB_SAY_TAKE_COVER])
assert n1 <= 2, ('CJ stands still: 6 s of fight say it at most twice', n1)
passed('"Into cover" is not repeated every 6 s at a CJ who does not move (a second time only after 15 s or when he has moved)')

# a man far from his post who does not get nearer (fifth log: two men stood 57 s, 37 and 58 m off): by the path network at once
sc = Scene(); team = detail8(sc); sc.step(20)
j = by_job(sc); far = [w_ for w_, p in sc.posts.items() if p.job == HCB_ROLE_POINT][0]
sc.walk_posts = False; sc.body = 0                       # (the script body: with the mod's own body the map does this)
sc.peds[far]['pos'] = [35., 35., 1.]
sc.step(30)
assert sc.posts[far].move == 4 and sc.posts[far].stuck, (sc.posts[far].move, sc.posts[far].stuck)
passed('A man 30 m or more from his post who gets no nearer goes by the path network after the first 1.5 s (not after the third try)')

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_detail_tests.txt').write_text(text)
print(text)
