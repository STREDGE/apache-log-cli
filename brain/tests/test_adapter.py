#!/usr/bin/env python3
"""Runs libHelicoverBrain64.so (the phone build) on an emulated arm64 CPU against the player's REAL libGTASA.so and the
REAL code of his CLEO library.

    python3 brain/tests/test_adapter.py path/to/libGTASA.so path/to/libSAcleo64.so.image [path/to/libHelicoverBrain64.so]

(the .image file and its .names.json are written by cleo-ui/tools/unpack_cleo.py from the player's libSAcleo64.so)

The mod's install checks read the real game code. The game's world (pools, peds, vehicles, the player) is laid out in
memory by this test exactly as brain/research/game_facts.md describes it; the handful of game functions the mod calls
are replaced by recorders. The bridge is the real thing: the mod registers its opcode with CLEO's own RegisterOpcode,
the test then calls CLEO's own opcode dispatcher on a script laid out in memory, and the parameters are read by the
game's own CollectParameters / GetPointerToScriptVariable. The report the mod writes is replayed by the host build of
the core: the decisions taken on the emulated arm64 CPU must be reproduced bit for bit on this computer.
"""
import math, os, re, struct, subprocess, sys, tempfile
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

import json
LIB = sys.argv[1] if len(sys.argv) > 1 else ''
CLEO_FILE = sys.argv[2] if len(sys.argv) > 2 else ''
MOD = sys.argv[3] if len(sys.argv) > 3 else str(HERE.parent.parent / 'build' / 'brain' / 'libHelicoverBrain64.so')
if not LIB or not CLEO_FILE:
    sys.exit(__doc__)
CLEO_BYTES = Path(CLEO_FILE).read_bytes()
CLEO_NAMES = {int(k, 16): v.replace('dyn:', '') for k, v in json.load(open(CLEO_FILE + '.names.json')).items()}
GTA, MODB, CLEO, STUB, STACK, DATA, SENT, WORLD = 0x7000000000, 0x7100000000, 0x7200000000, 0x6000000000, 0x6100000000, 0x6300000000, 0x6200000000, 0x6400000000
OLDSTUB, CHEAP, TLS = 0x7600000000, 0x6500000000, 0x6600000000      # the unpacker's import stubs (baked into the image); CLEO's heap; thread data
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
GOT_IGNORE, IGNORE_ENTITY, F_COLLECT, F_VARPTR, SCRIPT_PARAMS = 0x84b180, 0xbdcaf8, 0x3f1fcc, 0x3f2654, 0xa001ac
HC_STATE = 0x48456A00
HC_HELLO, HC_POLICE, HC_MISSION, HELLO_MAGIC = HC_STATE + 440, HC_STATE + 441, HC_STATE + 442, 0x42520021
CLEO_IMAGE = 0x88000
I_DISPATCH, I_REGISTER, I_MAP, I_VERSION, I_SHARED = 0x37904, 0x38a58, 0x27d988, 0x1bc30, 0x7d1f8
I_G_COLLECT, I_G_VARPTR, I_G_PARAMS, I_G_BASE = 0x7d248, 0x7d240, 0x7d220, 0x7d1a0
CMD_GUNNER, CMD_SQUAD, CMD_STATUS = 1, 2, 3
CI = CLEO + CLEO_IMAGE


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
# what the linker does at load: the game's own code is run here (the script parameter readers), and it finds its data
# through the GOT
UNDEF = STUB + 0xfff0
_symdata = _elf.get_section_by_name('.dynsym').data()
for _name in ('.rela.dyn', '.rela.plt'):
    _sec = _elf.get_section_by_name(_name)
    for _off, _info, _add in struct.iter_unpack('<QQq', _sec.data() if _sec else b''):
        _t, _si = _info & 0xffffffff, _info >> 32
        if _t == 1027:
            struct.pack_into('<Q', GTA_IMAGE, _off, GTA + _add)
        elif _t in (1025, 1026, 257):
            _shndx, _value = struct.unpack_from('<HQ', _symdata, _si * 24 + 6)
            struct.pack_into('<Q', GTA_IMAGE, _off, (GTA + _value + (_add if _t == 257 else 0)) if _shndx else UNDEF)
GTA_IMAGE = bytes(GTA_IMAGE)


class Emu:
    def __init__(self, tweak=None, cleo=None, sautils=True, mod=None, cleo_ready=True):
        self.mod_path = mod or MOD
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.imports, self.fs, self.fds, self.polys, self.items, self.prot, self.los_calls, self.threads = {}, {}, {}, [], [], [], [], []
        self.signals, self.sigactions, self.clock_step, self.deliver = [], [], 5, None
        self.clock, self.sautils, self.walls, self.orig_calls = 1000, sautils, False, {'scripts': 0, 'hud': 0, 'gunshot': 0}
        uc.mem_map(GTA, GTA_SIZE); uc.mem_write(GTA, GTA_IMAGE)
        for slot, target in ((GOT_SCRIPTS, F_SCRIPTS), (GOT_HUD, F_HUD), (GOT_GUNSHOT, F_GUNSHOT)):      # what the linker binds at load
            uc.mem_write(GTA + slot, struct.pack('<Q', GTA + target))
        uc.mem_write(GTA + GOT_IGNORE, struct.pack('<Q', GTA + IGNORE_ENTITY))
        uc.mem_write(GTA + IGNORE_ENTITY, struct.pack('<Q', 0x5e17))          # whatever the game left there: it must still be there afterwards
        # the player's CLEO, unpacked: its real code and data at the address the image was made for
        self.cleo_size = (len(CLEO_BYTES) + 0xffff) & ~0xffff
        uc.mem_map(CLEO, self.cleo_size); uc.mem_write(CLEO, CLEO_BYTES)
        if cleo:
            uc.mem_write(CI + I_VERSION, cleo.encode() + b'\0')
        uc.mem_map(OLDSTUB, 0x100000); uc.mem_write(OLDSTUB, RET * (0x100000 // 4)); uc.mem_map(CHEAP, 0x100000); uc.mem_map(TLS, 0x10000)
        uc.mem_write(TLS + 0x28, struct.pack('<Q', 0x1122334455667788)); uc.reg_write(UC_ARM64_REG_TPIDR_EL0, TLS)
        self.cheap, self.cleo_unknown = CHEAP + 0x100, []
        uc.hook_add(UC_HOOK_CODE, self.on_cleo_stub, begin=OLDSTUB, end=OLDSTUB + 0xfffff)
        if cleo_ready:
            self.cleo_finds_game()
        uc.mem_map(STUB, 0x10000); uc.mem_write(UNDEF, RET); uc.mem_map(STACK, 0x100000); uc.mem_map(DATA, 0x10000); uc.mem_map(SENT, 0x1000); uc.mem_write(SENT, RET * 4)
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
        self.cleo_before = bytes(uc.mem_read(CLEO, self.cleo_size))
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
        uc.mem_write(CI + I_SHARED, struct.pack('<QQQ', self.shared, self.shared, self.shared + 0x2000))
        # a CLEO script as the game keeps it: CRunningScript with its 32 local variables at +0x6c, and some code
        self.script, self.code = self.alloc(0x200), self.alloc(0x100)
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

    def veh(self, x, y, z=1., health=1000., vtype=0, driver=0, speed=(0., 0., 0.), flag=1, model=400):
        uc = self.uc
        i = next(k for k in range(self.n_vehs) if bytes(uc.mem_read(self.veh_flags + k, 1))[0] & 0x80)
        v = self.veh_objs + i * VEH_STRIDE
        uc.mem_write(v, bytes(VEH_STRIDE)); uc.mem_write(self.veh_flags + i, bytes([flag]))
        mat = self.alloc(0x50)
        self.wf(mat, 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., x, y, z, 0.)
        self.w64(v + 0x18, mat); uc.mem_write(v + 0x5a, bytes([2 | (3 << 3)])); self.wf(v + 0x634, health); self.w32(v + 0x738, vtype); uc.mem_write(v + 0x32, struct.pack('<h', model))
        self.wf(v + 0x68, *[s / 50. for s in speed]); uc.mem_write(v + 0x5ec, b'\x03')
        if driver:
            self.w64(v + 0x5a0, driver); self.w64(driver + 0x708, v); uc.mem_write(driver + 0x585, b'\x01')
        return v

    def cleo_finds_game(self):
        """What CLEO stores when it has resolved the game's script functions (its own init, 0x2efac)."""
        for at, v in ((I_G_COLLECT, GTA + F_COLLECT), (I_G_VARPTR, GTA + F_VARPTR), (I_G_PARAMS, GTA + SCRIPT_PARAMS), (I_G_BASE, GTA)):
            self.w64(CI + at, v)

    def on_cleo_stub(self, uc, addr, size, _):
        n = CLEO_NAMES.get(addr)
        if n is None:
            return
        x = [uc.reg_read(r) for r in X]; ret = 0
        if n in ('malloc', '_Znwm', '_Znam'):
            ret = self.cheap; self.cheap += (x[0] + 0x2f) & ~0xf
        elif n == 'calloc':
            ret = self.cheap; self.cheap += (x[0] * x[1] + 0x2f) & ~0xf
        elif n in ('memcpy', 'memmove'): uc.mem_write(x[0], bytes(uc.mem_read(x[1], x[2]))); ret = x[0]
        elif n == 'memset': uc.mem_write(x[0], bytes([x[1] & 255]) * x[2]); ret = x[0]
        elif n in ('free', '_ZdlPv', '_ZdaPv', 'pthread_mutex_lock', 'pthread_mutex_unlock'): ret = 0
        else: self.cleo_unknown.append(n)
        uc.reg_write(UC_ARM64_REG_X0, ret & ((1 << 64) - 1))

    def shared_value(self, key):
        for k in range(self.shared_n):
            if self.r32(self.shared + 8 * k) == key:
                return self.r32(self.shared + 8 * k + 4)
        return None

    def locals(self, first=0, n=32):
        return list(struct.unpack('<%di' % n, bytes(self.uc.mem_read(self.script + 0x6c + 4 * first, 4 * n))))

    def opcode(self, first, count, cmd, handle=None, var=None):
        """0E48 first_variable count command, run as CLEO runs it: its dispatcher finds the handler the mod registered.
        Returns (handled, the `count` variables after the call, how many bytes of parameters were consumed)."""
        if handle is not None:
            self.w32(self.script + 0x6c + 4 * first, handle)
        code = b'\x48\x0e' + (var if var is not None else b'\x03' + struct.pack('<H', first)) + b'\x04' + struct.pack('<b', count) + b'\x04' + struct.pack('<b', cmd) + b'\x4e\x00'
        self.uc.mem_write(self.code, code)
        self.w64(self.script + 0x20, self.code + 2)                       # the ip is just behind the two opcode bytes
        handled = self.call(CI + I_DISPATCH, x=(self.script, self.script + 0x20, 0x0E48)) & 0xff
        return handled, self.locals(first, max(1, min(count, 32 - first))), self.r64(self.script + 0x20) - self.code - 2

    def share(self, key, value):
        """What a Helicover script does with 0DDC."""
        for k in range(self.shared_n):
            if self.r32(self.shared + 8 * k) == key:
                self.w32(self.shared + 8 * k + 4, value)
                return
        self.w32(self.shared + 8 * self.shared_n, key); self.w32(self.shared + 8 * self.shared_n + 4, value)
        self.shared_n += 1
        self.w64(CI + I_SHARED + 8, self.shared + 8 * self.shared_n)

    # ---------------------------------------------------------- the mod
    def load_mod(self):
        uc = self.uc; f = ELFFile(open(self.mod_path, 'rb')); loads = [s for s in f.iter_segments() if s['p_type'] == 'PT_LOAD']
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
        elif n == 'clock_gettime':      # the real clock: it moves with the frames (frame()) and a little with every reading (clock_step us)
            self.clock += self.clock_step; uc.mem_write(x[1], struct.pack('<qq', self.clock // 1000000, (self.clock % 1000000) * 1000)); ret = 0
        elif n == 'sigaction':
            act = bytes(uc.mem_read(x[1], 32)) if x[1] else None
            self.sigactions.append((x[0], struct.unpack('<iiQQQ', act) if act else None)); ret = 0
            if x[2]: uc.mem_write(x[2], struct.pack('<iiQQQ', 0, 0, 0xdead0, 0, 0))   # the previous handler (the game had one)
        elif n == 'syscall':
            if x[0] == 172: ret = 4242                       # getpid
            elif x[0] == 178: ret = 4243                     # gettid
            elif x[0] == 131:                                # tgkill: delivered at once when the test says so
                self.signals.append((x[1], x[2], x[3])); ret = 0
                if self.deliver:
                    uc.reg_write(X[0], x[3]); uc.reg_write(X[1], 0); uc.reg_write(X[2], self.deliver[1])
                    uc.reg_write(UC_ARM64_REG_PC, self.deliver[0]); return
            elif x[0] == 270:                                # process_vm_readv: a bad address is an error, not a fault
                lb, ln = struct.unpack('<QQ', bytes(uc.mem_read(x[2], 16))); rb, rn = struct.unpack('<QQ', bytes(uc.mem_read(x[4], 16)))
                try:
                    uc.mem_write(lb, bytes(uc.mem_read(rb, rn))); ret = rn
                except UcError:
                    ret = (1 << 64) - 14
            else: ret = (1 << 64) - 38
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
        self.los_calls.append((a, b, flags, self.r64(GTA + IGNORE_ENTITY)))
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

    def call(self, addr, x=(), s=(), count=20000000):
        uc = self.uc
        for i, v in enumerate(x):
            uc.reg_write(X[i], v & ((1 << 64) - 1))
        for i, v in enumerate(s):
            uc.reg_write(S[i], struct.unpack('<I', struct.pack('<f', v))[0])
        uc.reg_write(UC_ARM64_REG_SP, STACK + 0xf0000); uc.reg_write(UC_ARM64_REG_LR, SENT)
        uc.emu_start(addr, SENT, count=count)
        return uc.reg_read(UC_ARM64_REG_X0)

    def load(self):
        self.call(MODB + self.syms['OnModLoad'])
        return self.fs.get(MODS + 'hcbrain_log.txt', b'').decode()

    def slot(self, got): return self.r64(GTA + got)

    def frame(self, ms=100, n=1, hud=True):
        """What the game does in a frame: scripts (through the GOT slot), then the HUD."""
        for _ in range(n):
            self.w32(GTA + TIME_MS, self.r32(GTA + TIME_MS) + ms)
            self.clock += ms * 1000
            self.call(self.slot(GOT_SCRIPTS))
            if hud:
                self.call(self.slot(GOT_HUD))

    def gunshot(self, ped, to):
        m = self.r64(ped + 0x18)
        o = struct.unpack('<3f', bytes(self.uc.mem_read(m + 0x30, 12)))
        self.call(self.slot(GOT_GUNSHOT), x=(0x1234, ped, 0), s=(o[0], o[1], o[2], to[0], to[1], to[2]))

    def reports(self):
        return sorted(k[len(MODS):] for k in self.fs if k.startswith(MODS + 'hcbrain_report_'))

    def report(self):
        names = self.reports()
        return self.fs[MODS + names[-1]] if names else None

    def log(self):
        return self.fs.get(MODS + 'hcbrain_log.txt', b'').decode()

    def cleo_changes(self):
        now = bytes(self.uc.mem_read(CLEO, self.cleo_size))
        mine = set(range(I_SHARED, I_SHARED + 0x18, 8)) | {I_G_COLLECT, I_G_VARPTR, I_G_PARAMS, I_G_BASE}     # what this test itself writes as CLEO would
        return [i - CLEO_IMAGE for i in range(0, self.cleo_size, 8) if now[i:i + 8] != self.cleo_before[i:i + 8] and i - CLEO_IMAGE not in mine]

    def save(self, hud=True):
        """Tap "Brain report" and let a frame pass; returns the newest report."""
        self.call(self.items[1]['cb'], x=(0, 1, 0)); self.frame(n=1, hud=hud)
        return self.report()


results = []


def passed(t):
    results.append('PASS: ' + t)


def changed_bytes(e):
    """Words of the game image that differ from what it was at load - leaving out the game clock (this test moves it) and
    the game's own ScriptParams buffer (the game's CollectParameters fills it for every opcode of every script)."""
    now = bytes(e.uc.mem_read(GTA, GTA_SIZE))
    own = {TIME_MS & ~7} | set(range(SCRIPT_PARAMS & ~7, SCRIPT_PARAMS + 0x88, 8))
    return [i for i in range(0, GTA_SIZE, 8) if now[i:i + 8] != e.before[i:i + 8] and i not in own]


def f32(v):
    return struct.unpack('<f', struct.pack('<i', v))[0]


N_WORDS = len(re.findall(r'^\s+\{0x', (HERE.parent / 'game' / 'gta_words.h').read_text(), re.M))

# ------------------------------------------------------------------ install
e = Emu()
log = e.load()
slots = [e.slot(g) for g in (GOT_SCRIPTS, GOT_HUD, GOT_GUNSHOT)]
assert all(MODB <= s < MODB + e.mod_size for s in slots) and len(set(slots)) == 3, [hex(s) for s in slots]
assert 'the brain is running' in log and '%d instruction words match' % N_WORDS in log and 'brain: 3 of 3' in log and 'CLEO recognised' in log, log
assert sorted(changed_bytes(e)) == sorted([GOT_SCRIPTS, GOT_HUD, GOT_GUNSHOT]), 'exactly three GOT slots of the game differ, nothing else'
rw = [p for p in e.prot if p[2] == 3]; ro = [p for p in e.prot if p[2] == 1]
assert len(rw) == len(ro) == 3 and all(p[0] % 0x4000 == 0 and p[1] == 0x4000 for p in e.prot) and not [p for p in e.prot if p[2] & 4], e.prot
assert [i['name'] for i in e.items] == ['Brain markers', 'Brain report'] and e.items[0]['init'] == 0 and len(e.threads) == 1 and 'hang recorder on' in log, (e.threads, log)
assert not e.cleo_changes(), 'CLEO is not touched before the game runs its scripts'
passed('On the real libGTASA.so the mod finds all %d instruction words, changes exactly three GOT slots (page made writable, then read-only again; never executable) and nothing else in the game; two items in Mods Settings, the markers off by default' % N_WORDS)
e.frame(n=3)
assert e.orig_calls == {'scripts': 3, 'hud': 3, 'gunshot': 0}, e.orig_calls
passed('The game\'s own CTheScripts::Process and CHud::Draw are still called, once per call of the mod\'s functions')

# ------------------------------------------------------------------ the bridge: CLEO's own RegisterOpcode and dispatcher
assert 'bridge: opcode 0E48 registered with CLEO' in e.log() and not e.cleo_unknown, (e.log(), e.cleo_unknown)
ch = e.cleo_changes()
assert ch and all(I_MAP <= c < I_MAP + 0x18 for c in ch), [hex(c) for c in ch]
assert not e.polys, 'markers are off: nothing is drawn'
handled, v, used = e.opcode(5, 5, CMD_STATUS)
assert handled == 1 and used == 7 and v[:4] == [0, 0, 0, 0], (handled, v, used)
assert e.call(CI + I_DISPATCH, x=(e.script, e.script + 0x20, 0x0E49)) & 0xff == 0, 'only the one number is taken'
assert sorted(changed_bytes(e)) == sorted([GOT_SCRIPTS, GOT_HUD, GOT_GUNSHOT]), 'the game\'s own parameter readers ran, nothing else of the game changed'
passed('The bridge is made with CLEO\'s own code: RegisterOpcode(0E48) on the first frame (the only thing that changes inside CLEO is its opcode map), and CLEO\'s dispatcher then calls the brain with a script whose parameters are read by the game\'s own CollectParameters / GetPointerToScriptVariable')
assert e.shared_value(HC_HELLO) is None and e.shared_n == 0
e.frame(n=2)
assert e.shared_n == 0, 'the brain never adds a value to CLEO\'s storage'
e.share(HC_HELLO, 0)                                                  # the script: 0DDC HELLO 0
e.frame(n=1)
assert e.shared_value(HC_HELLO) == HELLO_MAGIC and e.shared_n == 1
e.w64(CI + I_SHARED + 8, e.shared); e.shared_n = 0                    # a loaded save: CLEO empties its storage and restarts the scripts
e.frame(n=2)
e.share(HC_HELLO, 0); e.frame(n=1)
assert e.shared_value(HC_HELLO) == HELLO_MAGIC
passed('Handshake: the script creates one shared value with 0, the brain answers in it on the next frame (and again after a load has emptied CLEO\'s storage); the brain itself never adds a value')


def refuses(tweak, text, **kw):
    e = Emu(tweak=tweak, **kw)
    log = e.load()
    assert text in log and 'the brain is running' not in log, log
    assert not changed_bytes(e) and not e.prot and not e.cleo_changes(), 'nothing in the game or in CLEO was touched'
    e.w32(GTA + TIME_MS, 600000)
    return e


refuses(lambda e: e.uc.mem_write(GTA + 0x40fb74, struct.pack('<I', 0xbd46b100)), 'differs from the build the brain was made for')       # health at another offset
refuses(lambda e: e.uc.mem_write(GTA + F_LOS + 4, struct.pack('<I', 0xd503201f)), 'differs from the build the brain was made for')
refuses(lambda e: e.uc.mem_write(GTA + F_COLLECT, struct.pack('<I', 0xd503201f)), 'differs from the build the brain was made for')
refuses(lambda e: e.uc.mem_write(GTA + GOT_SCRIPTS, struct.pack('<Q', 0x7300000000)), 'another mod has taken it')
passed('Another game build (one instruction differs, e.g. the health field at another offset or the parameter reader CLEO uses) or the per-frame slot already taken by another mod: nothing is changed, the log says exactly what differed')
e = Emu(tweak=lambda e: (e.uc.mem_write(GTA + GOT_HUD, struct.pack('<Q', GTA + F_HUD + 0x1000)), e.uc.mem_write(GTA + GOT_GUNSHOT, struct.pack('<Q', GTA + F_GUNSHOT + 0x1000))))
log = e.load()
assert 'the brain is running' in log and 'brain: 1 of 3' in log and 'no markers on screen' in log and 'shots will not be seen' in log, log
assert sorted(changed_bytes(e)) == [GOT_SCRIPTS] and e.slot(GOT_HUD) == GTA + F_HUD + 0x1000
gang_ = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
e.frame(n=3, hud=False)
t_ = replay_tool.replay(e.save(hud=False))[2]
assert len(t_) >= 4 and t_[-1]['out'].n_threats == 1 and all(x['match'] for x in t_)
passed('The HUD or gunshot slot taken by another mod: those two are left alone and the brain still runs and records (no markers, no shots) - it says so in the log')


def no_bridge(text, **kw):
    e = Emu(**kw)
    log = e.load()
    assert 'the brain is running' in log
    e.share(HC_HELLO, 0)
    e.frame(n=25)
    assert text in e.log() and e.shared_value(HC_HELLO) == 0, e.log()
    ch = e.cleo_changes()
    assert e.call(CI + I_DISPATCH, x=(e.script, e.script + 0x20, 0x0E48)) & 0xff == 0, 'the opcode is not registered'
    return e, ch


e, ch = no_bridge('CLEO not recognised', cleo='CLEO ANDROID (64-999999)')
assert len(e.threads) == 2 and not ch, [hex(c) for c in ch]     # waiting for CLEO, and the hang recorder
e, ch = no_bridge('CLEO\'s code is not the build the bridge was made for', tweak=lambda e: e.uc.mem_write(CI + I_REGISTER + 4, struct.pack('<I', 0xd503201f)))
assert ch == [I_REGISTER & ~7]
e, ch = no_bridge('CLEO\'s plugin table is not where it should be', tweak=lambda e: e.w64(CI + 0x27d9b8 + 8 * 19, CI + 0x38e80))
e, ch = no_bridge('CLEO has not found the game\'s script functions (yet)', cleo_ready=False)
assert e.log().count('bridge: not yet') == 1, 'said once, then tried again quietly'
e.cleo_finds_game()
e.frame(n=12)
assert 'bridge: opcode 0E48 registered' in e.log() and e.shared_value(HC_HELLO) == HELLO_MAGIC
passed('No bridge without the CLEO it was made for: another CLEO version, one changed instruction in CLEO\'s interface code, a moved plugin table - the opcode is not registered, the handshake is not answered (so Helicover refuses to work) and the log says why; a CLEO that has not found the game yet is tried again once a second')

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
police_heli = e.veh(60, 60, 50., vtype=3, model=497)
e.share(HC_STATE + 7, 3)
e.share(HC_STATE + 21, e.handle(heli) & 0x7fffffff)                 # the script's own handle of the helicopter
for k, p in enumerate((pilot, g1, g2)):
    e.share(HC_STATE + 22 + k, e.handle(p))
for k, p in enumerate((s1, s2)):
    e.share(HC_STATE + 71 + k, e.handle(p))
e.share(HC_STATE + 73, 0xdead01)                                     # a stale handle: must be ignored
e.share(HC_HELLO, 0)
e.frame(n=3)
data = e.save()
assert data is not None and e.reports() == ['hcbrain_report_01.bin']
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
ph = next(v for v in s.vehs[:s.n_vehs] if v.id == H_(police_heli))
assert ph.flags & h.HCB_VF_EMERGENCY and ph.model == 497, 'the police Maverick is known for what it is (it was not in the first real fight)'
assert o.alert == h.HCB_ALERT_THREAT and s.police == h.HCB_POLICE_ANSWER and s.mission_free == 0
passed('The world is read correctly out of the game\'s memory: CJ, 11 people (type, weapon, position, facing, vehicle and seat), vehicles (speed, driver, burning, helicopters, police models), our people and roles from the scripts\' shared values (a stale handle ignored), recruited homies from the player\'s group - and judged: armed Balla = THREAT, burning car and car on a collision course = hazards, Grove / recruit / ours = friends')
assert all(t['match'] for t in ticks) and len(ticks) >= 4 and ticks[0]['exact'], [(t['match'], t['exact']) for t in ticks]
passed('The report written on the emulated arm64 CPU replays on this computer to the same decisions, digest for digest: the core is bit-exact across the two architectures')
assert 'think time' in text and 'screen 2000x1250' in text and 'asked for in Mods Settings' in text and 'scripts bridge: opcode 0E48' in text, text
los_to_cj = [c for c in e.los_calls if abs(c[1][2] - 1.6) < .01 and abs(c[1][0]) < .01 and abs(c[1][1]) < .01]
assert los_to_cj and all(c[2] == [1, 1, 0, 1, 0, 0, 0] for c in e.los_calls), e.los_calls[:3]
assert any(abs(c[0][0] - 4) < .01 and abs(c[1][0] - 20) < .01 for c in e.los_calls), 'the core\'s question "does our guard see the Balla" is answered with a real ray'
to_driver = [c for c in e.los_calls if abs(c[1][0] + 40) < 1]
assert to_driver and all(c[3] == rammer for c in to_driver) and all(c[3] == 0 for c in e.los_calls if c not in to_driver) and e.r64(GTA + IGNORE_ENTITY) == 0x5e17, 'a ray to the man at the wheel passes through his own car, every other ray ignores nothing, and the game\'s own value is put back'
e.share(HC_POLICE, 1); e.share(HC_MISSION, 1); e.frame(n=1)
s = replay_tool.replay(e.save())[2][-1]['snapshot']
assert s.police == h.HCB_POLICE_EVADE and s.mission_free == 1
e.share(HC_POLICE, 0); e.share(HC_MISSION, 0)
e.share(HC_STATE + 27, 1); e.frame(n=1)                              # the helicopter has landed: the crew are guards on foot now
s = replay_tool.replay(e.save())[2][-1]['snapshot']
assert sorted(s.our_role[:s.n_ours]) == [1, 6, 6, 7, 7], list(s.our_role[:s.n_ours])
e.share(HC_STATE + 27, 0)
# a guard who was let go and walks away (the scripts keep him in LEAVE..+7) is still ours: a friend in every line of fire, no orders
gone = e.ped(-6, -9, pedtype=8, weapon=0)
e.share(HC_STATE + 416, e.handle(gone)); e.frame(n=1)
s = replay_tool.replay(e.save())[2][-1]['snapshot']
assert H_(gone) in list(s.ours[:s.n_ours]) and s.our_role[list(s.ours[:s.n_ours]).index(H_(gone))] == h.HCB_ROLE_NONE, list(s.our_role[:s.n_ours])
e.share(HC_STATE + 416, 0); e.frame(n=1)
passed('Lines of sight are asked from the game chest to chest (buildings, vehicles and objects block; people do not): armed people to CJ, and every pair the core asked about. The player\'s settings "police" and "missions" are read from the scripts\' shared values; the crew count as door gunners only while they are mounted (on foot they fire the game\'s own weapon and are judged like the ground team)')

# shots, a weapon on CJ, damage
e.aim(civ, e.cj); e.w32(civ + 0x730, 22)
e.gunshot(gang, (0., 0.5, 1.))
e.gunshot(cop, (0., 60., 1.))                                        # the policeman fires up the street, away from CJ
e.frame(n=1)
e.wf(e.cj + 0x6ac, 70.); e.w64(e.cj + 0x940, gang); e.w32(e.cj + 0x948, e.r32(GTA + TIME_MS)); e.uc.mem_write(e.cj + 0x93c, bytes([30]))
e.wf(s1 + 0x6ac, 60.); e.w64(s1 + 0x940, rammer); e.w32(s1 + 0x948, 77); e.uc.mem_write(s1 + 0x93c, bytes([49]))    # run over: the inflictor is the car
e.frame(n=3)
head, text, ticks = replay_tool.replay(e.save())
events = [(ev.type, ev.src, ev.dst, round(ev.value)) for t in ticks for ev in t['snapshot'].events[:t['snapshot'].n_events]]
assert (h.HCB_EV_SHOT, H_(gang), 0, 0) in events and (h.HCB_EV_SHOT, H_(cop), 0, 0) in events, events
assert (h.HCB_EV_DAMAGE, H_(gang), H_(e.cj), 30) in events and (h.HCB_EV_DAMAGE, H_(driver), H_(s1), 40) in events, events
o = ticks[-1]['out']; marks = {m.id: (m.cls, m.why) for m in o.marks[:o.n_marks]}
assert marks[H_(gang)] == (h.HCB_CLS_ATTACKER, h.HCB_WHY_HURT_CJ) and marks[H_(civ)] == (h.HCB_CLS_THREAT, h.HCB_WHY_AIMS_AT_CJ) and marks[H_(driver)][0] == h.HCB_CLS_ATTACKER, marks
assert marks[H_(cop)] == (h.HCB_CLS_WATCH, h.HCB_WHY_SHOOTING_NEARBY) and o.alert >= h.HCB_ALERT_COMBAT and all(t['match'] for t in ticks)
assert e.orig_calls['gunshot'] == 2
passed('Events: every gunshot is seen through the hook (and still reaches the game), damage to CJ and to ours is found from their health with the right inflictor (a car = its driver), a civilian\'s gun on CJ comes from his task - Balla = ATTACKER, civilian = THREAT, the policeman firing elsewhere is only watched')

# ------------------------------------------------------------------ fire control through the opcode
# the car that was bearing down on CJ and the civilian with the pistol leave the scene: one attacker, the Balla 20 m east
e.uc.mem_write(e.veh_flags + (rammer - e.veh_objs) // VEH_STRIDE, b'\x80'); e.uc.mem_write(e.ped_flags + (driver - e.ped_objs) // PED_STRIDE, b'\x80')
e.uc.mem_write(e.ped_flags + (civ - e.ped_objs) // PED_STRIDE, b'\x80')
e.los_calls.clear()
rounds, states, t0 = [], [], e.r32(GTA + TIME_MS)
for k in range(60):                                                  # three seconds at 20 frames a second
    e.frame(ms=50, hud=False)
    e.gunshot(gang, (0., 0.5, 1.)) if k % 8 == 0 else None
    n_los = len(e.los_calls)
    handled, v, used = e.opcode(3, 9, CMD_GUNNER, handle=H_(g1))
    assert handled == 1 and used == 7 and v[0] == H_(g1)
    states.append(v[1])
    if v[1] == 2:
        rounds.append(dict(t=e.r32(GTA + TIME_MS), muzzle=[f32(x) for x in v[3:6]], end=[f32(x) for x in v[6:9]], target=v[2], ray=e.los_calls[n_los:]))
    left = e.opcode(3, 9, CMD_GUNNER, handle=H_(g2))[1]
    assert left[1] != 2, 'the gunner in the left door does not fire across the cabin'
assert rounds and all(r['target'] == H_(gang) for r in rounds) and 1 in states, states
gaps = [b['t'] - a['t'] for a, b in zip(rounds, rounds[1:])]
assert min(gaps) >= 130 and 6 <= len(rounds) <= 20 and max(gaps) >= 300, (len(rounds), gaps)
me = (1.4, 9., 25.3)
for r in rounds:
    d = [r['end'][i] - me[i] for i in range(3)]
    n = math.sqrt(sum(x * x for x in d))
    out = math.dist(r['muzzle'], me)
    off_line = math.dist(r['muzzle'], [me[i] + d[i] / n * out for i in range(3)])
    assert abs(out - 5.5) < .01 and off_line < .01, 'the round starts 5.5 m out, on the line'
    aim = [r['end'][i] - d[i] / n * 0.6 for i in range(3)]
    assert max(abs(aim[i] - (20., 0., 1.2)[i]) for i in range(3)) <= 0.1 + 0.01 * n + .02, ('scattered round the man by no more than 0.1 m + 1 % of the range', aim)
    assert len(r['ray']) == 1 and r['ray'][0][2] == [1, 1, 0, 1, 0, 0, 0] and math.dist(r['ray'][0][0], r['muzzle']) < .01 and math.dist(r['ray'][0][1], aim) < .01, 'one ray along the very line of the round'
assert len({tuple(round(x, 2) for x in r['end']) for r in rounds}) == len(rounds), 'no two rounds on the same line'
passed('A door gunner asks every frame (0E48, 9 variables): weapon on the man, then rounds - each with its own line from 5.5 m outside the helicopter to a point scattered round the man and 0.6 m past it, checked by one ray along that very line; %d rounds in 3 s, never closer than 130 ms, with pauses between bursts; the gunner in the other door does not fire across the cabin' % len(rounds))


def until_round(who=None, frames=40):
    """Frames until the right gunner is given a round; returns the variables."""
    for _ in range(frames):
        e.frame(ms=50, hud=False)
        v = e.opcode(3, 9, CMD_GUNNER, handle=H_(who or g1))[1]
        if v[1] == 2:
            return v
    raise AssertionError('no round in %d frames' % frames)


def no_round(calls=20, ms=10):
    """The script keeps asking while the game time moves on (0.2 s: the next round falls due after 0.13-0.18 s), but the
    brain is not given a new look. An order older than 0.3 s is no order, so two of these in a row must stay below that."""
    out = []
    for _ in range(calls):
        e.w32(GTA + TIME_MS, e.r32(GTA + TIME_MS) + ms)
        out.append(e.opcode(3, 9, CMD_GUNNER, handle=H_(g1))[1][1])
    return out


e.gunshot(gang, (0., 0.5, 1.)); until_round()
e.move(e.cj, 18.6, 0.9)                                              # CJ runs up to the Balla: nothing has looked at the world since
assert set(no_round()) == {1}, 'CJ within 2 m of the line in THIS frame: no round, the weapon stays on the man'
e.move(e.cj, 0, 0)
assert 2 in no_round(9), 'CJ away again: the rounds go'
e.gunshot(gang, (0., 0.5, 1.)); until_round()
e.move(s2, 15.5, 2.3, 6.4)                                           # one of ours in the line (he has climbed something)
assert set(no_round()) == {1}
e.move(s2, 4, -2)
e.gunshot(gang, (0., 0.5, 1.)); until_round()
e.walls = True                                                       # a lorry drives between them
assert set(no_round()) == {1}
e.walls = False
car = e.veh(20, 0)                                                   # the Balla gets into a car
e.w64(car + 0x5a0, gang); e.w64(gang + 0x708, car); e.uc.mem_write(gang + 0x585, b'\x01')
e.gunshot(gang, (0., 0.5, 1.)); e.los_calls.clear()
v = until_round()
assert e.los_calls and all(c[3] == car for c in e.los_calls if abs(c[1][0] - 20) < 1.5) and e.r64(GTA + IGNORE_ENTITY) == 0x5e17, 'rays to a man in a car pass through that car, and the game\'s pointer is put back'
e.wf(car + 0x634, 500.); e.move(e.cj, 12, 3)                         # the car is damaged and CJ is 8.5 m from it
e.frame(ms=50, hud=False)
assert set(no_round()) <= {0, 1} and 2 not in [e.opcode(3, 9, CMD_GUNNER, handle=H_(g1))[1][1] for _ in range(3)], 'a damaged car beside CJ is not fired at'
e.move(e.cj, 0, 0); e.wf(car + 0x634, 1000.)
e.w64(car + 0x5a0, 0); e.w64(gang + 0x708, 0); e.uc.mem_write(gang + 0x585, b'\x00'); e.uc.mem_write(e.veh_flags + (car - e.veh_objs) // VEH_STRIDE, b'\x80')
data = e.save()
notes = [r for t in replay_tool.replay(data)[2] for r in t['rounds']]
why = {r.verdict if r.verdict else ('ray' if not r.ray else 0) for r in notes}
assert {0, 'ray', h.HCB_HOLD_FRIEND} <= why and why & {h.HCB_HOLD_CJ_IN_LINE, h.HCB_HOLD_CJ_BEHIND}, why
assert 'rounds of the door gunners' in replay_tool.summarize(data) and all(t['match'] for t in replay_tool.replay(data)[2] if t['exact'])
passed('Each round is refused in the very frame the picture changes, before the brain has even looked again: CJ within 2 m of the line, one of ours in it, something driving in between (the ray), a damaged car beside CJ. A man in a car is seen through his own car (CWorld::pIgnoreEntity set for the ray and put back). Every round and every refusal is in the report')

# a guard on foot
e.gunshot(gang, (0., 0.5, 1.))
got = set()
for _ in range(12):
    e.frame(ms=50, hud=False)
    handled, v, used = e.opcode(10, 3, CMD_SQUAD, handle=H_(s1))
    assert handled == 1 and used == 7
    got.add(v[1])
assert v[1] == 2 and v[2] == H_(gang) and got <= {1, 2}, (v, got)
e.move(e.cj, 12, 1)                                                  # CJ walks into his line
assert e.opcode(10, 3, CMD_SQUAD, handle=H_(s1))[1][1] == 3, 'cease fire in the same frame'
e.frame(ms=50, hud=False)
assert e.opcode(10, 3, CMD_SQUAD, handle=H_(s1))[1][1] == 3
e.move(e.cj, 0, 0); e.frame(ms=50, n=2, hud=False)
assert e.opcode(10, 3, CMD_SQUAD, handle=H_(s1))[1][1] == 2
e.share(HC_STATE + 7, 0); e.frame(ms=50, n=2, hud=False)             # the player says hold fire
assert e.opcode(10, 3, CMD_SQUAD, handle=H_(s1))[1][1] in (0, 3) and e.opcode(3, 9, CMD_GUNNER, handle=H_(g1))[1][1] != 2
e.share(HC_STATE + 7, 3); e.gunshot(gang, (0., 0.5, 1.)); e.frame(ms=50, n=8, hud=False)
handled, v, used = e.opcode(20, 5, CMD_STATUS)
assert v[0] >= h.HCB_ALERT_COMBAT and v[1] >= 1 and v[2] >= 1 and v[3] == 0 and v[4] == H_(gang), v
assert e.opcode(20, 8, CMD_STATUS)[1][5] == -1, 'CJ has not fired'
assert e.opcode(20, 9, CMD_STATUS)[1][8] == -1, 'nobody has fired at the helicopter'
e.gunshot(gang, (1., 8., 23.)); e.frame(ms=50, hud=False)               # a round up at the helicopter (it hangs at 0, 8, 25)
assert 0 <= e.opcode(20, 9, CMD_STATUS)[1][8] <= 100
e.gunshot(s1, (0., 8., 25.)); e.gunshot(gang, (0., 0.5, 1.)); e.frame(ms=200, hud=False)
assert e.opcode(20, 9, CMD_STATUS)[1][8] >= 200, 'our own rounds and rounds at CJ are not fire at the helicopter'
e.gunshot(e.cj, (30., 40., 1.)); e.frame(ms=50, hud=False)
v = e.opcode(20, 8, CMD_STATUS)[1]
assert 0 <= v[5] <= 100 and abs(f32(v[6]) - 0.6) < .01 and abs(f32(v[7]) - 0.8) < .01, (v[5], f32(v[6]), f32(v[7]))
until_round()
e.w32(gang + 0x54c, 55)                                              # he is dead
e.frame(ms=50, n=2, hud=False)
v = e.opcode(20, 5, CMD_STATUS)[1]
assert v[3] == 1 and v[4] != H_(gang) and e.opcode(3, 9, CMD_GUNNER, handle=H_(g1))[1][1:3] == [0, 0] and e.opcode(10, 3, CMD_SQUAD, handle=H_(s1))[1][1:3] == [0, 0], v
passed('A guard on foot asks with 3 variables: cover, fire, and "cease fire" in the very frame CJ walks into his line; "hold fire" in the menu stops everybody; the status request gives alert level, threats, attackers, kills, the most dangerous man, the direction of CJ\'s own last shot (the squad keeps out of his line of fire) and how long ago a stranger fired at the helicopter (the pilot breaks away); a dead man is nobody\'s target and is counted')

# what a script must not be able to do through the opcode
sentinel = [0x51515151] * 32
e.uc.mem_write(e.script + 0x6c, struct.pack('<32i', *sentinel))
for first, count in ((28, 9), (5, 40), (5, 0), (5, -3)):
    handled, v, used = e.opcode(first, count, CMD_GUNNER)
    assert handled == 1 and used == 7 and e.locals() == sentinel, (first, count)
space_before = bytes(e.uc.mem_read(GTA + SCRIPT_SPACE, 0x100))
handled, v, used = e.opcode(0, 9, CMD_GUNNER, var=b'\x02\x10\x00')    # a global variable instead of a local one
assert handled == 1 and used == 7 and e.locals() == sentinel and bytes(e.uc.mem_read(GTA + SCRIPT_SPACE, 0x100)) == space_before
handled, v, used = e.opcode(5, 9, 77)                                 # an unknown command
assert used == 7 and e.locals() == sentinel
handled, v, used = e.opcode(5, 9, CMD_GUNNER, handle=0x7fffff01)      # a handle that names nobody
assert v[1:3] == [0, 0] and e.locals(14, 18) == sentinel[14:]
passed('The opcode writes only inside the block of local variables it was given: a block that runs past the 32 locals, a count of 0 or below, a global variable, an unknown command or a handle that names nobody change nothing - and all three parameters are consumed every time, so the script never runs its own parameters as code')

# ------------------------------------------------------------------ markers
e.w32(gang + 0x54c, 1)
e.gunshot(gang, (0., 0.5, 1.)); until_round()
e.polys.clear(); e.frame(n=1)
assert not e.polys, 'off by default'
e.call(e.items[0]['cb'], x=(0, 1, 0)); e.polys.clear(); e.frame(ms=50, n=1)
bar, marks_drawn = e.polys[0], e.polys[1:]
assert H * .01 <= bar['p'][1] < bar['p'][5] <= H * .03 and W * .45 < bar['p'][0] < bar['p'][2] < W * .55 and bar['c'][:3] in ((240, 40, 40), (255, 255, 255)), bar
frames_ = [p for p in marks_drawn if p['c'][:3] == (255, 255, 255)]
fills = [p for p in marks_drawn if p['c'][:3] not in ((0, 0, 0), (255, 255, 255))]
edges = [p for p in marks_drawn if p['c'][:3] == (0, 0, 0)]
assert len(fills) == len(edges) >= 7
by_colour = {}
for p in fills:
    by_colour.setdefault(p['c'][:3], []).append(((p['p'][0] + p['p'][2]) / 2, (p['p'][1] + p['p'][5]) / 2, p['p'][2] - p['p'][0]))
assert len(by_colour[(240, 40, 40)]) == 1 and len(by_colour[(70, 150, 255)]) == 2 and len(by_colour[(60, 200, 90)]) >= 2, by_colour
gx = by_colour[(240, 40, 40)][0]
assert abs(gx[0] - (W / 2 + 20 * 20)) < 1 and abs(gx[1] - (H / 2 - 2.25 * 20)) < 1 and H * .008 <= gx[2] <= H * .03, gx
assert len(frames_) == 1 and abs((frames_[0]['p'][0] + frames_[0]['p'][2]) / 2 - gx[0]) < 1 and frames_[0]['p'][2] - frames_[0]['p'][0] > gx[2], 'a white frame round the man ours are firing at'
assert all(0 <= c[0] <= W and 0 <= c[1] <= H for v in by_colour.values() for c in v)
assert b'Markers = 1' in e.fs['/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/configs/net.helicover.brain.ini']
e.uc.mem_write(GTA + USER_PAUSE, b'\1'); e.polys.clear(); e.frame(n=1)
assert not e.polys
e.uc.mem_write(GTA + USER_PAUSE, b'\0')
e.call(e.items[0]['cb'], x=(1, 0, 0)); e.polys.clear(); e.frame(n=1)
assert not e.polys
e2 = Emu(tweak=lambda e: e.fs.__setitem__('/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/configs/net.helicover.brain.ini', b'[Preferences]\nMarks = 1\n'))
e2.load()
assert e2.items[0]['init'] == 0, 'the setting of the observer version does not switch the markers on'
passed('Markers are off until the player turns them on in Mods Settings (the setting left by version 0.1 does not count). On: a strip just below the top edge in the colour of the alert level, a square with a dark edge 1.25 m over every judged person (red attacker, green ours, blue ally) and a white frame round the man ours are firing at; nothing behind the camera, off screen or in the pause menu')

# ------------------------------------------------------------------ how often the brain looks
e = Emu()
e.load()
calm = e.ped(30, 0)
e.frame(ms=25, n=40)                                                 # one second at 40 frames a second, nothing going on
n_calm = len(replay_tool.replay(e.save())[2])
gang = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
e.frame(ms=25, n=40)
n_threat = len(replay_tool.replay(e.save())[2]) - n_calm
assert 9 <= n_calm <= 12 and 18 <= n_threat <= 22, (n_calm, n_threat)
e2 = Emu()
e2.load()
far = e2.ped(60, 0, pedtype=7, weapon=30, face=(1., 0.))             # armed, 60 m away, looking the other way: watched, no threat yet
ours = e2.ped(4, 2, pedtype=8, weapon=31)
e2.share(HC_STATE + 71, e2.handle(ours))
e2.frame(ms=100, n=3)
n0 = len(replay_tool.replay(e2.save())[2])
e2.gunshot(ours, (60., 0., 1.)); e2.frame(ms=45, n=1)                # one of ours fires: no hurry
n1 = len(replay_tool.replay(e2.save())[2])
e2.frame(ms=100, n=1)
n2 = len(replay_tool.replay(e2.save())[2])
e2.gunshot(far, (0., 0.5, 1.)); e2.frame(ms=45, n=1)                 # somebody else fires: the brain looks at once
t_ = replay_tool.replay(e2.save())[2]
assert n1 == n0 + 1 and len(t_) == n2 + 2 and t_[-2]['out'].n_attackers == 1, (n0, n1, n2, len(t_))
passed('The brain looks ten times a second, twenty times while there is a threat, and at once (45 ms later instead of 100) when somebody who is not ours has fired')

# ------------------------------------------------------------------ robustness
e.wf(e.cj + 0x6ac, 0.); n_before = len(e.reports()); e.frame(n=2)
assert len(e.reports()) == n_before + 1 and 'CJ died' in replay_tool.replay(e.report())[1]
assert e.reports() == ['hcbrain_report_%02d.bin' % k for k in range(1, n_before + 2)]
passed('When CJ dies a report is saved by itself; every report is a new numbered file, none is overwritten')
e = Emu()
e.load()
e.w64(GTA + PED_POOL, 0); e.frame(n=3)                                # the game has no pools yet (loading screen)
assert e.opcode(5, 9, CMD_GUNNER, handle=0x101)[1][1:3] == [0, 0] and e.opcode(5, 5, CMD_STATUS)[0] == 1
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
head, text, ticks = replay_tool.replay(e.save())
assert len(ticks) >= 30 and max(t['snapshot'].n_peds for t in ticks) == h.HCB_MAX_PEDS and max(t['snapshot'].peds_lost for t in ticks) > 50 and all(t['match'] for t in ticks if t['exact'])
passed('No pools yet, no player yet, a full pool of 139 people (64 nearest are taken), entities without a matrix or without an intelligence object, the clock jumping back after a load: no fault, the opcode answers "nothing" and the report still replays exactly')

# ------------------------------------------------------------------ a crowded street with every ray expensive
# (the freeze at Grove Street in 1.3 beta 1: a ray for every pair on every look, 20-25 looks a second - the frames grew
# longer, the brain looked in every one of them, the game all but stopped)
def crowd(ray_us):
    e = Emu(); e.load()
    pilot, g1, g2, g3, g4 = e.ped(0, 8, 25., pedtype=8), *(e.ped(x, 9, 25., pedtype=8, weapon=31) for x in (1.4, -1.4, 1.5, -1.5))
    heli = e.veh(0, 8, 25., vtype=3, driver=pilot)
    e.share(HC_STATE + 7, 3); e.share(HC_STATE + 21, e.handle(heli) & 0x7fffffff)
    for k, p in enumerate((pilot, g1, g2, g3, g4)):
        e.share(HC_STATE + 22 + k, e.handle(p))
    cops = [e.ped(math.cos(k * .4) * (15 + k), math.sin(k * .4) * (15 + k), pedtype=7, weapon=30, face=(-math.cos(k * .4), -math.sin(k * .4))) for k in range(24)]
    e.share(HC_HELLO, 0)
    e.frame(n=3)
    e.clock_step = ray_us                                            # every reading of the clock moves it on this much: a ray is measured as ray_us
    return e, cops
e, cops = crowd(300)
per_frame, answered, asked_pairs = [], set(), set()
for k in range(60):
    if k % 3 == 0:
        e.gunshot(cops[k % 24], (0., 0.5, 1.))
    n0 = len(e.los_calls); e.frame(ms=50, hud=False); per_frame.append(len(e.los_calls) - n0)
head, text, ticks = replay_tool.replay(e.save())
for t in ticks:
    o, s_ = t['out'], t['snapshot']
    asked_pairs |= {(getattr(q, 'from'), q.to) for q in o.queries[:o.n_queries]}
    answered |= {(getattr(l, 'from'), l.to) for l in s_.los[:s_.n_los]}
assert max(per_frame) <= 2500 // 300 + 2, ('a frame never spends much more than 2.5 ms on rays', max(per_frame))
assert len(asked_pairs) > 40 and len(asked_pairs - answered) <= 4, ('every question is answered in turn', len(asked_pairs), len(asked_pairs - answered))
looks = len(ticks); share_ = sum(per_frame) * 300 / (60 * 50000.)
assert 'looks put off to keep the brain under a quarter of the time' in text and share_ < 0.3 and all(t['match'] for t in ticks), (share_, looks)
cheap, _ = crowd(10)
n_cheap = []
for k in range(20):
    n0 = len(cheap.los_calls); cheap.frame(ms=50, hud=False); n_cheap.append(len(cheap.los_calls) - n0)
assert max(n_cheap) > max(per_frame) and max(n_cheap) <= 10 + 32 + 2, (n_cheap, per_frame)
passed('A crowded street (4 door gunners, 24 armed men, shots every 150 ms) with rays costing 0.3 ms each: at most %d rays a frame (2.5 ms), every one of the %d questions answered in turn, the brain under a quarter of the time (%.0f %%); with cheap rays more per frame, never more than 10 + 32 a look' % (max(per_frame), len(asked_pairs), share_ * 100))

# a man whose position is not a number (a broken entity): he is left out, no ray and no round ever gets such a point
e = Emu(); e.load()
pilot, g1 = e.ped(0, 8, 25., pedtype=8), e.ped(1.4, 9, 25., pedtype=8, weapon=31)
heli = e.veh(0, 8, 25., vtype=3, driver=pilot)
e.share(HC_STATE + 7, 3); e.share(HC_STATE + 21, e.handle(heli) & 0x7fffffff); e.share(HC_STATE + 22, e.handle(pilot)); e.share(HC_STATE + 23, e.handle(g1))
bad = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
e.share(HC_HELLO, 0); e.frame(n=3)
m = e.r64(bad + 0x18); e.wf(m + 0x30, float('nan'), 0., 1.)            # his position becomes "not a number"
t_nan = e.r32(GTA + TIME_MS)
far = e.ped(5000., 0, pedtype=7, weapon=30, face=(-1., 0.))           # and one far off the map
e.gunshot(bad, (0., 0.5, 1.))
e.los_calls.clear()
for k in range(20):
    e.frame(ms=50, hud=False); e.opcode(3, 9, CMD_GUNNER, handle=e.handle(g1))
finite = lambda v: all(c - c == 0 and abs(c) < 4000 for c in v)
assert e.los_calls is not None and all(finite(c[0]) and finite(c[1]) for c in e.los_calls), [c[:2] for c in e.los_calls if not (finite(c[0]) and finite(c[1]))][:2]
head, text, ticks = replay_tool.replay(e.save())
ids = {p.id for t in ticks if t['snapshot'].time > t_nan for p in t['snapshot'].peds[:t['snapshot'].n_peds]}
assert any(p.id == e.handle(bad) for t in ticks if t['snapshot'].time <= t_nan for p in t['snapshot'].peds[:t['snapshot'].n_peds]), '(control: before, he was in it)'
assert e.handle(bad) not in ids and e.handle(far) not in ids and all(t['match'] for t in ticks), 'neither is in the brain\'s picture'
passed('A man whose position is not a number, and one 5 km off the map: neither enters the brain\'s picture, and no ray or round is ever given such a point (the game\'s search through the map never ends on one)')

# the hang recorder: the game's frames stop, not paused - the log says where its thread is and the black box is saved
e = Emu(); e.load()
gang = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
e.share(HC_STATE + 0, 10); e.share(HC_HELLO, 0)
e.frame(n=5)
recorder = e.threads[-1]
SP_, CODE = STACK + 0x40000, GTA + 0x3f4010
e.w64(SP_ + 0x58, CODE)                                              # a return address left on its stack
e.fs['/proc/self/task/4243/stat'] = b'4243 (GLThread 1) S 1 2 3'
e.fs['/proc/self/task/4243/syscall'] = ('98 0x1 0x2 0x3 0x4 0x5 0x6 0x%x 0x%x\n' % (SP_, GTA + 0x228714)).encode()
reports0 = len(e.reports())
e.call(recorder[0], x=(recorder[1],), count=3000000)
log = e.log()
assert 'HANG: no new frame for 6 s' in log and 'asleep' in log and 'look 6' in log and '+0=10' in log, log[-900:]
assert ('pc 0x%016x' % (GTA + 0x228714)) in log and ('on the stack 0x%016x' % CODE) in log and not e.signals, log[-600:]
assert len(e.reports()) == reports0 + 1 and b'the game hung' in e.report()
# the same, but the thread is running round a loop: it is asked for its registers with a signal (and the old handler is put back)
e.fs['/proc/self/task/4243/stat'] = b'4243 (GLThread 1) R 1 2 3'
FP_ = STACK + 0x41000
e.w64(FP_, FP_ + 0x100); e.w64(FP_ + 8, GTA + 0x4d63e0); e.w64(FP_ + 0x100, 0); e.w64(FP_ + 0x108, GTA + 0x4d8e70)
UC_ = e.alloc(0x400)
e.w64(UC_ + 440, GTA + 0x3f4020); e.w64(UC_ + 424, GTA + 0x3f3e20); e.w64(UC_ + 416, FP_); e.w64(UC_ + 432, SP_)
e.deliver = None
e.call(recorder[0], x=(recorder[1],), count=200000)                 # (to learn the handler: the first sigaction)
handler = [a for a in e.sigactions if a[1] and a[1][2]][0][1][2]
e.signals.clear(); e.sigactions.clear(); e.deliver = (handler, UC_)
open_before = e.log()
e.call(recorder[0], x=(recorder[1],), count=3000000)
log = e.log()[len(open_before) - 200:]
assert len(e.signals) == 6 and all(sg == (4242, 4243, 27) for sg in e.signals), e.signals
assert ('pc 0x%016x' % (GTA + 0x3f4020)) in log and ('lr 0x%016x' % (GTA + 0x3f3e20)) in log and ('called from 0x%016x' % (GTA + 0x4d63e0)) in log and ('called from 0x%016x' % (GTA + 0x4d8e70)) in log, log[-900:]
assert e.sigactions[0][0] == 27 and e.sigactions[0][1][0] & 4 and e.sigactions[-1][1] == (0, 0, 0xdead0, 0, 0), e.sigactions
assert 'running' in log
passed('The hang recorder: no new frame for 6 s and not paused - the log tells where the game\'s thread is (asleep: from /proc; running in a loop: from its registers, taken with one signal, the game\'s own handler put back after), the calls that led there, return addresses on its stack and the place of every CLEO script; the black box is saved by itself')

# the black box: two halves that take turns (a build with small halves, the same source)
small_dir = tempfile.mkdtemp()
subprocess.check_call(['sh', str(HERE.parent / 'build.sh')], env=dict(os.environ, OUT=small_dir, BRAIN_DEFS='-DBOX_BYTES=262144'), stdout=subprocess.DEVNULL)
e = Emu(mod=small_dir + '/libHelicoverBrain64.so')
e.load()
for k in range(1, 30):
    e.ped((k % 6) * 4 - 10, (k // 6) * 4 + 6, pedtype=7 if k % 2 else 4, weapon=30 if k % 4 == 0 else 0)
sizes = []
for k in range(14):
    e.frame(n=25, ms=100)
    head, text, ticks = replay_tool.replay(e.save())
    sizes.append((len(e.report()), len(ticks), head.records))
    assert ticks and ticks[0]['exact'] and all(t['match'] for t in ticks), k
    assert ticks[-1]['snapshot'].time == e.r32(GTA + TIME_MS), 'the newest look is always in the report'
assert max(s_[0] for s_ in sizes) <= 2 * 262144 + 4096 and len({s_[1] for s_ in sizes[6:]}) > 1 and min(s_[1] for s_ in sizes[6:]) >= 0.4 * max(s_[1] for s_ in sizes), sizes
passed('Black box: two halves take turns (nothing is ever moved, so no pause); a report is the older half followed by the current one, it never loses the newest look, always starts from a stored memory of the brain and replays exactly - %d reports while the halves changed over several times, %d to %d looks in each' % (len(sizes), min(s_[1] for s_ in sizes[6:]), max(s_[1] for s_ in sizes)))

text = '\n'.join(results) + '\nThe phone build on an emulated CPU with the real libGTASA.so and the real code of the CLEO library; the world in memory is laid out by the test. Not run in the game.\n'
(h.OUT / 'brain_adapter_tests.txt').write_text(text)
print(text)
