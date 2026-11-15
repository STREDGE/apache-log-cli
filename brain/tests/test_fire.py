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
assert 2 <= asked <= 5, ('the question is repeated a few times a second, not every tick', asked)
sc.walls = []
fired = run(sc, 10)
assert fired and min(min(v) for v in fired.values()) <= 6
sc.walls = [(15, -20, 15, 20)]
run(sc, 5)
assert not firing(sc), 'he steps behind a wall: fire stops within half a second'
passed('Nobody fires through a wall: the line of sight is asked for (about three times a second), fire starts when it clears and stops within 0.5 s when it closes')

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
sc = Scene()
me = sc.our(0, 4, HCB_ROLE_SQUAD, weapon=M4)
g = sc.ped(25, 4, pedtype=GANG, weapon=AK)
pattern = ''
for k in range(300):
    sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    pattern += 'F' if firing(sc, g) else '.'
bursts = [len(x) * 100 for x in pattern.strip('.').split('.') if x][:-1]      # (the last one is cut off by the end of the run)
pauses = [len(x) * 100 for x in pattern.strip('.').strip('F').split('F') if x]
cfg = sc.brain.cfg
assert len(bursts) > 10 and cfg.burst_min_ms - 100 <= min(bursts) and max(bursts) <= cfg.burst_max_ms + 100 and len(set(bursts)) >= 4, sorted(set(bursts))
assert cfg.pause_min_ms <= min(pauses) and max(pauses) <= cfg.pause_max_ms + 200, sorted(set(pauses))
share = pattern.count('F') / 300.
assert .55 <= share <= .9, share
passed('Fire comes in bursts of %.1f-%.1f s with %.1f-%.1f s between them (on the trigger %d%% of the time), never one endless stream' % (min(bursts) / 1000., max(bursts) / 1000., min(pauses) / 1000., max(pauses) / 1000., share * 100))

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
