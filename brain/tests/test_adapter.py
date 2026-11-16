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
F_WATER, F_SAY = 0x6ba834, 0x5a57c4       # CWaterLevel::GetWaterLevel, CPed::Say (0.8)
EXPLOSIONS_T, PROJ_T, COVER_T = 0xd28c78, 0xd29508, 0xc9b390   # the game's tables the mod reads (0.8)
F_TASK_NEW, F_GOTO, F_SHOOT, F_SET_TASK, F_GROUND = 0x5d7414, 0x632400, 0x633510, 0x64e084, 0x50f408   # 1.0: the body and the map
VT_GOTO, VT_SHOOT, VT_ROPE = 0x839040 + 0x10, 0x839b98 + 0x10, 0x8381f8 + 0x10
HC_MODE, HC_RECALL, CMD_PLAN = 0x48456A00 + 573, 0x48456A00 + 574, 7
F_EV_CLEAR, F_SET_SEC, F_GUN_CTOR, F_GUN_CTL, F_RELOAD, ROPES_T = 0x64e734, 0x64e5c8, 0x5dd83c, 0x5dfb64, 0x700a2c, 0xbd3e50   # 1.1
F_FIRE, F_FLASH = 0x700c64, 0x59bcb0   # CWeapon::Fire, CPed::DoGunFlash (1.4.1: the gunners' own weapon fire)
GOT_SCRIPTS, GOT_HUD, GOT_GUNSHOT = 0x845438, 0x845ec8, 0x843f10
GOT_IGNORE, IGNORE_ENTITY, F_COLLECT, F_VARPTR, SCRIPT_PARAMS = 0x84b180, 0xbdcaf8, 0x3f1fcc, 0x3f2654, 0xa001ac
HC_STATE = 0x48456A00
HC_HELLO, HC_POLICE, HC_MISSION, HELLO_MAGIC = HC_STATE + 440, HC_STATE + 441, HC_STATE + 442, 0x42520021
CLEO_IMAGE = 0x88000
I_DISPATCH, I_REGISTER, I_MAP, I_VERSION, I_SHARED = 0x37904, 0x38a58, 0x27d988, 0x1bc30, 0x7d1f8
I_G_COLLECT, I_G_VARPTR, I_G_PARAMS, I_G_BASE = 0x7d248, 0x7d240, 0x7d220, 0x7d1a0
CMD_GUNNER, CMD_SQUAD, CMD_STATUS, CMD_POST, CMD_DETAIL, CMD_PILOT = 1, 2, 3, 4, 5, 6
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
    def __init__(self, tweak=None, cleo=None, sautils=True, mod=None, cleo_ready=True, gun=False):
        self.mod_path = mod or MOD
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.imports, self.fs, self.fds, self.polys, self.items, self.prot, self.los_calls, self.threads = {}, {}, {}, [], [], [], [], []
        self.signals, self.sigactions, self.clock_step, self.deliver, self.opens = [], [], 5, None, []
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
        self.fire_calls, self.flash_calls = [], []
        self.water_level, self.water_calls, self.say_calls = None, 0, []
        self.new_tasks, self.set_tasks, self.abort_calls, self.abort_ok, self.pool_full, self.ground_calls, self.los_fn = [], [], [], True, False, 0, None
        self.ground = lambda x, y, z: (1, 0.)                                # flat ground at height 0 everywhere
        self.ev_clears, self.sec_tasks, self.gun_cmds, self.reloads, self.gun_fires, self.thread_runs = [], [], [], [], True, True
        for addr, fn in ((F_TASK_NEW, self.g_task_new), (F_GOTO, self.g_goto), (F_SHOOT, self.g_shoot), (F_SET_TASK, self.g_set_task), (F_GROUND, self.g_ground),
                         (F_EV_CLEAR, self.g_ev_clear), (F_SET_SEC, self.g_set_sec), (F_GUN_CTOR, self.g_gun_ctor), (F_GUN_CTL, self.g_gun_ctl), (F_RELOAD, self.g_reload)):
            uc.hook_add(UC_HOOK_CODE, fn, begin=GTA + addr, end=GTA + addr)
        # the virtual functions the mod calls on a task: its type (+0x28) and "can you stop now?" (+0x38)
        for vt, typ in ((VT_USE_GUN, 1017), (VT_KILL, 1000), (VT_GOTO, 903), (VT_SHOOT, 911), (VT_ROPE, 1407)):
            uc.mem_write(GTA + vt + 0x28, struct.pack('<Q', self.stub('type:%d' % typ))); uc.mem_write(GTA + vt + 0x38, struct.pack('<Q', self.stub('abort')))
        self.vt_flee = 0x834000   # (1.1: a vtable for a task of the game AI's own - a flight - laid out by the test in the game's data)
        uc.mem_write(GTA + self.vt_flee + 0x28, struct.pack('<Q', self.stub('type:911'))); uc.mem_write(GTA + self.vt_flee + 0x38, struct.pack('<Q', self.stub('abort')))
        for addr, fn in ((F_SCRIPTS, self.g_scripts), (F_HUD, self.g_hud), (F_GUNSHOT, self.g_gunshot), (F_LOS, self.g_los), (F_POLY, self.g_poly), (F_SCREEN, self.g_screen), (F_FIRE, self.g_fire), (F_FLASH, self.g_flash), (F_WATER, self.g_water), (F_SAY, self.g_say)):
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
        if not gun:      # (1.1: the tests written before the mod's own gun task run with it refused - "the code differs" - so the scripts' fire states are what they see)
            uc.mem_write(GTA + F_GUN_CTL, b'\0\0\0\0')
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
        uc.mem_write(p + 0x8dc, b'\x00'); self.w32(p + 0x730, weapon); self.w32(p + 0x738, 30); self.w32(p + 0x73c, 500)   # (a full magazine, rounds in reserve)
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
        if n.startswith('type:'): ret = int(n[5:])
        elif n == 'abort': self.abort_calls.append((x[0], x[1], x[2] & 0xffffffff)); ret = 1 if self.abort_ok else 0
        elif n == 'open':
            path = self.cstr(x[0])
            if x[1] & 3 == 0:
                ret = (1 << 64) - 1 if path not in self.fs else self._fd(path)
            else:                                            # O_TRUNC (01000) empties it; O_APPEND (02000) keeps it (writes always go to the end)
                if x[1] & 0o1000 or path not in self.fs: self.fs[path] = b''
                self.opens.append((path, x[1])); ret = self._fd(path)
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
            elif x[0] == 62:                                 # lseek(fd, 0, SEEK_END): the size
                ret = len(self.fs[self.fds[x[1]][0]]) if x[1] in self.fds and x[3] == 2 else (1 << 64) - 22
            elif x[0] == 38:                                 # renameat(AT_FDCWD, old, AT_FDCWD, new)
                o, nw = self.cstr(x[2]), self.cstr(x[4])
                if o in self.fs: self.fs[nw] = self.fs.pop(o); ret = 0
                else: ret = (1 << 64) - 2
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
    def g_fire(self, uc, *_):
        w, ped = uc.reg_read(X[0]), uc.reg_read(X[1])
        v3 = lambda r: struct.unpack('<3f', bytes(uc.mem_read(uc.reg_read(r), 12))) if uc.reg_read(r) else None
        self.fire_calls.append(dict(w=w, ped=ped, start=v3(X[2]), barrel=v3(X[3]), ent=uc.reg_read(X[4]), target=v3(X[5]), alt=uc.reg_read(X[6]),
                                    ik=self.r32(ped + 0x698), clip=self.r32(w + 8), total=self.r32(w + 0xc), state=self.r32(w + 4), acc=bytes(uc.mem_read(ped + 0x8de, 1))[0]))
        self.w32(w + 4, 1)                                             # the game's Fire leaves the weapon "firing"
        self._ret(uc, 1)
    def g_water(self, uc, *_):
        self.water_calls += 1
        if self.water_level is not None: uc.mem_write(uc.reg_read(X[0]), struct.pack('<f', self.water_level))
        self._ret(uc, 0 if self.water_level is None else 1)
    def g_say(self, uc, *_):
        self.say_calls.append((uc.reg_read(X[0]), uc.reg_read(X[1]) & 0xffff, uc.reg_read(X[2]) & 0xffffffff, round(fl(uc.reg_read(S[0])), 3)))
        self._ret(uc, 0)
    def g_flash(self, uc, *_):
        self.flash_calls.append((uc.reg_read(X[0]), uc.reg_read(X[1]) & 0xffffffff, uc.reg_read(X[2]) & 0xff)); self._ret(uc, 1)
    def g_los(self, uc, *_):
        a = struct.unpack('<3f', bytes(uc.mem_read(uc.reg_read(X[0]), 12))); b = struct.unpack('<3f', bytes(uc.mem_read(uc.reg_read(X[1]), 12)))
        flags = [uc.reg_read(r) & 0xff for r in X[2:8]] + [bytes(uc.mem_read(uc.reg_read(UC_ARM64_REG_SP), 1))[0]]
        self.los_calls.append((a, b, flags, self.r64(GTA + IGNORE_ENTITY)))
        self._ret(uc, (0 if self.walls else 1) if self.los_fn is None else int(bool(self.los_fn(a, b))))

    def g_task_new(self, uc, *_):
        n = uc.reg_read(X[0]); a = 0 if self.pool_full else self.alloc(n)
        if a: uc.mem_write(a, bytes(n))
        self._ret(uc, a)
    def g_goto(self, uc, *_):
        t, ms, tp = uc.reg_read(X[0]), uc.reg_read(X[1]) & 0xffffffff, uc.reg_read(X[2])
        tg = struct.unpack('<3f', bytes(uc.mem_read(tp, 12))); rad, slow = fl(uc.reg_read(S[0])), fl(uc.reg_read(S[1]))
        self.w64(t, GTA + VT_GOTO); self.w32(t + 0x18, ms); self.wf(t + 0x1c, *tg); self.wf(t + 0x28, rad, slow)
        self.new_tasks.append(dict(kind='goto', task=t, ms=ms, target=tg, radius=round(rad, 2), slow=round(slow, 2), flags=(uc.reg_read(X[3]) & 0xff, uc.reg_read(X[4]) & 0xff)))
        self._ret(uc, t)
    def g_shoot(self, uc, *_):
        t, ms, tp, ent = uc.reg_read(X[0]), uc.reg_read(X[1]) & 0xffffffff, uc.reg_read(X[2]), uc.reg_read(X[3])
        tg = struct.unpack('<3f', bytes(uc.mem_read(tp, 12)))
        self.w64(t, GTA + VT_SHOOT); self.w32(t + 0x18, ms); self.w64(t + 0x20, ent); self.wf(t + 0x34, *tg)
        self.new_tasks.append(dict(kind='shoot', task=t, ms=ms, target=tg, ent=ent, radius=round(fl(uc.reg_read(S[3])), 2), slow=round(fl(uc.reg_read(S[4])), 2)))
        self._ret(uc, t)
    def g_set_task(self, uc, *_):
        mgr, t, slot = uc.reg_read(X[0]), uc.reg_read(X[1]), uc.reg_read(X[2]) & 0xffffffff
        self.w64(mgr + 8 * slot, t); self.set_tasks.append((mgr, t, slot)); self._ret(uc)
    # 1.1: the event slot, the secondary slots, the gun task, a magazine
    def g_ev_clear(self, uc, *_):
        mgr = uc.reg_read(X[0]); slot = 1 if self.r64(mgr + 8) else 2
        self.ev_clears.append((mgr, self.r64(mgr + 8 * slot))); self.w64(mgr + 8 * slot, 0); self._ret(uc)
    def g_set_sec(self, uc, *_):
        mgr, t, slot = uc.reg_read(X[0]), uc.reg_read(X[1]), uc.reg_read(X[2]) & 0xffffffff
        self.w64(mgr + 0x28 + 8 * slot, t); self.sec_tasks.append((mgr, t, slot)); self._ret(uc)
    def g_gun_ctor(self, uc, *_):
        t, ent, cmd, burst = uc.reg_read(X[0]), uc.reg_read(X[1]), uc.reg_read(X[2]) & 0xff, uc.reg_read(X[3]) & 0xffff
        self.w64(t, GTA + VT_USE_GUN); self.w64(t + 0x28, ent); uc.mem_write(t + 0x17, bytes([cmd]))
        self.new_tasks.append(dict(kind='gun', task=t, ent=ent, cmd=cmd, burst=burst)); self._ret(uc, t)
    def g_gun_ctl(self, uc, *_):
        t, ped, ent, cmd = uc.reg_read(X[0]), uc.reg_read(X[1]), uc.reg_read(X[2]), uc.reg_read(X[3]) & 0xff
        self.w64(t + 0x28, ent); uc.mem_write(t + 0x17, bytes([cmd])); self.gun_cmds.append((t, ped, ent, cmd))
        if cmd == 3 and self.gun_fires:                               # the game fires: a round leaves his magazine
            w = ped + 0x730 + struct.unpack('<b', bytes(uc.mem_read(ped + 0x8dc, 1)))[0] * 0x20
            self.w32(w + 8, max(0, self.r32(w + 8) - 1))
        self._ret(uc, 1)
    def g_reload(self, uc, *_):
        w, ped = uc.reg_read(X[0]), uc.reg_read(X[1]); self.reloads.append((w, ped)); self.w32(w + 8, 30); self._ret(uc)
    def g_ground(self, uc, *_):
        x, y, z = (fl(uc.reg_read(r)) for r in S[:3]); f, g = self.ground(x, y, z)
        self.ground_calls += 1
        if uc.reg_read(X[0]): uc.mem_write(uc.reg_read(X[0]), bytes([1 if f else 0]))
        uc.reg_write(UC_ARM64_REG_S0, struct.unpack('<I', struct.pack('<f', g if f else 0.))[0])
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

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
            if self.thread_runs and self.syms.get('hcb_path_work'):       # (1.1: the mod's own thread - the ways, the map file - has its turn between two frames)
                self.call(MODB + self.syms['hcb_path_work'])

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
assert [i['name'] for i in e.items] == ['Brain markers', 'Brain report'] and e.items[0]['init'] == 0 and len(e.threads) == 2 and 'hang recorder on' in log and 'way-finding thread on' in log, (e.threads, log)   # (1.1: + the way-finding thread)
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
assert len(e.threads) == 3 and not ch, [hex(c) for c in ch]     # waiting for CLEO, the way-finding thread and the hang recorder
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
assert los_to_cj and all(c[2] in ([1, 1, 0, 1, 0, 0, 0], [1, 0, 0, 1, 0, 0, 0]) for c in e.los_calls) and all(c[2][1] == 1 for c in los_to_cj), e.los_calls[:3]   # (1.1: the map's own rays leave cars out)
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
e.share(HC_STATE + 27, 2)                                            # (2 = moving to the doors: the brain fires no round by itself, so the rounds asked for by opcode below are all there are)
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


# 1.4.1: the gunners fire their own weapons through the game's weapon code - the brain checks the round, then calls
# CWeapon::Fire with the gunner's current weapon, aimed (IK bit) at the checked point, and the gun flash, as the game's task does
assert 'the gunners fire their own weapons through the game' in e.log(), e.log()
# (PHASE as the scripts really set it: 0 and 3 = the crew in its doors - they fire; 2 = moving to the doors - the Fire script rests
#  them and the brain fires nothing. 0.4.1 fired only in phase 2, which never coincides with a fight: 0 rounds in a whole game.)
e.fire_calls.clear(); e.flash_calls.clear()
for k in range(16):
    e.frame(ms=50, hud=False)
    e.gunshot(gang, (0., 0.5, 1.)) if k % 8 == 0 else None
assert not e.fire_calls, 'moving to the doors: no rounds'
n_by_phase = {}
for ph in (0, 3):
    e.share(HC_STATE + 27, ph); e.fire_calls.clear()
    for k in range(24):
        e.frame(ms=50, hud=False)
        e.gunshot(gang, (0., 0.5, 1.)) if k % 8 == 0 else None
    n_by_phase[ph] = len(e.fire_calls)
assert n_by_phase[0] and n_by_phase[3], n_by_phase
e.fire_calls.clear(); e.flash_calls.clear()
e.w32(g1 + 0x730 + 8, 0); e.w32(g1 + 0x730 + 0xc, 5); e.w32(g1 + 0x730 + 4, 2)   # an empty clip, reloading
for k in range(40):
    e.frame(ms=50, hud=False)
    e.gunshot(gang, (0., 0.5, 1.)) if k % 8 == 0 else None
fc = [c for c in e.fire_calls if c['ped'] == g1]
assert fc and not [c for c in e.fire_calls if c['ped'] == g2], 'the right-door gunner fires; the left one does not fire across the cabin'
for c in fc:
    assert c['w'] == g1 + 0x730 and c['ent'] == 0 and c['alt'] == 0 and c['start'] == c['barrel'] and c['ik'] & 1 and c['clip'] >= 2 and c['total'] >= 25000 and c['state'] <= 1 and c['acc'] == 100, c
    assert math.dist(c['start'], (1.4, 9., 25.5)) < 1.0 and math.dist(c['target'][:2], (20., 0.)) < 1.0, (c['start'], c['target'])
assert e.r32(g1 + 0x698) & 1 == 0, 'the IK bit is put back after the shot'
assert [f for f in e.flash_calls if f[0] == g1] and all(f[1:] == (250, 0) for f in e.flash_calls), e.flash_calls
assert e.opcode(3, 3, CMD_SQUAD, handle=H_(g1))[1][1] in (0, 1, 3, 4) and e.opcode(3, 3, CMD_SQUAD, handle=H_(g1))[1][1] != 2, 'the gunner\'s script only aims (4): the brain fires'
e.share(HC_STATE + 27, 2)
passed('1.4.1 gunners fire their own weapons: %d rounds through CWeapon::Fire - the current weapon of the gunner, from 0.8 m in front of him to the checked point (IK bit set for the shot and put back, clip and ammo topped up, no reload stall, no extra spread), the gun flash as the game\'s own task does; the script only keeps his weapon on the man' % len(fc))


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
# 1.4: the protective detail through the same opcode - a post for each guard on foot (10 variables), the commander's words (9)
n_rays = len(e.los_calls); e.frame(ms=50, n=4, hud=False)
handled, v, used = e.opcode(10, 10, CMD_POST, handle=H_(s1))
assert handled == 1 and used == 7 and v[0] == H_(s1) and v[1] in (0, 1, 2, 3), v
spot = [f32(x) for x in v[2:5]]; look = [f32(x) for x in v[6:9]]
assert all(abs(x) < 4000 for x in spot + look) and math.dist(spot[:2], (0., 0.)) < 20 and v[5] in (0, 1) and v[9] >= h.HCB_DUTY_WATCH, (spot, look, v)
assert e.opcode(10, 10, CMD_POST, handle=H_(gang))[1][1] == -1 and e.opcode(10, 10, CMD_POST, handle=0x7fffff01)[1][1] == -1, 'no post for a stranger or a handle that names nobody'
handled, v, used = e.opcode(20, 9, CMD_DETAIL)
assert handled == 1 and used == 7 and v[3] >= h.HCB_DUTY_WATCH and v[4] in (0, 1) and v[8] == H_(s1), ('the only guard on foot commands', v)
probes = [c for c in e.los_calls if abs(c[0][0] - c[1][0]) < 1e-4 and abs(c[0][1] - c[1][1]) < 1e-4 and abs((c[0][2] - c[1][2]) - 2.4) < .01]
assert probes, 'cover questions are answered with a ray straight down (is there ground under the spot)'
passed('1.4 protective detail through 0E48: a post for a guard on foot (move, spot, crouch, where to look, duty; none for strangers), the commander\'s words, his duty and who commands; the cover questions are answered with the game\'s own rays (hidden from the threat, ground under the spot)')

# 1.4: the pilot (command 6, 6 variables): the script gives the point and the roofs, the brain gives where to be now; the
# turn (pitch, bank, heading) is written into the helicopter's matrix after the scripts have run
hh = e.handle(heli) & 0x7fffffff
mat = e.r64(heli + 0x18)
def pilot_ask(tx, ty, ground=0., flags=1, handle=hh):
    e.uc.mem_write(e.script + 0x6c + 4 * 27, struct.pack('<3fi', tx, ty, ground, flags))
    return e.opcode(26, 6, CMD_PILOT, handle=handle)
def rows():
    return [struct.unpack('<3f', bytes(e.uc.mem_read(mat + o, 12))) for o in (0, 0x10, 0x20)]
assert pilot_ask(400., 8., handle=H_(police_heli) & 0x7fffffff)[1][5] == -1, 'only Helicover\'s own helicopter is flown'
assert pilot_ask(float('nan'), 8.)[1][5] == -1 and pilot_ask(9000., 8.)[1][5] == -1, 'never towards a point that is not on the map'
speeds, fz = [], []
for k in range(40):
    handled, v, used = pilot_ask(400., 8.)
    assert handled == 1 and used == 7 and v[5] != -1, v
    x, y, z, left, sp = (f32(q) for q in v[1:6])
    speeds.append(sp)
    e.wf(mat + 0x30, x, y, z)                                          # what SET_CAR_COORDINATES does
    e.frame(ms=50, hud=False)
    r_, f_, u_ = rows(); fz.append(f_[2])
    assert all(abs(math.hypot(*q) - 1) < 1e-3 for q in (r_, f_, u_)) and abs(sum(a * b for a, b in zip(r_, f_))) < 1e-3, (r_, f_, u_)
assert all(b - a < .5 for a, b in zip(speeds, speeds[1:])) and speeds[-1] > 5 and min(fz) < -.2 and f_[0] > .5, (speeds[-5:], min(fz), f_)
assert abs(left - math.hypot(400 - x, 8 - y)) < .5 and 0 < x < 100 and 25 < z < 36, (x, y, z, left)   # (it climbs to 35 m over the roofs for a 400 m trip)
passed('1.4 pilot through 0E48 (6 variables): only for Helicover\'s helicopter and a point on the map; it turns towards the point and speeds up smoothly with the nose down; its turn goes into the helicopter\'s matrix after the scripts (rows of length 1, square to each other)')

# 0.6: flag 4 - on station in a fight. The same pilot, but: short hops (28 m/s at most), down to the spot's height (never under
# 12 m over the roofs below), and on station the fuselage turns to lie along the line from CJ to the spot (side-on to the threat)
cjx, cjy = struct.unpack('<2f', bytes(e.uc.mem_read(e.r64(e.cj + 0x18) + 0x30, 8)))
sx, sy = x + 30., y + 10.
for k in range(260):
    handled, v, used = pilot_ask(sx, sy, flags=1 | 4)
    assert handled == 1 and v[5] != -1, v
    x, y, z, left, sp = (f32(q) for q in v[1:6])
    assert sp < 29.5, sp
    e.wf(mat + 0x30, x, y, z)
    e.frame(ms=50, hud=False)
r_, f_, u_ = rows()
line = (sx - cjx, sy - cjy); L_ = math.hypot(*line)
assert left < 2.0 and 11.5 < z < 41., (left, z)
assert abs(f_[0] * line[0] + f_[1] * line[1]) / L_ > 0.9, ('on station the fuselage lies along the line CJ - spot', f_, line)
passed('0.6 the brain\'s own pilot in a fight (flag 4 of the pilot command): a short hop at no more than 28 m/s to the spot, at the spot\'s height (%.0f m here; never under 12 m over the roofs), and there it turns side-on to the threat - the fuselage along the line from CJ to the spot' % z)

until_round()
e.w32(gang + 0x54c, 55)                                              # he is dead
e.frame(ms=50, n=2, hud=False)
v = e.opcode(20, 5, CMD_STATUS)[1]
assert v[3] == 1 and v[4] != H_(gang) and e.opcode(3, 9, CMD_GUNNER, handle=H_(g1))[1][1:3] == [0, 0] and e.opcode(10, 3, CMD_SQUAD, handle=H_(s1))[1][1:3] == [0, 0], v
passed('A guard on foot asks with 3 variables: cover, fire, and "cease fire" in the very frame CJ walks into his line; "hold fire" in the menu stops everybody; the status request gives alert level, threats, attackers, kills, the most dangerous man, the direction of CJ\'s own last shot (the squad keeps out of his line of fire) and how long ago a stranger fired at the helicopter (the pilot breaks away); a dead man is nobody\'s target and is counted')

# what a script must not be able to do through the opcode
sentinel = [0x51515151] * 32
e.uc.mem_write(e.script + 0x6c, struct.pack('<32i', *sentinel))
for cmd, first, count in ((CMD_GUNNER, 28, 9), (CMD_GUNNER, 5, 40), (CMD_GUNNER, 5, 0), (CMD_GUNNER, 5, -3), (CMD_POST, 25, 10), (CMD_DETAIL, 26, 9), (CMD_POST, 5, 9), (CMD_DETAIL, 5, 8)):
    handled, v, used = e.opcode(first, count, cmd)
    assert handled == 1 and used == 7 and e.locals() == sentinel, (cmd, first, count)
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
assert max(per_frame) <= (2500 + 1200) // 300 + 3, ('a frame never spends much more than 2.5 ms on rays of sight and 1.2 ms on the map (1.0)', max(per_frame))
assert len(asked_pairs) > 40 and len(asked_pairs - answered) <= 4, ('every question is answered in turn', len(asked_pairs), len(asked_pairs - answered))
looks = len(ticks); share_ = sum(per_frame) * 300 / (60 * 50000.)
assert 'looks put off to keep the brain under a quarter of the time' in text and share_ < 0.3 and all(t['match'] for t in ticks), (share_, looks)
cheap, _ = crowd(10)
n_cheap = []
for k in range(20):
    n0 = len(cheap.los_calls); cheap.frame(ms=50, hud=False); n_cheap.append(len(cheap.los_calls) - n0)
assert max(n_cheap) > max(per_frame) and max(n_cheap) <= 10 + 32 + 4, (n_cheap, per_frame)   # (+ one ray for each of the four gunners' own rounds)
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
assert 'no new frame for 1 s: the game went to the background' in log and 'HANG: no new frame for 6 s' in log and 'asleep' in log and 'look 6' in log and '+0=10' in log, log[-900:]
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

# 1.4.1: the crash recorder - a crash of the game is written down before the game's own handler gets it
e = Emu(); e.load()
acts = {a[0]: a[1] for a in e.sigactions if a[1]}
assert all(sg in acts and acts[sg][0] & 4 and acts[sg][2] == acts[11][2] for sg in (11, 7, 4, 8, 6)), acts
e.frame(n=3)
info, ucx = e.alloc(128), e.alloc(1024)
e.w64(info + 16, 0xdeadbeef)                                         # the fault address
e.w64(ucx + 440, GTA + F_LOS + 8); e.w64(ucx + 424, GTA + F_SCRIPTS); e.w64(ucx + 432, ucx + 600); e.w64(ucx + 416, 0)
e.sigactions.clear()
e.call(acts[11][2], x=(11, info, ucx), count=3000000)
lg_ = e.log()
cfg = [v for k, v in e.fs.items() if k.endswith('net.helicover.brain.ini')]
assert 'CRASH: signal 11 (bad memory access)' in lg_ and '0x00000000deadbeef' in lg_ and 'pc 0x%016x' % (GTA + F_LOS + 8) in lg_ and 'lr 0x%016x' % (GTA + F_SCRIPTS) in lg_, lg_[-800:]   # (names come from dladdr in the game)
assert lg_.rstrip().endswith('(the game ends here: its own crash handler takes over)') and 'brain: 3 of 3' in lg_, 'the block is in the file at once, after everything before it'
assert not [k for k in e.fs if k.endswith('hcbrain_crash.txt')] and cfg and b'LastCrash = 99' in cfg[-1], cfg
assert [a for a in e.sigactions if a[0] == 11], 'and the previous handler is put back (it gets the crash next)'
assert any(k.startswith('hcbrain_report_') or 'hcbrain_report_' in k for k in e.fs), 'a report is saved too'
# the next start of the game adds to the same file: the crash stays above, and the new game says where the last one crashed
e2 = Emu(); e2.fs.update({k: v for k, v in e.fs.items() if k.endswith(('hcbrain_log.txt', 'net.helicover.brain.ini'))})
lg2 = e2.load()
assert lg2.startswith(lg_) and lg2.count('a new game: Helicover Brain') == 2 and 'the last game crashed outside the brain (its CRASH block is above' in lg2[len(lg_):], lg2[len(lg_):][:600]
passed('Crash recorder: on a crash (bad memory, bus error, illegal instruction, arithmetic, abort) the log gets where it happened (pc and lr with the names in libGTASA, the fault address), what the brain was doing, Helicover\'s state and where each CLEO script stands - written into the one log file at once, after everything before it; a report is saved, the game\'s own handler is put back to take the crash, and the next start of the game adds to the same file below the crash')

# 0.4.1: one log for the whole game - added to as it goes, every second the full picture
e = Emu(); lg0 = e.load()
assert lg0.count('a new game: Helicover Brain') == 1 and 'libraries in the game:' in lg0 and 'settings: markers 0' in lg0, lg0
gang = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
pilot, g1, s1, s2 = e.ped(0, 8, 25., pedtype=8), e.ped(1.4, 9, 25., pedtype=8, weapon=31), e.ped(4, 2, pedtype=8, weapon=31), e.ped(4, -2, pedtype=8, weapon=31)
heli = e.veh(0, 8, 25., vtype=3, driver=pilot)
e.share(HC_STATE + 7, 3); e.share(HC_STATE + 21, e.handle(heli) & 0x7fffffff); e.share(HC_STATE + 22, e.handle(pilot)); e.share(HC_STATE + 23, e.handle(g1))
e.share(HC_STATE + 71, e.handle(s1)); e.share(HC_STATE + 72, e.handle(s2)); e.share(HC_HELLO, 0)
e.frame(n=3)
e.gunshot(gang, (0., 0.5, 1.))
for k in range(45):
    e.frame(ms=100, hud=False)
    e.opcode(10, 10, CMD_POST, handle=e.handle(s1)); e.opcode(3, 9, CMD_GUNNER, handle=e.handle(g1))
    if k == 20: e.share(HC_STATE + 27, 3)
lg1 = e.log()
if os.environ.get('HCB_LOG_SAMPLE'): Path(os.environ['HCB_LOG_SAMPLE']).write_text(lg1)     # (to read what the log looks like)
H_ = e.handle
secs = re.findall(r'^\[(\d+)\.\ds\] \[up [\d.]+s\] CJ \(', lg1, re.M)
assert len(secs) >= 3 and all(int(b_) - int(a_) == 1 for a_, b_ in zip(secs, secs[1:])), secs
assert re.search(r'brain: alert (COMBAT|threat|EVACUATE)', lg1) and 'contact #%d ' % H_(gang) in lg1 and re.search(r'contact #%d (THREAT|ATTACKER) ' % H_(gang), lg1), lg1[-3000:]
assert re.search(r'^  guard1#%d hp 100\.0/0\.0 \(4\.0 2\.0 1\.0\) w 31 .*\| post \w+ \w+ \(.*\| order ' % H_(s1), lg1, re.M), lg1[-3000:]
assert re.search(r'^  gunner1#%d .*\| order ' % H_(g1), lg1, re.M) and re.search(r'^  pilot#%d ' % H_(pilot), lg1, re.M)
assert re.search(r'0E48: gunner [1-9]\d* squad 0 status 0 post [1-9]', lg1) and re.search(r'shots: ours 0 others [1-9]', lg1)
assert 'Helicover (all): ' in lg1 and ' +7=3' in lg1 and re.search(r'Helicover changed:.* \+27=3', lg1), [l_ for l_ in lg1.splitlines() if 'Helicover' in l_]
assert 'detail: ' in lg1 and 'helicopter our-heli' in lg1 and 'time: looks ' in lg1
opens = [o for o in e.opens if o[0].endswith('hcbrain_log.txt')]
assert opens and all(f & 0o2000 and not f & 0o1000 for _, f in opens), 'the log file is only ever added to'
# the writer thread (the hang recorder's) adds the new text twice a second; the pause menu and stopped frames are noted
before = len(e.log()); e.frame(ms=100, n=3, hud=False)
assert len(e.log()) == before, '(the game thread writes only when the writer thread has been silent for 3 s)'
e.uc.mem_write(GTA + USER_PAUSE, b'\1')
rec = e.threads[-1]; e.call(rec[0], x=(rec[1],), count=300000)
lg3 = e.log()
assert len(lg3) > before and 'the game is paused (menu)' in lg3[before:] and 'HANG' not in lg3, lg3[before:][-500:]
e.uc.mem_write(GTA + USER_PAUSE, b'\0')
# the file grew over 24 MB: the next start renames it hcbrain_log_old.txt and begins a new one
e3 = Emu(); big = b'x' * (25 << 20); e3.fs[MODS + 'hcbrain_log.txt'] = big
lg4 = e3.load()
assert e3.fs.get(MODS + 'hcbrain_log_old.txt') == big and lg4.startswith('\n\n========== a new game') and len(lg4) < 20000
passed('One log for the whole game (0.4.1): every start of the game adds to the same hcbrain_log.txt (never rewritten; over 24 MB it becomes hcbrain_log_old.txt); every second CJ, the brain\'s alert, the detail\'s duty, mode and commander, the helicopter\'s spot, each of ours (where, health, weapon, post and how far, order and why he holds), each contact (class, why, distance, where, weapon), the pilot, Helicover\'s shared values that changed, the 0E48 calls and the timing - %d seconds of a fight written; the writer thread adds the text twice a second and notes the pause menu' % len(secs))

# 0.7: the places of earlier fights are kept in a file between games
PLACES = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/configs/net.helicover.brain.places'
e = Emu(); lg_ = e.load()
assert 'places of earlier attacks: none remembered yet' in lg_
gang = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
s1 = e.ped(4, 2, pedtype=8, weapon=31)
e.share(HC_STATE + 71, e.handle(s1)); e.share(HC_HELLO, 0)
e.frame(n=3); e.gunshot(gang, (0., 0.5, 1.)); e.frame(ms=100, n=10, hud=False)
assert PLACES in e.fs and struct.unpack('<I', e.fs[PLACES][:4])[0] == 1 and len(e.fs[PLACES]) == 20, len(e.fs.get(PLACES, b''))
px, py, pz, pn = struct.unpack('<3fI', e.fs[PLACES][4:20])
assert abs(px) < 1 and abs(py) < 1 and pn == 1, (px, py, pn)
e2 = Emu(); e2.fs[PLACES] = e.fs[PLACES] + b''; lg2 = e2.load()
assert 'places of earlier attacks remembered: 1' in lg2
e3 = Emu(); e3.fs[PLACES] = struct.pack('<I', 2) + struct.pack('<3fI', float('nan'), 0., 0., 3) + struct.pack('<3fI', 100., 50., 10., 4); lg3 = e3.load()
assert 'places of earlier attacks remembered: 1' in lg3, 'an entry that is not a number is left out'
e4 = Emu(); e4.fs[PLACES] = struct.pack('<I', 999999) + b'x' * 40; lg4 = e4.load()
assert 'the brain is running' in lg4 and 'remembered: 0' in lg4, 'a damaged file is ignored'
passed('0.7 memory of places: a fight writes its place to configs/net.helicover.brain.places; the next game loads it; a damaged file or an entry that is not a number is left out')

# 0.8: what the mod reads from the game besides - water, grenades, explosions, the game's cover points - and the commander's voice
e = Emu(); lg_ = e.load()
assert "the game's own knowledge: grenades, explosions and cover points read; water level asked; the commander's voice on" in lg_, lg_[-600:]
gang = e.ped(20, 0, pedtype=7, weapon=30, face=(-1., 0.))
s1 = e.ped(4, 2, pedtype=8, weapon=31)
e.share(HC_STATE + 71, e.handle(s1)); e.share(HC_HELLO, 0)
e.frame(n=2)
assert e.water_calls >= 1
e.water_level = 1.5                                                   # the water stands above CJ's middle: he swims
e.uc.mem_write(GTA + PROJ_T + 3 * 0x38, struct.pack('<I', 16) + b'\0' * 0x18 + b'\1\0\0\0' + struct.pack('<3f', 6., 2., 1.))     # a live grenade 6 m off
e.uc.mem_write(GTA + PROJ_T + 5 * 0x38, struct.pack('<I', 16) + b'\0' * 0x18 + b'\1\0\0\0' + struct.pack('<3f', 900., 2., 1.))   # one far away: left out
e.uc.mem_write(GTA + EXPLOSIONS_T + 2 * 0x88, struct.pack('<I3ff', 0, -8., 3., 1., 9.)); e.uc.mem_write(GTA + EXPLOSIONS_T + 2 * 0x88 + 0x30, b'\1')
e.uc.mem_write(GTA + COVER_T + 7 * 0x28, struct.pack('<bbbb3f', 2, 0, 0, 0, -5., 4., 1.) + struct.pack('<Q', 0))                    # a cover point of the game's 6 m off
e.uc.mem_write(GTA + COVER_T + 8 * 0x28, struct.pack('<bbbb3f', 1, 0, 0, 0, 0., 0., 0.) + struct.pack('<Q', 0xdead0000))            # one on a thing that is gone: left out
e.frame(n=6); e.gunshot(gang, (0., 0.5, 1.)); e.frame(ms=100, n=12, hud=False)
head, text, ticks = replay_tool.replay(e.save())
sn = ticks[-1]['snapshot']
assert sn.in_water == 1 and sn.n_hints == 1 and abs(sn.hints[0].x + 5.) < .01 and all(t['match'] for t in ticks), (sn.in_water, sn.n_hints)
dg = {(d.kind, round(d.at.x), round(d.radius)) for d in sn.dangers[:sn.n_dangers]}
assert dg == {(h.HCB_DG_GRENADE, 6, 10), (h.HCB_DG_BLAST, -8, 9)}, dg
e.frame(ms=100, n=35, hud=False)                                      # (the log is written out)
lg_ = e.log()
assert 'IN-WATER' in lg_ and 'danger: GRENADE at (6.0 2.0 1.0)' in lg_ and 'game cover points 1' in lg_ and '(table: live ' in lg_ and ') water asked ' in lg_ and ' in water ' in lg_, [l_ for l_ in lg_.splitlines() if 'danger' in l_][:3]
assert e.say_calls and all(c_[0] == s1 and c_[3] == 1.0 and 0 < c_[1] < 361 for c_ in e.say_calls), e.say_calls   # the commander (the only guard here) speaks
passed('0.8 the game\'s own knowledge: CJ swimming (the game\'s water level asked every look), live grenades and fresh explosions near CJ, the game\'s cover points (one on a thing that is gone is left out, never read) - all in the brain\'s picture, in the log and in the report, which replays exactly; the commander\'s words are also spoken with the game\'s own voice lines (CPed::Say) - %d lines here' % len(e.say_calls))
# the words differ / it crashed there once: that part is left out and said so
e = Emu(tweak=lambda e_: e_.uc.mem_write(GTA + F_SAY, b'\0\0\0\0')); lg_ = e.load()
assert "the commander's voice off (the code differs)" in lg_ and 'the brain is running' in lg_
CFG_ = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/configs/net.helicover.brain.ini'
e = Emu(); e.fs[CFG_] = b'[Preferences]\nMarkers = 0\nLastCrash = 22\nWaterOff = 1\n'; lg_ = e.load(); e.frame(n=3)
assert 'water level off (the game crashed in it once)' in lg_ and e.water_calls == 0
passed('0.8 safety: each of those parts is checked against the game\'s code at the start and left out when it differs; a part the game once crashed in (water level, voice) stays off from the next start on')

# ------------------------------------------------------------------ 1.0: the body (the mod walks the guards) and the map
def detail_world(tweak=None, cfg=None, n=1):
    e = Emu(tweak=tweak)
    if cfg: e.fs[CFG_] = cfg
    lg_ = e.load()
    guards = [e.ped(9 + 2 * k, 6, pedtype=8, weapon=31) for k in range(n)]
    for k, g in enumerate(guards): e.share(HC_STATE + 71 + k, e.handle(g))
    e.share(HC_HELLO, 0); e.share(HC_MODE, 0); e.share(HC_RECALL, 0)
    e.frame(n=6, hud=False)
    return e, guards, lg_
def post(e, g): return e.opcode(0, 10, CMD_POST, handle=e.handle(g))[1]
e, (g1,), lg_ = detail_world()
assert 'the body: the mod walks the guards itself (the game\'s go-to task, given once); the map: on' in lg_, lg_[-400:]
v = post(e, g1)
assert v[1] == 5 and len(e.new_tasks) == 1 and e.new_tasks[0]['kind'] == 'goto', (v, e.new_tasks)
t0 = e.new_tasks[0]; mgr = e.r64(g1 + 0x538) + 8
assert e.set_tasks == [(mgr, t0['task'], 3)] and e.r64(mgr + 24) == t0['task'], e.set_tasks          # the game's own SetTask, his main slot
assert t0['ms'] in (4, 6) and t0['radius'] == 0.5 and t0['flags'] == (0, 0) and math.dist(t0['target'][:2], (9., 6.)) > 2, t0   # a walk or a run towards CJ, never a sprint in peace
assert math.dist(t0['target'][:2], (0., 0.)) < 6, t0
for k in range(5):                                                   # ten times a second the script asks again: the task is NOT made anew
    e.frame(ms=100, hud=False); v = post(e, g1)
assert v[1] == 5 and len(e.new_tasks) == 1 and len(e.set_tasks) == 1, (v, len(e.new_tasks))
e.move(e.cj, -6, -3); e.frame(ms=100, n=3, hud=False); v = post(e, g1)                                # CJ walks off: only the target of the same task moves
tg = struct.unpack('<3f', bytes(e.uc.mem_read(t0['task'] + 0x1c, 12)))
assert len(e.new_tasks) == 1 and math.dist(tg[:2], t0['target'][:2]) > 3 and bytes(e.uc.mem_read(t0['task'] + 0x30, 1))[0] & 4, (tg, t0['target'])
e.move(g1, fl(v[2]), fl(v[3])); e.frame(ms=100, n=12, hud=False); v = post(e, g1)                         # he is there: the script has him again (0 = stay, crouch / look / fire are its)
assert v[1] == 0 and len(e.new_tasks) == 1, v
passed('1.0 the body: a guard on his way gets the game\'s own task ONCE (CTask::operator new, CTaskComplexGoToPointAndStandStill, CTaskManager::SetTask into his main slot) and the script is told 5 = "his legs are the mod\'s"; asked again ten times a second no new task is made; when CJ moves only the target of the same task is moved (its new-target flag set); arrived, the script has him again')
# another task of the game's in his main slot: asked to stop first, as the game does it; refused - nothing is replaced
e, (g1,), _ = detail_world()
other = e.alloc(0x60); e.w64(other, GTA + VT_USE_GUN); e.w64(e.r64(g1 + 0x538) + 8 + 24, other)
e.abort_ok = False; v = post(e, g1)
assert v[1] == 5 and not e.new_tasks and e.abort_calls and e.abort_calls[-1][:2] == (other, g1) and e.abort_calls[-1][2] == 1, (v, e.abort_calls)
e.abort_ok = True; e.frame(ms=100, hud=False); v = post(e, g1)
assert v[1] == 5 and len(e.new_tasks) == 1, v
# the game's task pool is full: the script walks him this time (the old way)
e, (g1,), _ = detail_world(); e.pool_full = True; v = post(e, g1)
assert v[1] in (1, 2, 3, 4) and not e.set_tasks, v
# a man coming down the rope, in the air, dead or in a car is never given a task
e, (g1,), _ = detail_world(); rope = e.alloc(0x40); e.w64(rope, GTA + VT_ROPE); e.w64(e.r64(g1 + 0x538) + 8 + 24, rope)
e.frame(ms=100, n=3, hud=False); v = post(e, g1)
assert not e.new_tasks and not e.abort_calls, (v, e.new_tasks)
head, text, ticks = replay_tool.replay(e.save())
sn = ticks[-1]['snapshot']
assert sn.body == 1 and sn.our_state[0] == (h.HCB_OS_ROPING | h.HCB_OS_NATIVE) and all(t['match'] for t in ticks), (sn.body, sn.our_state[0])
passed('1.0 the body, care: a task of the game\'s in his main slot is asked to stop first (MakeAbortable, urgent) and nothing is replaced while it refuses; no room in the game\'s task pool - the script walks him as before; a man on the rope or in the air is left alone and the core is told (no post until he stands)')
# the code differs / it crashed there once: the scripts walk the guards as before 1.0
e, (g1,), lg_ = detail_world(tweak=lambda e_: e_.uc.mem_write(GTA + F_SET_TASK, b'\0\0\0\0'))
v = post(e, g1)
assert 'the body: off (the code differs): the scripts walk the guards' in lg_ and v[1] in (1, 2, 3, 4) and not e.new_tasks and 'the brain is running' in lg_, (v, lg_[-300:])
head, text, ticks = replay_tool.replay(e.save())
assert ticks[-1]['snapshot'].body == 0 and all(t['match'] for t in ticks)
e, (g1,), lg_ = detail_world(cfg=b'[Preferences]\nMarkers = 0\nLastCrash = 23\n')
v = post(e, g1)
assert 'from now on the scripts walk the guards' in lg_ and not e.new_tasks and b'BodyOff = 1' in e.fs[CFG_] and v[1] != 5, (v, e.fs[CFG_])
e, (g1,), lg_ = detail_world(cfg=b'[Preferences]\nMarkers = 0\nBodyOff = 1\n')
assert 'the body: off (the game crashed in it once)' in lg_ and post(e, g1)[1] != 5 and b'BodyOff = 1' in e.fs[CFG_]
e, (g1,), lg_ = detail_world(cfg=b'[Preferences]\nMarkers = 0\nLastCrash = 24\n')
assert b'MapOff = 1' in e.fs[CFG_] and e.ground_calls == 0 and post(e, g1)[1] != 5, e.fs[CFG_]
passed('1.0 the body, safety: every function is checked by its first words - when one differs the mod does not walk anybody and the scripts do it as before; a crash while giving a task (step 23) or in a ground question (step 24) turns that part off for good (BodyOff / MapOff in the settings file)')
# the map: the ground cell by cell, what stands between cells, straight legs; a high place for the marksman
e, (g1,), _ = detail_world()
e.ground = lambda x, y, z: (1, 14.) if 20 < x < 30 and -5 < y < 5 and z > 14 else (1, 0.)            # a flat roof 14 m up, east of CJ
e.los_fn = lambda a, b: not (min(a[0], b[0]) < 3.0 < max(a[0], b[0]) and abs(a[1]) < 30 and a[2] < 3)   # a wall along x = 3
e.frame(ms=100, n=60, hud=False)
head, text, ticks = replay_tool.replay(e.save())
cells, walls, highs, legs = {}, set(), set(), 0
for t in ticks:
    sn = t['snapshot']
    for g in sn.ground[:sn.n_ground]:
        cells[(g.x, g.y)] = (g.found, g.z)
        if g.wall & 1: walls.add((g.x, g.y))
    highs |= {(round(q.at.x), round(q.at.y), round(q.height), q.sees_cj) for q in sn.high[:sn.n_high]}
    legs += sn.n_segs
assert len(cells) > 150 and all(f == 1 for f, z in cells.values()) and all(t['match'] for t in ticks), len(cells)
assert walls and all(x == 2.5 for x, y in walls), sorted(walls)[:5]                              # only the cells whose +x neighbour lies behind the wall
assert highs and all(20 < x < 30 and hh_ == 14 and sees == 1 for x, y, hh_, sees in highs), highs
assert e.ground_calls > 400
passed('1.0 the map: the core\'s ground questions are answered with the game\'s FindGroundZFor3DCoord and a level ray to the next cell (a wall along x = 3 marks exactly the cells before it); straight legs with two rays; a flat roof 14 m up from which CJ is seen is found and told as a high place; all of it within its own 1.2 ms a look; the report replays exactly')
# the player's mode and "to me"; what the scripts are told about the squad
e, (g1,), _ = detail_world()
v = e.opcode(0, 10, CMD_PLAN)[1]
assert v[0] == h.HCB_UMODE_PROTECT and v[1] == h.HCB_TASK_ESCORT and v[9] == 1, v
e.share(HC_MODE, 1); e.frame(ms=100, n=3, hud=False); v = e.opcode(0, 10, CMD_PLAN)[1]
assert v[0] == h.HCB_UMODE_ASSAULT and v[1] == h.HCB_TASK_REGROUP, v                                 # nobody to go for: with CJ
e.share(HC_RECALL, 1); e.frame(ms=100, n=2, hud=False)
assert e.shared_value(HC_RECALL) == 0                                                              # taken
head, text, ticks = replay_tool.replay(e.save())
assert ticks[-1]['snapshot'].recall == 1 and ticks[-1]['snapshot'].umode == 1 and all(t['match'] for t in ticks)
e.frame(ms=1000, n=11, hud=False)
head, text, ticks = replay_tool.replay(e.save())
assert ticks[-1]['snapshot'].recall == 0
lg_ = e.log()
assert 'squad: mode ASSAULT' in lg_ and '(TO ME)' in lg_ and 'body MOD: new tasks' in lg_ and 'map: ground asked' in lg_ and ' why ' in lg_ and 'game tasks' in lg_, [l_ for l_ in lg_.splitlines() if 'squad:' in l_][-2:]
SUM = MODS + 'hcbrain_summary.txt'
assert SUM in e.fs and b'guard farther than 8 m from his post while CJ stands' in e.fs[SUM] and b'the body: the mod' in e.fs[SUM], e.fs.get(SUM)
passed('1.0 the mode: PROTECT / ASSAULT is read from the scripts\' shared value, "to me" is taken once and holds ten seconds; command 7 tells the scripts the mode, the squad\'s task, the marksman\'s roof and whether the mod walks the men; the log has a line for the squad, the body and the map every second and every guard\'s action, stage, reason and the game\'s own task types; mods/hcbrain_summary.txt keeps the session\'s numbers (far from post, stuck, sprint, changes of action)')

# ------------------------------------------------------------------ 1.1: the mod's own gun task, magazines, the game AI kept off, ropes, the settings file
def fight_world(gun=True, cfg=None, far=False):
    e = Emu(gun=gun)
    if cfg: e.fs[CFG_] = cfg
    lg_ = e.load()
    g1 = e.ped(9 if far else 1.5, 6 if far else -1., pedtype=8, weapon=31)
    e.share(HC_STATE + 71, e.handle(g1)); e.share(HC_HELLO, 0); e.share(HC_MODE, 0); e.share(HC_RECALL, 0)
    e.frame(n=6, hud=False)
    gang = e.ped(18, 0, pedtype=7, weapon=30, face=(-1., 0.))
    e.frame(n=2, hud=False); e.gunshot(gang, (0., 0.5, 1.))
    return e, g1, gang, lg_
def squad(e, g): return e.opcode(10, 3, CMD_SQUAD, handle=e.handle(g))[1]
e, g1, gang, lg_ = fight_world()
assert "their weapons: the mod's own gun task" in lg_ and 'the game AI kept off the guards: yes' in lg_ and 'their ropes: held by the mod' in lg_, lg_[-500:]
states = []
for _ in range(14):
    e.frame(ms=50, hud=False); states.append(squad(e, g1)[1])
guns = [t for t in e.new_tasks if t['kind'] == 'gun']; mgr = e.r64(g1 + 0x538) + 8
assert states[-1] == 6 and len(guns) == 1 and guns[0]['ent'] == gang and e.sec_tasks == [(mgr, guns[0]['task'], 0)], (states, guns, e.sec_tasks)
assert e.r64(mgr + 24) == 0 or e.r64(mgr + 24) != guns[0]['task'], 'his main slot is not the gun task: he can walk and fire'
assert e.gun_cmds and e.gun_cmds[-1][2] == gang and e.gun_cmds[-1][3] == 3 and all(c[0] == guns[0]['task'] for c in e.gun_cmds), e.gun_cmds[-3:]
clip0 = e.r32(g1 + 0x738)
for _ in range(10):
    e.frame(ms=50, hud=False); squad(e, g1)
assert len([t for t in e.new_tasks if t['kind'] == 'gun']) == 1 and e.r32(g1 + 0x738) < clip0, 'asked every frame: no new task, only the command; rounds leave his magazine'
e.move(e.cj, 10, 0.3); e.frame(ms=50, n=2, hud=False); v = squad(e, g1)                         # CJ in his line: the same task is told to aim, not fire
assert v[1] == 6 and e.gun_cmds[-1][3] == 1, (v, e.gun_cmds[-1])
e.move(e.cj, 0, 0); e.w32(gang + 0x54c, 55); e.frame(ms=100, n=6, hud=False); v = squad(e, g1)    # the man is dead: the task is told to stop
assert e.gun_cmds[-1][3] == 6 and e.gun_cmds[-1][2] == 0 and v[1] != 6, (v, e.gun_cmds[-1])
head, text, ticks = replay_tool.replay(e.save())
assert ticks[-1]['snapshot'].our_clip[0] == e.r32(g1 + 0x738) and all(t['match'] for t in ticks)
passed('1.1 the guards\' weapons: with the brain\'s leave to fire a guard gets the game\'s own gun task ONCE in his attack slot (CTaskSimpleUseGun through SetTaskSecondary - the main slot is left alone) and the script is told 6 = "his weapon is the mod\'s"; after that only its command is set every look - fire a burst, aim (CJ in the line), stop (the man is dead); the rounds left in his magazine go to the core')
# the self-check: fire ordered for 3 s and no round leaves the weapon - the scripts fire from then on
e, g1, gang, _ = fight_world(); e.gun_fires = False
st = []
for k in range(90):
    if k % 12 == 0: e.gunshot(gang, (0., 0.5, 1.))
    e.frame(ms=50, hud=False); st.append(squad(e, g1)[1])
e.frame(ms=100, n=35, hud=False)                                    # (the log is written out)
assert st[10] == 6 and st[-1] == 2 and 'no round has left the weapon' in e.log() and e.gun_cmds[-1][3] == 7, (st[::10], e.gun_cmds[-1])
passed('1.1 the gun task checks itself: 3 s of fire orders and no round has left any guard\'s weapon - the mod says so in the log, ends its task and the scripts fire as before (the answer is 2 again)')
# magazines: the man whose turn it is gets CWeapon::Reload, once a turn
e, g1, gang, _ = fight_world()
for k in range(12):
    e.frame(ms=50, hud=False); squad(e, g1)
e.w32(g1 + 0x738, 3)
for k in range(30):
    if k % 12 == 0: e.gunshot(gang, (0., 0.5, 1.))
    e.frame(ms=50, hud=False); squad(e, g1)
assert len(e.reloads) == 1 and e.reloads[0] == (g1 + 0x730, g1) and e.r32(g1 + 0x738) > 20, e.reloads
passed('1.1 magazines: with 3 rounds left the guard takes the core\'s turn to reload - the mod calls the game\'s CWeapon::Reload for his weapon once and he fires on with a full magazine')
# fire on the move. With the mod's gun task: a plain walk and the gun task beside it. Without it: the game's go-and-shoot task, once.
e, g1, gang, _ = fight_world(far=True)
for k in range(8):
    e.frame(ms=50, hud=False); squad(e, g1); v = post(e, g1)
kinds = [t['kind'] for t in e.new_tasks]
assert v[1] == 5 and kinds.count('goto') == 1 and kinds.count('gun') == 1 and 'shoot' not in kinds, (v, kinds)
e, g1, gang, _ = fight_world(gun=False, far=True)
for k in range(8):
    e.frame(ms=50, hud=False); st_ = squad(e, g1); v = post(e, g1)
sh = [t for t in e.new_tasks if t['kind'] == 'shoot']
assert st_[1] == 2 and v[1] == 5 and len(sh) == 1 and sh[0]['ent'] == gang and sh[0]['ms'] in (4, 6, 7) and e.set_tasks[-1][1:] == (sh[0]['task'], 3), (st_, v, e.new_tasks)
for k in range(6):
    e.frame(ms=50, hud=False); squad(e, g1); post(e, g1)
assert len([t for t in e.new_tasks if t['kind'] == 'shoot']) == 1, 'asked again: the same task goes on'
gang2 = e.ped(16, 4, pedtype=7, weapon=30, face=(-1., 0.)); e.w32(gang + 0x54c, 55)
for k in range(14):
    if k % 4 == 0: e.gunshot(gang2, (0., 0.5, 1.))
    e.frame(ms=50, hud=False); squad(e, g1); post(e, g1)
sh = [t for t in e.new_tasks if t['kind'] == 'shoot']
assert len(sh) == 2 and sh[1]['ent'] == gang2, ('another man: another go-and-shoot task', [t['kind'] for t in e.new_tasks])
e.share(HC_STATE + 7, 0)                                             # HOLD FIRE: he goes on, without the weapon
for k in range(10):
    e.frame(ms=50, hud=False); squad(e, g1); v = post(e, g1)
assert e.new_tasks[-1]['kind'] == 'goto' and v[1] == 5, (e.new_tasks[-1]['kind'], v)
passed('1.1 fire on the move: with the mod\'s gun task a guard walks by the plain go-to task and fires by the gun task beside it; where that task is refused he gets the game\'s go-and-shoot task ONCE (the man the brain gave him), a new one for another man, and a plain walk again when fire is forbidden')
# the game AI kept off: the empty decision maker is put back, a flight in his event slot is removed, a walk is left alone
e, (g1,), _ = detail_world()
intel = e.r64(g1 + 0x538); e.w32(intel + 0x160, 5); post(e, g1)
e.w32(intel + 0x160, 9); e.frame(ms=100, hud=False); post(e, g1)
assert e.r32(intel + 0x160) == 5, e.r32(intel + 0x160)
flee = e.alloc(0x60); e.w64(flee, GTA + e.vt_flee); e.w64(intel + 8 + 16, flee); n0 = len(e.abort_calls)
e.frame(ms=100, hud=False); post(e, g1)
assert e.ev_clears == [(intel + 8, flee)] and e.r64(intel + 8 + 16) == 0 and e.abort_calls[n0][:2] == (flee, g1), (e.ev_clears, e.abort_calls[n0:])
walk = e.alloc(0x60); e.w64(walk, GTA + VT_GOTO); e.w64(intel + 8 + 16, walk); e.frame(ms=100, hud=False); post(e, g1)
assert len(e.ev_clears) == 1 and e.r64(intel + 8 + 16) == walk, 'a task that is not a reaction of the game AI is left where it is'
e.w64(intel + 8 + 16, flee); e.abort_ok = False; e.frame(ms=100, hud=False); post(e, g1)
assert len(e.ev_clears) == 1 and e.r64(intel + 8 + 16) == flee, 'and one that refuses to stop is not torn out'
e.frame(ms=100, n=40, hud=False); lg_ = e.log()
assert "the guards' decision maker (the scripts' empty one): 5" in lg_ and 'mind: decision maker 5 put back 1 AI reactions removed 1 (last type 911) refused' in lg_, [l_ for l_ in lg_.splitlines() if 'mind:' in l_][-1:]
passed('1.1 the game AI kept off a guard: the scripts\' empty decision maker is remembered and put back when something has changed it; a flight (type 911) in his event slot is asked to stop and removed with the game\'s ClearTaskEventResponse; a task of another kind is left alone and one that refuses is not torn out')
# ropes: while one of ours is on it the rope is kept alive and its top goes with the helicopter
e = Emu(); e.load()
pilot = e.ped(0, 8, 25., pedtype=8); heli = e.veh(0, 8, 25., vtype=3, driver=pilot)
g1 = e.ped(1.5, 8, 20., pedtype=8, weapon=31)
e.share(HC_STATE + 21, e.handle(heli) & 0x7fffffff); e.share(HC_STATE + 22, e.handle(pilot)); e.share(HC_STATE + 71, e.handle(g1)); e.share(HC_HELLO, 0)
rope_task = e.alloc(0x40); e.w64(rope_task, GTA + VT_ROPE); e.w32(rope_task + 0x18, 105); e.w64(e.r64(g1 + 0x538) + 8 + 24, rope_task)
R = GTA + ROPES_T + 2 * 0x340
e.wf(R, 1.5, 8., 24.); e.w64(R + 0x300, 105); e.uc.mem_write(R + 0x339, b'\x08'); e.w32(R + 0x334, e.r32(GTA + TIME_MS) + 400)
other = GTA + ROPES_T + 5 * 0x340; e.wf(other, 50., 50., 30.); e.w64(other + 0x300, 300); e.uc.mem_write(other + 0x339, b'\x08'); e.w32(other + 0x334, 12345)
e.frame(n=8, hud=False)
assert e.r32(R + 0x334) == e.r32(GTA + TIME_MS) + 4000 and e.r32(other + 0x334) == 12345, 'his rope lives on; a rope nobody of ours is on is not touched'
e.move(heli, 3, 10, 25.); e.frame(n=3, hud=False)
top = struct.unpack('<3f', bytes(e.uc.mem_read(R, 12)))
assert math.dist(top, (4.5, 10., 24.)) < 0.01, ('the top of the rope goes with the helicopter', top)
e.w64(e.r64(g1 + 0x538) + 8 + 24, 0); till = e.r32(R + 0x334); e.frame(n=5, hud=False)
assert e.r32(R + 0x334) == till, 'he stands: the rope is the game\'s again'
passed('1.1 ropes: a rope one of ours comes down (the game\'s own rope task names it) is kept alive past its 4 s and its top follows the helicopter; when he stands, or for a rope nobody of ours is on, nothing is touched')
# the settings file: every tactical number, checked
e = Emu(); e.fs[CFG_] = b'[Preferences]\nMarkers = 0\n\n[Tactics]\nGatherM = 40\nRiflesPerTarget = 9\nCornerMs = abc\nPlaceFire = 0.55\n'; lg_ = e.load()
assert 'tactical numbers from the settings file: 2 changed, 2 ignored' in lg_, [l_ for l_ in lg_.splitlines() if 'tactical' in l_]
out_ = e.fs[CFG_].decode()
assert '[Tactics]' in out_ and '\nGatherM = 40 ' in out_ and '\nPlaceFire = 0.55 ' in out_ and '\nRiflesPerTarget = 3 ' in out_ and '\nCornerMs = 800 ' in out_ and out_.count('\n') > 35, out_[:600]
e2 = Emu(); e2.fs[CFG_] = e.fs[CFG_] + b''; lg2 = e2.load()
assert 'tactical numbers from the settings file: 2 changed, 0 ignored' in lg2 and e2.fs[CFG_] == e.fs[CFG_], 'the file the mod wrote reads back the same'
e3 = Emu(gun=True); e3.fs[CFG_] = b'[Preferences]\nMarkers = 0\nLastCrash = 26\n'; lg3 = e3.load()
assert b'GunOff = 1' in e3.fs[CFG_] and 'the scripts fire the guards\' weapons from now on' in lg3
e3 = Emu(gun=True); e3.fs[CFG_] = b'[Preferences]\nMarkers = 0\nMindOff = 1\nRopeOff = 1\nGunOff = 1\n'; lg3 = e3.load()
assert 'the game AI kept off the guards: off in the settings; their weapons: the scripts (off in the settings); their ropes: the game\'s (off in the settings)' in lg3, lg3[-400:]
passed('1.1 the settings file: every tactical number is written to configs/net.helicover.brain.ini ([Tactics], with what it means and its limits); a changed value is taken at the next start, one that is not a number or outside its limits is ignored and written back as the built-in one; MindOff / GunOff / RopeOff switch those parts off, and a crash inside one of them (steps 25-27) does it by itself')

# ------------------------------------------------------------------ 1.1: the ways found by the mod's own thread; the map kept between games
MAPF = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/configs/net.helicover.brain.map'
def walled(e):
    e.los_fn = lambda a, b: not (min(a[1], b[1]) < 3.0 < max(a[1], b[1]) and -12 < a[0] < 12 and a[2] < 3)   # a wall along y = 3, 24 m long: between the guard and CJ
e, (g1,), lg_ = detail_world(tweak=walled)                          # (the wall stands from the start: the map asks about a cell once)
assert 'the map of earlier games: none yet' in lg_ and 'way-finding thread on' in lg_
e.move(g1, 0, 9)
kinds = []
gp, walked = [0., 9.], []
for k in range(260):
    e.frame(ms=100, hud=False); v = post(e, g1)
    if v[1] == 5 and e.new_tasks:                                    # (what the game's task does: the man walks to the task's target - not through the wall)
        tx, ty, _ = struct.unpack('<3f', bytes(e.uc.mem_read(e.new_tasks[-1]['task'] + 0x1c, 12))); d_ = math.hypot(tx - gp[0], ty - gp[1])
        if d_ > 0.05:
            st_ = min(d_, 0.45); nx, ny = gp[0] + (tx - gp[0]) * st_ / d_, gp[1] + (ty - gp[1]) * st_ / d_
            if not (min(gp[1], ny) < 3.0 < max(gp[1], ny) and -12 < nx < 12): gp = [nx, ny]; e.move(g1, nx, ny)
        walked.append(tuple(gp))
head, text, ticks = replay_tool.replay(e.save())
asked = sum(t['out'].n_path_q for t in ticks); answers = [p_ for t in ticks for p_ in t['snapshot'].paths[:t['snapshot'].n_paths]]
assert asked >= 1 and answers and any(a.n >= 2 for a in answers) and all(t['match'] for t in ticks), (asked, [a.n for a in answers])
ways = [[(round(a.wp[k].x, 1), round(a.wp[k].y, 1)) for k in range(a.n)] for a in answers if a.n >= 2]
assert any(any(abs(x) > 11 for x, y in w_) for w_ in ways), ('once the map knows the wall, the way goes round its end', ways[-3:])
assert max(abs(x) for x, y in walked) > 11.5 and gp[1] < 2.0 and math.hypot(gp[0] - fl(v[2]), gp[1] - fl(v[3])) < 2.0, ('walked along the way the thread found: round the end of the wall and on to his post', gp, max(abs(x) for x, y in walked))
lg_ = e.log()
passed('1.1 the ways: the straight way is blocked by a wall - the core asks for a way, the mod\'s thread finds it on a copy of the brain\'s map and the answer comes into a later look as an input (the report replays exactly); the way goes round the end of the wall and the guard is walked along it')
# the thread is slow or absent: nothing waits for it
e, (g1,), _ = detail_world(tweak=walled); e.thread_runs = False; e.move(g1, 0, 9)
for k in range(40):
    e.frame(ms=100, hud=False); post(e, g1)
head, text, ticks = replay_tool.replay(e.save())
late = ticks[-35:]                                                   # (the looks since the thread stopped having its turn)
assert sum(t['snapshot'].n_paths for t in late) == 0 and all(t['match'] for t in ticks) and sum(t['out'].n_path_q for t in late) >= 1, ('asked, no answer, no fault: the guard waits, the game goes on', sum(t['snapshot'].n_paths for t in late), sum(t['out'].n_path_q for t in late))
e.thread_runs = True
for k in range(30):
    e.frame(ms=100, hud=False); post(e, g1)
head, text, ticks = replay_tool.replay(e.save())
assert sum(t['snapshot'].n_paths for t in ticks[-33:]) >= 1, 'when the thread has its turn again the answers come'
passed('1.1 the ways, a slow thread: while it has no turn the look is not held up and nothing breaks (the guard waits where he is); the answers come when it runs again')
# the map: what was asked once is written to a file by the thread and known at once in the next game
e, (g1,), _ = detail_world()
e.frame(ms=100, n=60, hud=False)
calls1 = e.ground_calls
e.frame(ms=1000, n=32, hud=False)                                    # (30 s later the changed map goes to the thread)
assert MAPF in e.fs and e.fs[MAPF][:4] == b'HCMP' and struct.unpack('<III', e.fs[MAPF][:12])[1:] == (1, (len(e.fs[MAPF]) - 12) // 12) and len(e.fs[MAPF]) > 12 + 12 * 300, len(e.fs.get(MAPF, b''))
cars_flag = {c[2][1] for c in e.los_calls if abs(c[0][2] - 0.7) < 0.01 and abs(c[1][2] - 0.7) < 0.01 and abs(math.dist(c[0], c[1]) - 1.0) < 0.01}   # (cell centre to the next cell centre, knee high)
assert cars_flag == {0}, ('the map\'s rays do not count cars', cars_flag)
e2 = Emu(); e2.fs[MAPF] = e.fs[MAPF] + b''; lg2 = e2.load()
g2 = e2.ped(9, 6, pedtype=8, weapon=31); e2.share(HC_STATE + 71, e2.handle(g2)); e2.share(HC_HELLO, 0); e2.share(HC_MODE, 0); e2.share(HC_RECALL, 0)
e2.frame(ms=100, n=25, hud=False)
head, text, ticks = replay_tool.replay(e2.save())
known = sum(t['snapshot'].n_ground for t in ticks)
assert 'cells of ground known from the start' in lg2 and known > 300 and e2.ground_calls < calls1 // 4 and all(t['match'] for t in ticks), (known, e2.ground_calls, calls1)
e3 = Emu(); e3.fs[MAPF] = b'HCMP' + struct.pack('<II', 1, 3) + struct.pack('<hhfBxxx', 1, 1, float('nan'), 0) + struct.pack('<hhfBxxx', 2, 2, 5., 9) + struct.pack('<hhfBxxx', 3, 3, 5., 1); lg3 = e3.load()
assert 'the map of earlier games: 1 cells' in lg3 and 'the brain is running' in lg3
e4 = Emu(); e4.fs[MAPF] = b'junk' * 10; lg4 = e4.load()
assert 'the map of earlier games: 0 cells' in lg4 and 'the brain is running' in lg4
passed('1.1 the map between games: the cells asked about are kept (16384 of them) and written by the thread to configs/net.helicover.brain.map; in the next game the same ground is answered from the file - %d cells in 2.5 s with a quarter of the game\'s ground calls or fewer; the map\'s rays do not count cars; a damaged file or cell is left out' % known)

text = '\n'.join(results) + '\nThe phone build on an emulated CPU with the real libGTASA.so and the real code of the CLEO library; the world in memory is laid out by the test. Not run in the game.\n'
(h.OUT / 'brain_adapter_tests.txt').write_text(text)
print(text)
