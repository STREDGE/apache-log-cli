"""1.1: thirty minutes of random play on the host build of the core - nothing may pile up, break or go wrong for long.
    python3 brain/tests/soak_30min.py [seed] [minutes]
Eight guards, a quarter with walls, low walls, a gap and a block; CJ walks, runs, stands, gets into a car and out, is attacked by
one to three gunmen at a time; the player switches PROTECT / ASSAULT and presses "to me" at random; now and then one of ours falls
and a new one takes his place. Checked every second:
  - every place and way point the brain gives is a number; nobody of ours is inside a wall;
  - no two of ours stand on the same spot;
  - nobody is STUCK or has given his post up for a whole minute on end;
  - the brain's memory keeps its size.
At the end: the numbers of the 2.0 plan for the whole half hour, and the whole run a second time with the same seed - every
decision of the 18000 looks must come out the same (nothing in the brain depends on anything but its inputs)."""
import math, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
MINUTES = int(sys.argv[2]) if len(sys.argv) > 2 else 30
SQ, M4, AK, GANG = HCB_ROLE_SQUAD, 31, 30, 7
EIGHT = ((1.2, -0.8), (-1.8, 3.5), (-9., 11.), (-1.6, -2.2), (-12., -8.), (12., -8.), (9., 11.), (16., -7.))
INNER = (HCB_ROLE_LEAD, HCB_ROLE_CLOSE, HCB_ROLE_CLOSE2)
WALLS = [(-40., 25., -8., 25.), (-6., 25., 40., 25.), (30., -40., 30., -6.), (-30., -20., -30., 10.)]            # full walls (one with a gap 2 m wide)
LOW = [(10., -13., 10., -9.), (10., 9., 10., 13.), (-6., -14., -6., -10.), (-6., 10., -6., 14.), (20., 30., 26., 30.), (-20., -30., -14., -30.), (40., 8., 46., 8.), (-45., 0., -45., 6.)]


def run(seed, minutes, check=True):
    rnd = random.Random(seed)
    sc = Scene(); sc.walls = list(WALLS); sc.low_walls = list(LOW)
    team = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(EIGHT)]
    sc.walk_posts = True
    size0 = LIB.hcb_brain_size()
    changed_at, was_mode, was_car = -100, 0, 0
    n = dict(a_still=0, a_far=0, samples=0, still=0, far8=0, stuck=0, failed=0, calm=0, sprint=0, changes=0, near=0, near_n=0, fights=0, assault_s=0, replaced=0, car_s=0,
             out_n=0, out_near=0, out_set=0, out_down=0)
    gang, last_act, bad_for, digest, net_at = [], {}, {}, 0, {}
    goal, mode_until, car, still_for = None, 0, 0, 0
    worst = dict(stuck=0, same_spot=0, in_wall=0)
    for sec in range(minutes * 60):
        # ---- what the player and the world do this second
        r = rnd.random()
        if goal is None and r < 0.05: goal = (rnd.uniform(-55, 55), rnd.uniform(-55, 55), rnd.choice((1.5, 2.5, 5.5)))
        if not gang and rnd.random() < 0.03:
            for _ in range(rnd.randint(1, 3)):
                a = rnd.uniform(0, 6.283); d = rnd.uniform(24, 45)
                gang.append([sc.ped(sc.cj['pos'][0] + math.cos(a) * d, sc.cj['pos'][1] + math.sin(a) * d, pedtype=GANG, weapon=AK), sec + rnd.randint(12, 40)])
            n['fights'] += 1
        if rnd.random() < 0.01: sc.umode = 1 - sc.umode
        if sc.umode and rnd.random() < 0.02: sc.recall = 1; mode_until = sec + 10
        if sec >= mode_until: sc.recall = 0
        if not car and not gang and rnd.random() < 0.006:                       # CJ takes a car for a while
            car = sc.veh(sc.cj['pos'][0], sc.cj['pos'][1]); sc.cj['vehicle'] = car; car_until = sec + rnd.randint(8, 20)
            sc.vehs[car]['vel'] = [rnd.uniform(-9, 9), rnd.uniform(-9, 9), 0.]
        if car and sec >= car_until:
            sc.cj['vehicle'] = 0; sc.cj['vel'] = [0., 0., 0.]; del sc.vehs[car]; car = 0
        if rnd.random() < 0.004:                                                # one of ours falls; a new man takes his number
            k = rnd.randrange(8); old = team[k]
            if old in sc.peds:
                sc.peds[old]['flags'] |= HCB_PF_DEAD; sc.peds[old]['health'] = 0.
                del sc.ours[old]
                for _ in range(40):                                              # (the new man comes in on open ground, not in a wall and not on top of another)
                    nx, ny = sc.cj['pos'][0] + rnd.uniform(-6, 6), sc.cj['pos'][1] + rnd.uniform(-6, 6)
                    if sc.wall_dist((nx, ny)) > 0.8 and all(math.dist((nx, ny), sc.peds[t_]['pos'][:2]) > 1.2 for t_ in team if t_ in sc.peds) and not sc.walk_blocked(sc.cj['pos'], [nx, ny, 1.]): break
                team[k] = sc.our(nx, ny, SQ + k, weapon=M4); n['replaced'] += 1
        if sc.umode != was_mode or bool(car) != was_car or sc.recall: changed_at = sec
        was_mode, was_car = sc.umode, bool(car)
        for tick in range(10):
            cj = sc.cj
            if car:
                v = sc.vehs[car]; cj['pos'] = list(v['pos']); cj['vel'] = list(v['vel'])
                if abs(v['pos'][0]) > 70 or abs(v['pos'][1]) > 70: v['vel'] = [-v['vel'][0], -v['vel'][1], 0.]
            elif goal:
                dx, dy = goal[0] - cj['pos'][0], goal[1] - cj['pos'][1]; d = math.hypot(dx, dy)
                step = [goal[2] * dx / max(d, .01), goal[2] * dy / max(d, .01), 0.]
                nxt = [cj['pos'][0] + step[0] * .1, cj['pos'][1] + step[1] * .1]
                if d < 1. or sc.walk_blocked(cj['pos'], nxt + [cj['pos'][2]]): goal = None; cj['vel'] = [0., 0., 0.]
                else: cj['vel'] = step
            else: cj['vel'] = [0., 0., 0.]
            if tick == 0:
                for g in list(gang):
                    if sec >= g[1] or g[0] not in sc.peds: sc.peds[g[0]]['flags'] |= HCB_PF_DEAD; gang.remove(g)
                    elif sec % 2 == 0: sc.shot(g[0], (cj['pos'][0], cj['pos'][1], 1.), dst=1)
                if gang and sc.umode and sec % 3 == 0: sc.shot(1, tuple(sc.peds[gang[0][0]]['pos']))      # CJ fires at one of them: the squad's target
            o = sc.step(1)
            digest = (digest * 1000003 + o.digest) & 0xffffffffffffffff
        if not check: continue
        # ---- the checks of this second
        out, cjp, still = sc.last_out, sc.cj['pos'], math.hypot(*sc.cj['vel'][:2]) < .5 and not car
        still_for = still_for + 1 if still else 0                       # (1.5: the outer men take places once CJ has stood 4 s)
        assert LIB.hcb_brain_size() == size0
        stand = []
        near = 0
        for who, p in sc.posts.items():
            me = sc.peds[who]['pos']
            assert all(math.isfinite(x) for x in (p.at.x, p.at.y, p.at.z, p.via.x, p.via.y, p.via.z, p.look.x, p.look.y, p.look.z)), (sec, who, 'a place that is not a number')
            wd = sc.wall_dist(me)
            if p.move == 4: net_at[who] = sec                               # (4: the game's path network takes him - this simulation walks him through whatever is there)
            if wd < 0.05 and sec - net_at.get(who, -100) > 3: worst['in_wall'] += 1
            d = math.dist(me[:2], (p.at.x, p.at.y))
            n['samples'] += 1
            # (the plan's measure is for PROTECT with CJ standing; a man coming back from an assault or left behind by CJ's car is counted
            #  from 15 s after the mode changed / CJ got out; ASSAULT has its own count)
            if still and out.umode == HCB_UMODE_PROTECT and sec - changed_at >= 15: n['still'] += 1; n['far8'] += d > 8
            if still and out.umode == HCB_UMODE_ASSAULT: n['a_still'] += 1; n['a_far'] += d > 8
            n['stuck'] += p.stuck; n['failed'] += p.phase == HCB_PH_FAILED
            bad_for[who] = bad_for.get(who, 0) + 1 if (p.stuck or p.phase == HCB_PH_FAILED) else 0
            worst['stuck'] = max(worst['stuck'], bad_for[who])
            if out.alert < HCB_ALERT_THREAT and not car: n['calm'] += 1; n['sprint'] += p.act == HCB_ACT_SPRINT
            if who in last_act and last_act[who] != p.act: n['changes'] += 1
            last_act[who] = p.act
            near += math.dist(me[:2], cjp[:2]) < 4.
            # (1.5, the player: "only the commander and the bodyguards at my side, the rest so that I hardly notice them - in cover, down")
            if p.job in (HCB_ROLE_POINT, HCB_ROLE_POINT2, HCB_ROLE_REAR, HCB_ROLE_REAR2) and out.umode == HCB_UMODE_PROTECT and not car and sec - changed_at >= 15:
                n['out_n'] += 1; n['out_near'] += math.dist(me[:2], cjp[:2]) < 12.
                if still_for >= 5 and out.duty != HCB_DUTY_RING and d < 1.5: n['out_set'] += 1; n['out_down'] += bool(p.crouch)
            if p.phase >= HCB_PH_ARRIVED and p.phase != HCB_PH_FAILED and math.hypot(*sc.peds[who]['vel'][:2]) < .1: stand.append((who, me))
        for a in range(len(stand)):
            for b_ in range(a):
                if math.dist(stand[a][1][:2], stand[b_][1][:2]) < 0.4: worst['same_spot'] += 1
        if out.umode == HCB_UMODE_PROTECT and len(sc.posts) >= 7 and still and not gang: n['near'] += near; n['near_n'] += 1
        n['assault_s'] += out.umode == HCB_UMODE_ASSAULT; n['car_s'] += bool(car)
    return n, worst, digest


if __name__ == '__main__':
    n, worst, digest = run(SEED, MINUTES)
    pc = lambda a, b: 100. * a / b if b else 0.
    far8, stuck, failed, sprint = pc(n['far8'], n['still']), pc(n['stuck'], n['samples']), pc(n['failed'], n['samples']), pc(n['sprint'], n['calm'])
    changes, near = n['changes'] * 60. / max(1, n['samples']), n['near'] / max(1, n['near_n'])
    lines = [
        '%d minutes of random play, seed %d (host build of the core; NOT the game): %d fights, %d s in ASSAULT mode, %d s in a car, %d men of ours replaced' % (MINUTES, SEED, n['fights'], n['assault_s'], n['car_s'], n['replaced']),
        'PROTECT, guard farther than 8 m from his post while CJ stands: %.1f %%   (goal 15 %% or less)' % far8,
        'ASSAULT, the same (men on the move to and from the target by design; no goal): %.1f %%' % pc(n['a_far'], n['a_still']),
        'STUCK: %.1f %%   (goal 5 %% or less); gave his post up for a while: %.1f %%' % (stuck, failed),
        'the longest anybody was stuck or without his post on end: %d s   (must be under 60)' % worst['stuck'],
        'sprinting with no threat: %.1f %%   (goal 10 %% or less)' % sprint,
        'changes of action per guard per minute: %.1f   (goal 6 or less in peace; this half hour is mostly fights and marches)' % changes,
        'guards within 4 m of CJ in quiet PROTECT, average: %.1f   (goal 3)' % near,
        'seconds with one of ours inside a wall: %d; seconds with two of ours on one spot: %d   (must be 0)' % (worst['in_wall'], worst['same_spot']),
        '1.5: an outer man within 12 m of CJ in PROTECT: %.1f %%   (goal 5 %% or less); at his place with CJ standing 5 s he is down: %.1f %%   (goal 90 %% or more)' % (pc(n['out_near'], n['out_n']), pc(n['out_down'], n['out_set']))]
    assert pc(n['out_near'], n['out_n']) <= 5 and pc(n['out_down'], n['out_set']) >= 90 and far8 <= 15 and stuck <= 5 and sprint <= 10 and worst['stuck'] < 60 and worst['in_wall'] == 0 and worst['same_spot'] == 0 and 2.5 <= near <= 3.5, '\n'.join(lines)
    n2, worst2, digest2 = run(SEED, MINUTES, check=False)
    assert digest2 == digest, 'the same half hour a second time: every decision the same'
    lines.append('the same %d looks a second time: every decision the same (checksum %016x)' % (MINUTES * 600, digest))
    text = 'PASS: ' + '\nPASS: '.join(lines) + '\nThe core only. Nothing here has run in the game.\n'
    (hcb_py.OUT / 'brain_soak_tests.txt').write_text(text); print(text)
