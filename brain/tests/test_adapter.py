#!/usr/bin/env python3
"""Runs libHelicoverBrain64.so (the phone build) on an emulated arm64 CPU against the player's REAL libGTASA.so.

    python3 brain/tests/test_adapter.py path/to/libGTASA.so [path/to/libHelicoverBrain64.so]

The mod's install checks read the real game code. The game's world (pools, peds, vehicles, the player, CLEO's shared
values) is laid out in memory by this test exactly as brain/research/game_facts.md describes it; the handful of game
functions the mod calls are replaced by recorders. The report the mod writes is then replayed by the host build of
the core: the decisions taken on the emulated arm64 CPU must be reproduced bit for bit on this computer.
"""
import os, struct, subprocess, sys, tempfile
from pathlib import Path
from unicorn import *
from unicorn.arm64_const import *
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'tools'))
import hcb_py as h
import replay as replay_tool

LIB = sys.argv[1] if len(sys.argv) > 1 else ''
MOD = sys.argv[2] if len(sys.argv) > 2 else str(HERE.parent.parent / 'build' / 'brain' / 'libHelicoverBrain64.so')
if not LIB:
    sys.exit(__doc__)
GTA, MODB, CLEO, STUB, STACK, DATA, SENT, WORLD = 0x7000000000, 0x7100000000, 0x7200000000, 0x6000000000, 0x6100000000, 0x6300000000, 0x6200000000, 0x6400000000
MODS = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/mods/'
RET = struct.pack('<I', 0xd65f03c0)
X = [UC_ARM64_REG_X0 + i for i in range(8)]
S = [UC_ARM64_REG_S0 + i for i in range(8)]
W, H = 2000, 1250
# game addresses (the same numbers as brain/game/brain.c and gta_words.h)
PED_POOL, VEH_POOL, PED_STRIDE, VEH_STRIDE = 0xbc3bb8, 0xbc3bc0, 0x9c8, 0xc68
PLAYERS, PLAYER_FOCUS, TIME_MS, USER_PAUSE, CUTSCENE, MISSION_FLAG, SCRIPT_SPACE, GROUPS, RSGLOBAL = 0xbdc738, 0xbdcae8, 0xbdc558, 0xbdc594, 0xba8925, 0x9f83f8, 0x9a2038, 0xc89c20, 0xc9b320
VT_USE_GUN, VT_KILL = 0x8338c8 + 0x10, 0x833c80 + 0x10
F_SCRIPTS, F_HUD, F_GUNSHOT, F_LOS, F_POLY, F_SCREEN = 0x3f3ad8, 0x51f6f0, 0x442854, 0x5075a4, 0x6ee4a4, 0x6e9df8
GOT_SCRIPTS, GOT_HUD, GOT_GUNSHOT = 0x845438, 0x845ec8, 0x843f10
HC_STATE = 0x48456A00
CLEO_IMAGE = 0x88000


def fl(v):
    return struct.unpack('<f', struct.pack('<I', v & 0xffffffff))[0]


def assemble(text):
    with tempfile.TemporaryDirectory() as d:
        open(d + '/a.s', 'w').write('.text\n' + text + '\n')
        subprocess.check_call(['clang', '--target=aarch64-linux-android21', '-c', d + '/a.s', '-o', d + '/a.o'])
        subprocess.check_call(['llvm-objcopy', '-O', 'binary', '--only-section=.text', d + '/a.o', d + '/a.bin'])
        return open(d + '/a.bin', 'rb').read()


ITER = assemble('''stp x29, x30, [sp, #-0x30]!
stp x19, x20, [sp, #0x10]
stp x21, x22, [sp, #0x20]
mov x19, x0
mov x20, x1
ldr x21, =%d
ldr x22, [x21, #0x800]
1: cbz x22, 2f
mov x0, x21
mov x1, #0x20
mov x2, x20
blr x19
add x21, x21, #0x20
sub x22, x22, #1
b 1b
2: mov w0, #0
ldp x21, x22, [sp, #0x20]
ldp x19, x20, [sp, #0x10]
ldp x29, x30, [sp], #0x30
ret
.ltorg''' % DATA)
_elf = ELFFile(open(LIB, 'rb'))
_loads = [s for s in _elf.iter_segments() if s['p_type'] == 'PT_LOAD']
GTA_SIZE = (max(s['p_vaddr'] + s['p_memsz'] for s in _loads) + 0xffff) & ~0xffff
GTA_IMAGE = bytearray(GTA_SIZE)
for _s in _loads:
    _d = _s.data()
    GTA_IMAGE[_s['p_vaddr']:_s['p_vaddr'] + len(_d)] = _d
GTA_IMAGE = bytes(GTA_IMAGE)


class Emu:
    def __init__(self, tweak=None, cleo='CLEO ANDROID (64-260403)', sautils=True):
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.imports, self.fs, self.fds, self.polys, self.items, self.prot, self.los_calls, self.threads = {}, {}, {}, [], [], [], [], []
        self.clock, self.sautils, self.walls, self.orig_calls = 1000, sautils, False, {'scripts': 0, 'hud': 0, 'gunshot': 0}
        uc.mem_map(GTA, GTA_SIZE); uc.mem_write(GTA, GTA_IMAGE)
        for slot, target in ((GOT_SCRIPTS, F_SCRIPTS), (GOT_HUD, F_HUD), (GOT_GUNSHOT, F_GUNSHOT)):      # what the linker binds at load
            uc.mem_write(GTA + slot, struct.pack('<Q', GTA + target))
        uc.mem_map(CLEO, 0x400000)
        if cleo:
            uc.mem_write(CLEO + CLEO_IMAGE + 0x1bc30, cleo.encode() + b'\0')
        uc.mem_map(STUB, 0x10000); uc.mem_map(STACK, 0x100000); uc.mem_map(DATA, 0x10000); uc.mem_map(SENT, 0x1000); uc.mem_write(SENT, RET * 4)
        uc.mem_map(WORLD, 0x400000)
        uc.hook_add(UC_HOOK_CODE, self.on_stub, begin=STUB, end=STUB + 0xffff)
        for addr, fn in ((F_SCRIPTS, self.g_scripts), (F_HUD, self.g_hud), (F_GUNSHOT, self.g_gunshot), (F_LOS, self.g_los), (F_POLY, self.g_poly), (F_SCREEN, self.g_screen)):
            uc.hook_add(UC_HOOK_CODE, fn, begin=GTA + addr, end=GTA + addr)
        names = [b'/data/app/x/lib/arm64/libGTASA.so\0', b'/data/app/x/lib/arm64/libSAcleo64.so\0']
        ph = lambda va, sz: struct.pack('<IIQQQQQQ', 1, 6, va, va, va, sz, sz, 0x1000)
        uc.mem_write(DATA + 0x1000, names[0]); uc.mem_write(DATA + 0x1100, names[1])
        uc.mem_write(DATA + 0x2000, ph(0, GTA_SIZE)); uc.mem_write(DATA + 0x3000, ph(0, 0x37160) + ph(0x4f830, 0x2bf790 + 0x100000))
        uc.mem_write(DATA, struct.pack('<QQQHxxxxxx', GTA, DATA + 0x1000, DATA + 0x2000, 1) + struct.pack('<QQQHxxxxxx', CLEO, DATA + 0x1100, DATA + 0x3000, 2))
        uc.mem_write(DATA + 0x800, struct.pack('<Q', 2))
        uc.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
        self.sau = DATA + 0x6000; uc.mem_write(self.sau, struct.pack('<Q', self.sau + 0x100)); uc.mem_write(self.sau + 0x100, b''.join(struct.pack('<Q', self.stub('sau:%d' % i)) for i in range(8)))
        self.world()
        if tweak:
            tweak(self)
        self.load_mod()
        self.before = bytes(uc.mem_read(GTA, GTA_SIZE))

    # ---------------------------------------------------------- the world as the game lays it out
    def world(self):
        uc = self.uc
        self.ped_objs, self.ped_flags, self.veh_objs, self.veh_flags = WORLD + 0x10000, WORLD + 0x8000, WORLD + 0x100000, WORLD + 0x9000
        self.n_peds, self.n_vehs, self.heap = 140, 110, WORLD + 0x200000
        uc.mem_write(self.ped_flags, b'\x80' * self.n_peds); uc.mem_write(self.veh_flags, b'\x80' * self.n_vehs)
        uc.mem_write(WORLD, struct.pack('<QQi', self.ped_objs, self.ped_flags, self.n_peds)); uc.mem_write(WORLD + 0x100, struct.pack('<QQi', self.veh_objs, self.veh_flags, self.n_vehs))
        uc.mem_write(GTA + PED_POOL, struct.pack('<Q', WORLD)); uc.mem_write(GTA + VEH_POOL, struct.pack('<Q', WORLD + 0x100))
        uc.mem_write(GTA + RSGLOBAL + 8, struct.pack('<ii', W, H))
        uc.mem_write(GTA + TIME_MS, struct.pack('<I', 500000))
        uc.mem_write(GTA + PLAYER_FOCUS, b'\0'); uc.mem_write(GTA + USER_PAUSE, b'\0\0'); uc.mem_write(GTA + CUTSCENE, b'\0'); uc.mem_write(GTA + MISSION_FLAG, struct.pack('<I', 0))
        self.wanted = self.alloc(0x40)
        self.shared = self.alloc(0x2000)
        self.shared_n = 0
        uc.mem_write(CLEO + CLEO_IMAGE + 0x7d1f8, struct.pack('<QQQ', self.shared, self.shared, self.shared + 0x2000))
        self.cj = self.ped(0, 0, pedtype=0, flag=3)
        self.pdata = self.alloc(0xd8)
        uc.mem_write(self.pdata, struct.pack('<Q', self.wanted)); uc.mem_write(self.pdata + 0x4c, struct.pack('<I', 0))
        uc.mem_write(self.cj + 0x540, struct.pack('<Q', self.pdata))
        uc.mem_write(GTA + PLAYERS, struct.pack('<Q', self.cj) + struct.pack('<Q', self.wanted))

    def alloc(self, n):
        a = self.heap
        self.heap += (n + 15) & ~15
        return a

    def w32(self, a, v): self.uc.mem_write(a, struct.pack('<I', v & 0xffffffff))
    def w64(self, a, v): self.uc.mem_write(a, struct.pack('<Q', v))
    def wf(self, a, *v): self.uc.mem_write(a, struct.pack('<%df' % len(v), *v))
    def r32(self, a): return struct.unpack('<I', bytes(self.uc.mem_read(a, 4)))[0]
    def r64(self, a): return struct.unpack('<Q', bytes(self.uc.mem_read(a, 8)))[0]

    def ped(self, x, y, z=1., pedtype=4, weapon=0, health=100., flag=1, face=(0., 1.), model=20, index=None):
        uc = self.uc
        i = index if index is not None else next(k for k in range(self.n_peds) if bytes(uc.mem_read(self.ped_flags + k, 1))[0] & 0x80)
        p = self.ped_objs + i * PED_STRIDE
        uc.mem_write(p, bytes(PED_STRIDE)); uc.mem_write(self.ped_flags + i, bytes([flag]))
        mat = self.alloc(0x50)
        self.wf(mat, face[1], -face[0], 0., 0., face[0], face[1], 0., 0., 0., 0., 1., 0., x, y, z, 0.)
        self.w64(p + 0x18, mat); uc.mem_write(p + 0x5a, bytes([3])); uc.mem_write(p + 0x32, struct.pack('<h', model))
        intel = self.alloc(0x440); self.w64(intel, p); self.w64(p + 0x538, intel)
        uc.mem_write(p + 0x548, b'\x01'); self.w32(p + 0x54c, 1); self.wf(p + 0x6ac, health); self.w32(p + 0x720, pedtype)
        uc.mem_write(p + 0x8dc, b'\x00'); self.w32(p + 0x730, weapon)
        return p

    def handle(self, ptr):
        if self.ped_objs <= ptr < self.ped_objs + self.n_peds * PED_STRIDE:
            i = (ptr - self.ped_objs) // PED_STRIDE
            return (i << 8) | bytes(self.uc.mem_read(self.ped_flags + i, 1))[0]
        i = (ptr - self.veh_objs) // VEH_STRIDE
        return 0x80000000 | (i << 8) | bytes(self.uc.mem_read(self.veh_flags + i, 1))[0]      # vehicle ids carry bit 31 for the core

    def move(self, ptr, x, y, z=1.):
        self.wf(self.r64(ptr + 0x18) + 0x30, x, y, z)

    def aim(self, ped, target):
        """Give the ped a use-gun task pointed at target (0 = take it away)."""
        intel = self.r64(ped + 0x538)
        if not target:
            self.w64(intel + 0x30, 0)
            return
        t = self.alloc(0x40); self.w64(t, GTA + VT_USE_GUN); self.w64(t + 0x28, target); self.w64(intel + 0x30, t)

    def veh(self, x, y, z=1., health=1000., vtype=0, driver=0, speed=(0., 0., 0.), flag=1):
        uc = self.uc
        i = next(k for k in range(self.n_vehs) if bytes(uc.mem_read(self.veh_flags + k, 1))[0] & 0x80)
        v = self.veh_objs + i * VEH_STRIDE
        uc.mem_write(v, bytes(VEH_STRIDE)); uc.mem_write(self.veh_flags + i, bytes([flag]))
        mat = self.alloc(0x50)
        self.wf(mat, 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., x, y, z, 0.)
        self.w64(v + 0x18, mat); uc.mem_write(v + 0x5a, bytes([2 | (3 << 3)])); self.wf(v + 0x634, health); self.w32(v + 0x738, vtype)
        self.wf(v + 0x68, *[s / 50. for s in speed]); uc.mem_write(v + 0x5ec, b'\x03')
        if driver:
            self.w64(v + 0x5a0, driver); self.w64(driver + 0x708, v); uc.mem_write(driver + 0x585, b'\x01')
        return v

    def share(self, key, value):
        """What a Helicover script does with 0DDC."""
        for k in range(self.shared_n):
            if self.r32(self.shared + 8 * k) == key:
                self.w32(self.shared + 8 * k + 4, value)
                return
        self.w32(self.shared + 8 * self.shared_n, key); self.w32(self.shared + 8 * self.shared_n + 4, value)
        self.shared_n += 1
        self.w64(CLEO + CLEO_IMAGE + 0x7d200, self.shared + 8 * self.shared_n)

    # ---------------------------------------------------------- the mod
    def load_mod(self):
        uc = self.uc; f = ELFFile(open(MOD, 'rb')); loads = [s for s in f.iter_segments() if s['p_type'] == 'PT_LOAD']
        size = (max(s['p_vaddr'] + s['p_memsz'] for s in loads) + 0xffff) & ~0xffff; img = bytearray(size)
        for s in loads:
            d = s.data(); img[s['p_vaddr']:s['p_vaddr'] + len(d)] = d
        dsym = f.get_section_by_name('.dynsym')
        for sec in f.iter_sections():
            if not isinstance(sec, RelocationSection):
                continue
            for r in sec.iter_relocations():
                t, off = r['r_info_type'], r['r_offset']
                if t == 1027:
                    img[off:off + 8] = struct.pack('<Q', MODB + r['r_addend'])
                elif t in (1025, 1026, 257):
                    sym = dsym.get_symbol(r['r_info_sym'])
                    img[off:off + 8] = struct.pack('<Q', MODB + sym['st_value'] + (r['r_addend'] or 0) if sym['st_shndx'] != 'SHN_UNDEF' else self.stub(sym.name))
        uc.mem_map(MODB, size); uc.mem_write(MODB, bytes(img)); self.mod_size = size
        self.syms = {s.name: s['st_value'] for s in dsym.iter_symbols()}

    def stub(self, name):
        if name not in self.imports:
            a = STUB + 0x100 * (len(self.imports) + 1); self.imports[name] = a
            self.uc.mem_write(a, ITER if name == 'dl_iterate_phdr' else RET)
        return self.imports[name]

    def cstr(self, a): return bytes(self.uc.mem_read(a, 600)).split(b'\0')[0].decode()

    def on_stub(self, uc, addr, size, _):
        names = {v: k for k, v in self.imports.items()}
        if addr not in names:
            return
        n = names[addr]; x = [uc.reg_read(r) for r in X]; ret = x[0]
        if n == 'dl_iterate_phdr':
            return
        if n == 'open':
            path = self.cstr(x[0])
            if x[1] & 3 == 0:
                ret = (1 << 64) - 1 if path not in self.fs else self._fd(path)
            else:
                self.fs[path] = b''; ret = self._fd(path)
        elif n == 'read':
            path, pos = self.fds[x[0]]; d = self.fs[path][pos:pos + x[2]]; uc.mem_write(x[1], d); self.fds[x[0]][1] = pos + len(d); ret = len(d)
        elif n == 'write':
            self.fs[self.fds[x[0]][0]] += bytes(uc.mem_read(x[1], x[2])); ret = x[2]
        elif n == 'close': ret = 0
        elif n == 'mprotect': self.prot.append((x[0], x[1], x[2])); ret = 0
        elif n == 'getpagesize': ret = 0x4000
        elif n == 'dladdr': ret = 0
        elif n == 'dlopen': ret = 0xa31 if self.cstr(x[0]) == 'libAML.so' else 0
        elif n == 'dlsym': ret = self.stub('aml:GetInterface')
        elif n == 'aml:GetInterface': ret = self.sau if self.sautils and self.cstr(x[0]) == 'SAUtils' else 0
        elif n == 'sau:3': self.items.append(dict(name=self.cstr(x[2]), init=x[3], cb=x[7], labels=[self.cstr(self.r64(x[6] + 8 * k)) for k in range(x[5] + 1)])); ret = len(self.items)
        elif n == 'pthread_create': self.threads.append((x[2], x[3])); ret = 0
        elif n == 'usleep': ret = 0
        elif n == 'clock_gettime':
            self.clock += 137; uc.mem_write(x[1], struct.pack('<qq', self.clock // 1000000, (self.clock % 1000000) * 1000)); ret = 0
        uc.reg_write(UC_ARM64_REG_X0, ret & ((1 << 64) - 1))

    def _fd(self, path):
        fd = 10 + len(self.fds); self.fds[fd] = [path, 0]
        return fd

    def _ret(self, uc, value=None):
        if value is not None:
            uc.reg_write(UC_ARM64_REG_X0, value)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

    # the game functions the mod reaches: recorders
    def g_scripts(self, uc, *_): self.orig_calls['scripts'] += 1; self._ret(uc)
    def g_hud(self, uc, *_): self.orig_calls['hud'] += 1; self._ret(uc)
    def g_gunshot(self, uc, *_): self.orig_calls['gunshot'] += 1; self._ret(uc)
    def g_los(self, uc, *_):
        a = struct.unpack('<3f', bytes(uc.mem_read(uc.reg_read(X[0]), 12))); b = struct.unpack('<3f', bytes(uc.mem_read(uc.reg_read(X[1]), 12)))
        flags = [uc.reg_read(r) & 0xff for r in X[2:8]] + [bytes(uc.mem_read(uc.reg_read(UC_ARM64_REG_SP), 1))[0]]
        self.los_calls.append((a, b, flags))
        self._ret(uc, 0 if self.walls else 1)

    def g_poly(self, uc, *_):
        self.polys.append(dict(c=tuple(uc.mem_read(uc.reg_read(X[0]), 4)), p=[round(fl(uc.reg_read(r)), 1) for r in S]))
        self._ret(uc)

    def g_screen(self, uc, *_):
        x, y, z = struct.unpack('<3f', bytes(uc.mem_read(uc.reg_read(X[0]), 12)))
        if y < -5:                                           # behind the camera (it looks north from 5 m south of the origin)
            return self._ret(uc, 0)
        uc.mem_write(uc.reg_read(X[1]), struct.pack('<3f', W / 2 + x * 20, H / 2 - z * 20, y + 5))
        uc.mem_write(uc.reg_read(X[2]), struct.pack('<f', 40.)); uc.mem_write(uc.reg_read(X[3]), struct.pack('<f', 40.))
        self._ret(uc, 1)

    def call(self, addr, x=(), s=()):
        uc = self.uc
        for i, v in enumerate(x):
            uc.reg_write(X[i], v & ((1 << 64) - 1))
        for i, v in enumerate(s):
            uc.reg_write(S[i], struct.unpack('<I', struct.pack('<f', v))[0])
        uc.reg_write(UC_ARM64_REG_SP, STACK + 0xf0000); uc.reg_write(UC_ARM64_REG_LR, SENT)
        uc.emu_start(addr, SENT, count=20000000)
        return uc.reg_read(UC_ARM64_REG_X0)

    def load(self):
        self.call(MODB + self.syms['OnModLoad'])
        return self.fs.get(MODS + 'hcbrain_log.txt', b'').decode()

    def slot(self, got): return self.r64(GTA + got)

    def frame(self, ms=100, n=1, hud=True):
        """What the game does in a frame: scripts (through the GOT slot), then the HUD."""
        for _ in range(n):
            self.w32(GTA + TIME_MS, self.r32(GTA + TIME_MS) + ms)
            self.call(self.slot(GOT_SCRIPTS))
            if hud:
                self.call(self.slot(GOT_HUD))

    def gunshot(self, ped, to):
        m = self.r64(ped + 0x18)
        o = struct.unpack('<3f', bytes(self.uc.mem_read(m + 0x30, 12)))
        self.call(self.slot(GOT_GUNSHOT), x=(0x1234, ped, 0), s=(o[0], o[1], o[2], to[0], to[1], to[2]))

    def report(self):
        return self.fs.get(MODS + 'hcbrain_report.bin')


results = []


def passed(t):
    results.append('PASS: ' + t)


def changed_bytes(e):
    now = bytes(e.uc.mem_read(GTA, GTA_SIZE))
    return [i for i in range(0, GTA_SIZE, 8) if now[i:i + 8] != e.before[i:i + 8]]


# ------------------------------------------------------------------ install
e = Emu()
log = e.load()
slots = [e.slot(g) for g in (GOT_SCRIPTS, GOT_HUD, GOT_GUNSHOT)]
assert all(MODB <= s < MODB + e.mod_size for s in slots) and len(set(slots)) == 3, [hex(s) for s in slots]
assert 'the brain is watching' in log and '66 instruction words match' in log and 'brain: 3 of 3' in log and 'CLEO recognised' in log, log
assert sorted(changed_bytes(e)) == sorted([GOT_SCRIPTS, GOT_HUD, GOT_GUNSHOT]), 'exactly three GOT slots of the game differ, nothing else'
rw = [p for p in e.prot if p[2] == 3]; ro = [p for p in e.prot if p[2] == 1]
assert len(rw) == len(ro) == 3 and all(p[0] % 0x4000 == 0 and p[1] == 0x4000 for p in e.prot) and not [p for p in e.prot if p[2] & 4], e.prot
assert [i['name'] for i in e.items] == ['Brain markers', 'Brain report'] and e.items[0]['init'] == 1 and not e.threads
passed('On the real libGTASA.so the mod finds all 66 instruction words, changes exactly three GOT slots (page made writable, then read-only again; never executable) and nothing else in the game; two items in Mods Settings')
e.frame(n=3)
assert e.orig_calls == {'scripts': 3, 'hud': 3, 'gunshot': 0}, e.orig_calls
passed('The game\'s own CTheScripts::Process and CHud::Draw are still called, once per call of the mod\'s functions')


def refuses(tweak, text, **kw):
    e = Emu(tweak=tweak, **kw)
    log = e.load()
    assert text in log and 'the brain is watching' not in log, log
    assert not changed_bytes(e) and not e.prot, 'nothing in the game was touched'
    e.w32(GTA + TIME_MS, 600000)
    return e


refuses(lambda e: e.uc.mem_write(GTA + 0x40fb74, struct.pack('<I', 0xbd46b100)), 'differs from the build the brain was made for')       # health at another offset
refuses(lambda e: e.uc.mem_write(GTA + F_LOS + 4, struct.pack('<I', 0xd503201f)), 'differs from the build the brain was made for')
refuses(lambda e: e.uc.mem_write(GTA + GOT_SCRIPTS, struct.pack('<Q', 0x7300000000)), 'another mod has taken it')
passed('Another game build (one instruction differs, e.g. the health field at another offset) or the per-frame slot already taken by another mod: nothing is changed, the log says exactly what differed')
e = Emu(tweak=lambda e: (e.uc.mem_write(GTA + GOT_HUD, struct.pack('<Q', GTA + F_HUD + 0x1000)), e.uc.mem_write(GTA + GOT_GUNSHOT, struct.pack('<Q', GTA + F_GUNSHOT + 0x1000))))
log = e.load()
assert 'the brain is watching' in log and 'brain: 1 of 3' in log and 'no markers on screen' in log and 'shots will not be seen' in log, log
assert sorted(changed_bytes(e)) == [GOT_SCRIPTS] and e.slot(GOT_HUD) == GTA + F_HUD + 0x1000
gang_ = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
e.frame(n=3, hud=False)
e.call(e.items[1]['cb'], x=(0, 1, 0)); e.frame(n=1, hud=False)
t_ = replay_tool.replay(e.report())[2]
assert len(t_) == 4 and t_[-1]['out'].n_threats == 1 and all(x['match'] for x in t_)
passed('The HUD or gunshot slot taken by another mod: those two are left alone and the brain still watches and records (no markers, no shots) - it says so in the log')
e = Emu(cleo='CLEO ANDROID (64-999999)')
log = e.load()
assert 'the brain is watching' in log and 'CLEO not recognised' in log and len(e.threads) == 1, log
e.frame(n=3)
assert e.report() is None
passed('An unknown CLEO build: the brain still watches (it just cannot tell who is ours) and keeps looking for CLEO from a waiting thread')

# ------------------------------------------------------------------ a fight, seen through the game's memory
e = Emu()
e.load()
gang = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))            # an armed Balla 20 m east, turned to CJ
civ = e.ped(-15, 5, pedtype=4)
homie = e.ped(3, 3, pedtype=8, weapon=22)
recruit = e.ped(-3, 3, pedtype=4)
e.w64(GTA + GROUPS + 0x18 + 8 * 2, recruit)                          # member 2 of the player's group 0
cop = e.ped(0, 30, pedtype=6, weapon=22, face=(0., -1.))
pilot, g1, g2, s1, s2 = e.ped(0, 8, 25., pedtype=8), e.ped(1.4, 9, 25., pedtype=8, weapon=31), e.ped(-1.4, 9, 25., pedtype=8, weapon=31), e.ped(4, 2, pedtype=8, weapon=31), e.ped(4, -2, pedtype=8, weapon=31)
heli = e.veh(0, 8, 25., vtype=3, driver=pilot)
burning = e.veh(8, -6, health=200.)
driver = e.ped(-40, 0.5, pedtype=7)
rammer = e.veh(-40, 0.5, driver=driver, speed=(20., 0., 0.))
e.share(HC_STATE + 7, 3)
e.share(HC_STATE + 21, e.handle(heli) & 0x7fffffff)                 # the script's own handle of the helicopter
for k, p in enumerate((pilot, g1, g2)):
    e.share(HC_STATE + 22 + k, e.handle(p))
for k, p in enumerate((s1, s2)):
    e.share(HC_STATE + 71 + k, e.handle(p))
e.share(HC_STATE + 73, 0xdead01)                                     # a stale handle: must be ignored
e.frame(n=3)
e.items[1]['cb'] and e.call(e.items[1]['cb'], x=(0, 1, 0))           # "Brain report": tap
e.frame(n=1)
data = e.report()
assert data is not None
head, text, ticks = replay_tool.replay(data)
s = ticks[-1]['snapshot']; o = ticks[-1]['out']
marks = {m.id: (m.cls, m.why) for m in o.marks[:o.n_marks]}
H_ = e.handle
assert s.player.id == H_(e.cj) and s.n_peds == 11 and s.heli == H_(heli) and s.roe == 3 and s.wanted == 0, (s.n_peds, hex(s.heli), s.roe)
assert sorted(s.ours[:s.n_ours]) == sorted(H_(p) for p in (pilot, g1, g2, s1, s2)) and sorted(s.our_role[:s.n_ours]) == [1, 2, 3, 6, 7], list(s.our_role[:s.n_ours])
assert marks[H_(gang)] == (h.HCB_CLS_THREAT, h.HCB_WHY_ARMED_FACING) and H_(civ) not in marks and H_(cop) not in marks, marks
assert marks[H_(homie)] == (h.HCB_CLS_FRIEND, h.HCB_WHY_ALLY) and marks[H_(recruit)] == (h.HCB_CLS_FRIEND, h.HCB_WHY_ALLY) and marks[H_(s1)] == (h.HCB_CLS_FRIEND, h.HCB_WHY_OURS)
assert marks[H_(burning)] == (h.HCB_CLS_THREAT, h.HCB_WHY_BURNING) and marks[H_(rammer)] == (h.HCB_CLS_THREAT, h.HCB_WHY_RAMMING) and marks[H_(driver)] == (h.HCB_CLS_THREAT, h.HCB_WHY_RAMMING)
gp = next(p for p in s.peds[:s.n_peds] if p.id == H_(gang))
assert (gp.weapon, gp.pedtype, round(gp.pos.x), round(gp.fwd.x), gp.flags2 & 3) == (30, 7, 20, -1, 3) and abs(gp.health - 100) < .01
dp = next(p for p in s.peds[:s.n_peds] if p.id == H_(driver))
assert dp.vehicle == H_(rammer) and dp.flags2 & h.HCB_PF2_DRIVER
rv = next(v for v in s.vehs[:s.n_vehs] if v.id == H_(rammer))
assert abs(rv.vel.x - 20) < .01 and rv.driver == H_(driver) and next(v for v in s.vehs[:s.n_vehs] if v.id == H_(heli)).cls == h.HCB_VC_HELI
assert o.alert == h.HCB_ALERT_THREAT
passed('The world is read correctly out of the game\'s memory: CJ, 11 people (type, weapon, position, facing, vehicle and seat), vehicles (speed, driver, burning, helicopter), our people and roles from the scripts\' shared values (a stale handle ignored), recruited homies from the player\'s group - and judged: armed Balla = THREAT, burning car and car on a collision course = hazards, Grove / recruit / ours = friends')
assert all(t['match'] for t in ticks) and len(ticks) == 4 and ticks[0]['exact'], [(t['match'], t['exact']) for t in ticks]
passed('The report written on the emulated arm64 CPU replays on this computer to the same decisions, digest for digest: the core is bit-exact across the two architectures')
assert 'think time' in text and 'screen 2000x1250' in text and 'asked for in Mods Settings' in text and 'CLEO shared values' in text, text
los_to_cj = [c for c in e.los_calls if abs(c[1][2] - 1.6) < .01 and abs(c[1][0]) < .01 and abs(c[1][1]) < .01]
assert los_to_cj and all(c[2] == [1, 1, 0, 1, 0, 0, 0] for c in e.los_calls), e.los_calls[:3]
assert any(abs(c[0][0] - 4) < .01 and abs(c[1][0] - 20) < .01 for c in e.los_calls), 'the core\'s question "does our guard see the Balla" is answered with a real ray'
passed('Lines of sight are asked from the game chest to chest (buildings, vehicles and objects block; people do not): armed people to CJ, and the pairs the core asked about')

# shots, a weapon on CJ, damage
e.fs.pop(MODS + 'hcbrain_report.bin')
e.aim(civ, e.cj); e.w32(civ + 0x730, 22)
e.gunshot(gang, (0., 0.5, 1.))
e.gunshot(cop, (0., 60., 1.))                                        # the policeman fires up the street, away from CJ
e.frame(n=1)
e.wf(e.cj + 0x6ac, 70.); e.w64(e.cj + 0x940, gang); e.w32(e.cj + 0x948, e.r32(GTA + TIME_MS)); e.uc.mem_write(e.cj + 0x93c, bytes([30]))
e.wf(s1 + 0x6ac, 60.); e.w64(s1 + 0x940, rammer); e.w32(s1 + 0x948, 77); e.uc.mem_write(s1 + 0x93c, bytes([49]))    # run over: the inflictor is the car
e.frame(n=3)
e.call(e.items[1]['cb'], x=(1, 0, 0)); e.frame(n=1)
head, text, ticks = replay_tool.replay(e.report())
events = [(ev.type, ev.src, ev.dst, round(ev.value)) for t in ticks for ev in t['snapshot'].events[:t['snapshot'].n_events]]
assert (h.HCB_EV_SHOT, H_(gang), 0, 0) in events and (h.HCB_EV_SHOT, H_(cop), 0, 0) in events, events
assert (h.HCB_EV_DAMAGE, H_(gang), H_(e.cj), 30) in events and (h.HCB_EV_DAMAGE, H_(driver), H_(s1), 40) in events, events
o = ticks[-1]['out']; marks = {m.id: (m.cls, m.why) for m in o.marks[:o.n_marks]}
assert marks[H_(gang)] == (h.HCB_CLS_ATTACKER, h.HCB_WHY_HURT_CJ) and marks[H_(civ)] == (h.HCB_CLS_THREAT, h.HCB_WHY_AIMS_AT_CJ) and marks[H_(driver)][0] == h.HCB_CLS_ATTACKER, marks
assert marks[H_(cop)] == (h.HCB_CLS_WATCH, h.HCB_WHY_SHOOTING_NEARBY) and o.alert >= h.HCB_ALERT_COMBAT and all(t['match'] for t in ticks)
assert e.orig_calls['gunshot'] == 2
passed('Events: every gunshot is seen through the hook (and still reaches the game), damage to CJ and to ours is found from their health with the right inflictor (a car = its driver), a civilian\'s gun on CJ comes from his task - Balla = ATTACKER, civilian = THREAT, the policeman firing elsewhere is only watched')

# ------------------------------------------------------------------ markers
e.polys.clear()
e.frame(n=1)
bar, marks_drawn = e.polys[0], e.polys[1:]
assert bar['p'][1] == 0 and W * .45 < bar['p'][0] < bar['p'][2] < W * .55 and bar['c'][:3] in ((240, 40, 40), (255, 255, 255)), bar
fills = [p for p in marks_drawn if p['c'][:3] != (0, 0, 0)]
edges = [p for p in marks_drawn if p['c'][:3] == (0, 0, 0)]
assert len(fills) == len(edges) >= 8
by_colour = {}
for p in fills:
    by_colour.setdefault(p['c'][:3], []).append(((p['p'][0] + p['p'][2]) / 2, (p['p'][1] + p['p'][5]) / 2, p['p'][2] - p['p'][0]))
assert len(by_colour[(240, 40, 40)]) == 2 and len(by_colour[(70, 150, 255)]) == 2 and len(by_colour[(60, 200, 90)]) >= 2 and (255, 140, 0) in by_colour and (250, 220, 40) in by_colour, by_colour
gx = [c for c in by_colour[(240, 40, 40)] if abs(c[0] - (W / 2 + 20 * 20)) < 1]
assert gx and abs(gx[0][1] - (H / 2 - 2.25 * 20)) < 1 and H * .008 <= gx[0][2] <= H * .03, by_colour[(240, 40, 40)]
assert all(0 <= c[0] <= W and 0 <= c[1] <= H for v in by_colour.values() for c in v)
e.call(e.items[0]['cb'], x=(1, 0, 0)); e.polys.clear(); e.frame(n=1)
assert not e.polys and b'Marks = 0' in e.fs['/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/configs/net.helicover.brain.ini']
e.call(e.items[0]['cb'], x=(0, 1, 0)); e.uc.mem_write(GTA + USER_PAUSE, b'\1'); e.frame(n=1)
assert not e.polys
e.uc.mem_write(GTA + USER_PAUSE, b'\0')
passed('Markers: a strip at the top centre in the colour of the alert level, and a square with a dark edge 1.25 m over every judged person (red attacker, orange threat, yellow watched, green ours, blue ally); nothing behind the camera or off screen; "Brain markers: Off" and the pause menu draw nothing')

# ------------------------------------------------------------------ robustness
e.fs.pop(MODS + 'hcbrain_report.bin', None)
e.wf(e.cj + 0x6ac, 0.); e.frame(n=2)
assert e.report() is not None and 'CJ died' in replay_tool.replay(e.report())[1]
passed('When CJ dies a report is saved by itself')
e = Emu()
e.load()
e.w64(GTA + PED_POOL, 0); e.frame(n=3)                                # the game has no pools yet (loading screen)
e.w64(GTA + PED_POOL, WORLD); e.w64(GTA + PLAYERS, 0); e.frame(n=3)   # no player yet
e.w64(GTA + PLAYERS, e.cj)
for k in range(1, 140):                                               # a full pool, far more people than a snapshot holds
    p = e.ped((k % 12) * 3 - 18, (k // 12) * 3 - 18, pedtype=7 if k % 3 == 0 else 4, weapon=30 if k % 5 == 0 else 0, index=k)
    if k % 7 == 0:
        e.w64(p + 0x18, 0); e.wf(p + 8, float(k), 2., 1.)             # an entity without a matrix: the simple transform is used
    if k % 11 == 0:
        e.w64(p + 0x538, 0)                                           # no intelligence object
e.frame(n=30, ms=100)
e.w32(GTA + TIME_MS, 1000)                                            # the clock jumps back (a loaded save)
e.frame(n=5)
e.call(e.items[1]['cb'], x=(0, 1, 0)); e.frame(n=1)
head, text, ticks = replay_tool.replay(e.report())
assert len(ticks) >= 30 and max(t['snapshot'].n_peds for t in ticks) == h.HCB_MAX_PEDS and max(t['snapshot'].peds_lost for t in ticks) > 50 and all(t['match'] for t in ticks if t['exact'])
passed('No pools yet, no player yet, a full pool of 139 people (64 nearest are taken), entities without a matrix or without an intelligence object, the clock jumping back after a load: no fault, and the report still replays exactly')

text = '\n'.join(results) + '\nThe phone build on an emulated CPU with the real libGTASA.so; the world in memory is laid out by the test. Not run in the game.\n'
(h.OUT / 'brain_adapter_tests.txt').write_text(text)
print(text)
