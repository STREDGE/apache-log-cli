"""1.0: the squad's two modes (hcb_squad.c with hcb_detail.c), on the host build of the core.
    python3 brain/tests/test_squad.py
PROTECT: three at CJ, four in cover that sees CJ and the attackers, the marksman on a high place. ASSAULT: the squad goes for
the target by itself - gather, fire and movement by pairs, search, consolidate, back to CJ. Each drill checks what can be SEEN."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


SQ, M4, AK, GANG, CIV = HCB_ROLE_SQUAD, 31, 30, 7, 4
JOB = {HCB_ROLE_LEAD: 'lead', HCB_ROLE_CLOSE: 'close', HCB_ROLE_POINT: 'point', HCB_ROLE_REAR: 'rear', HCB_ROLE_CLOSE2: 'close2', HCB_ROLE_POINT2: 'point2',
       HCB_ROLE_REAR2: 'rear2', HCB_ROLE_MARKSMAN: 'delta'}
EIGHT = ((1.2, -0.8), (-1.8, 3.5), (-9., 11.), (-1.6, -2.2), (-12., -8.), (12., -8.), (9., 11.), (16., -7.))
TASK = {v: k[9:] for k, v in vars(hcb_py).items() if k.startswith('HCB_TASK_')}


def d2(a, b):
    return math.dist(a[:2], b[:2])


def at(p):
    return (p.at.x, p.at.y)


def squad(sc, n=8):
    t = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(EIGHT[:n])]
    sc.walk_posts = True
    return t


def by_job(sc):
    return {JOB[p.job]: p for p in sc.posts.values()}


def pos(sc, who):
    return sc.peds[who]['pos']


# ================================================================== PROTECT
# ------------------------------------------------------------------ a fight: exactly three at CJ; four out in cover that sees CJ and the shooter
LOW = [(10., -13., 10., -9.), (10., 9., 10., 13.), (-6., -14., -6., -10.), (-6., 10., -6., 14.), (13., -5., 13., -3.), (13., 3., 13., 5.), (-9., -17., -9., -13.), (-9., 13., -9., 17.),
       (15.5, 16., 15.5, 20.), (15.5, -20., 15.5, -16.), (-11., 17.5, -11., 21.), (-11., -21., -11., -17.5)]   # (1.5: cover out where the outer men are now)
sc = Scene(); sc.low_walls = list(LOW); team = squad(sc); sc.step(30)
g = sc.ped(34, 0, pedtype=GANG, weapon=AK, face=(-1., 0.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
near_hist, sees_both, on_post = [], 0, 0
for k in range(150):
    if k % 12 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
    j = by_job(sc)
    if k >= 60:
        near_hist.append(sum(1 for w in team if d2(pos(sc, w), sc.cj['pos']) < 4.5))
        for name in ('point', 'point2', 'rear', 'rear2'):
            p = j[name]
            if d2(pos(sc, p.who), at(p)) < 1.6:
                on_post += 1
                # a standing man there sees CJ and the shooter; crouched he is hidden from the shooter
                if not sc.blocked(pos(sc, p.who), sc.cj['pos'], low_too=False) and not sc.blocked(pos(sc, p.who), pos(sc, g), low_too=False):
                    sees_both += 1
assert sc.last_out.task == HCB_TASK_SHIELD and sc.last_out.umode == HCB_UMODE_PROTECT, TASK[sc.last_out.task]
assert set(near_hist) == {3}, ('exactly three stay at CJ', sorted(set(near_hist)))
assert {JOB[sc.posts[w].job] for w in team if d2(pos(sc, w), sc.cj['pos']) < 4.5} == {'lead', 'close', 'close2'}
outs = {n_: at(j[n_]) for n_ in ('point', 'point2', 'rear', 'rear2')}
assert all(15 <= d2(p_, sc.cj['pos']) <= 35 for p_ in outs.values()), ('1.5: the four are 15-35 m out', outs)
hidden = [n_ for n_, p_ in outs.items() if sc.blocked(pos(sc, g), p_)]
assert len(hidden) >= 3, ('behind something a crouching man is hidden by', outs, hidden)
share = sees_both / max(on_post, 1)
assert on_post > 200 and share >= 0.8, ('on their posts they see CJ and the attacker', on_post, share)
passed('PROTECT, a fight: exactly THREE at CJ the whole time (the commander and two bodyguards); the other four on posts 15-35 m out, %d of 4 behind low cover; standing there a man sees both CJ and the attacker %d %% of his time on the post' % (len(hidden), round(100 * share)))

# ------------------------------------------------------------------ the marksman: a high place, the helicopter takes him there
sc = Scene(); team = squad(sc, 7); sc.step(20)                     # seven on the ground: the marksman has not come down yet
heli = sc.veh(0., -30., cls=HCB_VC_HELI, z=30.); sc.heli = heli
sc.high = [(22., 14., 9., True), (40., -10., 3., True), (-25., 5., 12., False), (90., 0., 10., True)]
o = sc.step(3)
assert o.ow_ok and d2((o.ow_at.x, o.ow_at.y), (22., 14.)) < 0.1, ('the roof 9 m up, 26 m off, that sees CJ - not the low one, not the blind one, not the far one', o.ow_ok, o.ow_at.x, o.ow_at.y)
assert o.heli_ok and d2((o.heli_at.x, o.heli_at.y), (22., 14.)) < 0.1 and abs(o.heli_at.z - 20.) < 0.5 and not o.ow_ready, ('the helicopter is sent over it, 11 m above', o.heli_at.z)
sc.vehs[heli]['pos'] = [22.5, 14.5, 20.3]
o = sc.step(3)
assert o.ow_ready, 'steady over the roof: the rope may go down'
sc.vehs[heli]['vel'] = [4., 0., 0.]
o = sc.step(2)
assert not o.ow_ready, 'the helicopter moves: not now'
sc.vehs[heli]['vel'] = [0., 0., 0.]; sc.vehs[heli]['pos'] = [22.5, 14.5, 20.3]
m = sc.our(22., 14., SQ + 7, weapon=34, z=20.); sc.roping = {m}
o = sc.step(2)
assert not o.ow_ok and (m not in sc.posts or sc.posts[m].why == HCB_WHY2_IN_AIR), 'he is on the rope: the helicopter is free again, he gets no order'
sc.roping = set(); sc.peds[m]['pos'] = [22., 14., 10.]
sc.step(10)
p = sc.posts[m]
assert p.job == HCB_ROLE_MARKSMAN and p.move == 0 and d2(at(p), (22., 14.)) < 0.1 and p.act == HCB_ACT_OVERWATCH, ('on his roof he stays and watches', p.move, p.act)
g = sc.ped(30, -20, pedtype=GANG, weapon=AK, face=(-1., 0.7))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1); sc.step(20)
p = sc.posts[m]
assert p.move == 0 and d2(at(p), (22., 14.)) < 0.1 and d2((p.look.x, p.look.y), (30., -20.)) < 2, 'in a fight he stays up there, his eyes on the attacker'
passed('The marksman: of the high places the adapter has found the squad takes the one that sees CJ, 4-35 m up and 12-70 m off; the helicopter is sent to hang 11 m over it, and only when it hangs there steady may the rope go down; on the roof he stays, watches, and in a fight keeps his eyes on the attacker')
sc = Scene(); team = squad(sc, 7); sc.step(20)
heli = sc.veh(0., -30., cls=HCB_VC_HELI, z=30.); sc.heli = heli
o = sc.step(3)
assert not o.ow_ok, 'no high place known: nothing is asked of the helicopter (he comes down with the others)'
sc.high = [(22., 14., 9., True)]
for k in range(450): o = sc.step(1)
assert not o.ow_ok, 'the helicopter never got there in 40 s: the squad gives up (he comes down with the others)'
passed('No high place near, or the helicopter does not get there in 40 s: the squad does not wait - the marksman comes down with the others')

# 1.5 (the review): in a fight the helicopter is sent to hang over a roof only for a marksman who really waits aboard - not for a dead one
#      (he is "not on the ground" too): it keeps its firing spot
sc = Scene(); team = squad(sc, 7); sc.step(20)
heli = sc.veh(0., -30., cls=HCB_VC_HELI, z=30.); sc.heli = heli
sc.high = [(22., 14., 9., True)]
g = sc.ped(34, 0, pedtype=GANG, weapon=AK, face=(-1., 0.))
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
ow_seen = 0
for k in range(60):
    if k % 12 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    o = sc.step(1)
    ow_seen += bool(o.ow_ok)
assert ow_seen == 0, ('1.5: a fight, nobody aboard waiting for a roof: the helicopter is not sent over one', ow_seen)
passed('1.5: in a fight with no marksman waiting aboard (dead, or never picked up) the helicopter is not sent to hang over a roof - it keeps its firing spot')

# ================================================================== ASSAULT
def assault(target=(0., 70.), n=8, pedtype=CIV, weapon=0, walls=()):
    sc = Scene(); sc.low_walls = list(walls); team = squad(sc, n); sc.step(30)
    g = sc.ped(target[0], target[1], pedtype=pedtype, weapon=weapon, face=(0., -1.))
    sc.umode = HCB_UMODE_ASSAULT
    return sc, team, g


# ------------------------------------------------------------------ no target: the mode waits, the squad is with CJ
sc, team, g = assault()
sc.step(20)
assert sc.last_out.umode == HCB_UMODE_ASSAULT and sc.last_out.task == HCB_TASK_REGROUP and sc.last_out.target == 0, TASK[sc.last_out.task]
assert sum(1 for w in team if d2(pos(sc, w), sc.cj['pos']) < 5.0) == 3, 'nobody has gone anywhere: a passer-by is not a target'
passed('ASSAULT with nobody pointed out and no threat: the squad stays with CJ (task REGROUP), a passer-by 70 m off is not a target')

# 1.5 (the review): only the commander and a bodyguard left - nobody to send: back with CJ, not an assault nobody makes
sc, team, g = assault(n=2)
sc.cj['target'] = g; sc.step(3); sc.cj['target'] = 0
for k in range(40):
    if k % 30 == 0: sc.cj['target'] = g
    elif k % 30 == 3: sc.cj['target'] = 0
    sc.step(1)
assert sc.last_out.umode == HCB_UMODE_ASSAULT and sc.last_out.task == HCB_TASK_REGROUP, ('1.5: no outer man left: REGROUP', TASK[sc.last_out.task])
assert all(d2(pos(sc, w), sc.cj['pos']) < 5.0 for w in team), 'and both stay at CJ'
passed('1.5: ASSAULT with only the commander and a bodyguard left (nobody to send): the task is REGROUP at CJ, neither leaves him')

# ------------------------------------------------------------------ CJ points a man out: approach, gather, bounds - by itself
sc, team, g = assault()
sc.cj['target'] = g; sc.step(3); sc.cj['target'] = 0
tasks, first_pos_t, movers_max, pair_both = [], None, 0, 0
front0 = None
lead_far = 0.0
for k in range(700):
    if k % 30 == 0: sc.cj['target'] = g
    elif k % 30 == 3: sc.cj['target'] = 0
    o = sc.step(1)
    tasks.append(o.task)
    j = by_job(sc)
    if k >= 20: lead_far = max(lead_far, d2(pos(sc, j['lead'].who), sc.cj['pos']), d2(at(j['lead']), sc.cj['pos']))
    if o.task == HCB_TASK_BOUND:
        a1 = [j[n_] for n_ in ('point',) if n_ in j]; a2 = [j[n_] for n_ in ('point2',) if n_ in j]     # (1.3: the bodyguards stay with CJ)
        m1 = sum(1 for p in a1 if p.move); m2 = sum(1 for p in a2 if p.move)
        if m1 and m2: pair_both += 1
        if first_pos_t is None and any(p.phase >= HCB_PH_ARRIVED and d2(at(p), pos(sc, g)) < 40 for p in a1 + a2 + [j['rear'], j['rear2']]):
            first_pos_t = k / 10.
order = [t for i, t in enumerate(tasks) if i == 0 or tasks[i - 1] != t]
assert order[:3] == [HCB_TASK_APPROACH, HCB_TASK_GATHER, HCB_TASK_BOUND], [TASK[t] for t in order]
assert sc.last_out.target == g and d2((sc.last_out.target_at.x, sc.last_out.target_at.y), pos(sc, g)) < 0.5
j = by_job(sc)
ass = [d2(pos(sc, j[n_].who), pos(sc, g)) for n_ in ('point', 'point2')]
fire = [d2(pos(sc, j[n_].who), pos(sc, g)) for n_ in ('rear', 'rear2')]
body = [d2(pos(sc, j[n_].who), sc.cj['pos']) for n_ in ('close', 'close2')]
assert max(ass) < 16 and min(ass) >= 7.5, ('the assault pair has closed to 9-14 m, nobody ran INTO the target', ass)
assert all(20 <= d_ <= 52 for d_ in fire), ('the fire team stayed back, 30-46 m', fire)
assert all(d_ < 4.0 for d_ in body), ('1.3: the two bodyguards never left CJ (the first 2.0 log: CJ died alone during an assault)', body)
assert lead_far < 5.0, ('1.5 (the player: "only the bodyguards and the commander at my side"): the commander never goes with the assault', lead_far)
left = [pos(sc, j[n_].who) for n_ in ('point',)]; right = [pos(sc, j[n_].who) for n_ in ('point2',)]
assert all(p_[0] < -2 for p_ in left) and all(p_[0] > 2 for p_ in right), ('the pairs came in on the two flanks, not down the fire team\'s line', left, right)
# (each on his own flank line, the same way out on either side: with the old 4 m side offset the left man ended 3.7 m off the line to the
#  target - in front of the fire team's rifles - and the right one 14 m)
assert all(5. <= abs(p_[0]) <= 12. for p_ in left + right) and abs(abs(left[0][0]) - abs(right[0][0])) < 5., ('the two flanks are the same way out: 5-12 m off the line from CJ to the target', left, right)
bound_ticks = tasks.count(HCB_TASK_BOUND)
assert pair_both <= 0.12 * bound_ticks, ('one pair at a time: both pairs on the move in %d of %d looks' % (pair_both, bound_ticks))
assert all(d2(pos(sc, a_), pos(sc, b_)) > 1.5 for a_ in team for b_ in team if a_ < b_), 'no two men on one spot'
near_cj = sorted(JOB[sc.posts[w].job] for w in team if d2(pos(sc, w), sc.cj['pos']) < 6)
assert d2(sc.cj['pos'], (0, 0)) < 0.1 and set(near_cj) == {'lead', 'close', 'close2'}, ('CJ stood still: the squad went by itself - 1.3: with the two bodyguards at his side; 1.5 (the player: "only the bodyguards and the commander at my side"): the commander stays with him too', near_cj)
t_first = first_pos_t
passed('ASSAULT on a man CJ points out 70 m off: APPROACH -> GATHER -> BOUND by itself (CJ did not move; the commander and the two bodyguards stay at his side); the assault four close in pairs on the two flanks to 9-14 m, one pair at a time (both moving in %d of %d looks), the fire team holds 30-46 m back; nobody on the same spot' % (pair_both, bound_ticks))

# ------------------------------------------------------------------ the measured criterion: from 60 m, the first place taken near the target
sc, team, g = assault(target=(0., 60.), pedtype=GANG, weapon=AK)
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1)
t_pos = None
for k in range(400):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    o = sc.step(1)
    if t_pos is None and o.task >= HCB_TASK_GATHER and any(p.phase >= HCB_PH_ARRIVED and d2(pos(sc, p.who), pos(sc, g)) < 45 for p in sc.posts.values() if p.job not in (HCB_ROLE_LEAD,)):
        t_pos = k / 10.
assert t_pos is not None and t_pos <= 20., ('a confirmed threat 60 m off: the first man is in a place within 45 m of it', t_pos)
passed('ASSAULT on a confirmed threat 60 m off (it fires at CJ): the first man stands in a place within 45 m of it after %.1f s (criterion: 20 s)' % t_pos)

# ------------------------------------------------------------------ the target falls: consolidate beside the spot, then back to CJ; the mode stays
sc, team, g = assault(target=(0., 40.), pedtype=GANG, weapon=AK)
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1); sc.step(150)
gp = list(pos(sc, g))
sc.peds[g]['flags'] |= HCB_PF_DEAD
tasks = []
for k in range(600):
    o = sc.step(1); tasks.append(o.task)
    if o.task == HCB_TASK_CONSOLIDATE and k > 40 and 'cons' not in dir():
        cons = [pos(sc, w)[:2] for w in team]; looks = [(sc.posts[w].look.x, sc.posts[w].look.y) for w in team]
order = [t for i, t in enumerate(tasks) if i == 0 or tasks[i - 1] != t]
assert order[:2] == [HCB_TASK_CONSOLIDATE, HCB_TASK_REGROUP], [TASK[t] for t in order]
assert 70 <= tasks.count(HCB_TASK_CONSOLIDATE) <= 90, 'eight seconds of all-round watch'
assert all(d2(c_, gp) > 3.0 for c_ in cons), ('nobody stands ON the spot', cons)
assert sc.last_out.umode == HCB_UMODE_ASSAULT, 'the mode is still ASSAULT: it waits for the next target'
assert sum(1 for w in team if d2(pos(sc, w), sc.cj['pos']) < 5.0) == 3 and all(d2(pos(sc, w), sc.cj['pos']) < 34 for w in team), 'everybody is back with CJ, three at his side (1.5: the outer men at their places 15-33 m out)'
passed('The target is down: CONSOLIDATE - eight seconds of all-round watch beside the spot (nobody on it) - then REGROUP: back to CJ, three at his side again; the mode stays ASSAULT and waits for the next target')

# ------------------------------------------------------------------ the target out of sight: to where it was last SEEN, not to where it is
sc, team, g = assault(target=(0., 55.), pedtype=GANG, weapon=AK)
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1); sc.step(60)
seen_at = list(pos(sc, g))
del sc.peds[g]                                                    # gone (round a corner, into a car - the brain does not see him)
tasks, tat = [], []
for k in range(260):
    o = sc.step(1); tasks.append(o.task); tat.append((o.target_at.x, o.target_at.y))
assert HCB_TASK_SEARCH in tasks, [TASK[t] for t in sorted(set(tasks))]
assert all(d2(t_, seen_at) < 1.0 for t_, k_ in zip(tat, tasks) if k_ in (HCB_TASK_SEARCH, HCB_TASK_BOUND)), 'the squad goes to where he was last seen'
assert sc.last_out.target == 0, 'nobody is "the target" while nobody is seen'
assert tasks[-1] in (HCB_TASK_REGROUP, HCB_TASK_CONSOLIDATE, HCB_TASK_SEARCH)
for k in range(300): o = sc.step(1)
assert o.task == HCB_TASK_REGROUP, ('20 s without sight: the task is over', TASK[o.task])
passed('The target goes out of sight: after 6 s the squad SEARCHES - towards the place where he was last seen (his real position is not known to it); 20 s without sight and the task is over, back to CJ')

# ------------------------------------------------------------------ the player changes his mind on the move
sc, team, g = assault(target=(0., 70.))
sc.cj['target'] = g; sc.step(60)
ids = set(sc.posts)
assert sc.last_out.task in (HCB_TASK_APPROACH, HCB_TASK_GATHER)
sc.umode = HCB_UMODE_PROTECT
o = sc.step(2)
assert o.umode == HCB_UMODE_PROTECT and o.task == HCB_TASK_ESCORT and set(sc.posts) == ids, 'PROTECT at once, the same eight men'
j = by_job(sc)
assert d2(at(j['lead']), sc.cj['pos']) < 2 and all(d2(at(j[n_]), sc.cj['pos']) < 35 for n_ in j), 'every place is round CJ again - planned from where each man stands (1.5: the outer men 15-33 m out)'
sc.step(200)
assert sum(1 for w in team if d2(pos(sc, w), sc.cj['pos']) < 5.0) == 3
sc.umode = HCB_UMODE_ASSAULT; sc.cj['target'] = g; sc.step(40)
assert sc.last_out.task in (HCB_TASK_APPROACH, HCB_TASK_GATHER, HCB_TASK_BOUND)
sc.recall = 1; o = sc.step(2)
assert o.task == HCB_TASK_REGROUP and o.umode == HCB_UMODE_ASSAULT, '"to me": the task is dropped, the mode is not'
sc.recall = 0
passed('Switching on the move: ASSAULT -> PROTECT gives every man his place round CJ at once (nobody is re-created); "to me" drops the task and keeps the mode')

# ------------------------------------------------------------------ CJ is hurt during an assault: the two bodyguards come back, the rest go on
sc, team, g = assault(target=(0., 60.), pedtype=GANG, weapon=AK)
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1); sc.step(120)
sc.cj['health'] = 30.
for k in range(120):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    sc.step(1)
j = by_job(sc)
assert all(d2(pos(sc, j[n_].who), sc.cj['pos']) < 5 for n_ in ('close', 'close2')), 'both bodyguards are back at CJ'
assert sc.last_out.umode == HCB_UMODE_ASSAULT and any(d2(pos(sc, j[n_].who), sc.cj['pos']) > 15 for n_ in ('point', 'point2', 'rear', 'rear2')), 'the others carry on; the mode is the player\'s'
sc.cj['health'] = 100.
passed('CJ badly hurt during an assault: the two bodyguards come back to him while that lasts, the rest go on; the mode stays what the player chose')

# ------------------------------------------------------------------ three down: enough
sc, team, g = assault(target=(0., 60.), pedtype=GANG, weapon=AK)
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1); sc.step(60)
for w in team[5:8]: sc.peds[w]['flags'] |= HCB_PF_DEAD
for k in range(30):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    o = sc.step(1)
assert o.task == HCB_TASK_WITHDRAW, TASK[o.task]
passed('Three of ours down since the task began: WITHDRAW - the squad goes back to CJ and protects him')

# ------------------------------------------------------------------ the commander falls in an assault
sc, team, g = assault(target=(0., 60.), pedtype=GANG, weapon=AK)
sc.step(2); sc.shot(g, (0., 0., 1.), dst=1); sc.step(60)
jobs_before = {w: sc.posts[w].job for w in team[2:]}
sc.peds[team[0]]['flags'] |= HCB_PF_DEAD
o = sc.step(3)
assert o.lead == team[1] and o.task in (HCB_TASK_GATHER, HCB_TASK_BOUND, HCB_TASK_APPROACH), (o.lead, TASK[o.task])
passed('The commander falls during an assault: the next man takes command, the task goes on')

# ------------------------------------------------------------------ a "roof" must be a roof: 4 m up or more
sc = Scene(); team = squad(sc, 7); sc.heli = sc.veh(0, 30, z=30., cls=HCB_VC_HELI)
sc.high = [(25., 5., 3.2, 1)]; sc.step(40)
assert sc.last_out.ow_ok == 0, 'a place 2-3 m above CJ is no place for the marksman'
sc.high = [(25., 5., 9., 1)]; sc.step(10)
assert sc.last_out.ow_ok == 1, sc.last_out.ow_ok
passed('Overwatch: a high place counts from 4 m above CJ\'s feet - a wall top 2 m up is not offered to the marksman')

# ------------------------------------------------------------------ the marksman is on the rope over his roof: the helicopter stays where it hangs
sc = Scene(); team = squad(sc, 7); hl = sc.veh(25., 5., z=26., cls=HCB_VC_HELI); sc.heli = hl
sc.high = [(25., 5., 15., 1)]; sc.step(40)
assert sc.last_out.ow_ok == 1 and sc.last_out.ow_ready == 1 and sc.last_out.heli_ok == 1, (sc.last_out.ow_ok, sc.last_out.ow_ready)
mk = sc.our(25., 5., SQ + 7, weapon=34, z=24.); sc.roping = {mk}       # he is put on the rope
held = []
for k in range(20):
    o = sc.step(1); held.append(o.heli_ok == 1 and abs(o.heli_at.x - 25.) < 1 and abs(o.heli_at.z - 26.) < 1.5)
assert all(held), 'the helicopter\'s spot stays over the roof while he comes down'
sc.roping = set(); sc.peds[mk]['pos'] = [25., 5., 16.]; sc.step(10)
assert sc.last_out.ow_ok == 0, 'he stands on the roof: the roof is not looked for any more'
passed('The marksman on the rope: the helicopter\'s spot stays over the roof until he stands on it (it used to be given up the moment he appeared)')

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_squad_tests.txt').write_text(text)
print(text)
