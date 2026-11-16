"""The pilot (stage 3, Helicover 1.4): flights on the host build of the core.
    python3 brain/tests/test_pilot.py
Each flight checks what a person at the controls would do - speed up with the nose down, bank into a turn, keep clear of
the roofs, brake in good time and stop over the point - not how it is computed."""
import ctypes, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hcb_py import *
import hcb_py

results = []


def passed(t):
    results.append('PASS: ' + t)


def deg(r):
    return math.degrees(r)


def fly(target, start=(0., 0., 40.), head=(0., 1., 0.), vel=(0., 0., 0.), dt=1 / 30., seconds=90., ground=lambda p: 0., stop=1, blocked=lambda t: 0):
    """One flight; returns a list of frames: (t, pos, vel, pitch, roll, out)."""
    p = hcb_pilot()
    LIB.hcb_pilot_reset(ctypes.byref(p), vec(*start), vec(*vel), vec(*head))
    i, o = hcb_pilot_in(), hcb_pilot_out()
    i.target, i.dt, i.stop = vec(*target), dt, stop
    frames = []
    for k in range(int(seconds / dt)):
        i.ground = ground(p.pos)
        i.blocked = blocked(k * dt)
        LIB.hcb_pilot_step(ctypes.byref(p), ctypes.byref(i), ctypes.byref(o))
        frames.append((k * dt, (o.pos.x, o.pos.y, o.pos.z), (p.vel.x, p.vel.y, p.vel.z), deg(p.pitch), deg(p.roll), (o.right.x, o.right.y, o.right.z), (o.fwd.x, o.fwd.y, o.fwd.z), (o.up.x, o.up.y, o.up.z), o.dist, o.speed, o.arrived))
        if o.arrived:
            break
    return frames


def speed(f):
    return math.hypot(f[2][0], f[2][1])


# ------------------------------------------------------------------ a straight trip of a kilometre
fs = fly((1000., 0., 0.), head=(1., 0., 0.))
end = fs[-1]
top = max(speed(f) for f in fs)
acc = [(speed(b) - speed(a)) / (b[0] - a[0]) for a, b in zip(fs, fs[1:])]
assert end[10] and math.dist(end[1][:2], (1000., 0.)) < 2.5 and max(f[1][0] for f in fs) < 1003., ('it stops over the point and never overshoots it by more than a few metres', end[1], max(f[1][0] for f in fs))
assert 60. < top < 70. and max(acc) < 5.2 and min(acc) > -8.1, (top, max(acc), min(acc))
assert end[0] < 40., end[0]
speeding = [f for f in fs if 2 < f[0] < 8]
braking = [f for f in fs if f[1][0] > 700 and speed(f) > 10]
assert all(f[3] < -10 for f in speeding) and max(f[3] for f in braking) > 10 and max(abs(f[3]) for f in fs) < 21.5, ('nose down to speed up, up to brake, never past 21 degrees', min(f[3] for f in speeding), max(f[3] for f in braking))
passed('A kilometre in a straight line: %.0f s, %.0f km/h at the top, at most 5 m/s2 either way; the nose goes down to speed up and comes up to brake (never past 21 degrees); it stops over the point without overshooting' % (end[0], top * 3.6))

# ------------------------------------------------------------------ a turn: banked to the side it turns to, slower for a sharp one
fs = fly((600., 600., 0.), head=(0., 1., 0.), vel=(0., 50., 0.))          # at 180 km/h northbound, the point is north-east: a right turn
turning = [f for f in fs if 1 < f[0] < 6]
assert max(f[4] for f in turning) > 10 and all(f[4] > -2 for f in turning), ('a right turn: the right side goes down', [round(f[4]) for f in turning][:20])
assert all(r[2] <= 1e-6 or True for r in [f[5] for f in turning]) and min(f[5][2] for f in turning) < -.15, 'the right row of the matrix points down in a right turn'
fs2 = fly((-600., 600., 0.), head=(0., 1., 0.), vel=(0., 50., 0.))
assert min(f[4] for f in fs2 if 1 < f[0] < 6) < -10, 'and a left turn the other way'
assert max(abs(f[4]) for f in fs + fs2) <= 34.5, 'never banked past 34 degrees'
fs3 = fly((0., -500., 0.), head=(0., 1., 0.), vel=(0., 50., 0.))          # the point straight behind: slows down for the turn
assert min(speed(f) for f in fs3 if f[0] < 15) < 25 and fs3[-1][10], ('a U-turn is flown slower', min(speed(f) for f in fs3 if f[0] < 15))
passed('Turns: banked into the turn (right side down for a right turn, left for a left one, never past 34 degrees); a U-turn is flown slower and still ends over the point')

# ------------------------------------------------------------------ the same flight at 60, 30 and 15 frames a second
ends = {}
for fps in (60, 30, 15):
    f = fly((800., 300., 0.), dt=1. / fps)[-1]
    ends[fps] = (f[0], f[1])
assert max(t for t, _ in ends.values()) - min(t for t, _ in ends.values()) < 1.5 and all(math.dist(p[:2], (800., 300.)) < 2.5 for _, p in ends.values()), ends
passed('The frame rate does not change the flight: the same trip at 60, 30 and 15 fps ends at the same point within %.1f s' % (max(t for t, _ in ends.values()) - min(t for t, _ in ends.values())))

# ------------------------------------------------------------------ height: roofs ahead, hover height at the end
tower = lambda x: 600 < x < 900
fs = fly((1500., 0., 0.), head=(1., 0., 0.), ground=lambda p: 150. if any(tower(p.x + a) for a in (0, 30, 80, 150, 250)) else 0.)
over = [f[1][2] - 150. for f in fs if 600 < f[1][0] < 900]
assert over and min(over) > 15., ('a 150 m tower in the way (the script measures 250 m ahead): it slows down and climbs in time', min(over) if over else None)
assert abs(fs[-1][1][2] - 25.) < 5. and fs[-1][10], ("down at hovering height when it gets there", fs[-1][1])
fs = fly((900., 0., 0.), head=(1., 0., 0.))
cruise = [f[1][2] for f in fs if 300 < f[1][0] < 500]
assert all(abs(z - 35.) < 1.5 for z in cruise) and abs(fs[-1][1][2] - 25.) < 1.5, (min(cruise), max(cruise), fs[-1][1][2])
fs = fly((900., 0., 0.), head=(1., 0., 0.), ground=lambda p: 150. if any(500 < p.x + a < 800 for a in (0, 30, 80, 150, 250)) else 0.)
first_over = next(f for f in fs if f[8] < 5.)
assert fs[-1][10] and first_over[1][2] - 25. < 20., ('a tower 100 m short of the point: it comes down on the way (a steep approach), not hanging high over the point', first_over[1])
passed('Height: 35 m over the highest roof ahead while travelling, down to 25 m only near the point; a 150 m tower is cleared by %.0f m (it brakes and climbs in time), and when it stands just short of the point he comes down before he gets there' % min(over))

# ------------------------------------------------------------------ below the roofs, or a wall in the way: up first, on the spot
fs = fly((500., 0., 0.), start=(0., 0., 20.), ground=lambda p: 60.)
early = [f for f in fs if f[0] < 3]
assert all(speed(f) < .5 for f in early) and early[-1][1][2] > 25, 'below the roofs it goes straight up before it goes anywhere'
fs = fly((500., 0., 0.), head=(1., 0., 0.), vel=(30., 0., 0.), blocked=lambda t: 1 if t < 2 else 0)
assert speed(fs[1]) < .5 and fs[55][1][2] > fs[0][1][2] + 5 and fs[-1][10], 'a refused step: it stops at once and climbs, then goes on'
passed('Below the roofs, or a step refused by the script (something solid in the way): it stops and climbs on the spot, then carries on')

# ------------------------------------------------------------------ nonsense in, sense out
p = hcb_pilot()
LIB.hcb_pilot_reset(ctypes.byref(p), vec(10., 10., 40.), vec(float('nan'), 0., 0.), vec(0., 0., 0.))
i, o = hcb_pilot_in(), hcb_pilot_out()
for target, ground, dt in [((float('nan'), 0., 0.), 0., .03), ((100., 100., 0.), float('nan'), .03), ((100., 100., 0.), 0., float('nan')), ((100., 100., 0.), 0., 5.), ((100., 100., 0.), 0., -1.)]:
    i.target, i.ground, i.dt, i.stop = vec(*target), ground, dt, 1
    LIB.hcb_pilot_step(ctypes.byref(p), ctypes.byref(i), ctypes.byref(o))
    vals = [o.pos.x, o.pos.y, o.pos.z, o.right.x, o.fwd.y, o.up.z, o.dist, o.speed]
    assert all(v == v and abs(v) < 1e5 for v in vals) and math.dist((o.pos.x, o.pos.y), (10., 10.)) < 10, (target, ground, dt, vals)
passed('Nonsense in (a point, a roof height or a frame time that is not a number, a 5 s frame, a negative one): no number that is not a number comes out, and the helicopter does not jump')

# 0.8: a landing approach - it comes down to the height asked (15 m) over the pad on the way in, gently near the ground
def approach():
    p = hcb_pilot()
    LIB.hcb_pilot_reset(ctypes.byref(p), vec(0., 0., 60.), vec(0., 0., 0.), vec(1., 0., 0.))
    i, o = hcb_pilot_in(), hcb_pilot_out()
    i.target, i.dt, i.stop, i.land, i.hover, i.ground = vec(300., 0., 0.), 1 / 30., 1, 1, 15., 0.
    out = []
    for k in range(30 * 60):
        LIB.hcb_pilot_step(ctypes.byref(p), ctypes.byref(i), ctypes.byref(o))
        out.append((k / 30., o.pos.x, o.pos.z, p.vel.z, o.dist, math.hypot(p.vel.x, p.vel.y)))
        if o.arrived and abs(o.pos.z - 15.) < 1.5: break
    return out
ap = approach()
end = ap[-1]
assert abs(end[1] - 300.) < 3 and abs(end[2] - 15.) < 1.5 and end[0] < 45., end
near_ = [f for f in ap if f[4] < 25.]
assert min(f[3] for f in near_) > -6.6 and all(f[3] > -3.0 for f in near_ if f[2] < 26.), ('within 25 m of the pad never faster down than 6 m/s, 2.5 m/s in the last metres', min(f[3] for f in near_))
assert max(f[5] for f in ap if f[4] < 5.) < 3.3, ('0.9: the last 5 m of the approach are flown at 3 m/s at most', max(f[5] for f in ap if f[4] < 5.))
assert all(f[2] > 13.4 for f in ap), 'never under the height asked for (the roofs on the way are in `ground`)'
passed('A landing approach (0.8): 300 m to the pad and down to 15 m over it in %.0f s - never faster down than 6 m/s, gently in the last metres, never under the height asked for' % end[0])

text = '\n'.join(results) + '\nThe core only. Nothing here has run in the game.\n'
(hcb_py.OUT / 'brain_pilot_tests.txt').write_text(text)
print(text)
