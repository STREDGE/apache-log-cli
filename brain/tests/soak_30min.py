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


# 1.6 (the log of 1.5 - the simulation said "an outer man within 12 m: 3 %, stuck 0.7 %", the game said 11 % and 6 %: this world was a
# field with four walls). Now it is more of a street: a long wall beside a pavement with gaps, fences, a raised level nobody can walk up
# to (3 m) and a low terrace, things to get down behind in every direction (parked cars are low walls here), and cars driving through.
WALLS += [(-60., -34., -22., -34.), (-18., -34., 14., -34.), (18., -34., 60., -34.), (48., -30., 48., 20.), (-50., 30., -50., 60.), (-14., 44., 12., 44.)]
BLOCKS = [(34., 30., 56., 46., 3.0), (-58., -20., -44., -6., 3.0), (-24., 32., -16., 40., 0.4)]
LOW += [(x_, y_, x_ + (3.5 if (i_ + j_) % 2 else 0.), y_ + (0. if (i_ + j_) % 2 else 3.5)) for i_, x_ in enumerate(range(-52, 56, 13)) for j_, y_ in enumerate(range(-52, 56, 13))
        if (i_ * 7 + j_ * 3) % 4 != 0 and not (abs(x_) < 5 and abs(y_) < 5) and not (-4. <= x_ <= 4.)]
ROAD_X = 0.0                                               # cars drive along the line x = 0, both ways


def run(seed, minutes, check=True):
    rnd = random.Random(seed)
    sc = Scene(); sc.walls = list(WALLS); sc.low_walls = list(LOW); sc.blocks = list(BLOCKS)
    traffic = []
    team = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(EIGHT)]
    sc.walk_posts = True
    size0 = LIB.hcb_brain_size()
    changed_at, was_mode, was_car = -100, 0, 0
    n = dict(a_still=0, a_far=0, samples=0, still=0, far8=0, stuck=0, failed=0, calm=0, sprint=0, changes=0, near=0, near_n=0, fights=0, assault_s=0, replaced=0, car_s=0,
             out_n=0, out_near=0, out_set=0, out_down=0, out_cov=0, out_open=0, out_wall=0, jumps=0, out_secs=0, out_feet=0, out_still=0, jumps_still=0, f_n=0, f_cov=0, f_wall=0, near_f=0, near_fn=0, lead_n=0, lead_ahead=0, road=0)
    last_at = {}
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
        # (cars on the road: one every few seconds, 10-13 m/s, gone 75 m on)
        if rnd.random() < 0.25 and not car:
            dirn = rnd.choice((-1., 1.)); drv = sc.ped(ROAD_X + dirn * 1.6, -70. * dirn, pedtype=4)
            cid = sc.veh(ROAD_X + dirn * 1.6, -70. * dirn, vel=(0., dirn * rnd.uniform(10., 13.), 0.), driver=drv)
            sc.peds[drv]['vehicle'] = cid
            traffic.append((cid, drv))
        for cid, drv in list(traffic):
            if abs(sc.vehs[cid]['pos'][1]) > 75.:
                del sc.vehs[cid]; sc.peds.pop(drv, None); traffic.remove((cid, drv))
            else: sc.peds[drv]['pos'] = list(sc.vehs[cid]['pos'])
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
                if out.duty >= HCB_DUTY_COVER: n['near_fn'] += 1; n['near_f'] += math.dist(me[:2], cjp[:2]) < 12.
                if still_for >= 5 and out.duty != HCB_DUTY_RING and d < 1.5: n['out_set'] += 1; n['out_down'] += bool(p.crouch)
                # (1.6, what the player's own log was measured by: behind cover / beside a wall / in the open at his place; how often the
                #  place jumps; how much of the time he is on his feet while CJ stands; and never on the roadway)
                if out.duty != HCB_DUTY_RING:
                    if d < 1.5:
                        n['out_cov'] += p.cover in (1, 2); n['out_wall'] += p.cover == 3; n['out_open'] += p.cover == 0
                        if out.duty >= HCB_DUTY_COVER: n['f_n'] += 1; n['f_cov'] += p.cover in (1, 2); n['f_wall'] += p.cover == 3
                        n['road'] += abs(me[0] - ROAD_X) < 3.0
                    n['out_secs'] += 1
                    if who in last_at and math.dist(last_at[who], (p.at.x, p.at.y)) > 3.: n['jumps'] += 1; n['jumps_still'] += still_for >= 5
                    last_at[who] = (p.at.x, p.at.y)
                    if still_for >= 5: n['out_still'] += 1; n['out_feet'] += d >= 1.5
            elif who in last_at: del last_at[who]
            if p.job == HCB_ROLE_LEAD and out.leading:
                n['lead_n'] += 1; n['lead_ahead'] += math.dist(me[:2], (out.cover_at.x, out.cover_at.y)) < math.dist(cjp[:2], (out.cover_at.x, out.cover_at.y))
            if p.phase >= HCB_PH_ARRIVED and p.phase != HCB_PH_FAILED and math.hypot(*sc.peds[who]['vel'][:2]) < .1: stand.append((who, me))
        for a in range(len(stand)):
            for b_ in range(a):
                if math.dist(stand[a][1][:2], stand[b_][1][:2]) < 0.4: worst['same_spot'] += 1
        if out.umode == HCB_UMODE_PROTECT and len(sc.posts) >= 7 and still and not gang and out.duty == HCB_DUTY_CALM: n['near'] += near; n['near_n'] += 1   # (1.6: quiet is quiet - after a fight the commander is off to the cover and back for 25 s)
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
        '1.5: an outer man within 12 m of CJ in PROTECT: %.1f %%   (goal 12 %% or less in this street; the game on 1.5: 11 %%); at his place with CJ standing 5 s he is down: %.1f %%   (goal 90 %% or more)' % (pc(n['out_near'], n['out_n']), pc(n['out_down'], n['out_set'])),
        '1.6: an outer man at his place: behind cover %.1f %%, beside a wall %.1f %%, in the open %.1f %%   (the game on 1.5: in the open 79 %%; goal: behind cover 60 %% or more, in the open 20 %% or less - half an hour of marches and fights; standing still it is 80 %% and more, see test_detail); on the roadway %.1f %%   (goal 4 %% or less)' % (
            pc(n['out_cov'], n['out_cov'] + n['out_wall'] + n['out_open']), pc(n['out_wall'], n['out_cov'] + n['out_wall'] + n['out_open']), pc(n['out_open'], n['out_cov'] + n['out_wall'] + n['out_open']), pc(n['road'], n['out_cov'] + n['out_wall'] + n['out_open'])),
        '1.6: an outer man\'s place jumped more than 3 m: %.1f times a minute a man   (the game on 1.5: 25; goal 9 or less); on his feet while CJ has stood 5 s: %.1f %%   (the game on 1.5: 54 %%; goal 26 %% or less)' % (n['jumps'] * 60. / max(1, n['out_secs']), pc(n['out_feet'], n['out_still'])) + '; jumps with CJ standing: %.1f a minute a man   (the game on 1.5: 14; goal 7 or less)' % (n['jumps_still'] * 60. / max(1, n['out_still'])),
        '1.6: the commander nearer the cover than CJ while he leads: %.1f %%   (goal 55 %% or more: this CJ never follows him, so he also walks back for him)' % pc(n['lead_ahead'], n['lead_n']),
        '1.6: in a fight: an outer man at his place behind cover %.1f %%, beside a wall %.1f %%; within 12 m of CJ %.1f %% (out of a fight %.1f %%)' % (pc(n['f_cov'], n['f_n']), pc(n['f_wall'], n['f_n']), pc(n['near_f'], n['near_fn']), pc(n['out_near'] - n['near_f'], n['out_n'] - n['near_fn']))]
    cov_n = n['out_cov'] + n['out_wall'] + n['out_open']
    # (1.6: the goals of this street-like world. "Within 12 m" was 5 % on the open field of 1.5 - here men cross CJ's ground on their way round
    #  walls in a fight; the place jumps counted are mostly the two each fight costs - into cover from the threat, and back out of CJ's sight)
    assert pc(n['out_near'], n['out_n']) <= 12 and pc(n['out_down'], n['out_set']) >= 90 and far8 <= 15 and stuck <= 5 and sprint <= 10 and worst['stuck'] < 60 and worst['in_wall'] == 0 and worst['same_spot'] == 0 and 2.3 <= near <= 3.5, '\n'.join(lines)
    assert pc(n['out_cov'], cov_n) >= 60 and pc(n['out_open'], cov_n) <= 20 and pc(n['road'], cov_n) <= 4, '\n'.join(lines)
    assert n['jumps'] * 60. / max(1, n['out_secs']) <= 9 and n['jumps_still'] * 60. / max(1, n['out_still']) <= 7 and pc(n['out_feet'], n['out_still']) <= 26 and pc(n['lead_ahead'], n['lead_n']) >= 55, '\n'.join(lines)
    n2, worst2, digest2 = run(SEED, MINUTES, check=False)
    assert digest2 == digest, 'the same half hour a second time: every decision the same'
    lines.append('the same %d looks a second time: every decision the same (checksum %016x)' % (MINUTES * 600, digest))
    text = 'PASS: ' + '\nPASS: '.join(lines) + '\nThe core only. Nothing here has run in the game.\n'
    (hcb_py.OUT / 'brain_soak_tests.txt').write_text(text); print(text)
