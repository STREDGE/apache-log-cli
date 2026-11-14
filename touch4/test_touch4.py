#!/usr/bin/env python3
"""Runs libMultiTouch64.so on an emulated arm64 CPU (unicorn) against a real libGTASA.so.

usage: python3 touch4/test_touch4.py path/to/libGTASA.so [path/to/libMultiTouch64.so]

Checks: the install patches exactly what it should (and nothing when the game code differs);
the first touch switches Java to 4 fingers; every finger keeps its game slot by its Android
pointer id while other fingers go up and down; touches reach AND_TouchEvent from the
ProcessEvents hook and the relocated prologues resume the original functions; the SAUtils
"Mods Settings" item switches back to the game's own 2-finger code and is saved to a file.
"""
import os, re, struct, sys
from unicorn import Uc, UcError, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_PROT_ALL, UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC, UC_HOOK_MEM_WRITE_PROT, UC_HOOK_MEM_FETCH_PROT
from unicorn.arm64_const import *
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

HERE = os.path.dirname(os.path.abspath(__file__))
GTA = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('GTASA_SO', '')
MOD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'build', 'touch4', 'libMultiTouch64.so')

def header_consts():
    s = open(os.path.join(HERE, 'gtasa_offsets.h')).read()
    c = {k: int(v, 16) for k, v in re.findall(r'#define (OFF_\w+) (0x[0-9a-f]+)UL', s)}
    c['PATCHES'] = [tuple(int(x, 16) for x in m) for m in re.findall(r'\{(0x[0-9a-f]+)UL,(0x[0-9a-f]+)U,(0x[0-9a-f]+)U\}', s)]
    return c
C = header_consts()

GTA_BASE = 0x7000000000
MOD_BASE = 0x7100000000
STUB = 0x6000000000
STACK = 0x6100000000
SENT = 0x6200000000
DATA = 0x6300000000
ENV = 0x6400000000
SAU = 0x6500000000
EVENT = 0x6600000000          # the MotionEvent jobject
ACT = 0x7417                  # the activity jobject
CLS_ACT, CLS_EVENT, FID, MID, AML_HANDLE = 0xc1a55, 0xc1a5e, 0xf1d, 0x31d, 0xa31
GAME_DIR = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/'
CFG = GAME_DIR + 'configs/net.helicover.touch4.ini'
CFG_ALT = GAME_DIR + 'mods/touch4.ini'
LOG = GAME_DIR + 'mods/touch4_log.txt'
RET = 0xd65f03c0
XREG = [UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5, UC_ARM64_REG_X6, UC_ARM64_REG_X7]
R_RELATIVE, R_GLOB_DAT, R_JUMP_SLOT, R_ABS64 = 1027, 1025, 1026, 257

def u32(v): return struct.pack('<I', v & 0xffffffff)

def prot_of(flags):
    p = 0
    if flags & 4: p |= UC_PROT_READ
    if flags & 2: p |= UC_PROT_WRITE
    if flags & 1: p |= UC_PROT_EXEC
    return p

class Emu:
    def __init__(self, page, tweak=None, fs=None, has_sautils=True, deny=()):
        self.page = page
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.mprotects, self.mmaps, self.mt2, self.touches, self.pe_tail = [], [], [], [], []
        self.fs, self.fds, self.deny = dict(fs or {}), {}, deny
        self.jni_calls, self.jni_fail, self.pid_fail, self.flips, self.ids = [], False, False, [], [0, 1, 2, 3]
        self.has_sautils, self.sau_add = has_sautils, []
        self.imports = {}
        self.gta = self.load(GTA, GTA_BASE, tweak)
        self.mod = self.load(MOD, MOD_BASE)
        uc.mem_map(STACK, 0x100000)
        uc.mem_map(SENT, 0x1000); uc.mem_write(SENT, u32(RET) * 4)
        uc.mem_map(DATA, 0x1000)
        uc.mem_map(ENV, 0x1000)
        name = b'/data/app/~~abc==/com.rockstargames.gtasa-xyz==/lib/arm64/libGTASA.so\0'
        uc.mem_write(DATA + 0x100, name)
        uc.mem_write(DATA, struct.pack('<QQQH', GTA_BASE, DATA + 0x100, 0, 0))
        # game functions the test replaces with recorders (none of them is checked by the mod)
        g = GTA_BASE
        uc.mem_write(g + C['OFF_MT2'] + 24, u32(0x9101c3ff) + u32(0x52800020) + u32(RET))  # add sp,#0x70; mov w0,#1; ret
        uc.mem_write(g + C['OFF_AND_TOUCH'], u32(RET))
        uc.mem_write(g + C['OFF_PROCESS_EVENTS'] + 16, u32(0x910203ff) + u32(0x52800aa0) + u32(RET))  # add sp,#0x80; mov w0,#0x55; ret
        uc.hook_add(UC_HOOK_CODE, self.on_mt2, begin=g + C['OFF_MT2'] + 24, end=g + C['OFF_MT2'] + 24)
        # fake JNIEnv: ENV -> function table of 229 recording stubs
        uc.mem_write(ENV, struct.pack('<Q', ENV + 0x100))
        uc.mem_write(ENV + 0x100, b''.join(struct.pack('<Q', self.stub_for('jni:%d' % i)) for i in range(229)))
        # fake SAUtils interface object: SAU -> vtable of recording stubs
        uc.mem_map(SAU, 0x1000)
        uc.mem_write(SAU, struct.pack('<Q', SAU + 0x100))
        uc.mem_write(SAU + 0x100, b''.join(struct.pack('<Q', self.stub_for('sau:%d' % i)) for i in range(80)))
        self.getif = self.stub_for('aml:GetInterface')
        uc.hook_add(UC_HOOK_CODE, self.on_touch, begin=g + C['OFF_AND_TOUCH'], end=g + C['OFF_AND_TOUCH'])
        uc.hook_add(UC_HOOK_CODE, self.on_pe_tail, begin=g + C['OFF_PROCESS_EVENTS'] + 16, end=g + C['OFF_PROCESS_EVENTS'] + 16)
        uc.hook_add(UC_HOOK_MEM_WRITE_PROT, self.on_bad, None)
        uc.hook_add(UC_HOOK_MEM_FETCH_PROT, self.on_bad, None)

    def on_bad(self, uc, access, addr, size, value, data):
        print('  protection fault at', hex(addr), 'pc', hex(uc.reg_read(UC_ARM64_REG_PC)))
        return False

    def load(self, path, base, tweak=None):
        uc = self.uc
        f = ELFFile(open(path, 'rb'))
        loads = [s for s in f.iter_segments() if s['p_type'] == 'PT_LOAD']
        top = max(s['p_vaddr'] + s['p_memsz'] for s in loads)
        size = (top + 0xffff) & ~0xffff
        img = bytearray(size)
        for s in loads:
            d = s.data(); img[s['p_vaddr']:s['p_vaddr'] + len(d)] = d
        dsym = f.get_section_by_name('.dynsym')
        syms = {sym.name: sym['st_value'] for sym in dsym.iter_symbols()} if dsym else {}
        for sec in f.iter_sections():
            if not isinstance(sec, RelocationSection): continue
            for r in sec.iter_relocations():
                t, off = r['r_info_type'], r['r_offset']
                if t == R_RELATIVE:
                    img[off:off + 8] = struct.pack('<Q', base + r['r_addend'])
                elif t in (R_GLOB_DAT, R_JUMP_SLOT, R_ABS64):
                    sym = dsym.get_symbol(r['r_info_sym'])
                    if sym['st_shndx'] != 'SHN_UNDEF':
                        img[off:off + 8] = struct.pack('<Q', base + sym['st_value'] + (r['r_addend'] or 0))
                    else:
                        img[off:off + 8] = struct.pack('<Q', self.stub_for(sym.name))
        if tweak: tweak(img)
        uc.mem_map(base, size, UC_PROT_ALL)
        uc.mem_write(base, bytes(img))
        P = self.page
        for s in loads:
            a = (s['p_vaddr'] // P) * P; e = -(-(s['p_vaddr'] + s['p_memsz']) // P) * P
            uc.mem_protect(base + a, e - a, prot_of(s['p_flags']))
        for s in f.iter_segments():
            if s['p_type'] == 'PT_GNU_RELRO':
                a = (s['p_vaddr'] // P) * P; e = ((s['p_vaddr'] + s['p_memsz']) // P) * P
                if e > a: uc.mem_protect(base + a, e - a, UC_PROT_READ)
        return syms

    def stub_for(self, name):
        if name not in self.imports:
            if not self.imports:
                self.uc.mem_map(STUB, 0x10000, UC_PROT_READ | UC_PROT_EXEC)
                self.uc.hook_add(UC_HOOK_CODE, self.on_stub, begin=STUB, end=STUB + 0xffff)
            addr = STUB + 0x40 * len(self.imports)
            self.imports[name] = addr
            code = u32(RET)
            if name == 'dl_iterate_phdr':   # cb(info, sizeof info, data) for libGTASA only
                code = b''.join(u32(w) for w in (0xa9bf7bfd, 0xaa0103e2, 0xaa0003e3, 0x580000a0, 0xd2800501,
                                                 0xd63f0060, 0xa8c17bfd, RET)) + struct.pack('<Q', DATA)
            self.uc.mem_write(addr, code)
        return self.imports[name]

    def cstr(self, a): return bytes(self.uc.mem_read(a, 300)).split(b'\0')[0].decode()

    def on_stub(self, uc, addr, size, _):
        names = {v: k for k, v in self.imports.items()}
        if addr not in names: return
        n = names[addr]; x = [uc.reg_read(XREG[i]) for i in range(8)]
        ret = 0
        if n.startswith('jni:'):
            slot = int(n[4:])
            self.jni_calls.append(slot)
            assert x[0] == ENV, 'JNI call without env'
            if slot == 31: ret = CLS_EVENT if x[1] == EVENT else CLS_ACT
            elif slot == 33:
                assert x[1] == CLS_EVENT and [self.cstr(x[2]), self.cstr(x[3])] == ['getPointerId', '(I)I']
                ret = 0 if self.pid_fail else MID
                self.jni_exc = self.pid_fail
            elif slot == 51:
                assert x[1] == EVENT and x[2] == MID
                ret = self.ids[struct.unpack('<i', bytes(uc.mem_read(x[3], 4)))[0]]
            elif slot == 94:
                assert x[1] == CLS_ACT and [self.cstr(x[2]), self.cstr(x[3])] == ['Use2Touches', 'Z']
                ret = 0 if self.jni_fail else FID
                self.jni_exc = self.jni_fail
            elif slot == 228: ret = int(getattr(self, 'jni_exc', False))
            elif slot == 17: self.jni_exc = False
            elif slot == 105: self.flips.append((x[1], x[2], x[3] & 0xff))
            elif slot == 23: assert x[1] in (CLS_ACT, CLS_EVENT)
            else: raise AssertionError('unexpected JNI slot %d' % slot)
        elif n.startswith('sau:'):
            assert n == 'sau:3' and x[0] == SAU, 'unexpected SAUtils call ' + n
            sw = [self.cstr(struct.unpack('<Q', bytes(uc.mem_read(x[6] + 8 * i, 8)))[0]) for i in range(2)]
            self.sau_add.append((x[1] & 0xff, self.cstr(x[2]), x[3] & 0xffffffff, x[4] & 0xffffffff, x[5] & 0xffffffff, sw, x[7]))
            ret = 40
        elif n == 'aml:GetInterface':
            ret = SAU if self.cstr(x[0]) == 'SAUtils' and self.has_sautils else 0
        elif n == 'dlopen': ret = AML_HANDLE if self.cstr(x[0]) == 'libAML.so' else 0
        elif n == 'dlsym':
            assert x[0] == AML_HANDLE and self.cstr(x[1]) == 'GetInterface'
            ret = self.getif
        elif n == 'getpagesize': ret = self.page
        elif n == 'mprotect':
            assert x[0] % self.page == 0 and x[1] % self.page == 0, ('unaligned mprotect', hex(x[0]), hex(x[1]))
            self.mprotects.append((x[0], x[1], x[2]))
            p = (UC_PROT_READ if x[2] & 1 else 0) | (UC_PROT_WRITE if x[2] & 2 else 0) | (UC_PROT_EXEC if x[2] & 4 else 0)
            uc.mem_protect(x[0], x[1], p)
        elif n == 'mmap':
            hint = x[0]
            assert x[2] == 7 and x[1] == self.page
            try:
                uc.mem_map(hint, x[1], UC_PROT_ALL); ret = hint
            except UcError:
                ret = (1 << 64) - 1
            self.mmaps.append((hint, ret))
        elif n == 'munmap': uc.mem_unmap(x[0], x[1])
        elif n == 'open':
            path, flags = self.cstr(x[0]), x[1]
            ok = path.startswith('/storage/emulated/0/Android_unprotected/') and not any(d in path for d in self.deny)
            if ok and flags & 0o100: self.fs[path] = b'' if flags & 0o1000 else self.fs.get(path, b'')
            if ok and path in self.fs:
                ret = 3 + len(self.fds) + 10 * len(self.fs); self.fds[ret] = [path, 0]
            else: ret = (1 << 64) - 1
        elif n == 'read':
            path, pos = self.fds[x[0]]; d = self.fs[path][pos:pos + x[2]]
            uc.mem_write(x[1], d); self.fds[x[0]][1] += len(d); ret = len(d)
        elif n == 'write': self.fs[self.fds[x[0]][0]] += bytes(uc.mem_read(x[1], x[2])); ret = x[2]
        elif n == 'close': del self.fds[x[0]]
        elif n == 'dladdr':   # the .so path AML loaded us from
            self.uc.mem_write(DATA + 0x300, (GAME_DIR + 'lib/libMultiTouch64.so\0').encode())
            self.uc.mem_write(x[1], struct.pack('<QQQQ', DATA + 0x300, MOD_BASE, 0, 0)); ret = 1
        elif n == 'dl_iterate_phdr': return
        else: raise AssertionError('unexpected import ' + n)
        uc.reg_write(UC_ARM64_REG_X0, ret)

    def on_mt2(self, uc, addr, size, _):
        self.mt2.append(tuple(uc.reg_read(r) & 0xffffffff for r in (UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5, UC_ARM64_REG_X6, UC_ARM64_REG_X7)))
    def on_touch(self, uc, addr, size, _):
        self.touches.append(tuple(uc.reg_read(r) & 0xffffffff for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3)))
    def on_pe_tail(self, uc, addr, size, _):
        sp = uc.reg_read(UC_ARM64_REG_SP)
        saved = struct.unpack('<6Q', bytes(uc.mem_read(sp + 0x20, 48)))
        self.pe_tail.append((sp, saved, uc.reg_read(UC_ARM64_REG_X0) & 0xffffffff))

    def call(self, addr, *args):
        uc = self.uc
        sp = STACK + 0x80000
        regs, stack = args[:8], args[8:]
        for i, v in enumerate(regs): uc.reg_write(XREG[i], v & 0xffffffffffffffff)
        if stack:
            sp -= 8 * len(stack) + (8 * len(stack)) % 16
            for i, v in enumerate(stack): uc.mem_write(sp + 8 * i, struct.pack('<Q', v & 0xffffffffffffffff))
        for i, reg in enumerate((UC_ARM64_REG_X23, UC_ARM64_REG_X24, UC_ARM64_REG_X25, UC_ARM64_REG_X26, UC_ARM64_REG_X27, UC_ARM64_REG_X28)):
            uc.reg_write(reg, 0x2300 + i)
        uc.reg_write(UC_ARM64_REG_SP, sp)
        uc.reg_write(UC_ARM64_REG_LR, SENT)
        uc.emu_start(addr, SENT, count=2000000)
        assert uc.reg_read(UC_ARM64_REG_PC) == SENT, 'did not return'
        assert uc.reg_read(UC_ARM64_REG_SP) == sp, 'stack not balanced'
        return uc.reg_read(UC_ARM64_REG_X0)

    def r32(self, off): return struct.unpack('<I', bytes(self.uc.mem_read(GTA_BASE + off, 4)))[0]
    def r64(self, off): return struct.unpack('<Q', bytes(self.uc.mem_read(GTA_BASE + off, 8)))[0]
    def log(self): return self.fs.get(LOG, b'').decode()
    def ints(self, off, n=2): return struct.unpack('<%di' % n, bytes(self.uc.mem_read(GTA_BASE + off, 4 * n)))
    # Java -> native entries
    def mt2_entry(self, action, count, x0=0, y0=0, x1=0, y1=0, ids=None, thiz=ACT):
        if ids is not None: self.ids = ids
        return self.call(GTA_BASE + C['OFF_MT2'], ENV, thiz, action, count, x0, y0, x1, y1, EVENT)
    def mt4(self, action, count, *xy, ids=None):
        if ids is not None: self.ids = list(ids) + [99] * (4 - len(ids))
        xy = list(xy) + [0] * (8 - len(xy))
        return self.call(GTA_BASE + C['OFF_MT4_STUB'], ENV, ACT, action, count, *xy, EVENT)
    def frame(self):
        self.touches.clear(); n = len(self.pe_tail)
        r = self.call(GTA_BASE + C['OFF_PROCESS_EVENTS'], 1)
        check(r == 0x55 and len(self.pe_tail) == n + 1, 'original ProcessEvents resumed')
        sp, saved, x0 = self.pe_tail[-1]
        check(sp % 16 == 0, 'stack aligned in original ProcessEvents')
        check(saved == (0x2300 + 5, 0x2300 + 4, 0x2300 + 3, 0x2300 + 2, 0x2300 + 1, 0x2300), 'prologue stored x28..x23')
        check(x0 == 1, 'bool argument passed on')
        return list(self.touches)

PASS = 0
def check(cond, what):
    global PASS
    if not cond: raise AssertionError(what)
    PASS += 1

def load(e):
    e.call(MOD_BASE + e.mod['OnModLoad'])
    return e

def test_install(page):
    e = Emu(page)
    check(e.r64(C['OFF_POINTS_GOT']) == GTA_BASE + C['OFF_POINTS'], 'GOT relocated in emulator')
    load(e)
    log = e.log()
    check('4-finger input enabled' in log, 'install log: ' + log)
    check(set(e.fs) == {LOG}, 'only the log is written: %r' % list(e.fs))
    for off, expect, patch in C['PATCHES']:
        check(e.r32(off) == patch, 'patch at %x' % off)
    check(e.ints(C['OFF_MAX_TOUCHES'], 1) == (4,), 'm_nMaxTouches')
    got = e.r64(C['OFF_POINTS_GOT'])
    check(MOD_BASE <= got < MOD_BASE + 0x100000, 'Points GOT -> mod array')
    check(bytes(e.uc.mem_read(got, 56)) == bytes(e.uc.mem_read(GTA_BASE + C['OFF_POINTS'], 56)), 'Points copied')
    # v1.2: the 8-byte stub loads the 4-finger handler from the patched 2-finger entry (mt2+16)
    l, br = e.r32(C['OFF_MT4_STUB']), e.r32(C['OFF_MT4_STUB'] + 4)
    imm = (l >> 5) & 0x7ffff
    if imm & 0x40000: imm -= 0x80000
    check(l & 0xff00001f == 0x58000010 and br == 0xd61f0200, 'stub is ldr x16 / br x16')
    lit = C['OFF_MT4_STUB'] + imm * 4
    check(lit == C['OFF_MT2'] + 0x10, 'stub literal is the pointer stored at mt2+16')
    check(MOD_BASE <= e.r64(lit) < MOD_BASE + 0x100000, 'that pointer is in the mod')
    check(not e.mmaps, 'no executable memory allocated')
    check(e.r32(C['OFF_PROCESS_EVENTS']) == 0x58000051 and e.r32(C['OFF_PROCESS_EVENTS'] + 4) == 0xd61f0220, 'ProcessEvents hooked')
    check(e.r32(C['OFF_MT2']) == 0x58000051, '2-finger entry hooked')
    last = {}
    for a, n, p in e.mprotects: last[a] = p
    check(last.get((GTA_BASE + C['OFF_POINTS_GOT']) // page * page) == 1, 'GOT page back to read-only')
    for off, _, _ in C['PATCHES']:
        check(last.get((GTA_BASE + off) // page * page) == 5, 'text page %x back to R+X' % off)
    # SAUtils "Mods Settings" item
    check(len(e.sau_add) == 1, 'one SAUtils item')
    typ, name, init, mn, mx, sw, cb = e.sau_add[0]
    check((typ, name, init, mn, mx, sw) == (5, '4-Finger Touch', 1, 0, 1, ['Off', 'On']), 'item %r' % (e.sau_add[0],))
    check(MOD_BASE <= cb < MOD_BASE + 0x100000, 'callback in the mod')
    check('Mods Settings item id 40' in log, 'item logged')
    return e

def test_touches(e):
    # first touch: Java still in 2-finger mode; the mod switches it and takes the touch itself
    check(e.mt2_entry(0, 1, 100, 200, ids=[0]) == 1, 'returns true')
    check(e.flips == [(ACT, FID, 0)], 'Use2Touches = false')
    check(e.mt2 == [], 'original 2-finger code not used any more')
    check(e.frame() == [(2, 0, 100, 200)], 'finger A down in slot 0')
    check(e.frame() == [], 'queue drained')
    e.mt4(0x105, 2, 100, 200, 300, 400, ids=[0, 1])
    check(e.frame() == [(2, 1, 300, 400)], 'B down in slot 1')
    e.mt4(0x205, 3, 100, 200, 300, 400, 500, 600, ids=[0, 1, 2])
    e.mt4(2, 3, 100, 200, 300, 400, 500, 600)                     # nothing moved: no event
    e.mt4(0x305, 4, 101, 200, 300, 400, 500, 600, 700, 800, ids=[0, 1, 2, 3])
    check(e.frame() == [(2, 2, 500, 600), (3, 0, 101, 200), (2, 3, 700, 800)], 'C, D down; A moved')
    # A (the first finger) goes up: B, C, D shift to indexes 0-2 but keep their slots
    e.mt4(0x006, 4, 102, 200, 300, 400, 500, 600, 700, 800)
    check(e.frame() == [(1, 0, 102, 200)], 'A up where it is')
    e.mt4(2, 3, 300, 400, 500, 600, 700, 800, ids=[1, 2, 3])
    check(e.frame() == [], 'no jumps after the index shift')
    e.mt4(2, 3, 300, 400, 510, 600, 700, 800)
    check(e.frame() == [(3, 2, 510, 600)], 'C still moves in slot 2')
    # a new finger E gets pointer id 0 and index 0: takes the free slot 0
    e.mt4(0x005, 4, 50, 60, 300, 400, 510, 600, 700, 800, ids=[0, 1, 2, 3])
    check(e.frame() == [(2, 0, 50, 60)], 'E down in free slot 0')
    # C (index 2) goes up
    e.mt4(0x206, 4, 50, 60, 300, 400, 515, 605, 700, 800)
    e.mt4(2, 3, 50, 60, 300, 400, 700, 800, ids=[0, 1, 3])
    check(e.frame() == [(1, 2, 515, 605)], 'C up at its last point, D untouched')
    # F gets id 2 and index 2 again
    e.mt4(0x205, 4, 50, 60, 300, 400, 900, 100, 700, 800, ids=[0, 1, 2, 3])
    check(e.frame() == [(2, 2, 900, 100)], 'F down in slot 2')
    # a 5th finger (id 4) is outside the 4 indexes Java sends; when B (id 1) lifts it comes in
    e.mt4(0x405, 4, 50, 60, 300, 400, 900, 100, 700, 800)
    check(e.frame() == [], '5th finger ignored while 4 are down')
    e.mt4(0x106, 4, 50, 60, 300, 400, 900, 100, 700, 800)
    e.mt4(2, 4, 50, 60, 900, 100, 700, 800, 10, 20, ids=[0, 2, 3, 4])
    check(e.frame() == [(1, 1, 300, 400), (2, 1, 10, 20)], 'B up, 5th finger takes slot 1')
    # everything up (ACTION_UP)
    e.mt4(1, 4, 50, 60, 900, 100, 700, 800, 10, 20)
    check(e.frame() == [(1, 0, 50, 60), (1, 1, 10, 20), (1, 2, 900, 100), (1, 3, 700, 800)], 'all up')
    # cancel
    e.mt4(0, 1, 5, 6, ids=[0])
    e.mt4(3, 1, 5, 6)
    check(e.frame() == [(2, 0, 5, 6), (4, 0, 5, 6)], 'cancel')
    # a new finger under an id that is still in a slot (its up was lost): restarted
    e.mt4(0, 1, 8, 8, ids=[0])
    e.mt4(0x105, 2, 8, 8, 6, 6, ids=[0, 1])
    e.mt4(0x105, 2, 8, 8, 7, 7, ids=[0, 1])
    check(e.frame() == [(2, 0, 8, 8), (2, 1, 6, 6), (1, 1, 6, 6), (2, 1, 7, 7)], 'reused id restarts its slot')
    e.mt4(1, 2, 8, 8, 7, 7)
    e.frame()
    # a new gesture while a slot is still down (lost up): ended first
    e.mt4(0, 1, 1, 1, ids=[0])
    e.mt4(0, 1, 2, 2, ids=[0])
    check(e.frame() == [(2, 0, 1, 1), (1, 0, 1, 1), (2, 0, 2, 2)], 'ACTION_DOWN ends a stale slot')
    e.mt4(1, 1, 2, 2)
    e.frame()
    check(e.jni_calls.count(33) == 1, 'getPointerId looked up once')
    # queue flood while the game is paused keeps room for down/up
    e.mt4(0, 1, 0, 0, ids=[0])
    for i in range(1, 700): e.mt4(2, 1, i, i)
    e.mt4(1, 1, 999, 999)
    t = e.frame()
    check(t[0] == (2, 0, 0, 0) and t[-1] == (1, 0, 999, 999) and len(t) <= 512, 'flood keeps down and up (%d events)' % len(t))

def test_menu(page):
    e = load(Emu(page))
    cb = e.sau_add[0][6]
    e.mt2_entry(0, 1, 10, 20, ids=[0])
    check(e.frame() == [(2, 0, 10, 20)], '4-finger mode on')
    # Mods Settings -> Off (SAUtils calls back on the game thread when the screen closes)
    e.call(cb, 1, 0, 0)
    check(e.fs.get(CFG) == b'[Preferences]\nEnabled = 0\n', 'saved Off')
    check('menu: 4-Finger Touch Off' in e.log(), 'Off logged')
    e.uc.mem_write(GTA_BASE + C['OFF_LAST_ACTION'], struct.pack('<2i', 2, 3))
    e.uc.mem_write(GTA_BASE + C['OFF_LAST_X'], struct.pack('<2i', 7, 8))
    e.uc.mem_write(GTA_BASE + C['OFF_LAST_Y'], struct.pack('<2i', 9, 10))
    e.mt4(2, 1, 11, 21)
    check(e.flips[-1] == (ACT, FID, 1), 'Use2Touches = true again')
    check(e.mt2 == [(2, 1, 11, 21, 0, 0)], 'touch handed to the original 2-finger code')
    check(e.ints(C['OFF_LAST_ACTION']) == (1, 1) and e.ints(C['OFF_LAST_X']) == (0, 0) and e.ints(C['OFF_LAST_Y']) == (0, 0), 'game 2-finger state reset')
    check(e.frame() == [(1, 0, 10, 20)], 'our finger released')
    n = len(e.flips)
    e.mt2_entry(1, 1, 11, 21)
    check(e.mt2[-1] == (1, 1, 11, 21, 0, 0) and len(e.flips) == n, 'Off: game handles touches, no switching')
    check(e.frame() == [], 'nothing from the mod while Off')
    # back On
    e.call(cb, 0, 1, 0)
    check(e.fs.get(CFG) == b'[Preferences]\nEnabled = 1\n', 'saved On')
    m = len(e.mt2)
    e.mt2_entry(0, 1, 30, 40, ids=[0])
    check(e.flips[-1] == (ACT, FID, 0) and len(e.mt2) == m, 'On again: switched to 4 fingers')
    check(e.frame() == [(2, 0, 30, 40)], 'tracked by the mod again')

def test_config(page):
    e = load(Emu(page, fs={CFG: b'[Preferences]\nEnabled = 0\n'}))
    check(e.sau_add[0][2] == 0, 'menu shows Off')
    check('switched off in Mods Settings' in e.log(), 'Off logged at start')
    e.mt2_entry(0, 1, 5, 5, ids=[0])
    check(e.flips == [] and e.mt2 == [(0, 1, 5, 5, 0, 0)], 'Off from the file: game keeps 2 fingers')
    # no configs folder: falls back to the mods folder, both ways
    e = load(Emu(page, deny=('/configs/',)))
    e.call(e.sau_add[0][6], 1, 0, 0)
    check(e.fs.get(CFG_ALT) == b'[Preferences]\nEnabled = 0\n' and CFG not in e.fs, 'saved next to the mods')
    e = load(Emu(page, deny=('/configs/',), fs={CFG_ALT: b'Enabled=0'}))
    check(e.sau_add[0][2] == 0, 'read from the mods folder')

def test_no_sautils_and_fallbacks(page):
    # mods folder not writable: the log goes next to the loaded .so
    e = load(Emu(page, deny=('mods/touch4_log',)))
    check(LOG not in e.fs and '4-finger input enabled' in e.fs.get(GAME_DIR + 'lib/touch4_log.txt', b'').decode(), 'log next to the .so')
    e = load(Emu(page, has_sautils=False))
    check('SAUtils not found' in e.log() and '4-finger input enabled' in e.log(), 'works without SAUtils')
    e.mt2_entry(0, 1, 1, 2, ids=[0])
    check(e.frame() == [(2, 0, 1, 2)], 'tracked')
    # getPointerId missing: fingers follow their index
    e = load(Emu(page))
    e.pid_fail = True
    e.mt2_entry(0, 1, 1, 2, ids=[0])
    check('getPointerId not available' in e.log(), 'logged')
    e.mt4(0x105, 2, 1, 2, 3, 4)
    check(e.frame() == [(2, 0, 1, 2), (2, 1, 3, 4)], 'still tracked by index')
    check(e.jni_calls.count(33) == 1 and 51 not in e.jni_calls, 'lookup not retried')
    # Use2Touches missing: stays on the game's 2-finger code, no retries
    e = load(Emu(page))
    e.jni_fail = True
    e.mt2_entry(0, 1, 10, 20, ids=[0])
    check(e.jni_calls == [31, 94, 228, 17, 23] and e.flips == [], 'exception cleared, nothing set')
    check(e.mt2 == [(0, 1, 10, 20, 0, 0)] and 'staying with 2 fingers' in e.log(), 'handled by the game')
    e.mt2_entry(2, 1, 11, 21)
    check(len(e.jni_calls) == 5 and e.mt2[-1] == (2, 1, 11, 21, 0, 0), 'no retry')
    # a new activity instance (Use2Touches true again) is switched too, logged once
    e = load(Emu(page))
    e.mt2_entry(0, 1, 1, 1, ids=[0])
    e.mt2_entry(1, 1, 1, 1, thiz=ACT + 1)
    check(e.flips == [(ACT, FID, 0), (ACT + 1, FID, 0)] and e.log().count('up to 4 fingers') == 1, 'new activity switched')

def test_refuses(page):
    for what, tweak in (('ProcessEvents', lambda img: img.__setitem__(C['OFF_PROCESS_EVENTS'], img[C['OFF_PROCESS_EVENTS']] ^ 1)),
                        ('state', lambda img: img.__setitem__(0x31e7e0, img[0x31e7e0] ^ 1))):
        e = Emu(page, tweak)
        before = {off: e.r32(off) for off, _, _ in C['PATCHES']}
        got = e.r64(C['OFF_POINTS_GOT'])
        load(e)
        check('nothing changed' in e.log(), 'refusal logged: ' + e.log())
        check(all(e.r32(o) == v for o, v in before.items()) and e.r64(C['OFF_POINTS_GOT']) == got, 'nothing patched (%s)' % what)
        check(e.r32(C['OFF_MT4_STUB']) == 0x320003e0 and not e.mprotects, 'stub and protections untouched')
        check(e.r32(C['OFF_MT2']) == 0xd101c3ff, '2-finger entry untouched')
        check(e.sau_add == [], 'no menu item when nothing was installed')
        load(e)  # second call is ignored
        check(e.r32(C['OFF_MT4_STUB']) == 0x320003e0, 'second OnModLoad ignored')

def test_modinfo():
    e = Emu(4096)
    p = e.call(MOD_BASE + e.mod['__GetModInfo'])
    raw = bytes(e.uc.mem_read(p, 176))
    f = [raw[i:j].split(b'\0')[0].decode() for i, j in ((0, 48), (48, 96), (96, 120), (120, 168))]
    check(f == ['net.helicover.touch4', 'Touch x4', '1.2', 'Helicover'], 'ModInfo strings %r' % f)
    check(struct.unpack('<4H', raw[168:176]) == (1, 2, 0, 0), 'ModInfo version')
    check(bytes(e.uc.mem_read(p + 176, 336)) == b'\0' * 336, 'ModInfo padding zero')

if __name__ == '__main__':
    if not GTA or not os.path.exists(GTA):
        print('SKIP: pass the path to libGTASA.so'); sys.exit(0)
    test_modinfo()
    for page in (4096, 16384):
        test_touches(test_install(page))
        test_menu(page)
        test_config(page)
        test_no_sautils_and_fallbacks(page)
        test_refuses(page)
    print('PASS', PASS)
