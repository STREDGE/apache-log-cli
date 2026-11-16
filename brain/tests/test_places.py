"""1.1: a firing place chosen by weights (hcb_places.c through hcb_detail.c), on the host build of the core.
    python3 brain/tests/test_places.py
The four outer men of the detail in a fight: each takes the best-valued place near his corner. Every drill checks what can be
SEEN in the scene - who is hidden from whom, who stands where - not the brain's own numbers."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


SQ, M4, AK, GANG = HCB_ROLE_SQUAD, 31, 30, 7
JOB = {HCB_ROLE_LEAD: 'lead', HCB_ROLE_CLOSE: 'close', HCB_ROLE_POINT: 'point', HCB_ROLE_REAR: 'rear', HCB_ROLE_CLOSE2: 'close2', HCB_ROLE_POINT2: 'point2',
       HCB_ROLE_REAR2: 'rear2', HCB_ROLE_MARKSMAN: 'delta'}
OUTER = ('point', 'point2', 'rear', 'rear2')
EIGHT = ((1.2, -0.8), (-1.8, 3.5), (-9., 11.), (-1.6, -2.2), (-12., -8.), (12., -8.), (9., 11.), (16., -7.))


def d2(a, b):
    return math.dist(a[:2], b[:2])


def at(p):
    return (p.at.x, p.at.y)


def fight(low=(), full=(), threats=((34., 0.),), tune=None, cj_fires=False, ticks=170):
    sc = Scene(); sc.low_walls = list(low); sc.walls = list(full)
    sc.brain.cfg.outer_fight_m = 18.0          # (1.5: the weights are tested at the old 18 m ring - the geometry of these scenes)
    if tune: tune(sc.brain.cfg)
    team = [sc.our(x, y, SQ + k, weapon=M4) for k, (x, y) in enumerate(EIGHT)]
    sc.walk_posts = True; sc.step(20)
    gs = [sc.ped(x, y, pedtype=GANG, weapon=AK, face=(-1., 0.)) for x, y in threats]
    sc.step(2)
    for k in range(ticks):
        if k % 9 == 0:
            for g in gs: sc.shot(g, (0., 0., 1.), dst=1)
            if cj_fires: sc.shot(1, tuple(sc.peds[gs[0]]['pos']))
        sc.step(1)
    j = {JOB[p.job]: p for p in sc.posts.values()}
    # (1.5: the quarters are dealt out by the least way, not by the man's number: "the point man" is the one in the quarter
    #  ahead-left of the line to the threat - north-east here)
    ne = [k for k in OUTER if j[k].at.x > 0 and j[k].at.y > 0]
    if ne:
        pm = j[ne[0]]; j[ne[0]] = j['point']; j['point'] = pm
    return sc, team, gs, j


def hidden(sc, frm, p, low_too=True):
    return sc.blocked(tuple(frm[:2]), tuple(p[:2]), low_too=low_too)


# ------------------------------------------------------------------ low cover with a line of fire wins over open ground and over a blind wall
LOW = [(10., 9., 10., 13.), (10., -13., 10., -9.), (-6., 10., -6., 14.), (-6., -14., -6., -10.)]
sc, team, (g,), j = fight(low=LOW)
gp, cjp = sc.peds[g]['pos'], sc.cj['pos']
outs = {k: at(j[k]) for k in OUTER}
assert all(hidden(sc, gp, p) and not hidden(sc, gp, p, low_too=False) for p in outs.values()), ('each of the four is behind something he can fire over', outs)
assert all(not hidden(sc, cjp, p, low_too=False) for p in outs.values()), 'and sees CJ'
assert all(12 <= d2(p, cjp) <= 32 for p in outs.values()), outs
passed('Low cover near each corner: all four outer men take a place a crouching man is hidden in and a standing one fires over, 12-32 m from CJ, CJ in sight')

FULL = [(10., 8.5, 10., 13.5)]                                      # the point man's nearest cover is a blind wall; low cover is 5 m further on
sc, team, (g,), j = fight(low=[(8., 15., 8., 19.)] + LOW[1:], full=FULL)
gp = sc.peds[g]['pos']; p = at(j['point'])
assert not hidden(sc, gp, p, low_too=False), ('he does not hide behind a wall he cannot fire over while there is a firing place', p)
passed('A blind wall is next to worthless: the man whose nearest "cover" is a full wall takes a place he can fire from instead')

# ------------------------------------------------------------------ the weights are the settings file's: with fire cover worth nothing he stands in the open
def no_cover_value(c): c.place_w_fire = 0.0; c.place_w_open = 1.0
sc, team, (g,), j = fight(low=LOW, tune=no_cover_value)
gp = sc.peds[g]['pos']
assert sum(1 for k in OUTER if not hidden(sc, gp, at(j[k]))) >= 3, 'with the weight of cover set to nothing the men stand where they see best'
passed('The weights decide: with place_w_fire = 0 and place_w_open = 1 (as the settings file can set them) the same men stand in the open')

# ------------------------------------------------------------------ two threats: a place hidden from both is worth more
TWO = ((34., 0.), (0., 40.))
LOW2 = [(10., 9., 10., 13.), (8., 13., 12., 13.)]                   # an L: its inside corner is hidden from the east AND from the north
sc, team, gs, j = fight(low=LOW2 + LOW[1:], threats=TWO, ticks=220)
p = at(j['point']); a_, b_ = sc.peds[gs[0]]['pos'], sc.peds[gs[1]]['pos']
assert hidden(sc, a_, p) and hidden(sc, b_, p), ('the point man is in the corner hidden from both shooters', p)
passed('Two shooters: the man takes the place hidden from both (the weight of "the other threats") rather than one hidden from the main threat only')

# ------------------------------------------------------------------ nobody on top of another, nobody on the line of the fight, nobody in front of CJ's weapon
sc, team, (g,), j = fight(low=LOW, cj_fires=True)
gp, cjp = sc.peds[g]['pos'], sc.cj['pos']
pts = [at(j[k]) for k in OUTER]
assert all(d2(pts[a], pts[b]) >= 3.0 for a in range(4) for b in range(a)), ('3 m or more between any two of the four', pts)
def off_line(p):
    dx, dy = gp[0] - cjp[0], gp[1] - cjp[1]; l = math.hypot(dx, dy); t = ((p[0] - cjp[0]) * dx + (p[1] - cjp[1]) * dy) / l
    return abs((p[0] - cjp[0]) * dy - (p[1] - cjp[1]) * dx) / l if 0 < t < l else 99.
assert all(off_line(p) >= 2.0 for p in pts), ('nobody between CJ and the man he is firing at', [round(off_line(p), 1) for p in pts])
passed('Places apart (3 m or more between any two men) and clear of CJ\'s line of fire while he shoots')

# ------------------------------------------------------------------ CJ must be seen from it
BLIND = [(9., 6., 9., 16.)]                                          # a long wall between the point man's cover and CJ
sc, team, (g,), j = fight(low=[(12., 9., 12., 13.)] + LOW[1:], full=BLIND, ticks=220)
p = at(j['point'])
assert not hidden(sc, sc.cj['pos'], p, low_too=False), ('a place from which CJ cannot be seen is not taken, however good its cover', p)
passed('A place hidden from the shooter but with a wall between it and CJ is not taken: the outer man must keep CJ in sight')

# ------------------------------------------------------------------ he keeps a place: no moving for a little, no moving before 4 s
sc, team, (g,), j = fight(low=LOW, ticks=170)
kept = {JOB[p.job]: at(p) for p in sc.posts.values()}; moves = 0
for k in range(200):
    if k % 9 == 0: sc.shot(g, (0., 0., 1.), dst=1)
    if k == 20: sc.cj['pos'][0] += 1.5                               # CJ shifts a step: every value changes a little
    sc.step(1)
    now_ = {JOB[p.job]: at(p) for p in sc.posts.values()}
    moves += sum(d2(now_[n], kept[n]) > 0.5 for n in OUTER); kept = {n: now_[n] for n in OUTER}
assert moves <= 1, ('a place is kept: a small change of the picture moves nobody', moves)
passed('A place is kept: when CJ shifts a step and every value changes a little, nobody moves (a new place must be 20 % better and 4 s must have passed)')

# ------------------------------------------------------------------ the single weights, by what a place is worth (hcb_place_value)
sc, team, gs, j = fight(low=LOW2 + LOW[1:], threats=TWO, ticks=220)
me = j['point']; man = sc.peds[me.who]['pos']; p3 = (me.at.x, me.at.y, me.at.z)
cjp, a_, b_ = sc.cj['pos'], sc.peds[gs[0]]['pos'], sc.peds[gs[1]]['pos']
args = (sc.brain, p3, tuple(man), tuple(cjp), tuple(a_), p3, sc.time)
alone = hcb_py.place_value(*args)
both = hcb_py.place_value(*args, others=[tuple(b_)])
assert alone > 0 and abs((both - alone) - sc.brain.cfg.place_w_others) < 0.01, ('hidden from the second shooter too: worth place_w_others more', alone, both)
_dx, _dy = a_[0] - p3[0], a_[1] - p3[1]; _l = math.hypot(_dx, _dy)
crowded = hcb_py.place_value(*args, taken=[(p3[0] - _dy / _l * 2.0, p3[1] + _dx / _l * 2.0, p3[2])])          # (2 m to his side, not in his line)
assert abs((alone - crowded) - sc.brain.cfg.place_w_crowd) < 0.01, ('another of ours 2 m off: worth place_w_crowd less', alone, crowded)
assert hcb_py.place_value(*args, taken=[(p3[0] + _dx / _l * 2.0, p3[1] + _dy / _l * 2.0, p3[2])]) < 0, '1.3: one of ours 2 m in front of him, in his line to the shooter: no place'
assert hcb_py.place_value(sc.brain, p3, tuple(man), (p3[0] + _dx / _l * 5.0, p3[1] + _dy / _l * 5.0, cjp[2]), tuple(a_), p3, sc.time) < 0, '1.3: CJ in his line to the shooter: no place'
# 1.5: CJ 2.3 m beside that line (5 m out): inside the corridor a NEW place needs (2.4 m + 2 cm a metre), outside the one a place he HOLDS
#      goes with (2 m + 2 cm a metre) - no flapping between the two
_cj23 = (p3[0] + _dx / _l * 5.0 - _dy / _l * 2.3, p3[1] + _dy / _l * 5.0 + _dx / _l * 2.3, cjp[2])
assert hcb_py.place_value(sc.brain, p3, tuple(man), _cj23, tuple(a_), p3, sc.time) < 0 and hcb_py.place_value(sc.brain, p3, tuple(man), _cj23, tuple(a_), p3, sc.time, keep=1) >= 0, '1.5: a new place keeps 0.4 m more off the line of CJ than a place he holds'
on_top = hcb_py.place_value(*args, taken=[(p3[0] + 0.8, p3[1], p3[2])])
assert on_top < 0, 'and within 1.2 m of his place it is no place at all'
dx, dy = p3[0] - cjp[0], p3[1] - cjp[1]; l_ = math.hypot(dx, dy)
in_line = hcb_py.place_value(*args, cj_dir=(dx / l_, dy / l_, 0.), cj_fires=1)
beside = hcb_py.place_value(*args, cj_dir=(-dy / l_, dx / l_, 0.), cj_fires=1)
assert in_line < 0 and abs(beside - alone) < 0.01, ('in front of CJ\'s weapon it is no place; with CJ firing another way it is worth the same', in_line, beside)
# 1.5 (the review): in peace a man's place hides him from a point 30 m beyond his own quarter - that point is no man, and the middle of his
#      quarter lies right on the line CJ - point: the rules of the line of a fight would throw out the very place he is sent to
_far = (cjp[0] + dx / l_ * (l_ + 30.0), cjp[1] + dy / l_ * (l_ + 30.0), cjp[2] + 0.6)
assert hcb_py.place_value(sc.brain, p3, tuple(man), tuple(cjp), _far, p3, sc.time) < 0, 'the same point taken for a man: the line of the fight runs through the place'
assert hcb_py.place_value(sc.brain, p3, tuple(man), tuple(cjp), _far, p3, sc.time, stand_in=1) >= 0, '1.5: the peace stand-in: the middle of his quarter is a place'
passed('What a place is worth, weight by weight: hidden from a second shooter +%.2f, another of ours within 3 m -%.2f (within 1.2 m - no place), in front of CJ\'s weapon while he fires - no place; 1.3: CJ or one of ours in his line to the shooter - no place (1.5: a place he holds goes only when CJ comes within 1.5 m of that line, a new one needs 1.8 m - no flapping); in peace the point beyond his quarter is no man - the middle of his quarter is a place' % (sc.brain.cfg.place_w_others, sc.brain.cfg.place_w_crowd))

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_places_tests.txt').write_text(text)
print(text)
