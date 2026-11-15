"""Python side of the brain's core: ctypes mirrors of every struct in brain/core/hcb.h (built from the header itself,
so there is one description of the layout), the host build of the core, and a small scene builder for tests.

    from hcb_py import *            # constants HCB_..., structs hcb_ped ..., Brain, Scene
"""
import ctypes, os, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HEADER = ROOT / 'core' / 'hcb.h'
OUT = Path(os.environ.get('HCB_OUT', ROOT.parent / 'build' / 'brain'))
_C = {'uint8_t': ctypes.c_uint8, 'int8_t': ctypes.c_int8, 'uint16_t': ctypes.c_uint16, 'int16_t': ctypes.c_int16,
      'uint32_t': ctypes.c_uint32, 'int32_t': ctypes.c_int32, 'float': ctypes.c_float}


def _parse(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    consts, structs = {}, {}
    for name, value in re.findall(r'^#define\s+(HCB_\w+)\s+(-?\d+)\s*$', text, re.M):
        consts[name] = int(value)
    for body, name in re.findall(r'typedef\s+struct\s+\w+\s*\{(.*?)\}\s*(\w+)\s*;', text, re.S):
        fields = []
        for line in body.split(';'):
            line = line.strip()
            if not line:
                continue
            m = re.fullmatch(r'(\w+)\s+(\w+)(?:\[(\w+)\])?', line)
            assert m, ('hcb.h: a field hcb_py cannot read', name, line)
            ctype, field, count = m.groups()
            t = _C.get(ctype) or structs[ctype]
            if count:
                t = t * (consts[count] if count in consts else int(count))
            fields.append((field, t))
        structs[name] = type(name, (ctypes.Structure,), {'_fields_': fields})
    return consts, structs


CONSTS, STRUCTS = _parse(HEADER.read_text())
globals().update(CONSTS)
globals().update(STRUCTS)
__all__ = list(CONSTS) + list(STRUCTS) + ['Brain', 'Scene', 'LIB', 'vec', 'build', 'CONSTS', 'STRUCTS', 'Recorder']


def build():
    """(Re)build the host library when a source is newer than it."""
    lib = OUT / 'libhcbcore_host.so'
    sources = list((ROOT / 'core').glob('*.[ch]')) + [ROOT / 'build_host.sh']
    if not lib.exists() or any(s.stat().st_mtime > lib.stat().st_mtime for s in sources):
        env = dict(os.environ, OUT=str(OUT))
        r = subprocess.run(['sh', str(ROOT / 'build_host.sh')], capture_output=True, text=True, env=env)
        if r.returncode:
            sys.exit('core build failed:\n' + r.stdout + r.stderr)
    return lib


LIB = ctypes.CDLL(str(build()))
LIB.hcb_brain_size.restype = ctypes.c_uint32
LIB.hcb_struct_size.restype = ctypes.c_uint32
LIB.hcb_config.restype = ctypes.POINTER(hcb_cfg)
LIB.hcb_weapon_dps.restype = ctypes.c_float
LIB.hcb_weapon_range.restype = ctypes.c_float
for _i, _n in enumerate(['hcb_ped', 'hcb_veh', 'hcb_event', 'hcb_snapshot', 'hcb_out', 'hcb_cfg', 'hcb_mark', 'hcb_track_info', 'hcb_rec']):
    assert LIB.hcb_struct_size(_i) == ctypes.sizeof(STRUCTS[_n]), ('layout differs between C and Python', _n, LIB.hcb_struct_size(_i), ctypes.sizeof(STRUCTS[_n]))
    assert ctypes.sizeof(STRUCTS[_n]) % 4 == 0, _n


def vec(x=0., y=0., z=0.):
    return hcb_vec(x, y, z)


class Brain:
    def __init__(self, seed=1):
        self.mem = ctypes.create_string_buffer(LIB.hcb_brain_size())
        LIB.hcb_init(self.mem, seed)
        self.cfg = LIB.hcb_config(self.mem).contents
        self.out = hcb_out()

    def think(self, snapshot):
        LIB.hcb_think(self.mem, ctypes.byref(snapshot), ctypes.byref(self.out))
        return self.out

    def track(self, id):
        info = hcb_track_info()
        return info if LIB.hcb_track(self.mem, id, ctypes.byref(info)) else None

    def marks(self):
        return {m.id: m for m in self.out.marks[:self.out.n_marks]}

    def cls(self, id):
        m = self.marks().get(id)
        if m:
            return m.cls
        t = self.track(id)
        return t.cls if t else None

    def why(self, id):
        m = self.marks().get(id)
        return m.why if m else (self.track(id).why if self.track(id) else None)


class Recorder:
    def __init__(self, cap=1 << 20):
        self.rec = hcb_rec()
        self.buf = (ctypes.c_uint8 * cap)()
        LIB.hcb_rec_init(ctypes.byref(self.rec), cap)

    def push(self, snapshot, digest):
        LIB.hcb_rec_push(ctypes.byref(self.rec), self.buf, ctypes.byref(snapshot), digest)

    def records(self):
        """[(snapshot, digest)] oldest first, decoded by the core itself."""
        out, off = [], ctypes.c_uint32(self.rec.start)
        while True:
            s, d = hcb_snapshot(), ctypes.c_uint32()
            if not LIB.hcb_rec_next(self.buf, self.rec.end, ctypes.byref(off), ctypes.byref(s), ctypes.byref(d)):
                break
            out.append((s, d.value))
        return out


class Scene:
    """A little world for tests: CJ at the origin facing north (+y), people and cars added by hand, time in 100 ms steps.
    Positions are metres, x east, y north. `step()` builds the snapshot, lets the brain think and moves everybody on."""

    def __init__(self, brain=None, wanted=0, on_mission=0):
        self.brain = brain or Brain()
        self.time = 100000
        self.frame = 0
        self.cj = dict(id=1, pos=[0., 0., 1.], vel=[0., 0., 0.], fwd=[0., 1., 0.], health=100., armour=0., weapon=0, pedtype=0, flags=0, flags2=0,
                       target=0, vehicle=0, model=0, seat=0)
        self.peds, self.vehs, self.events, self.ours = {}, {}, [], {}
        self.wanted, self.on_mission, self.cutscene, self.heli = wanted, on_mission, 0, 0
        self.next_id = 0x100
        self.recorder = None
        self.snapshots = []

    def _id(self):
        self.next_id += 0x100
        return self.next_id | 1

    def ped(self, x, y, pedtype=4, weapon=0, face=None, vel=(0., 0., 0.), flags=0, flags2=0, target=0, z=1., health=100., model=20, vehicle=0, seat=0):
        id = self._id()
        p = dict(id=id, pos=[float(x), float(y), float(z)], vel=list(map(float, vel)), fwd=[0., 1., 0.], health=health, armour=0., weapon=weapon,
                 pedtype=pedtype, flags=flags, flags2=flags2, target=target, vehicle=vehicle, model=model, seat=seat)
        self.peds[id] = p
        if face is None or face == 'cj':
            self.face(id, self.cj['pos'])
        elif face == 'away':
            self.face(id, self.cj['pos'], away=True)
        else:
            p['fwd'] = list(map(float, face))
        return id

    def face(self, id, point, away=False, turn_deg=0.):
        import math
        p = self.peds[id]
        dx, dy = point[0] - p['pos'][0], point[1] - p['pos'][1]
        d = math.hypot(dx, dy) or 1.
        a = math.atan2(dy, dx) + math.radians(turn_deg) + (math.pi if away else 0.)
        p['fwd'] = [math.cos(a), math.sin(a), 0.]

    def our(self, x, y, role, **kw):
        id = self.ped(x, y, pedtype=8, **kw)
        self.ours[id] = role
        return id

    def veh(self, x, y, vel=(0., 0., 0.), driver=0, health=1000., cls=0, flags=0, z=1., model=400):
        id = self._id()
        import math
        s = math.hypot(vel[0], vel[1]) or 1.
        self.vehs[id] = dict(id=id, pos=[float(x), float(y), float(z)], vel=list(map(float, vel)), fwd=[vel[0] / s, vel[1] / s, 0.] if any(vel) else [0., 1., 0.],
                             health=health, cls=cls, flags=flags, driver=driver, model=model, passengers=0, max_passengers=3)
        if driver:
            self.peds[driver]['vehicle'] = id
            self.peds[driver]['pos'] = [float(x), float(y), float(z)]
        return id

    def shot(self, src, to, dst=0, weapon=None):
        a = self.peds[src]['pos'] if src in self.peds else self.cj['pos']
        self.events.append(dict(type=HCB_EV_SHOT, src=src, dst=dst, a=list(a), b=list(map(float, to)), value=0.,
                                weapon=weapon if weapon is not None else (self.peds.get(src) or self.cj)['weapon']))
        if src in self.peds:
            self.peds[src]['shot'] = True

    def damage(self, src, dst, value=20., weapon=0):
        self.events.append(dict(type=HCB_EV_DAMAGE, src=src, dst=dst, a=[0., 0., 0.], b=[0., 0., 0.], value=float(value), weapon=weapon))

    @staticmethod
    def _fill_ped(o, p):
        o.id, o.target, o.vehicle = p['id'], p['target'], p['vehicle']
        o.pos, o.vel, o.fwd = vec(*p['pos']), vec(*p['vel']), vec(*p['fwd'])
        o.health, o.armour, o.model, o.pedtype, o.weapon = p['health'], p['armour'], p['model'], p['pedtype'], p['weapon']
        o.flags, o.flags2, o.seat = p['flags'] | (HCB_PF_SHOOTING if p.get('shot') else 0), p['flags2'], p['seat']

    def snapshot(self):
        import math
        s = hcb_snapshot()
        s.time, s.frame, s.heli = self.time, self.frame, self.heli
        s.wanted, s.on_mission, s.cutscene = self.wanted, self.on_mission, self.cutscene
        self._fill_ped(s.player, self.cj)
        near = sorted(self.peds.values(), key=lambda p: math.dist(p['pos'], self.cj['pos']))
        s.n_peds = min(len(near), HCB_MAX_PEDS)
        s.peds_lost = len(near) - s.n_peds
        for o, p in zip(s.peds, near):
            self._fill_ped(o, p)
        vs = sorted(self.vehs.values(), key=lambda v: math.dist(v['pos'], self.cj['pos']))[:HCB_MAX_VEHS]
        s.n_vehs = len(vs)
        for o, v in zip(s.vehs, vs):
            o.id, o.driver, o.pos, o.vel, o.fwd = v['id'], v['driver'], vec(*v['pos']), vec(*v['vel']), vec(*v['fwd'])
            o.health, o.model, o.cls, o.flags, o.passengers, o.max_passengers = v['health'], v['model'], v['cls'], v['flags'], v['passengers'], v['max_passengers']
        ev = self.events[:HCB_MAX_EVENTS]
        s.n_events, s.events_lost = len(ev), len(self.events) - len(ev)
        for o, e in zip(s.events, ev):
            o.time, o.src, o.dst, o.a, o.b, o.value, o.type, o.weapon = self.time, e['src'], e['dst'], vec(*e['a']), vec(*e['b']), e['value'], e['type'], e['weapon']
        s.n_ours = len(self.ours)
        for i, (id, role) in enumerate(self.ours.items()):
            s.ours[i], s.our_role[i] = id, role
        return s

    def step(self, n=1, ms=100):
        out = None
        for _ in range(n):
            self.time += ms
            self.frame += 1
            s = self.snapshot()
            out = self.brain.think(s)
            if self.recorder:
                self.recorder.push(s, out.digest)
            self.snapshots.append(s)
            self.events = []
            for p in list(self.peds.values()) + [self.cj]:
                p.pop('shot', None)
                p['pos'] = [p['pos'][i] + p['vel'][i] * ms / 1000. for i in range(3)]
            for v in self.vehs.values():
                v['pos'] = [v['pos'][i] + v['vel'][i] * ms / 1000. for i in range(3)]
                if v['driver'] in self.peds:
                    self.peds[v['driver']]['pos'] = list(v['pos'])
        return out
