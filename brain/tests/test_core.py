"""Helicover Brain, stage 1: the core's memory of contacts, threat assessment, alert level and black box.
Runs the real C core (host build) on hand-made scenes. No game here: what the adapter must feed in is the snapshot."""
import ctypes, math, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


GANG, COP, CIV, GROVE = 7, 6, 4, 8
PISTOL, AK, BAT, KNIFE, SNIPER = 22, 30, 5, 4, 34


def classes(sc):
    return {i: (m.cls, m.why) for i, m in sc.brain.marks().items()}


# ------------------------------------------------------------------ who is a threat by what he is and does
sc = Scene()
civ = sc.ped(10, 0)
armed_civ = sc.ped(12, 5, weapon=PISTOL)
gang_far = sc.ped(0, 30, pedtype=GANG)
gang_close = sc.ped(0, 10, pedtype=GANG)
facing = sc.ped(20, 0, pedtype=GANG, weapon=AK)
away = sc.ped(-20, 0, pedtype=GANG, weapon=AK, face='away')
far_armed = sc.ped(0, -75, pedtype=GANG, weapon=AK)
bat = sc.ped(-8, -8, pedtype=GANG, weapon=BAT, face='away')
cop = sc.ped(15, 15, pedtype=COP, weapon=PISTOL)
sc.step(3)
c = classes(sc)
assert civ not in c and armed_civ not in c and gang_far not in c and cop not in c and far_armed not in c, c
assert c[facing] == (HCB_CLS_THREAT, HCB_WHY_ARMED_FACING) and c[away] == (HCB_CLS_WATCH, HCB_WHY_ARMED_NEAR), c
assert c[gang_close] == (HCB_CLS_WATCH, HCB_WHY_HOSTILE_NEAR) and c[bat] == (HCB_CLS_WATCH, HCB_WHY_HOSTILE_NEAR), c
passed('Passers-by, an armed civilian, police without stars and a gang member 30 m away are nobody; an armed gang member turned to CJ is a THREAT, turned away he is only watched')
sc = Scene(wanted=2)
cop = sc.ped(15, 15, pedtype=COP, weapon=PISTOL)
stick = sc.ped(-10, 10, pedtype=COP, weapon=3)
sc.step(2)
assert classes(sc)[cop] == (HCB_CLS_THREAT, HCB_WHY_ARMED_FACING) and classes(sc)[stick][0] == HCB_CLS_WATCH, classes(sc)
passed('With a wanted level an armed policeman turned to CJ is a THREAT, one with a nightstick is watched')
for turn, want in ((30, HCB_CLS_THREAT), (-30, HCB_CLS_THREAT), (55, HCB_CLS_WATCH), (-55, HCB_CLS_WATCH), (175, HCB_CLS_WATCH)):
    sc = Scene()
    g = sc.ped(20, 5, pedtype=GANG, weapon=AK)
    sc.face(g, sc.cj['pos'], turn_deg=turn)
    sc.step(2)
    assert classes(sc)[g][0] == want, (turn, classes(sc))
sc = Scene()
g = sc.ped(20, 0, pedtype=GANG, weapon=AK, flags2=HCB_PF2_LOS_KNOWN)        # behind a wall
g2 = sc.ped(-20, 0, pedtype=GANG, weapon=AK, flags2=HCB_PF2_LOS_KNOWN | HCB_PF2_LOS_CLEAR)
g3 = sc.ped(0, 55, pedtype=GANG, weapon=AK)
drv = sc.ped(0, -20, pedtype=GANG, weapon=AK)
sc.veh(0, -20, driver=drv)
sc.step(2)
c = classes(sc)
assert c[g][0] == HCB_CLS_WATCH and c[g2][0] == HCB_CLS_THREAT and c[g3][0] == HCB_CLS_WATCH and c[drv][0] == HCB_CLS_WATCH, c
passed('"Turned to CJ" is 40 degrees either side; a man known to be behind a wall, one 55 m away or one sitting in a car is watched, not engaged')

# ------------------------------------------------------------------ a weapon held on CJ
sc = Scene()
a = sc.ped(15, 0, weapon=PISTOL, target=1)             # an ordinary civilian, but his gun is on CJ
sc.step(2)
assert a not in classes(sc), 'not yet: 0.2 s'
sc.step(2)
assert classes(sc)[a] == (HCB_CLS_THREAT, HCB_WHY_AIMS_AT_CJ) and sc.brain.out.top == a
sc.peds[a]['target'] = 0
sc.step(1)
assert classes(sc)[a][0] == HCB_CLS_THREAT, 'the clock runs back, it does not snap to zero'
sc.step(2)
assert a not in classes(sc)
passed('Anybody who holds a weapon on CJ for a quarter of a second is a THREAT, whoever he is; lowering it clears him within 0.3 s (not on the very next look: a gun that wavers is still a gun)')
sc = Scene()
guard = sc.our(2, 0, HCB_ROLE_SQUAD)
a = sc.ped(15, 0, weapon=PISTOL, target=guard)
unarmed = sc.ped(10, 10, target=1)                     # staring at CJ with empty hands from 14 m
sc.step(4)
assert classes(sc)[a] == (HCB_CLS_THREAT, HCB_WHY_AIMS_AT_OURS) and unarmed not in classes(sc), classes(sc)
passed('A weapon held on one of ours counts the same; an unarmed man "targeting" CJ from a distance does not')

# ------------------------------------------------------------------ shots
def shoot_scene(to, dst=0, shooter_at=(30., 0.)):
    sc = Scene()
    s = sc.ped(*shooter_at, weapon=AK, face='away')    # what he is and where he looks does not matter: he fired
    sc.step(1)
    sc.shot(s, to, dst)
    sc.step(1)
    return sc, s


sc, s = shoot_scene((-20., 1.5, 1.))                   # the round passes 1.5 m from CJ
assert classes(sc)[s] == (HCB_CLS_ATTACKER, HCB_WHY_SHOT_AT_CJ) and sc.brain.track(s).shots_at_cj == 1
sc, s = shoot_scene((3.6, 0.3, 1.))                    # stopped by a wall 3.6 m short of him: the line still runs through him
assert classes(sc)[s][0] == HCB_CLS_ATTACKER
sc, s = shoot_scene((0., 0., 1.), dst=1)               # the game says it hit him
assert classes(sc)[s][0] == HCB_CLS_ATTACKER
sc, s = shoot_scene((30., 40., 1.))                    # fired along the street, nowhere near
assert classes(sc)[s] == (HCB_CLS_WATCH, HCB_WHY_SHOOTING_NEARBY) and sc.brain.track(s).shots_at_cj == 0
sc, s = shoot_scene((60., 0., 1.))                     # fired away from CJ: the line behind the muzzle is not a line of fire
assert classes(sc)[s][0] == HCB_CLS_WATCH
sc, s = shoot_scene((-20., 6., 1.))                    # passes 6 m from him
assert classes(sc)[s][0] == HCB_CLS_WATCH
sc, s = shoot_scene((40., 0., 1.), shooter_at=(2., 0.)) # a man two steps from CJ firing AWAY from him: the muzzle is near, the line is not
assert classes(sc)[s][0] == HCB_CLS_WATCH and sc.brain.track(s).shots_at_cj == 0
passed('A round that passes within 3 m of CJ (or stops just short of him) makes the shooter an ATTACKER; shooting somewhere else nearby only gets him watched')
sc = Scene()
guard = sc.our(0, -6, HCB_ROLE_SQUAD)
s = sc.ped(30, -6, weapon=AK)
sc.step(1)
sc.shot(s, (-10., -6., 1.))
sc.step(1)
assert classes(sc)[s] == (HCB_CLS_ATTACKER, HCB_WHY_SHOT_AT_OURS)
sc = Scene()
guard = sc.our(3, 0, HCB_ROLE_SQUAD, weapon=AK)
t = sc.ped(30, 0, pedtype=GANG, weapon=AK)
sc.step(1)
sc.shot(guard, (30., 0., 1.), dst=t)                   # our guard fires past CJ's shoulder at the threat
sc.shot(1, (30., 1., 1.))                              # and so does CJ
sc.damage(guard, t, 30)
sc.step(1)
assert classes(sc)[guard] == (HCB_CLS_FRIEND, HCB_WHY_OURS) and sc.brain.track(guard).shots_total == 0
passed('Fire at one of ours counts as an attack; our own fire and CJ\'s never turn anybody of ours into a suspect')
sc = Scene()
sc.step(1)
sc.events.append(dict(type=HCB_EV_SHOT, src=0x7777, dst=0, a=[90., 0., 20.], b=[0.5, 0., 1.], value=0., weapon=SNIPER))
sc.step(1)
m = sc.brain.marks()[0x7777]
assert m.cls == HCB_CLS_ATTACKER and m.seen == 0 and abs(sc.brain.track(0x7777).last_pos.x - 90) < .01 and abs(m.dist - 90) < 2.5, (m.cls, m.seen, m.dist)
passed('A sniper too far away to be in the snapshot is still known from his shot: an ATTACKER, placed at the muzzle')

# ------------------------------------------------------------------ damage
sc = Scene()
guard = sc.our(2, 2, HCB_ROLE_SQUAD)
a, b_, c_, d = sc.ped(3, 0), sc.ped(10, 0), sc.ped(-10, 0), sc.ped(0, 12)
sc.step(1)
sc.damage(a, 1, 8, weapon=0)                           # a punch
sc.damage(b_, guard, 25, weapon=PISTOL)
sc.damage(1, c_, 40, weapon=PISTOL)                    # CJ shot somebody
sc.damage(guard, d, 40, weapon=AK)                     # our guard shot somebody
sc.step(1)
c = classes(sc)
assert c[a] == (HCB_CLS_ATTACKER, HCB_WHY_HURT_CJ) and c[b_] == (HCB_CLS_ATTACKER, HCB_WHY_HURT_OURS) and c_ not in c and d not in c, c
assert sc.brain.track(a).damage_cj == 8 and sc.brain.track(b_).damage_ours == 25
passed('Whoever hurts CJ or one of ours is an ATTACKER (a punch is enough); the people CJ and the guards hurt are not thereby enemies')
sc.step(int(sc.brain.cfg.attacker_ms / 100) - 3)
assert classes(sc)[a][0] == HCB_CLS_ATTACKER
sc.step(4)
assert a not in classes(sc)
passed('An attacker who does nothing more for 20 s is an ordinary man again')

# ------------------------------------------------------------------ memory of people out of sight
sc = Scene()
s = sc.ped(30, 0, pedtype=GANG, weapon=AK)
n = sc.ped(10, 0)
sc.step(1)
sc.shot(s, (0., 0., 1.), dst=1)
sc.step(1)
last = list(sc.peds[s]['pos'])
del sc.peds[s], sc.peds[n]                            # both walk out of the snapshot (round a corner)
sc.step(1)
m = sc.brain.marks()[s]
assert m.cls == HCB_CLS_ATTACKER and m.seen == 0 and sc.brain.track(n) is not None
edps_seen = hcb_py.LIB.hcb_weapon_dps(AK)
assert 0 < m.edps < 0.3 * edps_seen
sc.step(int(sc.brain.cfg.forget_ms / 100) + 1)
assert sc.brain.track(n) is None and sc.brain.marks()[s].cls == HCB_CLS_ATTACKER, 'the passer-by is forgotten, the shooter is not'
sc.step(int(sc.brain.cfg.attacker_ms / 100))
assert sc.brain.track(s) is None
passed('A shooter who disappears round a corner is remembered where he was last seen for 20 s (at a quarter of his danger); a passer-by is forgotten in 4 s')
sc = Scene()
g = sc.ped(20, 0, pedtype=GANG, weapon=AK)
sc.step(2)
sc.peds[g]['flags'] |= HCB_PF_DEAD
sc.step(1)
assert sc.brain.track(g) is None and sc.brain.out.n_threats == 0
passed('A dead man is dropped at once')

# ------------------------------------------------------------------ friends
sc = Scene()
gunner = sc.our(0, 30, HCB_ROLE_GUNNER, weapon=AK, target=1, z=25.)    # our gunner happens to have CJ in his sights
homie = sc.ped(3, 3, pedtype=GROVE, weapon=PISTOL)
recruit = sc.ped(-3, 3, pedtype=CIV, weapon=AK, flags=HCB_PF_IN_GROUP)
mission_friend = sc.ped(5, 0, pedtype=GANG, weapon=AK, flags=HCB_PF_RESPECTS)
turncoat = sc.ped(-5, 0, pedtype=GROVE, weapon=AK, flags=HCB_PF_HATES)
sc.step(5)
c = classes(sc)
assert c[gunner] == (HCB_CLS_FRIEND, HCB_WHY_OURS) and c[homie] == c[recruit] == c[mission_friend] == (HCB_CLS_FRIEND, HCB_WHY_ALLY), c
assert c[turncoat] == (HCB_CLS_THREAT, HCB_WHY_ARMED_FACING), c
assert sc.brain.out.alert == HCB_ALERT_THREAT and sc.brain.out.n_threats == 1
sc.damage(homie, 1, 5)                                 # an accident
sc.step(1)
assert classes(sc)[homie][0] == HCB_CLS_FRIEND
sc.damage(homie, 1, 30)                                # that was no accident
sc.step(1)
assert classes(sc)[homie] == (HCB_CLS_ATTACKER, HCB_WHY_HURT_CJ)
sc.damage(gunner, 1, 50)                               # our own people are never judged by this code: the hard rules stop them earlier
sc.step(1)
assert classes(sc)[gunner][0] == HCB_CLS_FRIEND
passed('Friends come from the game: ours, Grove, recruited homies, whoever respects CJ - even armed and looking at him. Hatred set by the game overrides the uniform, and an "ally" who puts 20+ damage into CJ is an attacker')

# ------------------------------------------------------------------ missions
sc = Scene(on_mission=1)
target = sc.ped(20, 0, pedtype=GANG, weapon=AK, flags=HCB_PF_MISSION)       # somebody the mission placed
ambient = sc.ped(-20, 0, pedtype=GANG, weapon=AK)
sc.step(2)
c = classes(sc)
assert c[target] == (HCB_CLS_WATCH, HCB_WHY_ARMED_FACING) and c[ambient][0] == HCB_CLS_THREAT, c
sc.peds[target]['target'] = 1
sc.step(4)
assert classes(sc)[target] == (HCB_CLS_THREAT, HCB_WHY_AIMS_AT_CJ)
sc.peds[target]['target'] = 0
sc.shot(target, (0., 0.5, 1.))
sc.step(1)
assert classes(sc)[target][0] == HCB_CLS_ATTACKER
passed('In a mission the mission\'s own people are only watched until they put a weapon on CJ or attack - the brain does not start the mission\'s fights for it')

# ------------------------------------------------------------------ vehicles
def car(x, y, vel, cj_in_car=False, driver_type=CIV, **kw):
    sc = Scene()
    d = sc.ped(x, y, pedtype=driver_type)
    v = sc.veh(x, y, vel=vel, driver=d, **kw)
    if cj_in_car:
        sc.cj['vehicle'] = sc.veh(0, 0)
    sc.step(1)
    return sc, v


sc, v = car(-20, 0.5, (15., 0., 0.))                   # 1.3 s away, straight at him
assert classes(sc)[v] == (HCB_CLS_THREAT, HCB_WHY_RAMMING) and sc.brain.out.alert == HCB_ALERT_THREAT
sc, v = car(-20, 6, (15., 0., 0.))                     # passes 6 m in front
assert v not in classes(sc)
sc, v = car(-8, 0.5, (5., 0., 0.))                     # crawling: 1.6 s away, but at walking pace
assert v not in classes(sc)
sc, v = car(-60, 0.5, (15., 0., 0.))                   # 4 s away
assert v not in classes(sc)
sc, v = car(20, 0.5, (15., 0., 0.))                    # driving away
assert v not in classes(sc)
sc, v = car(-20, 0.5, (15., 0., 0.), cj_in_car=True)   # CJ is in a car himself
assert v not in classes(sc)
passed('A car whose path comes within 2.5 m of CJ in the next 2 s at 8 m/s or more is called out as RAMMING; passing wide, slow, far, leaving, or CJ in a car - not')
sc = Scene()
b1 = sc.veh(8, 0, health=200., flags=HCB_VF_BURNING)
b2 = sc.veh(30, 0, health=200., flags=HCB_VF_BURNING)
b3 = sc.veh(-8, 0, health=0., flags=HCB_VF_BURNING | HCB_VF_WRECKED)
sc.heli = sc.veh(0, 10, vel=(0., -12., 0.), z=20., cls=HCB_VC_HELI)
pilot = sc.our(0, 10, HCB_ROLE_PILOT)
sc.vehs[sc.heli]['driver'] = pilot
sc.step(1)
c = classes(sc)
assert c[b1] == (HCB_CLS_THREAT, HCB_WHY_BURNING) and b2 not in c and b3 not in c and sc.heli not in c, c
passed('A burning car within 14 m of CJ is a hazard; a wreck or a distant fire is not, and our own helicopter never is')

# ------------------------------------------------------------------ alert level
sc = Scene()
sc.step(2)
assert sc.brain.out.alert == HCB_ALERT_CALM
g = sc.ped(0, 12, pedtype=GANG)
sc.step(1)
assert sc.brain.out.alert == HCB_ALERT_WARY
sc.peds[g]['weapon'] = AK
sc.step(1)
assert sc.brain.out.alert == HCB_ALERT_THREAT
sc.shot(g, (0., 0., 1.), dst=1)
sc.step(1)
assert sc.brain.out.alert == HCB_ALERT_COMBAT
sc.peds[g]['flags'] |= HCB_PF_DEAD
levels = []
for _ in range(200):
    levels.append(sc.step(1).alert)
steps = [i for i in range(1, len(levels)) if levels[i] != levels[i - 1]]
assert levels[0] == HCB_ALERT_COMBAT and levels[-1] == HCB_ALERT_CALM and [levels[i] for i in steps] == [2, 1, 0], (levels[:5], steps)
assert all(55 <= b - a <= 65 for a, b in zip([0] + steps, steps)), steps
passed('The alert level rises at once (calm, wary, threat, combat) and comes down one step per 6 quiet seconds, not straight to calm')
sc = Scene()
for k in range(4):
    g = sc.ped(10 + k, 5 * k, pedtype=GANG, weapon=AK)
    sc.shot(g, (0., 0., 1.), dst=1)
sc.step(1)
assert sc.brain.out.alert == HCB_ALERT_EVACUATE and sc.brain.out.danger >= sc.brain.cfg.evac_danger, sc.brain.out.danger
sc = Scene()
g = sc.ped(30, 0, pedtype=GANG, weapon=PISTOL)
sc.shot(g, (0., 0., 1.), dst=1)
sc.step(1)
assert sc.brain.out.alert == HCB_ALERT_COMBAT
sc.cj['health'] = 25.
sc.step(1)
assert sc.brain.out.alert == HCB_ALERT_EVACUATE
sc.cutscene = 1
sc.step(70)
assert sc.brain.out.alert < HCB_ALERT_EVACUATE
passed('Four riflemen on CJ at once, or any attacker while CJ is below 30 health, means EVACUATE; a cutscene lets the level fall')

# ------------------------------------------------------------------ who is the most dangerous
sc = Scene()
far_pistol = sc.ped(34, 0, pedtype=GANG, weapon=PISTOL)
close_rifle = sc.ped(0, 12, pedtype=GANG, weapon=AK)
aiming = sc.ped(-15, 0, pedtype=GANG, weapon=AK, target=1)
watcher = sc.ped(0, -30, pedtype=GANG, weapon=AK, face='away')
sc.step(4)
order = [m.id for m in sc.brain.out.marks[:sc.brain.out.n_marks]]
mk = sc.brain.marks()
assert order[:3] == [aiming, close_rifle, far_pistol] and order[3] == watcher and sc.brain.out.top == aiming, order
assert mk[aiming].edps > mk[close_rifle].edps > mk[far_pistol].edps > 0 and mk[watcher].edps > 0   # (class first: the man looking away ranks last even with a rifle)
assert abs(sc.brain.out.danger - sum(m.edps for m in mk.values())) < 1e-3
sc = Scene()
near, mid, far, out_of_range = [sc.ped(d, 0, pedtype=GANG, weapon=w) for d, w in ((10, AK), (60, AK), (100, AK), (60, PISTOL))]
for s_ in (near, mid, far, out_of_range):
    sc.shot(s_, (0., 0., 1.), dst=1)
sc.step(1)
mk = sc.brain.marks()
assert mk[near].edps > mk[mid].edps > mk[far].edps > 0 and mk[out_of_range].edps == 0 and all(m.cls == HCB_CLS_ATTACKER for m in mk.values()), [(m.dist, m.edps) for m in mk.values()]
passed('Contacts are ranked by the damage they can be expected to do to CJ: the rifle already on him, then the rifle close by, then the pistol at long range, then the man looking away; the same rifle counts for less the further away it is, and a pistol at 60 m for nothing')

# ------------------------------------------------------------------ a crowd bigger than the memory
sc = Scene()
shooters = []
for k in range(6):
    s = sc.ped(40 + k, 0, pedtype=GANG, weapon=AK)
    sc.shot(s, (0., 0., 1.), dst=1)
    shooters.append(s)
sc.step(1)
rnd = random.Random(5)
for k in range(300):
    sc.ped(rnd.uniform(-35, 35), rnd.uniform(-35, 35))
for _ in range(20):
    for p in list(sc.peds):
        if p not in shooters and rnd.random() < .3:
            del sc.peds[p]
            sc.ped(rnd.uniform(-35, 35), rnd.uniform(-35, 35))
    sc.step(1)
assert all(sc.brain.cls(s) == HCB_CLS_ATTACKER for s in shooters) and sc.brain.out.n_attackers == 6 and sc.snapshots[-1].peds_lost > 200
passed('300 people around CJ (64 fit in a snapshot, 96 in memory): the six who fired, standing further away than all of them, are never pushed out')

# ------------------------------------------------------------------ black box: record, decode, replay
def random_fight(seed, ticks=300, recorder=None, state_every=0):
    rnd = random.Random(seed)
    sc = Scene(wanted=rnd.choice([0, 0, 2]))
    sc.recorder = recorder
    sc.state_every = state_every
    for k in range(4):
        sc.our(rnd.uniform(-5, 5), rnd.uniform(-5, 5), HCB_ROLE_SQUAD + k, weapon=AK)
    digests = []
    for t in range(ticks):
        if rnd.random() < .15 and len(sc.peds) < 90:
            sc.ped(rnd.uniform(-60, 60), rnd.uniform(-60, 60), pedtype=rnd.choice([CIV, CIV, GANG, COP, GROVE]), weapon=rnd.choice([0, 0, PISTOL, AK, BAT]),
                   vel=(rnd.uniform(-3, 3), rnd.uniform(-3, 3), 0.), flags=rnd.choice([0, 0, HCB_PF_MISSION, HCB_PF_HATES]))
        if rnd.random() < .05 and len(sc.vehs) < 30:
            d = sc.ped(0, 0, pedtype=rnd.choice([CIV, GANG]))
            sc.veh(rnd.uniform(-50, 50), rnd.uniform(-50, 50), vel=(rnd.uniform(-20, 20), rnd.uniform(-20, 20), 0.), driver=d, flags=rnd.choice([0, 0, HCB_VF_BURNING]))
        strangers = [p for p in sc.peds if p not in sc.ours]
        for p in strangers:
            r = rnd.random()
            if r < .02:
                sc.peds[p]['target'] = rnd.choice([0, 1, next(iter(sc.ours))])
            elif r < .04 and sc.peds[p]['weapon'] >= 22:
                sc.shot(p, (rnd.uniform(-8, 8), rnd.uniform(-8, 8), 1.), dst=rnd.choice([0, 0, 1]))
            elif r < .05:
                sc.damage(p, rnd.choice([1, next(iter(sc.ours))]), rnd.uniform(3, 40))
            elif r < .06:
                del sc.peds[p]
        sc.cj['vel'] = [rnd.uniform(-4, 4), rnd.uniform(-4, 4), 0.]
        digests.append((sc.step(1).digest, sc.brain.out.alert, sc.brain.out.n_marks))
    return sc, digests


rec = Recorder(1 << 22)
sc, digests = random_fight(11, recorder=rec)
records = rec.records()
assert len(records) == len(digests) == rec.rec.records and rec.rec.dropped == 0
assert all(bytes(a) == bytes(b_) for (a, _), b_ in zip(records, sc.snapshots)), 'every snapshot comes back byte for byte'
assert [d for _, d in records] == [d for d, _, _ in digests]
replay = Brain()
again = [(replay.think(s).digest, replay.out.alert, replay.out.n_marks) for s, _ in records]
assert again == digests and len({d for d, _, _ in digests}) > 50 and max(a for _, a, _ in digests) >= HCB_ALERT_COMBAT
size = rec.rec.end - rec.rec.start
passed('Black box: a random 30 s fight (%d snapshots, %.0f kB) decodes byte for byte and replays in a fresh brain to exactly the same decisions, tick by tick' % (len(records), size / 1024.))
small = Recorder(200 * 1024)
sc, digests = random_fight(12, recorder=small)
tail = small.records()
assert small.rec.dropped > 0 and small.rec.records == len(tail) and 20 < len(tail) < len(digests) and small.rec.end <= small.rec.cap
assert all(bytes(a) == bytes(b_) for (a, _), b_ in zip(tail, sc.snapshots[-len(tail):])) and [d for _, d in tail] == [d for d, _, _ in digests[-len(tail):]]
broken = Recorder(1 << 20)
sc_, _ = random_fight(13, ticks=30, recorder=broken)
assert len(broken.records()) == 30
at = broken.rec.start + 12 + hcb_snapshot.n_peds.offset           # the first record now claims one ped more than it holds
broken.buf[at] += 1
assert broken.records() == [], 'a record whose length does not match its counts is refused, not read past its end'
# the brain's own memory is stored every 5 s: a replay that starts there is exact even though the beginning is gone
ring = Recorder(700 * 1024)
sc, digests = random_fight(14, ticks=400, recorder=ring, state_every=50)
recs = ring.all()
first_state = next(i for i, r in enumerate(recs) if r[0] == 'state')
kept = [r for r in recs if r[0] == 'snapshot']
assert ring.rec.dropped > 0 and len(kept) < 400 and first_state > 0, (ring.rec.dropped, len(kept), first_state)
replay = Brain(seed=99)
after = 0
for r in recs[first_state:]:
    if r[0] == 'state':
        ctypes.memmove(replay.mem, r[1], len(r[1]))
    else:
        assert replay.think(r[1]).digest == r[2], 'a replay from a stored state reproduces every later decision'
        after += 1
cold = Brain()
differs = sum(cold.think(r[1]).digest != r[2] for r in kept[:20])
assert after > 100 and differs > 0, (after, differs)
passed('Black box with the brain\'s memory stored every 5 s: after the ring has dropped its beginning, a replay from the first stored state reproduces all %d later decisions exactly (a cold start on the same data gets %d of the first 20 wrong)' % (after, differs))
# the report file
import hcb_py as _h
data = ring.box(sc.brain, 'device: test\n')
head, recs2, text = _h.read_box(data)
assert head.seed == 1 and _h.read_box(Recorder(4096).box(Brain(seed=77)))[0].seed == 77, 'the seed the brain was started with travels in the report'
assert text == 'device: test\n' and head.records == ring.rec.records and head.dropped == ring.rec.dropped and len(recs2) == len(recs) and [r[0] for r in recs2] == [r[0] for r in recs]
assert all(bytes(a[1]) == bytes(b_[1]) for a, b_ in zip(recs, recs2))
for bad, why in ((b'junk' + data, 'not a'), (data[:len(data) // 2], 'cut short'), (data[:8] + bytes([9]) + data[9:], 'another version')):
    try:
        _h.read_box(bad)
        raise AssertionError('accepted a bad report: ' + why)
    except ValueError as e:
        assert why in str(e), (why, str(e))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import replay as replay_tool
head, text, ticks = replay_tool.replay(data)
exact = [t for t in ticks if t['exact']]
assert len(ticks) == len(kept) and len(exact) == after and all(t['match'] for t in exact)
report = replay_tool.summarize(data)
assert 'reproduce the phone\'s decisions exactly' in report and 'ATTACKER' in report and 'alert COMBAT' in report and 'device: test' in report, report[:600]
passed('The report file (head, records, text) reads back whole; a file that is not a report, is cut short or comes from another version of the brain is refused with a plain reason. tools/replay.py turns a report into a timeline (alert changes, who became a threat and why) and confirms the replay is exact')
passed('Black box in a small buffer: the oldest records make room (%d dropped), the last %d are intact and in order; a damaged record is refused' % (small.rec.dropped, len(tail)))
for seed in range(20):
    a = random_fight(100 + seed, ticks=120)[1]
    b_ = random_fight(100 + seed, ticks=120)[1]
    assert a == b_, seed
passed('Twenty random fights run twice give identical decisions: the core has no hidden state and no hidden randomness')

# ------------------------------------------------------------------ garbage in
rnd = random.Random(3)
br = Brain()
for _ in range(300):
    s = hcb_snapshot()
    raw = bytes(rnd.getrandbits(8) for _ in range(ctypes.sizeof(s)))
    ctypes.memmove(ctypes.byref(s), raw, len(raw))
    br.think(s)
    assert br.out.n_marks <= HCB_MAX_MARKS and br.out.alert <= HCB_ALERT_EVACUATE
r = Recorder(64 * 1024)
for _ in range(50):
    s = hcb_snapshot()
    raw = bytes(rnd.getrandbits(8) for _ in range(ctypes.sizeof(s)))
    ctypes.memmove(ctypes.byref(s), raw, len(raw))
    r.push(s, 1)
junk = (ctypes.c_uint8 * 4096)(*[rnd.getrandbits(8) for _ in range(4096)])
off, s = ctypes.c_uint32(0), hcb_snapshot()
while hcb_py.LIB.hcb_rec_next(junk, 4096, ctypes.byref(off), ctypes.byref(s), None):
    pass
passed('300 snapshots of pure noise (counts beyond the arrays, NaNs, wild ids) and a damaged black box: no crash, outputs stay in range')

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
hcb_py.OUT.mkdir(parents=True, exist_ok=True)
(hcb_py.OUT / 'brain_core_tests.txt').write_text(text)
print(text)
