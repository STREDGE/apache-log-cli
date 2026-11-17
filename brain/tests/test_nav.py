"""1.0: the brain's own map and the men's own way to their places (hcb_nav.c, hcb_agent.c), on the host build of the core.
    python3 brain/tests/test_nav.py
The scene has solid boxes, thin fences (which a ray straight down does not see), holes and ledges; a man who walks into one
stops there, as he would in the game. Each drill checks that the men ARRIVE, by which way, and what they do when they cannot."""
import math, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


SQ, M4, AK, GANG = HCB_ROLE_SQUAD, 31, 30, 7
SOUTH = tuple((x, -30. - 2 * (k % 2)) for k, x in enumerate((-7., -5., -3., -1., 1., 3., 5., 7.)))


def d2(a, b):
    return math.dist(a[:2], b[:2])


def team_at(sc, places):
    t = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(places)]
    sc.walk_posts = True
    return t


def arrived(sc, team, r=1.6):
    return [w for w in team if w in sc.posts and d2(sc.peds[w]['pos'], (sc.posts[w].at.x, sc.posts[w].at.y)) < r]


def run_until(sc, team, ticks, need=None):
    """Step until `need` men stand at their places; returns the seconds it took (None = not in time)."""
    need = len(team) if need is None else need
    for k in range(ticks):
        sc.step(1)
        if len(arrived(sc, team)) >= need:
            return (k + 1) / 10.
    return None


# ------------------------------------------------------------------ the map fills, nearest ground first, within its budget
sc = Scene(); team = team_at(sc, SOUTH)
qs, sg = [], []
for _ in range(90):
    o = sc.step(1); qs.append(o.n_ground_q); sg.append(o.n_seg_q)
assert max(qs) <= HCB_MAX_GROUND and max(sg) <= HCB_MAX_SEGS, (max(qs), max(sg))
assert sum(qs) >= 48 * 48 - 10, ('the whole 48 x 48 m is known after 8 s', sum(qs))
assert sum(qs[80:]) == 0, 'and then nothing more is asked while CJ stays (an answer is kept)'
first = [(q.x, q.y) for q in sc.snapshots[1].ground[:8]]
assert all(math.hypot(x, y) < 3 for x, y in first), ('the cells next to CJ first', first)
passed('The map: 48 x 48 one-metre cells round CJ, asked for nearest first, at most %d questions a look - known in about %d s, and nothing is asked twice' % (HCB_MAX_GROUND, math.ceil(48 * 48 / HCB_MAX_GROUND / 10)))

# ------------------------------------------------------------------ open ground: straight there
sc = Scene(); team = team_at(sc, SOUTH)
t_open = run_until(sc, team, 300)
assert t_open is not None and t_open < 20, t_open
sc.step(20)
assert all(sc.posts[w].why in (HCB_WHY2_ARRIVED,) and sc.posts[w].phase in (HCB_PH_ARRIVED, HCB_PH_ACTING) and sc.posts[w].move == 0 for w in team)
passed('Open ground: all eight walk straight to their places (30 m in %.0f s) and STOP there - the order is finished, not repeated' % t_open)

# ------------------------------------------------------------------ a building in the way: round it
sc = Scene(); sc.blocks = [(-10., -20., 10., -10., 4.)]; team = team_at(sc, SOUTH)
t_box = run_until(sc, team, 400)
assert t_box is not None and t_box < 2.2 * t_open + 6, ('everybody is at his place although a 20 x 10 m block stands in the way', t_box, t_open)
assert all(sc.ground_at(*sc.peds[w]['pos'][:2]) == 0. for w in team), 'nobody stands on it'
passed('A block 20 x 10 m between the men and CJ: all eight go round it and arrive (%.0f s; %.0f s on open ground) - nobody runs at the wall' % (t_box, t_open))

# ------------------------------------------------------------------ a fence: a ray down does not see it, the level rays do
sc = Scene(); sc.walls = [(-14., -12., 14., -12.)]; team = team_at(sc, SOUTH)
whys = set()
t_fence = None
for k in range(450):
    sc.step(1)
    whys |= {sc.posts[w].why for w in team if w in sc.posts}
    if len(arrived(sc, team)) == 8 and t_fence is None: t_fence = (k + 1) / 10.
assert t_fence is not None and t_fence < 40, ('all eight are round a 28 m fence', t_fence, len(arrived(sc, team)))
assert HCB_WHY2_ROUTE in whys, whys
passed('A fence 28 m long (nothing a ray straight down can see): the map has it from the level rays between cells, and all eight go round its ends (%.0f s)' % t_fence)

# ------------------------------------------------------------------ a hole: nobody walks into it
sc = Scene(); sc.holes = [(0., -18., 6.)]; team = team_at(sc, SOUTH)
inside = 0
for k in range(350):
    sc.step(1)
    inside += sum(1 for w in team if math.dist(sc.peds[w]['pos'][:2], (0., -18.)) < 5.5)
assert len(arrived(sc, team)) == 8 and inside == 0, (len(arrived(sc, team)), inside)
passed('A hole 12 m across (nothing to stand on) on the straight line: the ways go round it, nobody steps in')

# ------------------------------------------------------------------ a ledge: up 0.6 m is a step, 2 m is a wall
sc = Scene(); sc.blocks = [(-20., -20., 20., -10., 0.6)]; team = team_at(sc, SOUTH)
assert run_until(sc, team, 300) is not None, 'a kerb / low platform 0.6 m high is walked over'
sc = Scene(); sc.blocks = [(-9., -20., 9., -10., 2.0)]; team = team_at(sc, SOUTH)
on_top = 0
for k in range(400):
    sc.step(1)
    on_top += sum(1 for w in team if sc.ground_at(*sc.peds[w]['pos'][:2]) == 2.0)
assert len(arrived(sc, team)) == 8 and on_top == 0, (len(arrived(sc, team)), on_top)
passed('Heights: a step of 0.6 m is walked over; a platform 2 m high is a wall - the men go round it')

# ------------------------------------------------------------------ no way at all: it fails, says why, and stops trying the same thing
sc = Scene(); sc.walls = [(-8., -8., 8., -8.), (8., -8., 8., 8.), (8., 8., -8., 8.), (-8., 8., -8., -8.)]       # CJ in a closed yard
team = team_at(sc, SOUTH); sc.net_blocked = True                       # (and the game's path network has no way in either)
hist = {w: [] for w in team}
for k in range(600):
    sc.step(1)
    for w in team:
        hist[w].append((sc.posts[w].act, sc.posts[w].phase, sc.posts[w].why, sc.posts[w].stuck, sc.posts[w].move))
inner = [w for w in team if sc.posts[w].job in (HCB_ROLE_LEAD, HCB_ROLE_CLOSE, HCB_ROLE_CLOSE2)]
assert all(any(h[1] == HCB_PH_FAILED for h in hist[w]) and any(h[3] for h in hist[w]) for w in inner), 'the three whose places are inside the yard: the action FAILS and the game\'s path network is asked'
assert all(any(h[4] == 4 for h in hist[w]) for w in inner), 'and before that the game\'s path network was tried (move 4)'
stood = max(max((len(list(g)) for k_, g in __import__('itertools').groupby(hist[w], key=lambda h: h[1] == HCB_PH_FAILED) if k_), default=0) for w in inner)
assert stood <= 30, ('1.2: "failed" is 2.5 s of standing, then he tries again from the beginning (it was 8 s)', stood)
assert all(any(h[2] in (HCB_WHY2_NO_PROGRESS, HCB_WHY2_BLOCKED, HCB_WHY2_NO_ROUTE) for h in hist[w]) for w in inner), 'with the reason'
assert all(d2(sc.peds[w]['pos'], (0, 0)) > 7.5 for w in team), 'nobody went through the wall'
changes = max(sum(1 for a_, b_ in zip(hist[w], hist[w][1:]) if a_[0] != b_[0]) for w in team)
assert changes <= 80, ('no frantic switching: at most %d changes of action in a minute' % changes)
passed('A place that cannot be reached (CJ in a closed yard): the men try another way, a step round, the game\'s path network - then the action is marked FAILED with its reason; in that whole minute no man changed his action more than %d times' % changes)

# ------------------------------------------------------------------ 1.2: "no way on the map" is not "stand"
# (the first log of 2.0 from the game: the map said "no way" for three ways out of four and every such answer stood the man for 8 s)
sc = Scene(); sc.walls = [(-8., -8., 8., -8.), (8., -8., 8., 8.), (8., 8., -8., 8.), (-8., 8., -8., -8.)]       # the same yard; the game's path network has a way in
team = team_at(sc, SOUTH)
first_fail, asked4 = None, None
for k in range(400):
    sc.step(1)
    if first_fail is None and any(sc.posts[w].phase == HCB_PH_FAILED for w in team): first_fail = k
    if asked4 is None and any(sc.posts[w].move == 4 for w in team): asked4 = k
inner = [w for w in team if sc.posts[w].job in (HCB_ROLE_LEAD, HCB_ROLE_CLOSE, HCB_ROLE_CLOSE2)]
assert asked4 is not None and asked4 < 150 and (first_fail is None or first_fail > asked4), ('the path network is asked within seconds, before anybody "fails"', asked4, first_fail)
assert all(d2(sc.peds[w]['pos'], sc.cj['pos']) < 4.5 for w in inner), 'and the three are with CJ in the yard (at their places: the bodyguard ahead is 4 m out)'
passed('1.2 "no way on the map" is not "stand still": the men go straight at their places, then by the game\'s path network (asked after %.1f s) - the three are with CJ inside the yard the map takes for closed' % (asked4 / 10.))

# ------------------------------------------------------------------ the map goes with CJ
sc = Scene(); sc.blocks = [(90., -12., 110., -6., 4.)]; team = team_at(sc, ((-2., -3.), (2., -3.), (-4., 4.), (4., 4.)))
sc.step(40)
sc.cj['vel'] = [5., 0., 0.]
for k in range(200): sc.step(1)
sc.cj['vel'] = [0., 0., 0.]
assert run_until(sc, team, 200) is not None, 'after 100 m they are at their places again'
assert abs(sc.cj['pos'][0] - 100.) < 2
o = sc.step(1)
assert all(abs(q.x - sc.cj['pos'][0]) <= 25 for q in o.ground_q[:o.n_ground_q])
passed('CJ runs 100 m: the map moves with him (only the new ground is asked about) and the detail is round him at the end')

# ------------------------------------------------------------------ the same world gives the same ways
def digest_run():
    sc = Scene(); sc.blocks = [(-10., -20., 10., -10., 4.)]; sc.walls = [(12., -15., 20., -15.)]; team = team_at(sc, SOUTH)
    return [sc.step(1).digest for _ in range(150)]
assert digest_run() == digest_run()
passed('Deterministic: the same world twice gives the same map, the same ways and the same decisions, tick for tick')

# ------------------------------------------------------------------ the pace is chosen
sc = Scene(); team = team_at(sc, ((-2., -3.), (2., -3.), (-4., 4.), (4., 4.), (-9., 9.), (9., 9.), (-9., -9.), (9., -9.)))
sc.step(120)
acts = []
sc.cj['vel'] = [0., 1.4, 0.]                                # CJ strolls
for k in range(100):
    sc.step(1); acts += [sc.posts[w].act for w in team]
walk_share = sum(a in (HCB_ACT_WALK, HCB_ACT_FASTWALK, HCB_ACT_HOLD, HCB_ACT_OVERWATCH, HCB_ACT_COVER) for a in acts) / len(acts)   # (1.5: an outer man down at his place counts as calm)
assert walk_share > 0.85 and HCB_ACT_SPRINT not in acts, (walk_share, set(acts))
acts = []
sc.cj['vel'] = [0., 6.5, 0.]                                # CJ sprints
for k in range(60):
    sc.step(1); acts += [sc.posts[w].act for w in team if sc.posts[w].act not in (HCB_ACT_COVER, HCB_ACT_OVERWATCH)]   # (1.6: an outer man keeps his cover until CJ has gone on - then he sprints after him)
assert len(acts) > 250 and sum(a in (HCB_ACT_RUN, HCB_ACT_SPRINT) for a in acts) / len(acts) > 0.8, (len(acts), sum(a in (HCB_ACT_RUN, HCB_ACT_SPRINT) for a in acts))
sc.cj['vel'] = [0., 0., 0.]
sc.step(150)
assert all(sc.posts[w].move == 0 for w in team), 'he stops: they stop'
passed('The pace: CJ strolls - the detail walks with him (%d %% walking or standing, nobody sprints); he sprints - they run; he stops - they stop' % round(100 * walk_share))

# ------------------------------------------------------------------ on the rope: no orders
sc = Scene(); team = team_at(sc, ((-2., -3.), (2., -3.), (-4., 4.), (4., 4.)))
sc.roping = {team[3]}; sc.peds[team[3]]['pos'] = [4., 4., 12.]
sc.step(10)
assert team[3] not in sc.posts or (sc.posts[team[3]].move == 0 and sc.posts[team[3]].why == HCB_WHY2_IN_AIR), 'a man on the rope is given nothing to do'
assert len([w for w in sc.posts if w != team[3]]) == 3 and JOB_LEAD_OK if (JOB_LEAD_OK := sc.last_out.lead == team[0]) else False
sc.roping = set(); sc.peds[team[3]]['pos'] = [4., 4., 1.]
sc.step(5)
assert team[3] in sc.posts and sc.posts[team[3]].why != HCB_WHY2_IN_AIR
passed('A man on the rope is given no place and no order until he stands on the ground; then he takes his place in the detail')

# ------------------------------------------------------------------ what it costs
sc = Scene(); sc.blocks = [(-10., -20., 10., -10., 4.)]; sc.walls = [(12., -15., 20., -15.)]; team = team_at(sc, SOUTH)
g = sc.ped(40, 0, pedtype=GANG, weapon=AK, face=(-1., 0.))
ts = []
for k in range(300):
    if k % 15 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    s = sc.snapshot_only() if hasattr(sc, 'snapshot_only') else None
    t0 = time.perf_counter(); sc.step(1); ts.append(time.perf_counter() - t0)
ts.sort()
passed('Cost on this computer (the whole step of the test scene, Python included): median %.2f ms, worst %.2f ms a look - the phone has its own counters in the log' % (ts[len(ts) // 2] * 1e3, ts[-1] * 1e3))

# ------------------------------------------------------------------ heights: a ledge is not walked up, a drop is not walked off; arriving; "stuck"
def ground_blocks(blocks):
    return lambda x, y: max([h for x1, y1, x2, y2, h in blocks if x1 <= x <= x2 and y1 <= y <= y2] + [0.])
sc = Scene(); BOX = (-6., -16., 6., -8., 1.6); sc.ground_fn = ground_blocks([BOX]); team = team_at(sc, ((0., -30.),))
on_box = 0
for k in range(400):
    sc.step(1); x, y, _ = sc.peds[team[0]]['pos']
    on_box += BOX[0] + .2 < x < BOX[2] - .2 and BOX[1] + .2 < y < BOX[3] - .2
    if arrived(sc, team): break
assert arrived(sc, team) and on_box == 0, ('he goes round the block 1.6 m high, never over it', on_box, sc.peds[team[0]]['pos'])
sc.step(60)                                                        # (the whole map is known now)
way = hcb_py.nav_way(sc.brain, (0., -22., 1.), (0., -3., 1.), sc.time)
def crosses(p, q):
    return any(BOX[0] + .3 < p[0] + (q[0] - p[0]) * t / 20. < BOX[2] - .3 and BOX[1] + .3 < p[1] + (q[1] - p[1]) * t / 20. < BOX[3] - .3 for t in range(21))
assert way and not any(crosses(a_, b_) for a_, b_ in zip([(0., -22., 1.)] + way, way)), ('the map\'s own way from one side of the block to the other goes round it', way)
passed('Heights: a ledge 1.6 m high is not a step - the way goes round the block (the man never stands on it) and he arrives')
sc = Scene(); ROOF = (-4., -20., 4., -12., 5.); sc.ground_fn = ground_blocks([ROOF]); team = team_at(sc, ((0., -16.),)); sc.peds[team[0]]['pos'][2] = 6.   # (a roof inside the brain's map: 1.1 sends a man who is OUTSIDE it by the game's path network, drop or no drop)
left = 0
for k in range(250):
    sc.step(1); x, y, _ = sc.peds[team[0]]['pos']
    left += not (ROOF[0] - .1 <= x <= ROOF[2] + .1 and ROOF[1] - .1 <= y <= ROOF[3] + .1)
p_ = sc.posts[team[0]]
assert left == 0 and d2(sc.peds[team[0]]['pos'], (p_.at.x, p_.at.y)) > 5, ('a man on a roof 5 m up does not walk off its edge', left, p_.phase, p_.act)
passed('Heights: a drop of 5 m is not a way - a man on a roof stays on it (his post on the ground is given up, he is not walked off the edge)')
# (a drop the game WOULD let a man take - 3 m - and a ramp down 12 m away: the map knows both, from the terrace; the way is the ramp)
def terrace(x, y):
    if y <= 4.: return 3.0                                                 # CJ's terrace, its edge at y = 4
    if 12. <= x <= 16. and y <= 16.: return 3.0 - (y - 4.) * 0.25          # a ramp down from it, 12 m east of CJ
    return 0.
sc = Scene(); sc.ground_fn = terrace; sc.cj['pos'] = [0., 0., 4.]; team = team_at(sc, ((-1., -3.),)); sc.peds[team[0]]['pos'][2] = 4.
sc.step(100)                                                       # (the whole map is known: the terrace, the ramp, the ground below the edge)
sc.cj['pos'] = [0., 10., 1.]                                       # CJ jumps down: the commander is to be at his side, 6 m below the edge
way = hcb_py.nav_way(sc.brain, (0., 0., 4.), (0., 10., 1.), sc.time)
drop, by_ramp, t_down = 0., False, None
for k in range(400):
    z0 = sc.peds[team[0]]['pos'][2]; sc.step(1); x, y, z = sc.peds[team[0]]['pos']
    drop = max(drop, z0 - z); by_ramp |= 11.5 < x < 16.5 and 4. < y < 16.
    if t_down is None and z < 1.5 and d2((x, y), sc.cj['pos']) < 3.: t_down = (k + 1) / 10.
assert way and any(p[0] > 11. for p in way), ('the map\'s own way down from the terrace goes by the ramp, not off the edge', way)
assert drop <= 1.6 and by_ramp and t_down is not None, ('he comes down by the ramp - no step down of more than 1.5 m - and is at CJ\'s side', drop, by_ramp, t_down, sc.peds[team[0]]['pos'])
passed('Heights: a drop of 3 m (one the game would let a man take) is not walked off either - from a terrace with a ramp 12 m away the man comes down by the ramp (his largest step down %.1f m) and is at CJ\'s side below after %.0f s' % (drop, t_down))
sc = Scene(); team = team_at(sc, ((3., -9.),)); ph = []
for k in range(120):
    sc.step(1); ph.append((sc.posts[team[0]].phase, sc.posts[team[0]].act))
assert 0.3 < d2(sc.peds[team[0]]['pos'], (sc.posts[team[0]].at.x, sc.posts[team[0]].at.y)) < 0.95   # (within a step: he is not walked on to the centimetre)
assert ph[-1][0] in (HCB_PH_ARRIVED, HCB_PH_ACTING) and ph[-1][1] not in (HCB_ACT_WALK, HCB_ACT_FASTWALK, HCB_ACT_RUN, HCB_ACT_SPRINT), ('at his post he has arrived and stands', ph[-1])
passed('Arriving: within a step of his post the man has ARRIVED and stands - he is not sent on for the last centimetres for ever')
sc = Scene(); team = team_at(sc, ((0., -12.),)); sc.step(20); sc.stuck_men = {team[0]}
told = None
for k in range(200):
    sc.step(1); p_ = sc.posts[team[0]]
    if p_.stuck and p_.phase != HCB_PH_FAILED and told is None: told = k / 10.
    if p_.phase == HCB_PH_FAILED: break
assert told is not None and p_.phase == HCB_PH_FAILED, ('a man who cannot move is reported STUCK first, then his post is given up', told, p_.phase)
passed('Stuck: a man who does not move is reported STUCK after four failed tries (%.1f s) - before his post is given up for a while' % told)

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_nav_tests.txt').write_text(text)
print(text)
