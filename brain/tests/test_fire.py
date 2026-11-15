"""Helicover Brain, stage 2 (core): who of ours fires at whom - the player's fire rule, the hard rules that protect CJ,
our own people and bystanders, the sharing out of targets, and human timing. The real C core, hand-made scenes."""
import math, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


GANG, COP, CIV, GROVE = 7, 6, 4, 8
PISTOL, AK, M4, BAT = 22, 30, 31, 5
HOLD = {v: k[9:] for k, v in CONSTS.items() if k.startswith('HCB_HOLD_')}


# the default team stands in a line abreast east of CJ, so that none of them has CJ or a mate in his line to targets in the east
def squad(sc, places=((2, 7), (2, -7), (5, 12), (5, -12)), weapon=M4):
    return [sc.our(x, y, HCB_ROLE_SQUAD + k, weapon=weapon) for k, (x, y) in enumerate(places)]


def firing(sc, at=None):
    return [w for w, o in sc.orders.items() if o.fire and (at is None or o.target == at)]


def holds(sc):
    return {w: HOLD[o.hold] for w, o in sc.orders.items()}


def run(sc, ticks):
    """Step and collect, per shooter, the ticks on which he fired."""
    fired = {}
    for k in range(ticks):
        sc.step(1)
        for w in firing(sc):
            fired.setdefault(w, []).append(k)
    return fired


# ------------------------------------------------------------------ the first round: questions, reaction, fire
sc = Scene()
team = squad(sc)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.step(1)
assert not firing(sc) and set(holds(sc).values()) == {'NO_LOS'} and len(sc.asked) == 4 and all(b_ == g for _, b_ in sc.asked), (holds(sc), sc.asked)
assert all(o.target == g and o.ready for o in sc.orders.values()), 'weapons come up on him at once'
first = {}
for k in range(1, 12):
    sc.step(1)
    for w in firing(sc, g):
        first.setdefault(w, k * 100)
cfg = sc.brain.cfg
assert set(first) and all(cfg.react_min_ms <= t <= cfg.react_max_ms + 100 for t in first.values()), first
assert len(set(first.values())) >= 2, 'they do not all open fire on the same tick'
assert len(firing(sc, g)) <= 3 and sum(1 for o in sc.orders.values() if o.target == g) >= 3
passed('An armed gang member turns to CJ 25 m away: weapons on him at once, the line of sight is asked for, and the first rounds go out %d-%d ms later - a human reaction, not the same instant for everybody' % (min(first.values()), max(first.values())))

# ------------------------------------------------------------------ the player's fire rule
def rule(roe, **kw):
    sc = Scene(roe=roe, **kw)
    squad(sc)
    return sc


sc = rule(HCB_ROE_HOLD)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
assert not run(sc, 30) and set(holds(sc).values()) == {'ROE'}
passed('HOLD FIRE: nobody fires, even at a man shooting CJ')
for roe, fires in ((HCB_ROE_DEFEND, False), (HCB_ROE_ARMED, True), (HCB_ROE_LEGACY_ALL, True)):
    sc = rule(roe)
    watch = sc.ped(25, 0, pedtype=GANG, weapon=AK, face='away')
    civ = sc.ped(-20, 5, weapon=PISTOL)
    fired = run(sc, 30)
    assert bool(fired) == fires, (roe, fired)
    assert not any(o.target == civ for o in sc.orders.values()), 'an armed civilian is nobody\'s target under any rule'
    if not fires:
        assert set(holds(sc).values()) == {'COVERING'} and all(o.target == watch and o.ready and not o.fire for o in sc.orders.values())
passed('DEFEND: an armed gang member who is not looking at CJ is covered - weapons on him, no fire. ARMED ONLY (and the old "fire at all"): he is engaged. An armed civilian never is')
sc = rule(HCB_ROE_FOLLOW)
a, b_ = sc.ped(25, 0, pedtype=GANG, weapon=AK), sc.ped(0, 25, pedtype=GANG, weapon=AK)
sc.shot(a, (0., 0., 1.), dst=1)
assert not run(sc, 20), 'FOLLOW: not even an attacker until CJ points at him'
sc.cj['target'] = b_
fired = run(sc, 15)
assert fired and all(o.target == b_ for o in sc.orders.values() if o.fire) and not any(o.target == a and o.fire for o in sc.orders.values())
sc.cj['target'] = 0
run(sc, 5)
run(sc, int(sc.brain.cfg.follow_ms / 100) + 15)
assert not firing(sc), 'three seconds after CJ stopped pointing, they stop'
sc.shot(1, (25., 0.3, 1.))                             # CJ fires a round that passes 0.3 m from a
fired = run(sc, 8)
assert fired and all(o.target == a for o in sc.orders.values() if o.fire) and firing(sc, a) is not None, holds(sc)
run(sc, int(sc.brain.cfg.follow_ms / 100) + 15)
assert not firing(sc)
civ = sc.ped(30, -10)
sc.step(2)
sc.damage(1, civ, 30)                                  # CJ shoots a passer-by: his decision, they follow
hit = False
for _ in range(10):
    sc.step(1)
    hit = hit or bool(firing(sc, civ))
assert hit, holds(sc)
passed('WHERE I SHOOT: only the man CJ locks on, hits, or whose head his rounds pass - and for 3 s after; an attacker CJ ignores is left alone')

# ------------------------------------------------------------------ police
for policy, attacked, fires in ((HCB_POLICE_ANSWER, False, False), (HCB_POLICE_ANSWER, True, True), (HCB_POLICE_EVADE, True, False)):
    sc = rule(HCB_ROE_DEFEND, wanted=2)
    sc.police = policy
    cop = sc.ped(25, 0, pedtype=COP, weapon=PISTOL)
    if attacked:
        sc.shot(cop, (0., 0., 1.), dst=1)
    fired = run(sc, 25)
    assert bool(fired) == fires, (policy, attacked, fired, holds(sc))
    if not fires:
        assert all(not o.fire for o in sc.orders.values())
passed('Police with a wanted level: an armed policeman is covered, fired at only once he has attacked ("answer"); with "evade" never')

# ------------------------------------------------------------------ CJ in the line of fire
def one_shooter(shooter_at, target_at, cj_at=(0., 0.), ticks=12, **kw):
    sc = Scene()
    me = sc.our(shooter_at[0], shooter_at[1], HCB_ROLE_SQUAD, weapon=M4)
    sc.cj['pos'] = [cj_at[0], cj_at[1], 1.]
    t = sc.ped(target_at[0], target_at[1], pedtype=GANG, weapon=AK, **kw)
    sc.shot(t, (cj_at[0], cj_at[1], 1.), dst=1)
    fired = run(sc, ticks)
    return bool(fired), HOLD[sc.orders[me].hold], sc


assert one_shooter((-10, 0), (10, 0)) == (False, 'CJ_IN_LINE', one_shooter((-10, 0), (10, 0))[2]) or one_shooter((-10, 0), (10, 0))[:2] == (False, 'CJ_IN_LINE')
assert one_shooter((-10, 3), (10, 3))[0], 'the same shot 3 m to the side of him is fine'
assert one_shooter((-10, 1.8), (10, 1.8))[:2] == (False, 'CJ_IN_LINE'), 'within 2 m (+2 cm per metre of range)'
assert one_shooter((-60, 3), (20, 3))[:2] == (False, 'CJ_IN_LINE'), '3 m is not enough 60 m down range: 2 m + 60 * 0.02 = 3.2 m'
assert one_shooter((30, 0), (15, 0))[:2] == (False, 'CJ_BEHIND'), 'CJ 15 m behind the target'
assert one_shooter((70, 0), (55, 0))[0], 'CJ 55 m behind the target: beyond the backstop distance'
assert one_shooter((0.6, 0), (20, 0))[0], 'CJ at the shooter\'s shoulder, behind the muzzle: not in the line'
assert one_shooter((1, 0), (-20, 0))[:2] == (False, 'CJ_IN_LINE'), 'the same shooter turned round to fire past CJ'
passed('No order to fire when CJ is within 2 m of the line (wider with range), or stands up to 40 m behind the target; CJ behind the muzzle does not block')

# ------------------------------------------------------------------ our own people, allies, bystanders
def with_third(third_at, third_type=GROVE, ours=False, target_at=(20, 0), attacker=True, weapon=AK, **kw):
    sc = Scene()
    me = sc.our(-10, 6, HCB_ROLE_SQUAD, weapon=M4)
    sc.cj['pos'] = [0., -8., 1.]
    t = sc.ped(target_at[0] - 10, 6, pedtype=GANG, weapon=weapon, **kw)
    if attacker:
        sc.shot(t, (0., -8., 1.), dst=1)
    if ours:
        third = sc.our(third_at[0] - 10, 6 + third_at[1], HCB_ROLE_SQUAD + 1, weapon=0)
    else:
        third = sc.ped(third_at[0] - 10, 6 + third_at[1], pedtype=third_type)
    fired = run(sc, 12)
    return bool(me in fired), HOLD[sc.orders[me].hold]


assert with_third((10, 0.5), ours=True) == (False, 'FRIEND') and with_third((10, 0.5)) == (False, 'FRIEND'), 'a guard or a Grove homie in the line'
assert with_third((10, 2.0), ours=True)[0] and with_third((30, 0.3), ours=True) == (False, 'FRIEND') and with_third((50, 0.3), ours=True)[0], 'beside the line / 10 m behind the target / 30 m behind it'
assert with_third((10, 0.4), third_type=CIV) == (False, 'BYSTANDER') and with_third((10, 1.2), third_type=CIV)[0], 'a passer-by in front of the target'
assert with_third((25, 0.3), third_type=CIV)[0], 'a passer-by behind a man who is shooting CJ does not save him'
assert with_third((45, 0.3), third_type=CIV, attacker=False, target_at=(38, 0), weapon=PISTOL) == (False, 'BYSTANDER'), '... but 7 m behind a man who has not fired yet he does stop the shot'
assert with_third((60, 0.3), third_type=CIV, attacker=False, target_at=(38, 0), weapon=PISTOL)[0], '... not 22 m behind him'
passed('Our own people and allies in or behind the line stop the shot; so does a passer-by in front of the target, and one behind it unless the target is already hurting CJ')

# ------------------------------------------------------------------ vehicles
def car_target(car_at, health=1000., flags=0, vel=(0., 0., 0.), attacker=True):
    sc = Scene()
    me = sc.our(0, 12, HCB_ROLE_SQUAD, weapon=M4)
    d = sc.ped(car_at[0], car_at[1], pedtype=GANG, weapon=AK)
    v = sc.veh(car_at[0], car_at[1], driver=d, health=health, flags=flags, vel=vel)
    if attacker:
        sc.shot(d, (0., 0., 1.), dst=1)
    fired = run(sc, 12)
    o = sc.orders[me]
    return bool(fired), HOLD[o.hold], o.aim_at, sc


assert car_target((12, 0))[:3] == (True, car_target((12, 0))[1], HCB_AIM_DRIVER), 'a healthy car beside CJ: at the man, not the engine'
assert car_target((12, 0), health=650.)[:2] == (False, 'CAR_NEAR') and car_target((12, 0), health=900., flags=HCB_VF_BURNING)[:2] == (False, 'CAR_NEAR')
far = car_target((60, 0), health=300.)
assert far[0] and far[2] == HCB_AIM_DRIVER, 'a wreck-to-be 60 m away may be stopped by fire - still aimed at the man'
sc = Scene()
me = sc.our(14, 14, HCB_ROLE_SQUAD, weapon=M4)
d = sc.ped(-20, 0.5, pedtype=CIV)
v = sc.veh(-20, 0.5, vel=(12., 0., 0.), driver=d)
run(sc, 6)
o = sc.orders[me]
assert o.target == d and o.aim_at == HCB_AIM_TYRE and (o.fire or o.hold in (HCB_HOLD_REACTING, HCB_HOLD_PAUSE, HCB_HOLD_NO_LOS)), (o.target, o.aim_at, HOLD[o.hold])
passed('Vehicles: fire at a man in a car is aimed at him; a car below 700 health or burning within 18 m of CJ or ours is not fired at at all; far away it may be; a car bearing down on CJ gets its tyres shot')

# ------------------------------------------------------------------ range, the far side of the helicopter, walls
sc = Scene()
me = sc.our(0, 3, HCB_ROLE_SQUAD, weapon=PISTOL)
far = sc.ped(60, 0, pedtype=GANG, weapon=AK)
sc.shot(far, (0., 0., 1.), dst=1)
assert not run(sc, 10) and HOLD[sc.orders[me].hold] == 'RANGE'
sc = Scene()
sc.heli = sc.veh(0, 5, z=25., cls=HCB_VC_HELI, vel=(0., 0., 0.))     # facing north: its right side is east
pilot = sc.our(0, 5, HCB_ROLE_PILOT, z=25.)
right = sc.our(1.4, 6, HCB_ROLE_GUNNER + 0, weapon=M4, z=25.)
left = sc.our(-1.4, 6, HCB_ROLE_GUNNER + 1, weapon=M4, z=25.)
east = sc.ped(40, 6, pedtype=GANG, weapon=AK)
sc.shot(east, (0., 0., 1.), dst=1)
fired = run(sc, 12)
assert right in fired and left not in fired and HOLD[sc.orders[left].hold] == 'NO_LOS' and pilot not in sc.orders, (fired, holds(sc))
passed('A pistol does not reach 60 m; a door gunner does not fire across his own cabin (the gunner on that side does); the pilot gets no fire orders')
sc = Scene()
team = squad(sc)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
sc.walls = [(15, -20, 15, 20)]
fired = run(sc, 15)
assert not fired and set(holds(sc).values()) == {'NO_LOS'}
asked = sum(1 for s_ in sc.snapshots[-10:] if s_.n_los)
assert asked == 10, ('the question is asked again on every tick', asked)
sc.walls = []
fired = run(sc, 10)
assert fired and min(min(v) for v in fired.values()) <= 6
sc.walls = [(15, -20, 15, 20)]
run(sc, 2)
assert not firing(sc), 'he steps behind a wall: fire stops on the second tick'
passed('Nobody fires through a wall: the line of sight is asked for on every tick, fire starts when it clears and stops within 0.2 s when it closes')

# ------------------------------------------------------------------ door gunners: rounds made by the script along a checked line
def heli_scene(cj_at=(0., 0.), z=31., rounds=True, **kw):
    """rounds=True: the 1.3 door gunner, whose rounds the script makes along a checked line (the round API is kept and tested);
    rounds=False: the 1.4 door gunner, who fires his own weapon and is judged like a guard on foot."""
    sc = Scene(**kw)
    sc.brain.cfg.gunner_weapon = 0. if rounds else 1.
    sc.cj['pos'] = [cj_at[0], cj_at[1], 1.]
    sc.heli = sc.veh(0, 40, z=z, cls=HCB_VC_HELI)            # facing north: the right door looks east
    pilot = sc.our(0, 41, HCB_ROLE_PILOT, z=z)
    sc.vehs[sc.heli]['driver'] = pilot
    front = sc.our(1.4, 41, HCB_ROLE_GUNNER + 0, weapon=M4, z=z)
    rear = sc.our(1.4, 39, HCB_ROLE_GUNNER + 2, weapon=M4, z=z)
    return sc, front, rear


sc, front, rear = heli_scene(cj_at=(-30., 0.))
g = sc.ped(3, 75, pedtype=GANG, weapon=AK, z=31.)      # on a roof ahead of the helicopter, level with it: the rear gunner's line passes 0.1 m from the front gunner
sc.shot(g, (-30., 0., 1.), dst=1)
fired = run(sc, 12)
assert front in fired and rear in fired, (fired, holds(sc))
sc, front, rear = heli_scene(cj_at=(-30., 0.))
mate = sc.our(2.2, 57, HCB_ROLE_SQUAD, weapon=M4, z=31.)   # ... but one of ours half-way down that same line does stop it
g = sc.ped(3, 75, pedtype=GANG, weapon=AK, z=31.)
sc.shot(g, (-30., 0., 1.), dst=1)
fired = run(sc, 12)
assert rear not in fired and HOLD[sc.orders[rear].hold] == 'FRIEND', (fired, holds(sc))
passed('Two gunners in one door: the rear one fires past the man kneeling beside him (his rounds start 5.5 m out, clear of the helicopter) - in the real fight this cost 9% of the fire; one of ours further down the line still stops the shot')

# ------------------------------------------------------------------ 1.4: the door gunner fires his own weapon
def gstate(sc, who, target):
    return sc.brain.squad(who, target, sc.time, sc.peds[who]['pos'], sc.peds[target]['pos'], sc.cj['pos'], [sc.peds[o]['pos'] for o in sc.ours if o != who])
# CJ sits in the helicopter: the gunner on the side of a man who fires at it answers (CJ is inside, behind the cabin wall) ...
sc, front, rear = heli_scene(cj_at=(-0.3, 40.), rounds=False)
sc.cj['vehicle'] = sc.heli
g = sc.ped(30, 40, pedtype=GANG, weapon=AK, z=1.)
sc.shot(g, (0., 40., 31.), dst=1)
states = []
for _ in range(14):
    sc.step(1)
    states.append(gstate(sc, front, g))
assert 2 in states and 3 in states and states.index(2) >= 1, ('his own weapon, in bursts (fire / a breath) after the reaction time', states)
# ... but not when CJ stands on the ground 10 m behind the man: a round of the game flies on past its target (a script's round did not)
sc, front, rear = heli_scene(cj_at=(40., 41.8), z=2., rounds=False)
g = sc.ped(30, 41, pedtype=GANG, weapon=AK)
sc.shot(g, (40., 41.8, 1.), dst=1)
seen = []
for _ in range(12):
    sc.step(1)
    seen.append(gstate(sc, front, g))
assert 2 not in seen and not firing(sc), ('CJ behind the man: no fire with a weapon whose round flies on', seen, holds(sc))
# ... and the man beside him in the door counts: the rear gunner's line passes 0.1 m from the front one
sc, front, rear = heli_scene(cj_at=(-30., 0.), rounds=False)
g = sc.ped(3, 75, pedtype=GANG, weapon=AK, z=31.)
sc.shot(g, (-30., 0., 1.), dst=1)
fired = run(sc, 12)
assert front in fired and rear not in fired and HOLD[sc.orders[rear].hold] == 'FRIEND', (fired, holds(sc))
passed('1.4 door gunners fire their own weapon: in bursts the brain paces, also with CJ sitting in the cabin (behind the cabin wall); a man 10 m in front of CJ on the line is not fired at (a round of the game flies on), and the rear gunner holds when his mate in the door is in his line')

sc, front, rear = heli_scene(cj_at=(40., 41.8), z=2.)  # the helicopter hovers low: a flat line, and CJ stands 10 m behind the target on it
g = sc.ped(30, 41, pedtype=GANG, weapon=AK)
sc.shot(g, (40., 41.8, 1.), dst=1)
fired = run(sc, 12)
assert front in fired, (fired, holds(sc))
sc = Scene()                                           # the same line for a guard on foot firing the game's own weapon
sc.cj['pos'] = [40., 41.8, 1.]
ground = sc.our(1.4, 41, HCB_ROLE_SQUAD, weapon=M4)
g = sc.ped(30, 41, pedtype=GANG, weapon=AK)
sc.shot(g, (40., 41.8, 1.), dst=1)
fired = run(sc, 12)
assert ground not in fired and HOLD[sc.orders[ground].hold] == 'CJ_BEHIND', (fired, holds(sc))
sc, front, rear = heli_scene(cj_at=(32., 47.6))        # CJ 2 m behind the target: nobody
g = sc.ped(30, 47, pedtype=GANG, weapon=AK)
sc.shot(g, (32., 47.6, 1.), dst=1)
fired = run(sc, 12)
assert not fired, (fired, holds(sc))
passed('A gunner\'s round ends 0.6 m past the point it is aimed at, so CJ 10 m behind the target does not stop a gunner (it stops a guard firing the game\'s own weapon); CJ 2 m behind the target stops everybody')

# ------------------------------------------------------------------ one round, at the moment it leaves
sc, front, rear = heli_scene(cj_at=(-30., 0.))
g = sc.ped(40, 41, pedtype=GANG, weapon=AK)
other = sc.ped(40, 60, pedtype=GANG, weapon=AK, face='away')
sc.shot(g, (-30., 0., 1.), dst=1)
run(sc, 6)
assert sc.orders[front].fire
b = sc.brain
me, him = sc.peds[front]['pos'], sc.peds[g]['pos']
d = [him[i] - me[i] for i in range(3)]
n = math.sqrt(sum(x * x for x in d))
muzzle = [me[i] + d[i] / n * 5.5 for i in range(3)]
mates = [sc.peds[rear]['pos'], sc.peds[[i for i, r in sc.ours.items() if r == HCB_ROLE_PILOT][0]]['pos']]
ask = lambda cj, to=None, friends=mates, time=None, target=g, who=front: HOLD[b.shot(who, target, time or sc.time, me, to or him, cj, friends, muzzle)]
assert ask(sc.cj['pos']) == 'NONE'
mid = [(me[i] + him[i]) / 2 for i in range(3)]
assert ask([mid[0], mid[1] + 1.5, mid[2]]) == 'CJ_IN_LINE', 'CJ has run into the line since the last look'
assert ask([mid[0], mid[1] + 2.6, mid[2]]) == 'NONE', '2.6 m from the line: the round goes'
assert ask([him[0] + 2.0, him[1], him[2]]) == 'CJ_BEHIND' and ask([him[0] + 4.0, him[1], him[2]]) == 'NONE', 'the round ends 0.6 m past the aim point'
assert ask(sc.cj['pos'], friends=mates + [[mid[0], mid[1] + 0.8, mid[2]]]) == 'FRIEND', 'one of ours in the line now'
assert ask(sc.cj['pos'], friends=[[me[0] + 2.0, me[1] + 0.3, me[2]]]) == 'NONE', 'the man inside the first 5.5 m is behind the muzzle'
assert ask(sc.cj['pos'], target=other) == 'NO_TARGET' and ask(sc.cj['pos'], target=g + 0x4000) == 'NO_TARGET', 'only the man of the standing order'
assert ask(sc.cj['pos'], time=sc.time + 400) == 'NO_TARGET', 'an order older than 0.3 s is no order'
sc.walls = [(20, 30, 20, 50)]                          # he steps behind a wall: the order still names him, but it is not an order to fire
sc.step(2)
assert sc.orders[front].target == g and not sc.orders[front].fire and ask(sc.cj['pos']) == 'NO_TARGET', holds(sc)
sc.walls = []
civ = sc.ped(mid[0], mid[1] + 1.0, z=mid[2])           # a passer-by 1 m from the line: the look allows it (0.8 m), the round is stricter (his place is 0.1 s old)
for _ in range(12):
    sc.step(1)
    if sc.orders[front].fire:
        break
assert sc.orders[front].fire and ask(sc.cj['pos']) == 'BYSTANDER', holds(sc)
sc.roe = HCB_ROE_HOLD
sc.peds.pop(civ)
sc.step(1)
assert ask(sc.cj['pos']) == 'NO_TARGET', 'the player said hold fire: no round after the next look'
sc, front, rear = heli_scene(cj_at=(10., 20.))
drv = sc.ped(40, 41, pedtype=GANG, weapon=AK)
carid = sc.veh(40, 41, driver=drv, health=500.)        # a damaged car 36 m from CJ: far enough to be fired at
sc.shot(drv, (10., 20., 1.), dst=1)
run(sc, 8)
me, him = sc.peds[front]['pos'], sc.peds[drv]['pos']
d = [him[i] - me[i] for i in range(3)]
n = math.sqrt(sum(x * x for x in d))
muzzle = [me[i] + d[i] / n * 5.5 for i in range(3)]
for _ in range(12):
    if sc.orders[front].fire:
        break
    sc.step(1)
assert sc.orders[front].fire and sc.orders[front].aim_at == HCB_AIM_DRIVER
assert HOLD[sc.brain.shot(front, drv, sc.time, me, him, sc.cj['pos'], [], muzzle)] == 'NONE'
assert HOLD[sc.brain.shot(front, drv, sc.time, me, him, [33., 33., 1.], [], muzzle)] == 'CAR_NEAR', 'CJ has run up to within 18 m of that car since the look'
assert HOLD[sc.brain.shot(front, drv, sc.time, me, him, sc.cj['pos'], [[36., 30., 1.]], muzzle)] == 'CAR_NEAR', '... or one of ours has'
sc2, f2, r2 = heli_scene(cj_at=(-30., 0.))
g2 = sc2.ped(40, 41, pedtype=GANG, weapon=AK)
sc2.shot(g2, (-30., 0., 1.), dst=1)
sc2.step(1)                                            # the man has been taken, the weapon is coming up: no round yet
assert sc2.orders[f2].target == g2 and not sc2.orders[f2].fire
assert HOLD[sc2.brain.shot(f2, g2, sc2.time, sc2.peds[f2]['pos'], sc2.peds[g2]['pos'], sc2.cj['pos'], [], None)] == 'NO_TARGET'
passed('Every round is asked for at the moment it leaves, with the positions of that frame: CJ stepping within 2 m of the line, one of ours in it, a passer-by, a damaged car beside CJ, an order that is stale or was for another man - the round does not go')

# ------------------------------------------------------------------ what the scripts ask for, frame by frame
sc, front, rear = heli_scene(cj_at=(-30., 0.))
g = sc.ped(40, 41, pedtype=GANG, weapon=AK)
watch = sc.ped(40, 70, pedtype=GANG, weapon=AK, face='away')
b = sc.brain
assert b.order(front) is None and b.order(0x7777) is None
sc.shot(g, (-30., 0., 1.), dst=1)
for _ in range(14):
    sc.step(1)
    for who, o in sc.orders.items():
        got = b.order(who)
        assert got and (got.target, got.fire, got.hold, got.ready) == (o.target, o.fire, o.hold, o.ready), (who, HOLD[o.hold], HOLD[got.hold])
mates = [sc.peds[rear]['pos'], sc.peds[[i for i, r in sc.ours.items() if r == HCB_ROLE_PILOT][0]]['pos']]
chest = lambda p, up: [p[0], p[1], p[2] + up]


def burst_of_rounds(sc, who, target, ms, heli_speed=0., near_heli=True, cj=None, step=10):
    """Ask for a round every `step` ms for `ms` ms, letting the brain look again every 100 ms."""
    out, t = [], sc.time
    for k in range(ms // step):
        t += step
        if t - sc.time >= 100:
            sc.shot(target, sc.cj['pos'], dst=1)
            sc.step(1)
        r = sc.brain.round(who, target, t, chest(sc.peds[who]['pos'], .3), chest(sc.peds[target]['pos'], .2), cj or sc.cj['pos'], mates, heli_speed, near_heli)
        if r:
            out.append(hcb_round.from_buffer_copy(bytes(r)))
    return out


rounds = burst_of_rounds(sc, front, g, 4000)
ok = [r for r in rounds if r.verdict == HCB_HOLD_NONE]
assert len(ok) >= 10 and len(ok) == len(rounds) and all(r.note for r in ok), len(rounds)
gaps = [b_.time - a_.time for a_, b_ in zip(ok, ok[1:])]
cfg = sc.brain.cfg
assert min(gaps) >= cfg.round_min_ms and sorted(gaps)[len(gaps) // 2] <= cfg.round_max_ms + 10 and max(gaps) >= 300 and len(set(gaps)) >= 3, sorted(set(gaps))
me, him = chest(sc.peds[front]['pos'], .3), chest(sc.peds[g]['pos'], .2)
dist = math.dist(me, him)
worst = 0.
for r in ok:
    mz, to, end = [r.muzzle.x, r.muzzle.y, r.muzzle.z], [r.to.x, r.to.y, r.to.z], [r.end.x, r.end.y, r.end.z]
    d = [to[i] - me[i] for i in range(3)]
    n = math.sqrt(sum(x * x for x in d))
    assert math.dist(mz, [me[i] + d[i] / n * cfg.muzzle_m for i in range(3)]) < .01 and math.dist(end, [to[i] + d[i] / n * cfg.round_past_m for i in range(3)]) < .01
    off = max(abs(to[i] - him[i]) for i in range(3))
    worst = max(worst, off)
    assert off <= cfg.scatter_m + cfg.scatter_per_m * dist + .01, off
assert worst > 0.5 * (cfg.scatter_m + cfg.scatter_per_m * dist) and len({round(r.to.x, 2) for r in ok}) > len(ok) // 2, worst
fast = burst_of_rounds(sc, front, g, 1500, heli_speed=25.)
assert max(max(abs(v_ - h_) for v_, h_ in zip([r.to.x, r.to.y, r.to.z], him)) for r in fast) > cfg.scatter_m + cfg.scatter_per_m * dist + .02, 'a fast helicopter scatters more'
foot = burst_of_rounds(sc, front, g, 800, near_heli=False)
assert foot and all(abs(math.dist([r.muzzle.x, r.muzzle.y, r.muzzle.z], me) - 0.8) < .01 for r in foot), 'dismounted: the round starts 0.8 m from him'
passed('A door gunner\'s rounds (the script asks every frame): never closer together than 130 ms, usually within 180 ms, with the pauses of his bursts; each on its own line - from 5.5 m outside the helicopter (0.8 m when dismounted), scattered round the man by up to 0.1 m + 1 % of the range (more from a fast helicopter), ending 0.6 m past the point aimed at')

mid = [(me[i] + him[i]) / 2 for i in range(3)]
t = sc.time
tries, notes = [], []
for k in range(100):                                   # CJ stands in the line for a second: the script keeps asking every 10 ms
    t += 10
    if t - sc.time >= 100:
        sc.shot(g, sc.cj['pos'], dst=1)
        sc.step(1)
        if not sc.orders[front].fire:
            continue
    r = b.round(front, g, t, me, him, [mid[0], mid[1] + 1.0, mid[2]], mates)
    if r:
        assert r.verdict == HCB_HOLD_CJ_IN_LINE
        tries.append(t)
        notes.append(t) if r.note else None
assert len(tries) >= 6 and min(b_ - a_ for a_, b_ in zip(tries, tries[1:])) >= 60 and 2 <= len(notes) <= 5, (tries, notes)
for _ in range(15):
    sc.shot(g, sc.cj['pos'], dst=1)
    sc.step(1)
    if sc.orders[front].fire:
        break
t = sc.time
r = None
while r is None:
    t += 10
    r = b.round(front, g, t, me, him, sc.cj['pos'], mates)
assert r.verdict == HCB_HOLD_NONE
b.blocked(front, t)                                    # the adapter's ray hit a lorry
again = [k for k in range(1, 20) if b.round(front, g, t + 10 * k, me, him, sc.cj['pos'], mates)]
assert again and again[0] == 6, ('tried again 60 ms later, not after a full round interval', again)
assert b.round(front, watch, t + 400, me, chest(sc.peds[watch]['pos'], .2), sc.cj['pos'], mates) is None, 'no rounds at a man he only covers'
assert b.round(front, g, t + 400, me, [me[0] + 4., me[1], me[2]], sc.cj['pos'], mates) is None, 'a man 4 m from the muzzle: nothing to aim past the door'
passed('A round the hard rules refuse is asked for again 60 ms later (and noted in the black box at most four times a second); so is one whose ray was blocked. No rounds at a suspect who is only covered')

sc = Scene()
sc.cj['pos'] = [0., -6., 1.]
me = sc.our(0, 4, HCB_ROLE_SQUAD, weapon=M4)
idle = sc.our(-30, 4, HCB_ROLE_SQUAD + 1, weapon=0)
sus = sc.ped(0, 40, pedtype=GANG, weapon=AK, face='away')
b = sc.brain
state = lambda who, target, cj=None: b.squad(who, target, sc.time, sc.peds[who]['pos'], sc.peds[target]['pos'], cj or sc.cj['pos'], [sc.peds[idle]['pos']] if who == me else [sc.peds[me]['pos']])
sc.step(3)
assert sc.orders[me].target == sus and state(me, sus) == 1 and state(idle, sus) == 1, (holds(sc), state(me, sus))
g = sc.ped(25, 4, pedtype=GANG, weapon=AK, face='away')
sc.step(1)
sc.shot(g, (0., -6., 1.), dst=1)
seen = []
for _ in range(8):
    sc.step(1)
    seen.append(state(me, g))
assert seen[-1] == 2 and set(seen) <= {3, 2} and seen.index(2) >= 1, ('his man at once, the first round after the reaction time', seen)
assert state(me, g, cj=[12., 4.5, 1.]) == 3, 'CJ in his line in this frame: cease fire'
sc.roe = HCB_ROE_HOLD
sc.step(1)
assert state(me, g) == 0 and not sc.orders[me].fire, 'hold fire: he has no man at all'
sc.roe = HCB_ROE_DEFEND
sc.peds[g]['flags'] |= HCB_PF_DEAD
sc.peds.pop(sus)
sc.step(2)
assert b.order(me).target == 0 and state(me, g) == 0
sc = Scene()
team = squad(sc)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
run(sc, 10)
states = sorted(sc.brain.squad(w_, g, sc.time, sc.peds[w_]['pos'], sc.peds[g]['pos'], sc.cj['pos'], [sc.peds[o_]['pos'] for o_ in team if o_ != w_]) for w_ in team)
assert states == [2, 2, 2, 3] and sorted(HOLD[o.hold] for o in sc.orders.values()) == ['ENOUGH', 'NONE', 'NONE', 'NONE'], (states, holds(sc))
# two attackers at once, both on the same side and one behind the other: two rifles each - not three on the nearer man
sc = Scene()
team = squad(sc)
near_, far_ = sc.ped(20, 2, pedtype=GANG, weapon=AK), sc.ped(30, 2, pedtype=GANG, weapon=AK)
sc.shot(near_, (0., 0., 1.), dst=1)
sc.shot(far_, (0., 0., 1.), dst=1)
run(sc, 10)
on_ = sorted(o.target for o in sc.orders.values() if o.fire)
assert on_ == sorted([near_, near_, far_, far_]), ('fire spreads: two and two', on_, holds(sc))
sc = Scene()
team = squad(sc)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
run(sc, 10)
# a second attacker turns up: the man with free hands takes him, the three who are firing keep their man
on = lambda: {w_: sc.orders[w_].target for w_ in team}
before = on()
free = [w_ for w_ in team if HOLD[sc.orders[w_].hold] == 'ENOUGH'][0]
g2 = sc.ped(-20, 8, pedtype=GANG, weapon=AK)
sc.shot(g2, (0., 0., 1.), dst=1)
run(sc, 10)
assert on()[free] == g2 and sc.orders[free].fire and all(on()[w_] == g for w_ in team if w_ != free), (free, before, on(), holds(sc))
# ...but when the free man cannot fire at the new attacker (CJ stands in his line), one of the firing men goes over at once
sc = Scene()
team = squad(sc)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
run(sc, 10)
free = [w_ for w_ in team if HOLD[sc.orders[w_].hold] == 'ENOUGH'][0]
fx, fy = sc.peds[free]['pos'][:2]
fl = math.hypot(fx, fy)
g2 = sc.ped(-fx / fl * 25, -fy / fl * 25, pedtype=GANG, weapon=PISTOL)    # straight behind CJ as the free man sees it
sc.shot(g2, (0., 0., 1.), dst=1)
run(sc, 10)
took = [w_ for w_ in team if sc.orders[w_].target == g2 and sc.orders[w_].fire]
assert took and free not in took, ('nobody who fires at CJ is left alone', free, holds(sc))
# ...and a much more dangerous one whom only a firing man can take (the free man has CJ in his line to both) is worth the change
sc = Scene()
team = squad(sc, places=((3, 8), (-5, 0)))
weak = sc.ped(25, 1, pedtype=GANG, weapon=PISTOL)
sc.shot(weak, (0., 0., 1.), dst=1)
run(sc, 10)
assert sc.orders[team[0]].target == weak and sc.orders[team[0]].fire and HOLD[sc.orders[team[1]].hold] == 'CJ_IN_LINE', holds(sc)
close = sc.ped(10, -1, pedtype=GANG, weapon=PISTOL)
sc.shot(close, (0., 0., 1.), dst=1)
run(sc, 10)
m_ = sc.brain.marks()
assert 1.4 < m_[close].edps / m_[weak].edps < 1.9, ('(the scene: about one and a half times as dangerous)', m_[close].edps, m_[weak].edps)
assert sc.orders[team[0]].target == close and sc.orders[team[0]].fire and HOLD[sc.orders[team[1]].hold] == 'CJ_IN_LINE', holds(sc)
# one rifle, two attackers: it stays on one man - a rifle is taken only from a man who has more than he needs
sc = Scene()
team = squad(sc, places=((3, 8),))
a_, b_ = sc.ped(25, 3, pedtype=GANG, weapon=AK), sc.ped(25, -3, pedtype=GANG, weapon=AK)
sc.shot(a_, (0., 0., 1.), dst=1)
sc.shot(b_, (0., 0., 1.), dst=1)
run(sc, 5)
seen = []
for _ in range(10):
    sc.step(1)
    seen.append((sc.orders[team[0]].target, sc.orders[team[0]].fire))
assert len(set(seen)) == 1 and seen[0][1] == 1, ('no hopping between two men', seen)
# ...and with nobody free the least needed rifle goes over: nobody who fires at CJ is left alone
sc = Scene()
team = squad(sc)[:3]
for w_ in list(sc.ours):
    if w_ not in team: sc.ours.pop(w_)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
run(sc, 10)
assert all(sc.orders[w_].target == g and sc.orders[w_].fire for w_ in team), holds(sc)
g2 = sc.ped(-20, 8, pedtype=GANG, weapon=AK)
sc.shot(g2, (0., 0., 1.), dst=1)
run(sc, 10)
assert sorted(sc.orders[w_].target for w_ in team) == sorted([g, g, g2]), holds(sc)
passed('A new attacker is taken by the guard whose hands are free; the men who are firing keep their man (with nobody free, one rifle goes over)')
sc, front, rear = heli_scene(cj_at=(40., 41.8), z=2.)  # a crewman by the landed helicopter, firing the game's own weapon: CJ 10 m behind his man
g = sc.ped(30, 41, pedtype=GANG, weapon=AK)
sc.shot(g, (40., 41.8, 1.), dst=1)
run(sc, 8)
assert sc.orders[front].fire, 'as a door gunner (his rounds end at the man) he may fire'
assert sc.brain.squad(front, g, sc.time, sc.peds[front]['pos'], sc.peds[g]['pos'], sc.cj['pos'], []) == 3, 'asked as a guard on foot: his rounds fly on to CJ - no'
# a position that is not a number (or a helicopter speed that is not one) never becomes a round: the game hangs on such a line
sc, front, rear = heli_scene()
g = sc.ped(30, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
run(sc, 8)
b = sc.brain
assert sc.orders[front].fire or sc.orders[rear].fire, holds(sc)
who = front if sc.orders[front].fire else rear
me_ = sc.peds[who]['pos']
nan, inf = float('nan'), float('inf')
bad = 0
for k_, (to_, cj_, spd) in enumerate([((nan, 0., 1.), None, 0.), ((30., nan, 1.), None, 0.), ((30., 0., inf), None, 0.), ((600., 0., 1.), None, 0.),
                                      ((30., 0., 1.), (nan, 0., 1.), 0.), ((30., 0., 1.), None, nan), ((30., 0., 1.), None, inf)]):
    r_ = b.round(who, g, sc.time + 200 * (k_ + 1), me_, to_, cj_ or sc.cj['pos'], [], spd, True)
    if r_ is not None:
        vals = [r_.muzzle.x, r_.muzzle.y, r_.muzzle.z, r_.end.x, r_.end.y, r_.end.z, r_.to.x, r_.to.y, r_.to.z]
        assert all(v - v == 0 for v in vals), (k_, vals)
        bad += 1
r_ = b.round(who, g, sc.time + 5000, me_, (30., 0., 1.), sc.cj['pos'], [], 12., True)
assert r_ is not None and all(v - v == 0 for v in [r_.muzzle.x, r_.end.x, r_.end.z]), '(control: a sane line gives a round)'
assert bad == 2, ('only the two with a nonsense speed give a round, and it is a sane one', bad)
passed('A position that is not a number, one 600 m away, or CJ at no number gives no round; a nonsense helicopter speed is taken as 0 - the game never gets such a line')
passed('A guard on foot (he fires the game\'s own weapon) is told: a suspect to keep a weapon on, fire, or "your man, but no fire" - in the very frame CJ comes into his line, while his weapon is coming up, and when three rifles are on the man already; hold fire leaves him no man at all')

# ------------------------------------------------------------------ the car CJ is shooting at
sc = rule(HCB_ROE_FOLLOW)
drv, mate = sc.ped(40, 0, pedtype=GANG, weapon=AK), sc.ped(40, 0, pedtype=GANG, weapon=PISTOL)
carid = sc.veh(40, 0, driver=drv)
sc.peds[mate]['vehicle'], sc.peds[mate]['seat'] = carid, 1
other = sc.ped(0, 30, pedtype=GANG, weapon=AK)
sc.step(3)
assert not firing(sc)
sc.shot(1, (40., 2.2, 1.))                             # CJ puts a round into the car's bonnet, 2.2 m from the men in it
targets = set()
for _ in range(10):
    sc.step(1)
    targets |= {o.target for o in sc.orders.values() if o.fire}
assert targets and targets <= {drv, mate} and other not in targets, (targets, holds(sc))
passed('WHERE I SHOOT: CJ fires at a car - the men in it are the targets (aimed at them, not at the engine); a man CJ is not shooting at is left alone')

# ------------------------------------------------------------------ kills
sc = Scene()
team = squad(sc)
g = sc.ped(25, 0, pedtype=GANG, weapon=AK)
sc.shot(g, (0., 0., 1.), dst=1)
run(sc, 8)
assert firing(sc, g) and sc.brain.out.kills == 0
sc.peds[g]['flags'] |= HCB_PF_DEAD
sc.step(1)
assert sc.brain.out.kills == 1
passer = sc.ped(-30, 0)
sc.step(2)
sc.peds[passer]['flags'] |= HCB_PF_DEAD                 # somebody dies whom nobody of ours was firing at
sc.step(1)
assert sc.brain.out.kills == 1
passed('A man who dies while ours are firing at him is counted as theirs; a death nobody of ours had a hand in is not')

# ------------------------------------------------------------------ many questions: the dangerous ones first
sc = Scene(roe=HCB_ROE_ARMED)
team = [sc.our(2 + k, 20 + 3 * k, HCB_ROLE_SQUAD + k % 4, weapon=M4) for k in range(8)]
crowd = [sc.ped(30 + 2 * k, -10 + k, pedtype=GANG, weapon=PISTOL, face='away') for k in range(20)]
killer = sc.ped(-75, 0, pedtype=GANG, weapon=AK)       # further from CJ than all of them: last in the snapshot, last in memory
sc.shot(killer, (0., 0., 1.), dst=1)
sc.step(1)
assert len(sc.asked) == HCB_MAX_LOS and all(t == killer for _, t in sc.asked[:8]), sc.asked[:10]
passed('Eight shooters and twenty-one armed men: 168 lines of sight do not fit into one look (96 do) - the ones to the man who is shooting CJ are asked first')

# ------------------------------------------------------------------ sharing the targets out
sc = Scene()
team = squad(sc)
threats = [sc.ped(30, y, pedtype=GANG, weapon=AK) for y in (-18, -6, 6, 18)]
for t in threats:
    sc.shot(t, (0., 0., 1.), dst=1)
run(sc, 10)
assert sorted(o.target for o in sc.orders.values()) == sorted(threats), 'four attackers, four shooters: one each'
sc = Scene()
team = squad(sc)
big = sc.ped(15, 0, pedtype=GANG, weapon=AK)
small = sc.ped(-30, 0, pedtype=GANG, weapon=PISTOL)
for t in (big, small):
    sc.shot(t, (0., 0., 1.), dst=1)
run(sc, 10)
on = [o.target for o in sc.orders.values()]
assert on.count(big) in (2, 3) and on.count(small) >= 1, on
sc = Scene()
team = squad(sc, places=((2, 7), (2, -7), (5, 12), (5, -12), (8, 17), (8, -17)))
one = sc.ped(35, 0, pedtype=GANG, weapon=AK)
sc.shot(one, (0., 0., 1.), dst=1)
run(sc, 10)
on = [o.target for o in sc.orders.values() if o.hold != HCB_HOLD_NO_TARGET]
assert [o.target for o in sc.orders.values() if o.fire or o.hold in (HCB_HOLD_REACTING, HCB_HOLD_PAUSE)].count(one) == 3, 'never more than three on one man'
passed('Targets are shared out: four attackers get one shooter each; a rifle close by gets two or three and the far pistol still gets one; never more than three on one man')
sc = Scene()
team = squad(sc)
a, b_ = sc.ped(25, 5, pedtype=GANG, weapon=AK), sc.ped(25, -5, pedtype=GANG, weapon=AK)
for t in (a, b_):
    sc.shot(t, (0., 0., 1.), dst=1)
run(sc, 8)
before = {w: o.target for w, o in sc.orders.items()}
swaps = 0
for _ in range(40):
    sc.shot(a, (0., 0., 1.), dst=1)
    sc.shot(b_, (0., 0., 1.), dst=1)
    sc.step(1)
    now = {w: o.target for w, o in sc.orders.items()}
    swaps += sum(now[w] != before[w] for w in now)
    before = now
assert swaps == 0, swaps
passed('Nobody changes his man from tick to tick while the picture stays the same')

# ------------------------------------------------------------------ timing: reaction, bursts
def first_shot(alert_first):
    times = []
    for seed in range(40):
        sc = Scene(brain=Brain(seed=seed + 1))
        me = sc.our(0, 4, HCB_ROLE_SQUAD, weapon=M4)
        if alert_first:                       # already in a fight with somebody else
            other = sc.ped(-25, 4, pedtype=GANG, weapon=AK)
            sc.shot(other, (0., 0., 1.), dst=1)
            run(sc, 12)
            del sc.peds[other]
        g = sc.ped(25, 4, pedtype=GANG, weapon=AK)
        sc.shot(g, (0., 0., 1.), dst=1)
        for k in range(1, 15):
            sc.step(1)
            if firing(sc, g):
                times.append(k * 100)
                break
    return times


cold, hot = first_shot(False), first_shot(True)
assert len(cold) == len(hot) == 40 and min(cold) >= 200 and max(cold) <= 500 and len(set(cold)) >= 2, sorted(set(cold))   # (the brain thinks in 100 ms ticks)
assert sum(hot) / 40. < sum(cold) / 40. - 40, (sum(hot) / 40., sum(cold) / 40.)
passed('First round at a new man: %d-%d ms from a standing start (40 different guards), about %d ms quicker when already fighting' % (min(cold), max(cold), sum(cold) / 40. - sum(hot) / 40.))
sc, me, rear_ = heli_scene(cj_at=(-30., 0.))
del sc.peds[rear_], sc.ours[rear_]
g = sc.ped(40, 41, pedtype=GANG, weapon=AK)
foot = sc.our(30, 30, HCB_ROLE_SQUAD, weapon=M4)       # a guard on foot beside the same fight
pattern, foot_pattern = '', ''
for k in range(300):
    sc.shot(g, (-30., 0., 1.), dst=1)
    sc.step(1)
    pattern += 'F' if sc.orders[me].fire else '.'
    foot_pattern += 'F' if sc.orders[foot].fire else '.'
assert '.' not in foot_pattern.lstrip('.') and len(foot_pattern) - len(foot_pattern.lstrip('.')) <= 5, foot_pattern[:40]
bursts = [len(x) * 100 for x in pattern.strip('.').split('.') if x][:-1]      # (the last one is cut off by the end of the run)
pauses = [len(x) * 100 for x in pattern.strip('.').strip('F').split('F') if x]
cfg = sc.brain.cfg
assert len(bursts) > 10 and cfg.burst_min_ms - 100 <= min(bursts) and max(bursts) <= cfg.burst_max_ms + 100 and len(set(bursts)) >= 4, sorted(set(bursts))
assert cfg.pause_min_ms <= min(pauses) and max(pauses) <= cfg.pause_max_ms + 200, sorted(set(pauses))
share = pattern.count('F') / 300.
assert .55 <= share <= .9, share
passed('A door gunner fires in bursts of %.1f-%.1f s with %.1f-%.1f s between them (on the trigger %d%% of the time), never one endless stream; a guard on foot gets a plain fire / cease fire - his bursts are the game\'s own weapon handling' % (min(bursts) / 1000., max(bursts) / 1000., min(pauses) / 1000., max(pauses) / 1000., share * 100))

delays = []
for seed in range(12):
    sc = Scene(brain=Brain(seed=seed + 1))
    me = sc.our(0, 4, HCB_ROLE_SQUAD, weapon=M4)
    sc.cj['pos'] = [0., -6., 1.]
    g = sc.ped(25, 4, pedtype=GANG, weapon=AK)
    sc.shot(g, (0., -6., 1.), dst=1)
    run(sc, 8)
    assert firing(sc, g)
    sc.cj['pos'] = [12., 4.5, 1.]                      # CJ crosses the line of fire
    run(sc, 5)
    assert not firing(sc) and HOLD[sc.orders[me].hold] == 'CJ_IN_LINE' and sc.orders[me].target == g
    sc.cj['pos'] = [0., -6., 1.]                       # ... and is out of it again
    for k in range(1, 8):
        sc.step(1)
        if firing(sc, g):
            delays.append(k * 100)
            break
assert delays == [100] * 12, delays
passed('CJ crosses the line of fire: the guard holds with his weapon still on the man, and fires on the very next look when the line is clear - no second reaction time')

# ------------------------------------------------------------------ the hard rules hold in any mess: random fights, an independent check
def check_orders(sc, s):
    """Every fire order of this tick against the rules, computed here from the snapshot (not by the core)."""
    cfg = sc.brain.cfg
    peds = {p.id: p for p in s.peds[:s.n_peds]}
    ours = set(s.ours[:s.n_ours])
    cj = (s.player.pos.x, s.player.pos.y, s.player.pos.z)

    def offs(a, e, p):
        d = [e[i] - a[i] for i in range(3)]
        ln = math.sqrt(sum(x * x for x in d))
        ap = [p[i] - a[i] for i in range(3)]
        along = sum(ap[i] * d[i] for i in range(3)) / ln
        lat = math.sqrt(max(0., sum(x * x for x in ap) - along * along))
        return ln, along, lat
    bad = []
    for o in sc.brain.out.orders[:sc.brain.out.n_orders]:
        if not o.fire:
            continue
        me, t = peds.get(o.who), peds.get(o.target)
        if me is None or t is None:
            bad.append(('fires at somebody who is not there', o.who, o.target))
            continue
        a, e = (me.pos.x, me.pos.y, me.pos.z), (t.pos.x, t.pos.y, t.pos.z)
        ln, along, lat = offs(a, e, cj)
        if 0.3 < along <= ln and lat <= cfg.cj_line_m + cfg.line_per_m * along - 1e-3:
            bad.append(('CJ in the line', o.who, o.target, along, lat))
        if ln < along <= ln + cfg.backstop_m and lat <= 1.0 + cfg.line_per_m * along - 1e-3:
            bad.append(('CJ behind the target', o.who, o.target, along, lat))
        if t.id in ours or t.pedtype == GROVE or (t.flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP)) and not (t.flags & HCB_PF_HATES):
            if sc.brain.cls(t.id) == HCB_CLS_FRIEND:
                bad.append(('fires at a friend', o.who, o.target))
        if sc.brain.cls(t.id) is not None and sc.brain.cls(t.id) < HCB_CLS_THREAT and s.roe == HCB_ROE_DEFEND:
            bad.append(('DEFEND: fires at somebody who is not a threat', o.who, o.target, sc.brain.cls(t.id)))
        for f in ours:
            if f != o.who and f in peds:
                l2, al, la = offs(a, e, (peds[f].pos.x, peds[f].pos.y, peds[f].pos.z))
                if 0.3 < al <= ln and la <= cfg.friend_line_m + cfg.line_per_m * 0.75 * al - 1e-3:
                    bad.append(('one of ours in the line', o.who, o.target, f, al, la))
        if s.roe == HCB_ROE_HOLD:
            bad.append(('fires under HOLD', o.who))
        if s.police == HCB_POLICE_EVADE and t.pedtype == COP:
            bad.append(('fires at the police under EVADE', o.who, o.target))
        if t.vehicle:
            v = next((v for v in s.vehs[:s.n_vehs] if v.id == t.vehicle), None)
            if v is not None:
                near = min([math.dist((v.pos.x, v.pos.y, v.pos.z), cj)] + [math.dist((v.pos.x, v.pos.y, v.pos.z), (peds[f].pos.x, peds[f].pos.y, peds[f].pos.z)) for f in ours if f in peds])
                if near <= cfg.explode_m and (v.health < cfg.car_floor or v.flags & HCB_VF_BURNING):
                    bad.append(('fires at a car that could blow up beside CJ', o.who, o.target, near, v.health))
    return bad


def mess(seed, ticks=250):
    rnd = random.Random(seed)
    sc = Scene(brain=Brain(seed=seed), wanted=rnd.choice([0, 0, 2]), roe=rnd.choice([HCB_ROE_DEFEND, HCB_ROE_DEFEND, HCB_ROE_ARMED, HCB_ROE_FOLLOW, HCB_ROE_HOLD]))
    sc.police = rnd.choice([HCB_POLICE_ANSWER, HCB_POLICE_EVADE])
    team = squad(sc, places=[(rnd.uniform(-6, 6), rnd.uniform(-6, 6)) for _ in range(4)])
    fire_orders, problems = 0, []
    for t in range(ticks):
        if rnd.random() < .2 and len(sc.peds) < 60:
            sc.ped(rnd.uniform(-45, 45), rnd.uniform(-45, 45), pedtype=rnd.choice([CIV, CIV, GANG, GANG, COP, GROVE]), weapon=rnd.choice([0, PISTOL, AK, AK, BAT]),
                   vel=(rnd.uniform(-3, 3), rnd.uniform(-3, 3), 0.))
        if rnd.random() < .04 and len(sc.vehs) < 12:
            d = sc.ped(0, 0, pedtype=rnd.choice([CIV, GANG]), weapon=rnd.choice([0, AK]))
            sc.veh(rnd.uniform(-40, 40), rnd.uniform(-40, 40), vel=(rnd.uniform(-15, 15), rnd.uniform(-15, 15), 0.), driver=d, health=rnd.choice([1000., 600., 240.]),
                   flags=rnd.choice([0, 0, HCB_VF_BURNING]))
        for p in [p for p in sc.peds if p not in sc.ours]:
            r = rnd.random()
            if r < .03 and sc.peds[p]['weapon'] >= 22:
                sc.shot(p, (sc.cj['pos'][0] + rnd.uniform(-4, 4), sc.cj['pos'][1] + rnd.uniform(-4, 4), 1.), dst=rnd.choice([0, 0, 1]))
            elif r < .04:
                sc.peds[p]['target'] = rnd.choice([0, 1])
            elif r < .045:
                del sc.peds[p]
        for g_ in team:
            sc.peds[g_]['vel'] = [rnd.uniform(-3, 3), rnd.uniform(-3, 3), 0.]
        sc.cj['vel'] = [rnd.uniform(-4, 4), rnd.uniform(-4, 4), 0.]
        if rnd.random() < .05:
            sc.cj['target'] = rnd.choice([0] + [p for p in sc.peds if p not in sc.ours][:5])
        sc.step(1)
        fire_orders += sum(1 for o in sc.brain.out.orders[:sc.brain.out.n_orders] if o.fire)
        problems += check_orders(sc, sc.snapshots[-1])
    return fire_orders, problems


total = 0
for seed in range(1, 61):
    n, problems = mess(seed)
    assert not problems, (seed, problems[:3])
    total += n
assert total > 3000, total
passed('60 random fights (25 s each, guards and CJ running about, cars, police, every fire rule): %d orders to fire, checked one by one by an independent calculation - none with CJ or one of ours in the line, at a friend, against the fire rule, or at a car that could blow up beside CJ' % total)

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_fire_tests.txt').write_text(text)
print(text)
