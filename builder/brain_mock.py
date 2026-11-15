"""The Helicover Brain inside the scripts' test world (test_v25.py).

The decisions are made by the REAL core (the host build of brain/core, through brain/tests/hcb_py.py). This file is
only what brain/game/brain.c is on the phone - the adapter: it turns the test world into the snapshot the core
reads, answers its line-of-sight questions with the world's own rule, and serves opcode 0E48 to the scripts.
The round pacing, the scatter, the hard rules and the guard's fire state all come from the core.

World attributes it reads (all optional except the usual ones):
  shooting_chars   people who are firing this frame (a round along the way they face, or at shot_at[who])
  shooting         CJ is firing (at `targeting` when he has a lock, else at cj_aim, else where the camera looks)
  damage           {(victim, attacker)}: every new pair is a damage event
  npc_target       {who: whom he holds his weapon on}
  on_mission, mission_peds   a mission is running / the people that belong to it
"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'brain' / 'tests'))
import hcb_py as h
import build_v25 as b

VEH = 0x80000000


def vid(car):
    return (car | VEH) if car and car > 0 else 0


class BrainSim:
    def __init__(self, seed=1):
        self.brain = h.Brain(seed=seed)
        self.out = None
        self.last = None            # game time of the last look
        self.events, self.seen_damage, self.asked = [], set(), []
        self.cj_shot, self.heli_shot = None, None
        self.snap = None
        self.rounds = []            # every hcb_round the scripts were given (fired or refused): for the tests
        self.said = []              # (time, guard, state): what each guard on foot was told, frame by frame
        self.looks = 0
        self.probe_q = []           # the cover questions of the last look (answered in the next snapshot)
        self.say = (0, 0, 0)        # the commander's last words: (seq, HCB_SAY_*, direction)
        self.words = []             # (time, HCB_SAY_*, direction): everything the commander said

    # ------------------------------------------------------------ the world as a snapshot
    @staticmethod
    def sight(w, a, c):
        """The game's line of sight as the test world models it (buildings, vehicles and objects block; people do not)."""
        if not (w.siteclear and w.clear_fn(a[0], a[1]) and getattr(w, 'los_fn', lambda p, q: True)(list(a), list(c))):
            return False
        if w.ray_block_distance is not None and math.dist(a, c) >= w.ray_block_distance:
            return False
        return not any(w.seg_dist(list(a), list(c), pos) < rad for pos, rad in getattr(w, 'blockers', []))

    @staticmethod
    def facing(w, who):
        a = math.radians(w.actor_heading[who])
        return [-math.sin(a), math.cos(a), 0.]

    def peds(self, w):
        return [i for i in w.exists if i != 1 and i not in w.cars and (i in w.pos or i in w.incar or i in w.attach) and i not in getattr(w, 'objects', {})]

    def ours(self, w):
        out = []
        for k in range(18):
            v = w.shared[b.PUB + 2 + k] if k < 5 else w.shared[b.GROUND_PUB + k - 5] if k < 10 else w.shared[b.LEAVE + k - 10]
            if len(out) == h.HCB_MAX_OURS:
                break
            if v > 1 and v in w.exists and v not in w.cars and all(v != o for o, _ in out):
                # (the crew are door gunners while mounted; after a landing - PHASE 1 - they are guards on foot like the ground team)
                crew = h.HCB_ROLE_SQUAD if w.shared[b.PHASE] == 1 else h.HCB_ROLE_GUNNER
                out.append((v, h.HCB_ROLE_PILOT if k == 0 else crew + k - 1 if k < 5 else h.HCB_ROLE_SQUAD + min(k - 5, 3) if k < 10 else h.HCB_ROLE_NONE))
        return out

    def fill(self, w, o, who, cj=False):
        pos = w.coords(who)
        o.id, o.pos, o.vel = who, h.vec(*pos), h.vec(*w.velocity.get(who, [0., 0., 0.]))
        o.fwd = h.vec(*self.facing(w, who))
        o.health, o.armour = float(w.health[who]), float(w.armor[who])
        o.pedtype, o.weapon, o.model = (0 if cj else w.pedtype.get(who, 4)) & 255, w.weapons[who] & 255, w.skin.get(who, 0) & 0xffff
        flags = (h.HCB_PF_DEAD if who in w.dead else 0) | (h.HCB_PF_SHOOTING if (w.shooting if cj else who in w.shooting_chars) else 0)
        if who in getattr(w, 'mission_peds', ()):
            flags |= h.HCB_PF_MISSION
        if who in getattr(w, 'respects', ()):
            flags |= h.HCB_PF_RESPECTS
        if who in w.incar:
            o.vehicle = vid(w.incar[who])
            o.seat = 0 if w.seats.get((w.incar[who], -1), 1 if who == 1 else -1) == who else 1
        if cj:
            o.target = w.targeting if w.targeting in w.exists and w.targeting > 1 else 0
        else:
            o.target = getattr(w, 'npc_target', {}).get(who, 0)
            if o.target:
                flags |= h.HCB_PF_AIMING
            if h.LIB.hcb_weapon_class(o.weapon) >= h.HCB_WC_PISTOL and who not in w.dead:
                o.flags2 = h.HCB_PF2_LOS_KNOWN | (h.HCB_PF2_LOS_CLEAR if self.sight(w, self.chest(pos), self.chest(w.coords(1))) else 0)
        o.flags = flags

    @staticmethod
    def chest(p, up=.6):
        return [p[0], p[1], p[2] + up]

    def gather(self, w):
        """Events of this frame: they are kept until the brain's next look."""
        for who in list(w.shooting_chars):
            if who in w.exists and who not in w.dead:
                a = w.coords(who)
                to = getattr(w, 'shot_at', {}).get(who)
                if to is None:
                    f = self.facing(w, who)
                    to = [a[i] + f[i] * 40. for i in range(3)]
                self.shot(w, who, a, to)
        if w.shooting:
            a = w.coords(1)
            if w.targeting in w.exists and w.targeting > 1:
                to = w.coords(w.targeting)
            elif getattr(w, 'cj_aim', None) is not None:
                to = list(w.cj_aim)
            else:
                d = [w.lookat[i] - w.camera[i] for i in range(3)]
                n = math.sqrt(sum(x * x for x in d)) or 1.
                to = [a[i] + d[i] / n * 60. for i in range(3)]
            self.shot(w, 1, a, to)
        for victim, attacker in w.damage - self.seen_damage:
            self.events.append(dict(type=h.HCB_EV_DAMAGE, src=attacker if attacker in w.exists and attacker not in w.cars else 0, dst=vid(victim) if victim in w.cars else victim,
                                    a=[0., 0., 0.], b=[0., 0., 0.], value=20., weapon=w.weapons[attacker] if attacker in w.exists else 49, time=w.now))
        self.seen_damage = set(w.damage)

    def shot(self, w, who, a, to):
        self.events.append(dict(type=h.HCB_EV_SHOT, src=who, dst=0, a=list(a), b=list(to), value=0., weapon=w.weapons[who], time=w.now))
        ours = {1, w.shared[b.PUB + 1]} | {o for o, _ in self.ours(w)}
        if who == 1:
            d = [to[0] - a[0], to[1] - a[1]]
            n = math.hypot(*d)
            if n > .2:
                self.cj_shot = (w.now, d[0] / n, d[1] / n)
        elif who not in ours and w.shared[b.PUB + 1] in w.cars:
            if w.seg_dist(list(a), [a[i] + (to[i] - a[i]) * 1.2 for i in range(3)], w.cars[w.shared[b.PUB + 1]]['pos']) < 6.:
                self.heli_shot = w.now

    def snapshot(self, w):
        s = h.hcb_snapshot()
        s.time, s.frame = w.now & 0xffffffff, self.looks
        self.fill(w, s.player, 1, cj=True)
        heli = w.shared[b.PUB + 1]
        s.heli = vid(heli) if heli in w.cars else 0
        s.wanted, s.on_mission = w.wanted, int(getattr(w, 'on_mission', 0))
        roe = w.shared[b.FIRE]
        s.roe = roe if 0 <= roe <= 4 else h.HCB_ROE_DEFEND
        s.police = h.HCB_POLICE_EVADE if w.shared[b.POLICE] == 1 else h.HCB_POLICE_ANSWER
        s.mission_free = int(w.shared[b.MISSIONS] == 1)
        s.tactics = int(w.shared[b.TACTICS] == 1)
        # the cover questions: is a man crouching at `at` hidden from the threat's chest, is there ground under it
        s.n_probes = len(self.probe_q)
        for o, (at, frm) in zip(s.probes, self.probe_q):
            o.at = h.vec(*at)
            setattr(o, 'from', h.vec(*frm))
            o.hidden = int(not self.sight(w, list(frm), [at[0], at[1], at[2] - .3]))
            o.ground = int(not any(math.dist(at[:2], hp[:2]) < hr for hp, hr in getattr(w, 'holes', [])))
        ours = self.ours(w)
        s.n_ours = len(ours)
        for i, (who, role) in enumerate(ours):
            s.ours[i], s.our_role[i] = who, role
        cj = w.coords(1)
        mine = {o for o, _ in ours}
        people = sorted(self.peds(w), key=lambda p: 0. if p in mine else math.dist(w.coords(p), cj))
        people = [p for p in people if p in mine or math.dist(w.coords(p), cj) <= 150.][:h.HCB_MAX_PEDS]
        s.n_peds = len(people)
        for o, who in zip(s.peds, people):
            self.fill(w, o, who)
        cars = sorted((c for c in w.cars if c in w.exists), key=lambda c: math.dist(w.cars[c]['pos'], cj))[:h.HCB_MAX_VEHS]
        s.n_vehs = len(cars)
        for o, car in zip(s.vehs, cars):
            c = w.cars[car]
            o.id, o.pos, o.vel = vid(car), h.vec(*c['pos']), h.vec(*c.get('vel', [0., 0., 0.]))
            a = math.radians(c.get('heading', 0.))
            o.fwd = h.vec(-math.sin(a), math.cos(a), 0.)
            o.health, o.model = float(w.health[car]), w.model.get(car, 400) & 0xffff
            o.cls = h.HCB_VC_HELI if w.kind.get(car) == 'heli' or w.model.get(car) in (487, 497, 425) else h.HCB_VC_CAR
            driver = w.seats.get((car, -1), next((p for p in w.incar if w.incar[p] == car and (w.kind.get(p) == 'pilot' or p == 1 and not getattr(w, 'cj_is_passenger', False))), 0))
            o.driver = driver if driver and driver > 0 and driver in w.exists else 0
            if w.health[car] < 250 or car in getattr(w, 'burning', ()):
                o.flags |= h.HCB_VF_BURNING
        ev = self.events[:h.HCB_MAX_EVENTS]
        s.n_events, s.events_lost = len(ev), len(self.events) - len(ev)
        for o, e in zip(s.events, ev):
            o.time, o.src, o.dst, o.a, o.b, o.value, o.type, o.weapon = e['time'] & 0xffffffff, e['src'], e['dst'], h.vec(*e['a']), h.vec(*e['b']), e['value'], e['type'], e['weapon'] & 255
        self.events = []
        n = 0
        for a, c in self.asked[:h.HCB_MAX_LOS]:
            if a in w.exists and c in w.exists:
                s.los[n].to = c
                setattr(s.los[n], 'from', a)
                s.los[n].clear = int(self.sight(w, self.chest(w.coords(a)), self.chest(w.coords(c))))
                n += 1
        s.n_los = n
        return s

    # ------------------------------------------------------------ once a frame, before the scripts (the GOT hook on the phone)
    def frame(self, w):
        if b.BRAIN_HELLO in w.shared and w.shared[b.BRAIN_HELLO] != b.BRAIN_MAGIC:
            w.shared[b.BRAIN_HELLO] = b.BRAIN_MAGIC           # the handshake: only a value the scripts have created is answered
        self.gather(w)
        every = 50 if self.out is not None and self.out.alert >= h.HCB_ALERT_THREAT else 100
        if self.last is not None and 0 <= w.now - self.last < every:
            return
        self.last = w.now
        self.snap = self.snapshot(w)
        self.out = self.brain.think(self.snap)
        self.looks += 1
        self.asked = [(getattr(q, 'from'), q.to) for q in self.out.queries[:self.out.n_queries]]
        self.probe_q = [((q.at.x, q.at.y, q.at.z), (getattr(q, 'from').x, getattr(q, 'from').y, getattr(q, 'from').z)) for q in self.out.probe_q[:self.out.n_probe_q]]
        if self.out.say:
            self.say = (self.out.say_seq, self.out.say, self.out.say_dir)
            self.words.append((w.now, self.out.say, self.out.say_dir))

    # ------------------------------------------------------------ opcode 0E48
    def post(self, w, v, f):
        who = v[f]
        v[f + 1] = -1
        for p in (self.out.posts[:self.out.n_posts] if self.out is not None else []):
            if p.who == who:
                v[f + 1], v[f + 2], v[f + 3], v[f + 4], v[f + 5] = p.move, p.at.x, p.at.y, p.at.z, p.crouch
                v[f + 6], v[f + 7], v[f + 8], v[f + 9] = p.look.x, p.look.y, p.look.z, p.duty
                return

    def detail(self, w, v, f):
        o = self.out
        v[f], v[f + 1], v[f + 2] = self.say
        if o is None:
            v[f + 3] = v[f + 4] = v[f + 8] = 0; v[f + 5] = v[f + 6] = v[f + 7] = 0.
            return
        v[f + 3], v[f + 4], v[f + 5], v[f + 6], v[f + 7], v[f + 8] = o.duty, o.cover_ok, o.cover_at.x, o.cover_at.y, o.cover_at.z, o.lead

    def pilot(self, w, v, f):
        """1.4: the brain's pilot (the real core, hcb_pilot.c). In: 0 helicopter, 1/2 the point, 3 the roofs, 4 flags (1 stop,
        2 the last step was refused). Out: 1-3 where to be now, 4 metres left, 5 speed (-1 = no pilot). The turn is applied
        the way the adapter does it after the scripts: the world's heading (and its pitch and bank) follow the matrix."""
        import ctypes
        heli = v[f]
        v[f + 5] = -1
        if heli not in w.cars or heli != w.shared[b.PUB + 1]:
            return
        car = w.cars[heli]
        st = getattr(self, 'pilots', None)
        if st is None:
            st = self.pilots = {}
        p, last = st.get(heli, (None, None))
        hd = math.radians(car.get('heading', 0.))
        if p is None or last is None or not 0 <= w.now - last <= 500:
            p = h.hcb_pilot()
            speed = float(w.shared.get(b.CR_V, 0.) or 0.)
            h.LIB.hcb_pilot_reset(ctypes.byref(p), h.vec(*car['pos']), h.vec(-math.sin(hd) * speed, math.cos(hd) * speed, 0.), h.vec(-math.sin(hd), math.cos(hd), 0.))
            last = w.now - 16
        # the real position on the ground plane; the height is the pilot's own (SET_CAR_COORDINATES puts a helicopter a bit
        # higher than asked - read back, it would climb a little every frame), unless something moved it a long way
        z = p.pos.z if abs(car['pos'][2] - p.pos.z) < 8. else car['pos'][2]
        p.pos = h.vec(car['pos'][0], car['pos'][1], z)
        i = h.hcb_pilot_in()
        i.target = h.vec(float(v[f + 1]), float(v[f + 2]), 0.)
        i.ground, i.dt, i.stop, i.blocked = float(v[f + 3]), max(.001, (w.now - last) / 1000.), int(v[f + 4]) & 1, (int(v[f + 4]) >> 1) & 1
        o = h.hcb_pilot_out()
        h.LIB.hcb_pilot_step(ctypes.byref(p), ctypes.byref(i), ctypes.byref(o))
        st[heli] = (p, w.now)
        v[f + 1], v[f + 2], v[f + 3], v[f + 4], v[f + 5] = o.pos.x, o.pos.y, o.pos.z, o.dist, o.speed
        car['heading'] = math.degrees(math.atan2(-o.fwd.x, o.fwd.y)) % 360.
        car['pitch'], car['bank'] = math.degrees(math.asin(max(-1., min(1., o.fwd.z)))), math.degrees(math.asin(max(-1., min(1., -o.right.z))))
        self.flown = getattr(self, 'flown', 0) + 1

    def posts(self):
        """who -> hcb_post of the last look (for the tests)"""
        return {p.who: p for p in (self.out.posts[:self.out.n_posts] if self.out is not None else [])}

    def friends(self, w, who):
        return [w.coords(o) for o, _ in self.ours(w) if o != who and o not in w.dead]

    def exchange(self, vm, first, count, cmd):
        w, v = vm.w, vm.v
        assert 0 <= first and first + count <= 32 and count >= 1, ('0E48: a block outside the 32 local variables', first, count)
        if cmd == 1 and count >= 9:
            self.gunner(w, v, first)
        elif cmd == 2 and count >= 3:
            self.guard(w, v, first)
        elif cmd == 3 and count >= 5:
            self.status(w, v, first, count)
        elif cmd == 4 and count >= 10:
            self.post(w, v, first)
        elif cmd == 5 and count >= 9:
            self.detail(w, v, first)
        elif cmd == 6 and count >= 6:
            self.pilot(w, v, first)
        else:
            raise AssertionError(('0E48: unknown command or too few variables', cmd, count))

    def gunner(self, w, v, f):
        who = v[f]
        v[f + 1] = v[f + 2] = 0
        o = self.brain.order(who) if self.out is not None else None
        if not o or not o.target or who not in w.exists or who in w.dead or o.target not in w.exists or o.target in w.dead:
            return
        v[f + 1], v[f + 2] = (1 if o.ready else 0), o.target
        if not o.fire:
            return
        heli = w.shared[b.PUB + 1]
        me, him = w.coords(who), w.coords(o.target)
        near = heli in w.cars and math.dist(w.cars[heli]['pos'], me) < 6.
        speed = (0. if w.frozen.get(heli) else getattr(w, 'car_speeds', {}).get(heli, w.speed)) if near else 0.
        r = self.brain.round(who, o.target, w.now & 0xffffffff, self.chest(me, .3), self.chest(him, .2), w.coords(1), self.friends(w, who), float(speed), near)
        if r is None:
            return
        r = h.hcb_round.from_buffer_copy(bytes(r))
        if r.verdict == h.HCB_HOLD_NONE:
            r.ray = int(self.sight(w, [r.muzzle.x, r.muzzle.y, r.muzzle.z], [r.to.x, r.to.y, r.to.z]))
            if not r.ray:
                self.brain.blocked(who, w.now & 0xffffffff)
        self.rounds.append(r)
        if r.verdict == h.HCB_HOLD_NONE and r.ray:
            v[f + 1] = 2
            v[f + 3], v[f + 4], v[f + 5] = r.muzzle.x, r.muzzle.y, r.muzzle.z
            v[f + 6], v[f + 7], v[f + 8] = r.end.x, r.end.y, r.end.z

    def guard(self, w, v, f):
        who = v[f]
        v[f + 1] = v[f + 2] = 0
        o = self.brain.order(who) if self.out is not None else None
        if not o or not o.target or who not in w.exists or who in w.dead or o.target not in w.exists or o.target in w.dead:
            return
        v[f + 2] = o.target
        v[f + 1] = self.brain.squad(who, o.target, w.now & 0xffffffff, w.coords(who), w.coords(o.target), w.coords(1), self.friends(w, who))
        self.said.append((w.now, who, v[f + 1], o.target))

    def status(self, w, v, f, count):
        o = self.out
        v[f], v[f + 1], v[f + 2], v[f + 3], v[f + 4] = (o.alert, o.n_threats, o.n_attackers, o.kills, 0) if o is not None else (0, 0, 0, 0, 0)
        if o is not None:
            for m in o.marks[:o.n_marks]:
                if m.kind == h.HCB_KIND_PED and m.cls >= h.HCB_CLS_THREAT and m.id in w.exists and m.id not in w.dead:
                    v[f + 4] = m.id
                    break
        if count >= 8:
            if self.cj_shot and w.now - self.cj_shot[0] < 60000:
                v[f + 5], v[f + 6], v[f + 7] = w.now - self.cj_shot[0], self.cj_shot[1], self.cj_shot[2]
            else:
                v[f + 5], v[f + 6], v[f + 7] = -1, 0., 0.
        if count >= 9:
            v[f + 8] = w.now - self.heli_shot if self.heli_shot is not None and w.now - self.heli_shot < 60000 else -1

    # ------------------------------------------------------------ for the tests
    def marks(self):
        return {m.id: (m.cls, m.why) for m in self.out.marks[:self.out.n_marks]} if self.out is not None else {}

    def orders(self):
        return {o.who: (o.target, o.fire, o.hold) for o in self.out.orders[:self.out.n_orders]} if self.out is not None else {}
