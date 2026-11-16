"""Python side of the brain's core: ctypes mirrors of every struct in brain/core/hcb.h (built from the header itself,
so there is one description of the layout), the host build of the core, and a small scene builder for tests.

    from hcb_py import *            # constants HCB_..., structs hcb_ped ..., Brain, Scene
"""
import ctypes, math, os, re, subprocess, sys
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
__all__ = list(CONSTS) + list(STRUCTS) + ['Brain', 'Scene', 'LIB', 'vec', 'build', 'CONSTS', 'STRUCTS', 'Recorder', 'read_box', 'decode', 'load_fight']


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
LIB.hcb_gunner_round.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_void_p]
LIB.hcb_gunner_blocked.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
LIB.hcb_pilot_reset.argtypes = [ctypes.c_void_p, hcb_vec, hcb_vec, hcb_vec]
LIB.hcb_pilot_step.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
for _i, _n in enumerate(['hcb_ped', 'hcb_veh', 'hcb_event', 'hcb_snapshot', 'hcb_out', 'hcb_cfg', 'hcb_mark', 'hcb_track_info', 'hcb_rec', 'hcb_box_head', 'hcb_los', 'hcb_order', 'hcb_shot', 'hcb_round', 'hcb_pilot', 'hcb_pilot_in', 'hcb_pilot_out']):
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

    @staticmethod
    def _shot(who, target, time, frm, to, cj, friends=(), muzzle=None):
        q = hcb_shot()
        q.who, q.target, q.time, q.n_friends = who, target, time, len(friends)
        q.muzzle, q.to, q.cj = vec(*(muzzle or frm)), vec(*to), vec(*cj)
        setattr(q, 'from', vec(*frm))
        for i, f in enumerate(friends):
            q.friends[i] = vec(*f)
        return q

    def shot(self, who, target, time, frm, to, cj, friends=(), muzzle=None):
        """hcb_shot_check: may this round go, with these positions of this frame? Returns HCB_HOLD_*."""
        return LIB.hcb_shot_check(self.mem, ctypes.byref(self._shot(who, target, time, frm, to, cj, friends, muzzle)))

    def order(self, who):
        """hcb_order_get: the standing order of one of ours, or None."""
        o = hcb_order()
        return o if LIB.hcb_order_get(self.mem, who, ctypes.byref(o)) else None

    def round(self, who, target, time, frm, to, cj, friends=(), heli_speed=0., near_heli=True):
        """hcb_gunner_round: None while no round is due, else the hcb_round (its line and the verdict of the hard rules)."""
        r = hcb_round()
        q = self._shot(who, target, time, frm, to, cj, friends)
        return r if LIB.hcb_gunner_round(self.mem, ctypes.byref(q), heli_speed, int(near_heli), ctypes.byref(r)) else None

    def blocked(self, who, time):
        LIB.hcb_gunner_blocked(self.mem, who, time)

    def squad(self, who, target, time, frm, to, cj, friends=()):
        """hcb_squad_state: 0 nothing, 1 cover, 2 fire, 3 cease fire now."""
        return LIB.hcb_squad_state(self.mem, ctypes.byref(self._shot(who, target, time, frm, to, cj, friends)))

    def cls(self, id):
        m = self.marks().get(id)
        if m:
            return m.cls
        t = self.track(id)
        return t.cls if t else None

    def why(self, id):
        m = self.marks().get(id)
        return m.why if m else (self.track(id).why if self.track(id) else None)


def decode(buf, start, end):
    """Records of a black box, oldest first, decoded by the core itself:
    [('snapshot', hcb_snapshot, digest) | ('state', bytes) | ('round', hcb_round)]."""
    out, off = [], ctypes.c_uint32(start)
    state = ctypes.create_string_buffer(LIB.hcb_brain_size())
    while True:
        s, d, rnd = hcb_snapshot(), ctypes.c_uint32(), hcb_round()
        kind = LIB.hcb_rec_next(buf, end, ctypes.byref(off), ctypes.byref(s), ctypes.byref(d), state, ctypes.byref(rnd))
        if kind == HCB_REC_SNAPSHOT:
            out.append(('snapshot', s, d.value))
        elif kind == HCB_REC_STATE:
            out.append(('state', state.raw))
        elif kind == HCB_REC_ROUND:
            out.append(('round', rnd))
        else:
            break
    return out


def load_fight(path):
    """A recorded fight (brain/tools/box2json.py) as a list of hcb_snapshot. The file names every field, so a fight
    recorded by an older core still loads: fields it does not have stay 0."""
    import gzip, json
    fight = json.load(gzip.open(path))
    schema = fight['schema']

    def fill(obj, names, row):
        for name, value in zip(names, row):
            target, parts = obj, name.split('.')
            try:
                for part in parts[:-1]:
                    target = getattr(target, part)
                setattr(target, parts[-1], value)
            except AttributeError:
                pass                                    # a field this core no longer has
        return obj
    kinds = dict(peds=('hcb_ped', hcb_ped), vehs=('hcb_veh', hcb_veh), events=('hcb_event', hcb_event), los=('hcb_los', hcb_los))
    out = []
    for t in fight['ticks']:
        s = fill(hcb_snapshot(), schema['hcb_snapshot'], t['head'])
        for arr, (name, _) in kinds.items():
            for i, row in enumerate(t[arr][:len(getattr(s, arr))]):
                fill(getattr(s, arr)[i], schema[name], row)
        for i, v in enumerate(t['ours']):
            s.ours[i] = v
        for i, v in enumerate(t['our_role']):
            s.our_role[i] = v
        out.append(s)
    return out


class Recorder:
    def __init__(self, cap=1 << 20):
        self.rec = hcb_rec()
        self.buf = (ctypes.c_uint8 * cap)()
        LIB.hcb_rec_init(ctypes.byref(self.rec), cap)

    def push(self, snapshot, digest):
        LIB.hcb_rec_push(ctypes.byref(self.rec), self.buf, ctypes.byref(snapshot), digest)

    def push_state(self, brain):
        LIB.hcb_rec_push_state(ctypes.byref(self.rec), self.buf, brain.mem)

    def push_round(self, round):
        LIB.hcb_rec_push_round(ctypes.byref(self.rec), self.buf, ctypes.byref(round))

    def all(self):
        return decode(self.buf, self.rec.start, self.rec.end)

    def records(self):
        """[(snapshot, digest)] oldest first."""
        return [(r[1], r[2]) for r in self.all() if r[0] == 'snapshot']

    def box(self, brain, text=''):
        """The report file exactly as the phone writes it: head, records, text."""
        raw = text.encode('utf-8')
        head = hcb_box_head()
        LIB.hcb_box_head_fill(ctypes.byref(head), ctypes.byref(self.rec), brain.mem, len(raw))
        return bytes(head) + bytes(self.buf[self.rec.start:self.rec.end]) + raw


def read_box(data):
    """Parse a report file. Returns (head, records, text); raises ValueError with a plain reason when it cannot be used."""
    n = ctypes.sizeof(hcb_box_head)
    if len(data) < n or data[:7] != b'HCBBOX1':
        raise ValueError('not a Helicover Brain report')
    head = hcb_box_head.from_buffer_copy(data[:n])
    mine = dict(version=HCB_VERSION, brain_size=LIB.hcb_brain_size(), snapshot_size=ctypes.sizeof(hcb_snapshot), ped_size=ctypes.sizeof(hcb_ped),
                veh_size=ctypes.sizeof(hcb_veh), event_size=ctypes.sizeof(hcb_event))
    for k, v in mine.items():
        if getattr(head, k) != v:
            raise ValueError('the report was written by another version of the brain (%s %d, here %d)' % (k, getattr(head, k), v))
    if n + head.data_len + head.text_len > len(data):
        raise ValueError('the report is cut short')
    buf = (ctypes.c_uint8 * max(head.data_len, 1)).from_buffer_copy(data[n:n + head.data_len].ljust(1, b'\0'))
    return head, decode(buf, 0, head.data_len), data[n + head.data_len:n + head.data_len + head.text_len].decode('utf-8', 'replace')


class Scene:
    """A little world for tests: CJ at the origin facing north (+y), people and cars added by hand, time in 100 ms steps.
    Positions are metres, x east, y north. `step()` builds the snapshot, lets the brain think and moves everybody on."""

    def __init__(self, brain=None, wanted=0, on_mission=0, roe=None):
        self.brain = brain or Brain()
        self.time = 100000
        self.frame = 0
        self.cj = dict(id=1, pos=[0., 0., 1.], vel=[0., 0., 0.], fwd=[0., 1., 0.], health=100., armour=0., weapon=0, pedtype=0, flags=0, flags2=0,
                       target=0, vehicle=0, model=0, seat=0)
        self.peds, self.vehs, self.events, self.ours = {}, {}, [], {}
        self.wanted, self.on_mission, self.cutscene, self.heli, self.mission_free = wanted, on_mission, 0, 0, 0
        self.roe, self.police = HCB_ROE_DEFEND if roe is None else roe, HCB_POLICE_ANSWER
        self.walls = []          # [(x1, y1, x2, y2)]: segments that block the line of sight (answers to the brain's questions)
        self.holes = []          # [(x, y, r)]: no ground there (water, a drop): a cover question about such a spot says "no ground"
        self.probe_q = []        # the cover questions of the last tick (answered in the next snapshot)
        self.posts = {}          # who -> hcb_post of the last tick (the protective detail)
        self.walk_posts = False  # True: our guards on foot go to their posts as the scripts would make them
        self.said = []           # (time, HCB_SAY_*, dir) of the commander
        self.tactics = 0
        self.los_fn = None       # or a function (from_id, to_id) -> bool
        self.asked = []          # the questions of the last tick
        self.orders = {}         # who -> hcb_order of the last tick
        self.next_id = 0x100
        self.recorder = None
        self.state_every = 0     # with a recorder: store the brain's memory every this many ticks
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

    def pos_of(self, id):
        return (self.peds.get(id) or self.vehs.get(id) or self.cj)['pos'] if id != 1 else self.cj['pos']

    def blocked(self, p, q):
        """Does a wall stand between the points p and q (on the ground plan)?"""
        def cross(o, u, v):
            return (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])
        for x1, y1, x2, y2 in self.walls:
            w1, w2 = (x1, y1), (x2, y2)
            if cross(p, q, w1) * cross(p, q, w2) < 0 and cross(w1, w2, p) * cross(w1, w2, q) < 0:
                return True
        return False

    def sees(self, a, b):
        """The adapter's answer to "is there a clear line from a to b"."""
        if a not in self.peds or b not in self.peds:
            return False
        if self.los_fn:
            return bool(self.los_fn(a, b))
        p, q = self.peds[a]['pos'], self.peds[b]['pos']

        def cross(o, u, v):
            return (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])
        for x1, y1, x2, y2 in self.walls:
            w1, w2 = (x1, y1), (x2, y2)
            if cross(p, q, w1) * cross(p, q, w2) < 0 and cross(w1, w2, p) * cross(w1, w2, q) < 0:
                return False
        return True

    def snapshot(self):
        import math
        s = hcb_snapshot()
        s.time, s.frame, s.heli = self.time, self.frame, self.heli
        s.wanted, s.on_mission, s.cutscene, s.roe, s.police = self.wanted, self.on_mission, self.cutscene, self.roe, self.police
        s.mission_free = self.mission_free
        s.tactics = self.tactics
        s.n_probes = len(self.probe_q)
        for o, (at, frm) in zip(s.probes, self.probe_q):
            o.at = vec(*at)
            setattr(o, 'from', vec(*frm))
            o.hidden = int(self.blocked(frm, at))
            o.ground = int(not any(math.dist(at[:2], (hx, hy)) < hr for hx, hy, hr in self.holes))
        s.n_los = len(self.asked)
        for o, (a, b) in zip(s.los, self.asked):
            o.to = b
            o.clear = int(self.sees(a, b))
            setattr(o, 'from', a)
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
            if self.recorder and self.state_every and self.frame % self.state_every == 1:
                self.recorder.push_state(self.brain)
            out = self.brain.think(s)
            if self.recorder:
                self.recorder.push(s, out.digest)
            self.snapshots.append(s)
            self.events = []
            self.asked = [(getattr(q, 'from'), q.to) for q in out.queries[:out.n_queries]]
            self.orders = {o.who: hcb_order.from_buffer_copy(bytes(o)) for o in out.orders[:out.n_orders]}
            self.probe_q = [((q.at.x, q.at.y, q.at.z), (getattr(q, 'from').x, getattr(q, 'from').y, getattr(q, 'from').z)) for q in out.probe_q[:out.n_probe_q]]
            self.posts = {p_.who: hcb_post.from_buffer_copy(bytes(p_)) for p_ in out.posts[:out.n_posts]}
            if out.say:
                self.said.append((self.time, out.say, out.say_dir))
            if self.walk_posts:
                for who, p_ in self.posts.items():
                    if who in self.peds and p_.move and who not in getattr(self, 'stuck_men', ()):
                        me, to = self.peds[who]['pos'], [p_.at.x, p_.at.y, me_z] if (me_z := self.peds[who]['pos'][2]) is not None else None
                        d = math.dist(me[:2], to[:2])
                        step = min(d, (1.4, 3.5, 5.5, 3.5)[min(p_.move, 4) - 1] * ms / 1000.)   # 4: by the path network
                        if d > 1e-6:
                            self.peds[who]['pos'] = [me[0] + (to[0] - me[0]) * step / d, me[1] + (to[1] - me[1]) * step / d, me[2]]
            for p in list(self.peds.values()) + [self.cj]:
                p.pop('shot', None)
                p['pos'] = [p['pos'][i] + p['vel'][i] * ms / 1000. for i in range(3)]
            for v in self.vehs.values():
                v['pos'] = [v['pos'][i] + v['vel'][i] * ms / 1000. for i in range(3)]
                if v['driver'] in self.peds:
                    self.peds[v['driver']]['pos'] = list(v['pos'])
        return out
