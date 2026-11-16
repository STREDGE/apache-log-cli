"""Brain 1.3 (Helicover 2.0 beta 4): one test for every rule made after the second 2.0 log, on the host build of the core with the
simulated world of hcb_py (game-like where the log showed the game breaking the brain: a man slides along what is in his way,
steps off a ledge, climbs only what the game's climb can).
    python3 brain/tests/test_rules13.py"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *

results = []


def passed(t):
    results.append('PASS: ' + t)


SQ, M4, SNIPER, AK, GANG, CIV = HCB_ROLE_SQUAD, 31, 34, 30, 7, 4
EIGHT = ((1.2, -0.8), (-1.8, 3.5), (-9., 11.), (-1.6, -2.2), (-12., -8.), (12., -8.), (9., 11.), (16., -7.))


def d2(a, b):
    return math.dist(a[:2], b[:2])


def squad(sc, n=8):
    t = [sc.our(x, y, SQ + k, weapon=SNIPER if k == 7 else M4) for k, (x, y) in enumerate(EIGHT[:n])]
    sc.walk_posts = True
    return t


def pos(sc, who):
    return sc.peds[who]['pos']


def feet(sc, who):
    return pos(sc, who)[2] - 1.


# ================================================================== the marksman (plan item F)
# ------------------------------------------------------------------ a shed 2.5 m high: he walks to it, finds the wall and climbs it himself
sc = Scene(); team = squad(sc); mk = team[7]
sc.blocks = [(18., 8., 26., 16., 2.5)]
sc.high = [(22., 12., 3.5, True)]
sc.step(10)
up_at = None
for k in range(400):
    sc.step(1)
    if up_at is None and feet(sc, mk) > 2.0: up_at = k / 10.
assert up_at is not None and up_at < 30, ('he is up on the shed', up_at, pos(sc, mk))
assert getattr(sc, 'climbs', 0) >= 1, 'by the climb (the game\'s jump-and-climb, given by the mod)'
z_up = [feet(sc, mk) for _ in range(150) if sc.step(1)]
assert min(z_up) > 2.0 and sc.posts[mk].move == 0, ('and he stays up there while CJ is near', min(z_up))
passed('The marksman and a shed 2.5 m high 25 m from CJ: he walks to it, finds the wall in his way and climbs it himself (up after %.1f s), then stays up there watching' % up_at)

# ------------------------------------------------------------------ a roof 4 m up: too high to climb - by a parked car next to the wall, in two climbs
sc = Scene(); team = squad(sc); mk = team[7]
sc.blocks = [(16.2, 10.5, 18.0, 13.5, 1.4), (18., 8., 26., 16., 4.0)]          # the car's roof, then the building
car = sc.veh(17.1, 12., model=400)
sc.high = [(22., 12., 5.0, True)]
sc.step(10)
up_at, on_car = None, False
for k in range(500):
    sc.step(1)
    on_car = on_car or 1.0 < feet(sc, mk) < 2.0
    if up_at is None and feet(sc, mk) > 3.5: up_at = k / 10.
assert on_car and up_at is not None, ('first onto the car, then onto the roof', on_car, up_at, pos(sc, mk))
assert getattr(sc, 'climbs', 0) >= 2
passed('A roof 4 m up (too high for one climb) with a parked car at its wall: the marksman gets onto the car first and from it onto the roof - up after %.1f s' % up_at)

# ------------------------------------------------------------------ a wall too high, nothing to step on: he does not stand at it - he takes the next place
sc = Scene(); team = squad(sc); mk = team[7]
sc.blocks = [(18., 8., 26., 16., 4.0)]
sc.high = [(22., 12., 5.0, True)]
sc.step(10)
for k in range(300): sc.step(1)
assert feet(sc, mk) < 0.5 and d2(pos(sc, mk), (18., 12.)) > 3., ('a 4 m wall and nothing to step on: he is not even sent there', pos(sc, mk))
passed('A roof 4 m up and nothing to step on: he judges before he goes that he cannot get up there - he is not sent to stand at the wall')

# ------------------------------------------------------------------ no roof at all: in a fight a long look from the ground, 28 m out towards the threat
sc = Scene(); team = squad(sc); mk = team[7]
sc.step(30)
peace = list(pos(sc, mk))
g = sc.ped(0., 60., pedtype=GANG, weapon=AK, face=(0., -1.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
for k in range(200):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
p = sc.posts[mk]
assert 22. <= d2(pos(sc, mk), sc.cj['pos']) <= 34. and pos(sc, mk)[1] > 15., ('no roof: a long look up the street the threat came from', pos(sc, mk))
assert d2((p.look.x, p.look.y), (0., 60.)) < 6., 'his eyes on the threat'
passed('No roof, no high ground, no bus: in a fight the marksman improvises a long look - 28 m out from CJ towards where the fire came from, his eyes on it (in peace his place in the detail stands)')

# ------------------------------------------------------------------ high ground on the map (a ramp up to a terrace 3 m above CJ): he walks up
def terrace(x, y):
    if 22. <= x <= 40. and -10. <= y <= 10.: return 3.0
    if 10. <= x < 22. and -3. <= y <= 3.: return (x - 10.) / 12. * 3.0
    return 0.
sc = Scene(); team = squad(sc); mk = team[7]
sc.ground_fn = terrace
for k in range(600):
    sc.step(1)
    if feet(sc, mk) > 2.0: break
assert feet(sc, mk) > 2.0, ('he went up the ramp onto the terrace', pos(sc, mk))
passed('No roof, but the brain\'s map knows ground 3 m above CJ 25 m off, with a ramp: the marksman walks up the ramp and watches from the terrace (up after %.1f s)' % (k / 10.))

# ------------------------------------------------------------------ CJ goes away: 10 s beyond 60 m and he comes down (steps off the edge) and follows
sc = Scene(); team = squad(sc); mk = team[7]
sc.blocks = [(18., 8., 26., 16., 2.5)]
sc.high = [(22., 12., 3.5, True)]
for k in range(400):
    sc.step(1)
    if feet(sc, mk) > 2.0: break
assert feet(sc, mk) > 2.0
sc.high = []
sc.cj['pos'] = [-50., 0., 1.]
for k in range(80): sc.step(1)
assert feet(sc, mk) > 2.0, 'CJ 72 m away for 8 s: he stays up'
for k in range(300): sc.step(1)
assert feet(sc, mk) < 0.5 and d2(pos(sc, mk), sc.cj['pos']) < 40., ('down and on his way to CJ', pos(sc, mk))
passed('On the shed and CJ goes 72 m away: 8 s later he is still up; past 10 s he comes down - off the edge (2.5 m, as the game lets a man drop) - and goes with the detail')

# ------------------------------------------------------------------ no roof, no high ground: the roof of a parked bus
sc = Scene(); team = squad(sc); mk = team[7]
bus = sc.veh(14., 14., model=431)
sc.blocks = [(12.8, 9., 15.2, 19., 2.6)]                       # the bus's roof
for k in range(400):
    sc.step(1)
    if feet(sc, mk) > 2.0: break
assert feet(sc, mk) > 2.0 and d2(pos(sc, mk), (14., 14.)) < 5., ('up on the bus', pos(sc, mk))
passed('No roof and no high ground, but a bus parked 20 m from CJ: the marksman climbs onto its roof (up after %.1f s)' % (k / 10.))

# ------------------------------------------------------------------ a wall he cannot get up after all: three tries, then the next place - no standing at the wall
sc = Scene(); team = squad(sc); mk = team[7]
sc.climb_max = 1.5                                             # (the game's climb fails here: a ledge, a fence on top)
sc.blocks = [(18., 8., 26., 16., 2.5)]
sc.high = [(22., 12., 3.5, True)]
g = sc.ped(-10., -60., pedtype=GANG, weapon=AK, face=(0., 1.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
at_wall, left_at = None, None
for k in range(450):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    if at_wall is None and d2(pos(sc, mk), (22., 12.)) < 5.: at_wall = k
    if at_wall is not None and left_at is None and d2(pos(sc, mk), (22., 12.)) > 7.: left_at = k
assert left_at is not None and left_at - at_wall < 160, ('three tries of 3.5 s and he leaves the wall - not the 20 s timeout', at_wall, left_at)
assert feet(sc, mk) < 0.5 and d2(pos(sc, mk), (18., 12.)) > 6. and pos(sc, mk)[1] < -12., ('gave up the shed, a long look towards the fire instead', pos(sc, mk), getattr(sc, 'climbs', 0))
passed('A wall the game will not let him climb: three tries (3.5 s each), then the shed is marked no good for a minute and he takes the next place - in a fight a long look towards the fire - instead of standing at the wall')

# ------------------------------------------------------------------ "to me": he comes down at once
sc = Scene(); team = squad(sc); mk = team[7]
sc.blocks = [(18., 8., 26., 16., 2.5)]
sc.high = [(22., 12., 3.5, True)]
for k in range(400):
    sc.step(1)
    if feet(sc, mk) > 2.0: break
assert feet(sc, mk) > 2.0
sc.recall = 1; sc.step(2); sc.recall = 0
for k in range(150): sc.step(1)
assert feet(sc, mk) < 0.5 and d2(pos(sc, mk), sc.cj['pos']) < 22., ('"to me": down and back in the detail round CJ', pos(sc, mk))
passed('"To me" from the menu: the marksman comes down off the shed at once and back into the detail round CJ (no new high place for 20 s)')

# ================================================================== fire (plan item A)
# ------------------------------------------------------------------ HOLD FIRE: the man who hurts CJ is answered, the commander says so once a fight
sc = Scene(roe=HCB_ROE_HOLD); team = squad(sc); sc.step(20)
watcher = sc.ped(-25., 10., pedtype=GANG, weapon=AK, face=(1., -0.4))
sc.step(30)
assert not any(o.fire for o in sc.orders.values()), 'an armed man turned to CJ: nobody opens fire'
g = sc.ped(25., 0., pedtype=GANG, weapon=AK, face=(-1., 0.))
sc.step(2)
fired_at = set()
for k in range(300):
    if k % 10 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    if k % 25 == 5: sc.damage(g, 1, 15.)
    sc.step(1)
    fired_at |= {o.target for o in sc.orders.values() if o.fire}
said = [s_ for s_ in sc.said if s_[1] == HCB_SAY_HOLD_FIRE]
assert g in fired_at and watcher not in fired_at, ('the attacker is answered, the man who only watches is not', fired_at)
assert len(said) == 1, ('"fire is held - we answer only those who hit you" once in the fight', said)
passed('HOLD FIRE (the second 2.0 log: CJ killed with twelve rifles silent): nobody opens fire on an armed man who only watches CJ, the man who shoots and hits CJ is answered, and the commander says once that fire is held')

# ================================================================== the helicopter (plan item U)
def heli_scene(blind):
    sc = Scene(); team = squad(sc, 4); sc.step(10)
    heli = sc.veh(0., -30., z=25., cls=HCB_VC_HELI); sc.heli = heli
    gun = [sc.our(0., -30., HCB_ROLE_GUNNER + k, weapon=AK, z=25., vehicle=heli, seat=k + 1) for k in range(2)]
    if blind: sc.los_fn = lambda a, b_: a not in gun
    g = sc.ped(25., 0., pedtype=GANG, weapon=AK, face=(-1., 0.))
    sc.step(2)
    spots = []
    for k in range(150):
        if k % 10 == 0: sc.shot(g, (0., 0., 1.), dst=1)
        o = sc.step(1)
        if o.heli_ok:
            sc.vehs[heli]['pos'] = [o.heli_at.x, o.heli_at.y, o.heli_at.z]
            for m in gun: sc.peds[m]['pos'] = [o.heli_at.x, o.heli_at.y, o.heli_at.z]
            if not spots or d2(spots[-1][1], (o.heli_at.x, o.heli_at.y)) > 2.: spots.append((k, (o.heli_at.x, o.heli_at.y)))
    return spots
blind, clear = heli_scene(True), heli_scene(False)
assert len(clear) == 1, ('the gunners see the man: the helicopter keeps its spot', clear)
gaps = [b_[0] - a_[0] for a_, b_ in zip(blind, blind[1:])]
assert len(blind) >= 3 and min(gaps) >= 30, ('the gunners have no line for 3 s: the helicopter moves round to another spot, and again', blind)
passed('The gunners all have a man and none has a line to him (houses in the way) for 3 s: the helicopter moves round the circle to the next spot (%d spots in 15 s, never sooner than 3 s apart); with a line it keeps its spot' % len(blind))

# ------------------------------------------------------------------ one of ours in his line: he steps out of it (2.5 m, away from CJ) and fires
sc = Scene(roe=HCB_ROE_ARMED); team = squad(sc, 5); sc.step(30)
g = sc.ped(0., 30., pedtype=GANG, weapon=AK, face=(0., 1.))
front = {w for w in team if sc.posts[w].job in (HCB_ROLE_POINT, HCB_ROLE_CLOSE)}
sc.los_fn = lambda a, b_: a not in front                       # (the two in front have a wall in their way: the rear man is the one to fire)
rear = [w for w in team if sc.posts[w].job == HCB_ROLE_REAR][0]
friend = sc.our(-9.5, 0., HCB_ROLE_NONE)                       # one of ours standing in his line
p0 = list(pos(sc, rear)); blocked_t, fired_t = None, None
for k in range(60):
    sc.step(1)
    o = sc.orders.get(rear)
    if o and o.hold == HCB_HOLD_FRIEND and blocked_t is None: blocked_t = k
    if o and o.fire and fired_t is None: fired_t = k; p1 = list(pos(sc, rear))
assert blocked_t is not None and fired_t is not None and 1.8 < d2(p1, p0) < 3.2, ('a man in his line: a step aside, then fire', blocked_t, fired_t, p0, pos(sc, rear))
assert d2(p1, sc.cj['pos']) > d2(p0, sc.cj['pos']), 'the step is away from CJ'
passed('One of ours in his line to the man he is to fire at (the second 2.0 log: "one of ours in the line" in one order of five, and the man stood): after 0.7 s he steps 2.5 m aside, away from CJ, and fires %.1f s after he was first held' % ((fired_t - blocked_t) / 10.))

# ================================================================== movement (plan items V, I, K)
# ------------------------------------------------------------------ no fight: nobody "waits his turn" - the turn to move is a firefight rule only
sc = Scene(); team = squad(sc); sc.step(20)
waits = 0
for k in range(300):
    sc.cj['vel'] = [0., 1.4, 0.] if (k // 40) % 2 == 0 else [0., 0., 0.]
    sc.step(1)
    waits += sum(1 for p_ in sc.posts.values() if p_.why == HCB_WHY2_WAIT_TURN)
assert waits == 0, ('in peace nobody waits for a turn to move (the second 2.0 log: 13 % of all looks were "waiting my turn")', waits)
passed('No firefight (CJ walks and stops): nobody of the eight ever "waits his turn" to move - the turn is a firefight rule only (in the second 2.0 log it was 13 % of all looks)')

# ------------------------------------------------------------------ pace: no flicker
def pace_run(vel_of, ticks=600):
    sc = Scene(); team = squad(sc); sc.step(20)
    acts, changes, cj_changes, last = {}, 0, 0, None
    for k in range(ticks):
        v = vel_of(k)
        if last is not None and v != last: cj_changes += 1
        last = v; sc.cj['vel'] = list(v)
        sc.step(1)
        for w, p_ in sc.posts.items():
            if w in acts and acts[w] != p_.act: changes += 1
            acts[w] = p_.act
    return changes / len(team) / (ticks / 600.), cj_changes / (ticks / 600.)
SQUARE = [(1.4, 0., 0.), (0., 1.4, 0.), (-1.4, 0., 0.), (0., -1.4, 0.)]
steady, _ = pace_run(lambda k: SQUARE[(k // 100) % 4])
assert steady <= 6, ('CJ walks steadily round a square: a man changes his action at most six times a minute', steady)
busy, cj_n = pace_run(lambda k: [(0., 1.4, 0.), (0., 3.0, 0.), (0., 0., 0.), (0., 5.5, 0.)][(k // 25) % 4])
assert busy <= 1.25 * cj_n, ('CJ changes his pace %d times a minute: a man follows each change once, no flicker in between' % cj_n, busy)
passed('Pace without flicker: CJ walking round a square - a man changes his action %.1f times a minute (the second 2.0 log: 18.9); CJ changing pace %d times a minute - %.1f, once for each of CJ\'s changes and no more' % (steady, cj_n, busy))

# ------------------------------------------------------------------ a man who has somewhere to go is never told to stand where he is (the map said "blocked")
sc = Scene(); team = squad(sc); sc.step(10)
sc.walls = [(6., -6., 6., 6.), (-6., 8., 6., 8.)]
bad, moving = 0, 0
for k in range(400):
    sc.cj['vel'] = [0., 1.4, 0.] if k < 200 else [0., -1.4, 0.]
    was = {w: list(pos(sc, w)) for w in team}                 # (where he stood when the brain looked)
    sc.step(1)
    for w, p_ in sc.posts.items():
        if p_.move and d2(was[w], (p_.at.x, p_.at.y)) > 2.5:
            moving += 1
            bad += d2(was[w], (p_.via.x, p_.via.y)) < 0.3
# (and CJ suddenly 30 m off behind a long wall: every man needs a way round, asked of the map's thread - while it is being found he goes on)
sc.cj['vel'] = [0., 0., 0.]; sc.cj['pos'] = [0., 32., 1.]; sc.walls = sc.walls + [(-25., 18., 25., 18.)]
sc.path_delay = 6                                                # (the way comes 0.6 s later: meanwhile nobody stands)
for k in range(120):
    was = {w: list(pos(sc, w)) for w in team}
    sc.step(1)
    for w, p_ in sc.posts.items():
        if p_.move and d2(was[w], (p_.at.x, p_.at.y)) > 2.5 and p_.act != HCB_ACT_SIDESTEP:   # (a step round that is made: a moment at its point)
            moving += 1
            bad += d2(was[w], (p_.via.x, p_.via.y)) < 0.3
assert moving > 100 and bad == 0, ('on his way, his next point is never where he stands (the second 2.0 log: 68 % of "blocked" answers left him standing)', bad, moving)
passed('Walls about and CJ walking, then CJ 30 m off behind a long wall with the ways coming 0.6 s late: in %d looks of a man on his way his next point was never the spot he stands on (the second 2.0 log: "leg blocked" or "a way is being looked for" left the man standing - 68 %% of "blocked" answers)' % moving)

# ================================================================== the detail with CJ (plan items D, E)
# ------------------------------------------------------------------ ASSAULT, CJ runs away from the squad: everybody back to him - and that holds for 8 s
sc = Scene(); team = squad(sc); sc.step(20)
sc.umode = HCB_UMODE_ASSAULT
g = sc.ped(0., 60., pedtype=GANG, weapon=AK, face=(0., -1.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
for k in range(150):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
OUT4 = (HCB_ROLE_POINT, HCB_ROLE_POINT2, HCB_ROLE_REAR, HCB_ROLE_REAR2)
sc.cj['vel'] = [0., -3.5, 0.]
tasks, la_at = [], None
for k in range(140):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    o = sc.step(1); tasks.append(o.task)
    if la_at is None and o.task == HCB_TASK_REGROUP:
        four = [pos(sc, w) for w, p_ in sc.posts.items() if p_.job in OUT4]
        cx, cy = sum(p_[0] for p_ in four) / len(four), sum(p_[1] for p_ in four) / len(four)
        la_at = math.dist((cx, cy), sc.cj['pos'][:2]); sc.cj['vel'] = [0., 0., 0.]
first = tasks.index(HCB_TASK_REGROUP) if HCB_TASK_REGROUP in tasks else None
assert first is not None and la_at < 58. and all(t_ == HCB_TASK_REGROUP for t_ in tasks[first:first + 80]), ('CJ runs off: REGROUP before he is 60 m from the four, held 8 s', first, la_at)
passed('ASSAULT, CJ runs away from the squad: the task is REGROUP when he is %.0f m from the four who are out and going away (not only at 60 m), and is held 8 s - no back-and-forth while he stands still again' % la_at)

# ================================================================== fire on the move (plan item T)
# ------------------------------------------------------------------ CJ moves off under fire: the men on the move go facing the attacker (the mod: go-and-shoot, backing away)
sc = Scene(); team = squad(sc); sc.step(20)
moving_calm = sum(1 for k in range(30) if sc.step(1) is not None for p_ in sc.posts.values() if p_.move and p_.face)
g = sc.ped(18., 6., pedtype=GANG, weapon=AK, face=(-1., 0.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
faced, moved, back = 0, 0, 0
sc.cj['vel'] = [-3.0, 0., 0.]
for k in range(80):
    if k % 8 == 0: sc.shot(g, (sc.cj['pos'][0], sc.cj['pos'][1], 1.), dst=1)
    sc.step(1)
    for w, p_ in sc.posts.items():
        if p_.move and w in sc.orders and sc.orders[w].target == g and d2(pos(sc, w), sc.peds[g]['pos']) < 33.:
            moved += 1; faced += p_.face
            gx, gy = sc.peds[g]['pos'][0] - pos(sc, w)[0], sc.peds[g]['pos'][1] - pos(sc, w)[1]
            vx, vy = p_.via.x - pos(sc, w)[0], p_.via.y - pos(sc, w)[1]
            back += p_.face and gx * vx + gy * vy < 0
assert moving_calm == 0, 'no enemy: nobody walks "facing" anybody'
assert moved > 50 and faced / moved > 0.9 and back > 20, ('on the move with the attacker within 35 m: facing him - and backing away from him', moved, faced, back)
passed('CJ moves off under fire: of the men on the move who have the attacker within 33 m for their man %d %% go facing him (the mod makes it go-and-shoot: weapon on him, feet where they go), %d looks of them backing away from him; with no enemy nobody does' % (round(100 * faced / moved), back))

# ================================================================== cars and tokens (plan items B, M, I)
# ------------------------------------------------------------------ a passer-by's car runs down a guard standing in the road: an accident, not an attack
sc = Scene(); team = squad(sc); sc.step(20)
civ = sc.ped(-30., 9., pedtype=CIV)
car_ = sc.veh(-30., 9., vel=(12., 0., 0.), driver=civ)
guard = team[2]; sc.peds[guard]['pos'] = [-6., 9., 1.]; sc.walk_posts = False
sc.step(2)
sc.damage(civ, guard, 25., weapon=49)
fired = set()
for k in range(30):
    sc.step(1); fired |= {o.target for o in sc.orders.values() if o.fire}
assert civ not in fired and sc.brain.cls(civ) < HCB_CLS_THREAT, ('a guard hit by a passing car: the driver is not an attacker', sc.brain.cls(civ), fired)
passed('A passer-by\'s car that was not coming at anybody runs down a guard standing in the road (the game names the driver): an accident - the driver is no attacker and nobody fires at him')

# ------------------------------------------------------------------ "car!" once for a car, however often it comes
sc = Scene(); team = squad(sc); sc.step(10)
d_ = sc.ped(-20., 0.5, pedtype=CIV)
car_ = sc.veh(-20., 0.5, vel=(15., 0., 0.), driver=d_)
cars_said = 0
for k in range(300):
    if k % 100 == 0: sc.vehs[car_]['pos'] = [-20., 0.5, 1.]; sc.vehs[car_]['vel'] = [15., 0., 0.]     # it comes again and again
    if k % 100 == 25: sc.vehs[car_]['vel'] = [0., 0., 0.]
    o = sc.step(1); cars_said += o.say == HCB_SAY_CAR
assert cars_said == 1, ('"car!" once for the car, though it came at CJ three times 10 s apart', cars_said)
passed('A car that comes at CJ three times, 10 s apart: "car - left!" once for it (the second 2.0 log: 13 warnings, no car hit him)')

# ------------------------------------------------------------------ the gunners' tokens are their own: three guards on the man do not stop the helicopter
sc = Scene(); team = squad(sc); sc.step(10)
heli = sc.veh(-20., -30., z=25., cls=HCB_VC_HELI); sc.heli = heli         # (further from him than the guards: they take him first)
gun = [sc.our(-20., -30., HCB_ROLE_GUNNER + k, weapon=AK, z=25., vehicle=heli, seat=k + 1) for k in range(2)]
g = sc.ped(12., 3., pedtype=GANG, weapon=AK, face=(-1., 0.))   # (12 m from CJ: the guards' man first)
sc.step(2)
gun_fire, gun_enough, sq_on = 0, 0, 0
for k in range(60):
    if k % 8 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    for w in gun:
        o = sc.orders.get(w)
        if o and o.target == g: gun_fire += o.fire; gun_enough += o.hold == HCB_HOLD_ENOUGH
    sq_on = max(sq_on, sum(1 for w in team if w in sc.orders and sc.orders[w].target == g and sc.orders[w].hold != HCB_HOLD_ENOUGH))
assert sq_on >= 3 and gun_fire > 20 and gun_enough == 0, ('three guards on him and both gunners too', sq_on, gun_fire, gun_enough)
passed('One attacker, three guards on him: the two door gunners still fire at him - their tokens are their own (the second 2.0 log: 18 % of the gunners\' looks were "enough on him already")')

# ------------------------------------------------------------------ no firefight near (an attacker 60 m off): nobody waits for a turn to move
sc = Scene(); team = squad(sc); sc.step(20)
g = sc.ped(0., 62., pedtype=GANG, weapon=AK, face=(0., -1.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1); sc.step(5)
for w in team: sc.peds[w]['pos'] = [sc.peds[w]['pos'][0] * 0.2, -22. + sc.peds[w]['pos'][1] * 0.2, 1.]    # all eight bunched 22 m south: everybody has to move
waits, fight_looks = 0, 0
for k in range(200):
    if k % 12 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    o = sc.step(1)
    fight_looks += o.duty >= HCB_DUTY_COVER
    waits += sum(1 for p_ in sc.posts.values() if p_.why == HCB_WHY2_WAIT_TURN)
assert fight_looks > 100 and waits == 0, ('a fight, but the attacker is 60 m off: nobody waits his turn to move', fight_looks, waits)
passed('A fight with the attacker 60 m off (no firefight near CJ): the detail takes its places without anybody waiting his turn - the turn is for a firefight within 40 m')

# ================================================================== windows of the second 2.0 log (the player's two black boxes, on the new core)
DATA = Path(__file__).resolve().parent / 'data'


def run_window(name):
    fight = load_fight(DATA / name)
    brain, ticks = Brain(seed=7), []
    for s in fight:
        out = brain.think(s)
        ticks.append((s, hcb_out.from_buffer_copy(bytes(out))))
    return ticks


# (a) HOLD FIRE on, a policeman shoots CJ down from 76 to 2 health (the guards' answer in 1.2: "not allowed by the rule", every one)
ticks = run_window('log20b_hold_fire.json.gz')
assert all(s.roe == HCB_ROE_HOLD for s, _ in ticks)
shooters = {e.src for s, _ in ticks for e in s.events[:s.n_events] if e.type == HCB_EV_DAMAGE and e.dst == s.player.id and e.src}
after, on_him, roe_held = 0, 0, 0
hit_t = min(s.time for s, _ in ticks for e in s.events[:s.n_events] if e.type == HCB_EV_DAMAGE and e.dst == s.player.id and e.src)
for s, o in ticks:
    if s.time < hit_t + 1000: continue
    for od in o.orders[:o.n_orders]:
        if od.who in [s.ours[i] for i in range(s.n_ours) if s.our_role[i] >= HCB_ROLE_SQUAD]:
            after += 1; on_him += od.target in shooters; roe_held += od.hold == HCB_HOLD_ROE and od.target in shooters
assert shooters and after > 500 and on_him / after > 0.8 and roe_held == 0, (shooters, after, on_him, roe_held)
passed('The black box of the second 2.0 log, HOLD FIRE on and a policeman shooting CJ down to 2 health: on the new core %d %% of the guards\' orders after his first hit are on him, none of those "held by the rule" (in 1.2 every one was) - whether a round goes is the line of sight, which the box answers only for the old core\'s questions' % round(100 * on_him / after))

# (b) cars driving past CJ on the road (the 1.2 core called them "ramming" and fired at their drivers)
ticks = run_window('log20b_traffic.json.gz')
bad, warned, false_warn, passing = [], 0, 0, 0
for k, (s, o) in enumerate(ticks):
    cars = {v.driver: v for v in s.vehs[:s.n_vehs] if v.driver and v.cls == HCB_VC_CAR}
    peds = {p.id: p for p in s.peds[:s.n_peds]}
    passing += sum(1 for v in cars.values() if math.hypot(v.vel.x, v.vel.y) > 8 and math.dist((v.pos.x, v.pos.y), (s.player.pos.x, s.player.pos.y)) < 6)
    if o.say == HCB_SAY_CAR:
        warned += 1
        rams = [m.id for m in o.marks[:o.n_marks] if m.why == HCB_WHY_RAMMING]
        near = min((math.dist((v.pos.x, v.pos.y), (s2.player.pos.x, s2.player.pos.y)) for s2, _ in ticks[k:k + 30] for v in s2.vehs[:s2.n_vehs] if v.id in rams), default=99.)
        false_warn += near > 4.
    for od in o.orders[:o.n_orders]:
        v = cars.get(od.target)
        if od.fire and v is not None and math.hypot(v.vel.x, v.vel.y) > 3 and peds.get(od.target) and peds[od.target].pedtype in (4, 5) and s.player.target != od.target:
            bad.append((s.time, od.target))
assert passing >= 15 and not bad and false_warn == 0 and warned <= 2, (passing, bad[:5], warned, false_warn)
passed('The black box, cars driving past CJ (%d looks of a car at 8 m/s or more within 6 m of him): no fire at the driver of a moving car that is a passer-by; "car!" %d time(s) - for a car that then came within 4 m of him as he walked into the road (in 1.2: half the fire went at such drivers, the wanted level came of it, and 13 warnings for no car)' % (passing, warned))

# (c) the commander far from CJ (1.2: "CJ, follow me - run to me" from 25-68 m, 21 times in 5 minutes)
ticks = run_window('log20b_commander_far.json.gz')
far_calls, calls_ = 0, 0
for s, o in ticks:
    if o.say in (HCB_SAY_TAKE_COVER,):
        calls_ += 1
        lead = next((p for p in s.peds[:s.n_peds] if p.id == o.lead), None)
        if lead is None or math.dist((lead.pos.x, lead.pos.y), (s.player.pos.x, s.player.pos.y)) > 6.: far_calls += 1
assert far_calls == 0, (far_calls, calls_)
passed('The black box, the commander 20-60 m from CJ for 48 s: "CJ, follow me - to the cover" is never said by a commander more than 6 m from CJ (said %d times near him); from afar the radio only gives the side of the cover' % calls_)

text = '\n'.join(results) + '\nThe core only, in a simulated world. Nothing here has run in the game.\n'
print(text)
