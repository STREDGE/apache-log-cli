#!/usr/bin/env python3
"""Runs libMultiTouch64.so on an emulated arm64 CPU (unicorn) against a real libGTASA.so.

usage: python3 touch4/test_touch4.py path/to/libGTASA.so [path/to/libMultiTouch64.so]

Checks: the install patches exactly what it should (and nothing when the game code differs),
the NVEventMultiTouchEvent4 stub reaches the mod, fingers 1-2 go to the original 2-finger
handler, fingers 3-4 are delivered through AND_TouchEvent from the ProcessEvents hook, and
the relocated ProcessEvents prologue resumes the original function with the right stack.
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
    def __init__(self, page, tweak=None):
        self.page = page
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.mprotects, self.mmaps, self.files, self.mt2, self.touches, self.pe_tail = [], [], {}, [], [], []
        self.jni_calls, self.jni_fail = [], False
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
        uc.mem_write(g + C['OFF_MT2'] + 16, u32(0x9101c3ff) + u32(0x52800020) + u32(RET))  # add sp,#0x70; mov w0,#1; ret
        uc.mem_write(g + C['OFF_AND_TOUCH'], u32(RET))
        uc.mem_write(g + C['OFF_PROCESS_EVENTS'] + 16, u32(0x910203ff) + u32(0x52800aa0) + u32(RET))  # add sp,#0x80; mov w0,#0x55; ret
        uc.hook_add(UC_HOOK_CODE, self.on_mt2, begin=g + C['OFF_MT2'] + 16, end=g + C['OFF_MT2'] + 16)
        # fake JNIEnv: ENV -> function table of 229 recording stubs
        uc.mem_write(ENV, struct.pack('<Q', ENV + 0x100))
        uc.mem_write(ENV + 0x100, b''.join(struct.pack('<Q', self.stub_for('jni:%d' % i)) for i in range(229)))
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

    def on_stub(self, uc, addr, size, _):
        names = {v: k for k, v in self.imports.items()}
        if addr not in names: return
        n = names[addr]; x = [uc.reg_read(XREG[i]) for i in range(6)]
        ret = 0
        if n.startswith('jni:'):
            slot = int(n[4:])
            self.jni_calls.append(slot)
            assert x[0] == ENV, 'JNI call without env'
            if slot == 31: ret = 0xc1a55
            elif slot == 94:
                f = [bytes(uc.mem_read(x[i], 40)).split(b'\0')[0].decode() for i in (2, 3)]
                assert x[1] == 0xc1a55 and f == ['Use2Touches', 'Z'], f
                ret = 0 if self.jni_fail else 0xf1d
                self.jni_exc = self.jni_fail
            elif slot == 228: ret = int(getattr(self, 'jni_exc', False))
            elif slot == 17: self.jni_exc = False
            elif slot == 105: self.flips = getattr(self, 'flips', []) + [(x[1], x[2], x[3] & 0xff)]
            elif slot == 23: assert x[1] == 0xc1a55
            else: raise AssertionError('unexpected JNI slot %d' % slot)
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
            path = bytes(uc.mem_read(x[0], 300)).split(b'\0')[0].decode()
            ret = 3 if path.startswith('/storage/emulated/0/Android_unprotected/') else (1 << 64) - 1
            if ret == 3: self.files[path] = b''; self.last = path
        elif n == 'write': self.files[self.last] += bytes(uc.mem_read(x[1], x[2])); ret = x[2]
        elif n in ('close', 'dladdr'): ret = 0
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
            for i, v in enumerate(stack): uc.mem_write(sp + 8 * i, struct.pack('<Q', v & 0xffffffff))
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
    def log(self): return b''.join(self.files.values()).decode()

PASS = 0
def check(cond, what):
    global PASS
    if not cond: raise AssertionError(what)
    PASS += 1

def test_install(page):
    e = Emu(page)
    orig_got = e.r64(C['OFF_POINTS_GOT'])
    check(orig_got == GTA_BASE + C['OFF_POINTS'], 'GOT relocated in emulator')
    e.call(MOD_BASE + e.mod['OnModLoad'])
    log = e.log()
    check('4-finger input enabled' in log, 'install log: ' + log)
    check(list(e.files) == ['/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/mods/touch4_log.txt'], 'log path')
    for off, expect, patch in C['PATCHES']:
        check(e.r32(off) == patch, 'patch at %x' % off)
    check(struct.unpack('<i', bytes(e.uc.mem_read(GTA_BASE + C['OFF_MAX_TOUCHES'], 4)))[0] == 4, 'm_nMaxTouches')
    got = e.r64(C['OFF_POINTS_GOT'])
    check(MOD_BASE <= got < MOD_BASE + 0x100000, 'Points GOT -> mod array')
    check(bytes(e.uc.mem_read(got, 56)) == bytes(e.uc.mem_read(GTA_BASE + C['OFF_POINTS'], 56)), 'Points copied')
    b = e.r32(C['OFF_MT4_STUB'])
    check(b >> 26 == 0x05, 'stub is a B')
    imm = b & 0x3ffffff
    if imm & 0x2000000: imm -= 0x4000000
    tramp = GTA_BASE + C['OFF_MT4_STUB'] + imm * 4
    check(any(r == tramp for h, r in e.mmaps), 'B lands on the mmap page')
    check(e.r32(C['OFF_PROCESS_EVENTS']) == 0x58000051 and e.r32(C['OFF_PROCESS_EVENTS'] + 4) == 0xd61f0220, 'ProcessEvents hooked')
    # protections restored: text R+X, GOT page read-only
    last = {}
    for a, n, p in e.mprotects:
        last[a] = p
    got_page = (GTA_BASE + C['OFF_POINTS_GOT']) // page * page
    check(last.get(got_page) == 1, 'GOT page back to read-only')
    for off, _, _ in C['PATCHES']:
        pg = (GTA_BASE + off) // page * page
        check(last.get(pg) == 5, 'text page %x back to R+X' % off)
    return e

def test_touches(e):
    S = GTA_BASE + C['OFF_MT4_STUB']
    PE = GTA_BASE + C['OFF_PROCESS_EVENTS']
    def mt(action, count, *xy):
        xy = list(xy) + [0] * (8 - len(xy))
        return e.call(S, 0xe0e0, 0x7417, action, count, *xy, 0xbeef)  # last = MotionEvent (13th arg)
    def frame():
        e.touches.clear(); n = len(e.pe_tail)
        r = e.call(PE, 1)
        check(r == 0x55 and len(e.pe_tail) == n + 1, 'original ProcessEvents resumed')
        sp, saved, x0 = e.pe_tail[-1]
        check(sp % 16 == 0, 'stack aligned in original ProcessEvents')
        check(saved == (0x2300 + 5, 0x2300 + 4, 0x2300 + 3, 0x2300 + 2, 0x2300 + 1, 0x2300), 'prologue stored x28..x23')
        check(x0 == 1, 'bool argument passed on')
        return list(e.touches)
    check(mt(0, 1, 100, 200) == 1, 'returns true')
    check(e.mt2[-1] == (0, 1, 100, 200, 0, 0), 'finger 1 to original')
    check(frame() == [], 'nothing extra for 1 finger')
    mt(0x105, 2, 100, 200, 300, 400)
    check(e.mt2[-1] == (0x105, 2, 100, 200, 300, 400), 'finger 2 to original unchanged')
    mt(0x205, 3, 100, 200, 300, 400, 500, 600)
    check(e.mt2[-1] == (2, 2, 100, 200, 300, 400), 'finger 3 down is a MOVE for fingers 1-2, count 2')
    mt(2, 3, 101, 200, 300, 400, 510, 600)
    mt(2, 3, 102, 200, 300, 400, 510, 600)   # finger 3 did not move: no event
    mt(0x305, 4, 102, 200, 300, 400, 510, 600, 700, 800)
    check(e.mt2[-1] == (2, 2, 102, 200, 300, 400), 'finger 4 down for fingers 1-2')
    check(frame() == [(2, 2, 500, 600), (3, 2, 510, 600), (2, 3, 700, 800)], 'fingers 3,4 down + move delivered in order')
    check(frame() == [], 'queue drained')
    mt(2, 4, 102, 200, 300, 400, 520, 610, 700, 810)
    mt(0x306, 4, 102, 200, 300, 400, 520, 610, 705, 815)
    check(e.mt2[-1] == (2, 2, 102, 200, 300, 400), 'finger 4 up is a MOVE for 1-2')
    mt(2, 3, 102, 200, 300, 400, 520, 610)
    check(frame() == [(3, 2, 520, 610), (3, 3, 700, 810), (1, 3, 705, 815)], 'finger 4 up at its last point')
    mt(0x206, 3, 102, 200, 300, 400, 530, 620)
    check(frame() == [(1, 2, 530, 620)], 'finger 3 up')
    # finger 3 back, then all fingers up at once (ACTION_UP from the system)
    mt(0x205, 3, 102, 200, 300, 400, 540, 640)
    mt(1, 3, 102, 200, 300, 400, 540, 640)
    check(e.mt2[-1] == (1, 2, 102, 200, 300, 400), 'ACTION_UP passed to original')
    check(frame() == [(2, 2, 540, 640), (1, 2, 540, 640)], 'up on ACTION_UP')
    # cancel
    mt(0x205, 3, 1, 2, 3, 4, 5, 6)
    mt(3, 3, 1, 2, 3, 4, 5, 6)
    check(frame() == [(2, 2, 5, 6), (4, 2, 5, 6)], 'cancel on ACTION_CANCEL')
    # a lower finger leaves: indexes shift, finger 3 vanishes from index 2
    mt(0x205, 3, 1, 2, 3, 4, 5, 6)
    mt(6, 3, 1, 2, 3, 4, 5, 6)
    mt(2, 2, 3, 4, 5, 6)
    check(frame() == [(2, 2, 5, 6), (1, 2, 5, 6)], 'index 2 gone -> up at last point')
    # 4 fingers A B C D, B goes up: C and D move to indexes 1 and 2
    mt(0x205, 3, 1, 1, 2, 2, 3, 3)
    mt(0x305, 4, 1, 1, 2, 2, 3, 3, 4, 4)
    frame()
    mt(0x106, 4, 1, 1, 2, 2, 3, 3, 4, 4)
    check(e.mt2[-1] == (0x106, 2, 1, 1, 2, 2), 'finger 2 up passed to original')
    mt(2, 3, 1, 1, 3, 3, 4, 4)
    check(frame() == [(1, 2, 3, 3), (1, 3, 4, 4), (2, 2, 4, 4)], 'lower finger up: slot 2 restarts with D, slot 3 ends')
    # a new finger E takes index 1 again: C, D move back up
    mt(0x105, 4, 1, 1, 5, 5, 3, 3, 4, 4)
    check(frame() == [(1, 2, 4, 4), (2, 2, 3, 3), (2, 3, 4, 4)], 'lower finger down: slots 2,3 restart')
    mt(1, 4, 1, 1, 5, 5, 3, 3, 4, 4)
    check(frame() == [(1, 2, 3, 3), (1, 3, 4, 4)], 'all up')
    # queue flood while the game is paused keeps room for down/up
    mt(0x205, 3, 1, 2, 3, 4, 0, 0)
    for i in range(1, 700): mt(2, 3, 1, 2, 3, 4, i, i)
    mt(0x206, 3, 1, 2, 3, 4, 999, 999)
    t = frame()
    check(t[0] == (2, 2, 0, 0) and t[-1] == (1, 2, 999, 999) and len(t) <= 512, 'flood keeps down and up (%d events)' % len(t))

def test_switch(page, fail=False):
    e = Emu(page)
    e.jni_fail = fail
    e.call(MOD_BASE + e.mod['OnModLoad'])
    check('4-finger input enabled' in e.log(), 'installed')
    check(e.r32(C['OFF_MT2']) == 0x58000051, '2-finger entry hooked')
    M2 = GTA_BASE + C['OFF_MT2']
    act = 0x7417
    check(e.call(M2, ENV, act, 0, 1, 10, 20, 0, 0) == 1, '2-finger entry returns the original result')
    check(e.mt2 == [(0, 1, 10, 20, 0, 0)], 'touch still handled by the original 2-finger code')
    if fail:
        check(e.jni_calls == [31, 94, 228, 17, 23] and not getattr(e, 'flips', []), 'missing field: exception cleared, nothing set')
        check('staying with 2 fingers' in e.log(), 'failure logged')
        e.call(M2, ENV, act, 2, 1, 11, 21, 0, 0)
        check(e.jni_calls == [31, 94, 228, 17, 23], 'no retry after failure')
        check(e.mt2[-1] == (2, 1, 11, 21, 0, 0), 'touches keep working')
        return
    check(e.jni_calls == [31, 94, 228, 105, 23], 'JNI sequence %r' % e.jni_calls)
    check(e.flips == [(act, 0xf1d, 0)], 'Use2Touches set to false on the activity')
    check('the game now gets up to 4 fingers' in e.log(), 'switch logged')
    # from now on Java uses multiTouchEvent4; the original 2-finger code is reached without JNI
    e.call(GTA_BASE + C['OFF_MT4_STUB'], ENV, act, 2, 1, 12, 22, 0, 0, 0, 0, 0, 0, 0xbeef)
    check(e.mt2[-1] == (2, 1, 12, 22, 0, 0) and len(e.jni_calls) == 5, '4-finger path does not switch again')
    # a new activity instance (Use2Touches true again) is switched too
    e.call(M2, ENV, 0x7418, 0, 1, 1, 2, 0, 0)
    check(e.flips[-1] == (0x7418, 0xf1d, 0) and e.log().count('up to 4 fingers') == 1, 'new activity switched, logged once')

def test_refuses(page):
    def tweak(img): img[C['OFF_PROCESS_EVENTS']] ^= 1
    e = Emu(page, tweak)
    before = {off: e.r32(off) for off, _, _ in C['PATCHES']}
    got = e.r64(C['OFF_POINTS_GOT'])
    e.call(MOD_BASE + e.mod['OnModLoad'])
    check('nothing changed' in e.log(), 'refusal logged: ' + e.log())
    check(all(e.r32(o) == v for o, v in before.items()) and e.r64(C['OFF_POINTS_GOT']) == got, 'nothing patched')
    check(e.r32(C['OFF_MT4_STUB']) == 0x320003e0 and not e.mprotects, 'stub and protections untouched')
    check(e.r32(C['OFF_MT2']) == 0xd101c3ff, '2-finger entry untouched')
    e.call(MOD_BASE + e.mod['OnModLoad'])  # second call is ignored
    check(e.r32(C['OFF_MT4_STUB']) == 0x320003e0, 'second OnModLoad ignored')

def test_modinfo():
    e = Emu(4096)
    p = e.call(MOD_BASE + e.mod['__GetModInfo'])
    raw = bytes(e.uc.mem_read(p, 176))
    f = [raw[i:j].split(b'\0')[0].decode() for i, j in ((0, 48), (48, 96), (96, 120), (120, 168))]
    check(f == ['net.helicover.touch4', 'Touch x4', '1.0', 'Helicover'], 'ModInfo strings %r' % f)
    check(struct.unpack('<4H', raw[168:176]) == (1, 0, 0, 0), 'ModInfo version')
    check(bytes(e.uc.mem_read(p + 176, 336)) == b'\0' * 336, 'ModInfo padding zero')

if __name__ == '__main__':
    if not GTA or not os.path.exists(GTA):
        print('SKIP: pass the path to libGTASA.so'); sys.exit(0)
    test_modinfo()
    for page in (4096, 16384):
        e = test_install(page)
        test_touches(e)
        test_switch(page)
        test_switch(page, fail=True)
        test_refuses(page)
    print('PASS', PASS)
