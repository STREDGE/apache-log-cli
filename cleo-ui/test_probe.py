#!/usr/bin/env python3
"""Runs libCleoUIProbe64.so on an emulated arm64 CPU (unicorn) against the real libGTASA.so.

usage: python3 cleo-ui/test_probe.py path/to/libGTASA.so [path/to/libCleoUIProbe64.so]

Checks that the probe only records: it patches exactly the four function entries (and none whose code differs), calls
coming from the game itself pass through untouched and unrecorded, calls from CLEO or from unpacked code are logged with
their arguments and reach the original function with the same arguments, and the memory copies never read a page that
cannot be read.
"""
import os, re, struct, subprocess, sys, tempfile
from unicorn import Uc, UcError, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_PROT_ALL, UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC, UC_HOOK_MEM_WRITE_PROT, UC_HOOK_MEM_FETCH_PROT, UC_HOOK_MEM_READ_UNMAPPED
from unicorn.arm64_const import *
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

HERE = os.path.dirname(os.path.abspath(__file__))
GTA = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('GTASA_SO', '')
MOD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'build', 'cleo-ui', 'libCleoUIProbe64.so')
SRC = open(os.path.join(HERE, 'cleoui_probe.c')).read()
OFF = {k: int(v, 16) for k, v in re.findall(r'#define OFF_(\w+) (0x[0-9a-f]+)UL', SRC)}
HOOKS = [('DrawRect', OFF['DRAWRECT']), ('DrawRect4', OFF['DRAWRECT4']), ('PrintString', OFF['PRINTSTRING']), ('GetStringWidth', OFF['STRWIDTH'])]

GTA_BASE, MOD_BASE, CLEO_BASE, ANON = 0x7000000000, 0x7100000000, 0x7200000000, 0x7300000000
STUB, STACK, SENT, DATA = 0x6000000000, 0x6100000000, 0x6200000000, 0x6300000000
MODS = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/mods/'
RET = 0xd65f03c0
R_RELATIVE, R_GLOB_DAT, R_JUMP_SLOT, R_ABS64 = 1027, 1025, 1026, 257
XREG = [UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5, UC_ARM64_REG_X6, UC_ARM64_REG_X7]
def u32(v): return struct.pack('<I', v & 0xffffffff)

def assemble(text):
    with tempfile.TemporaryDirectory() as d:
        open(d + '/a.s', 'w').write('.text\n' + text + '\n')
        subprocess.check_call(['clang', '--target=aarch64-linux-android21', '-c', d + '/a.s', '-o', d + '/a.o'])
        subprocess.check_call(['llvm-objcopy', '-O', 'binary', '--only-section=.text', d + '/a.o', d + '/a.bin'])
        return open(d + '/a.bin', 'rb').read()
# what stands in for the rest of each hooked function: undo the four prologue instructions and return
TAILS = {
    'DrawRect': 'ldp x29, x30, [sp, #0x10]\nldp x20, x19, [sp], #0x20\nret',
    'DrawRect4': 'ldp x29, x30, [sp, #0x30]\nldp x20, x19, [sp, #0x20]\nldp x22, x21, [sp, #0x10]\nldr x23, [sp], #0x40\nret',
    'PrintString': 'ldp x29, x30, [sp, #0x40]\nldp x20, x19, [sp, #0x30]\nldp d9, d8, [sp, #0x20]\nadd sp, sp, #0x50\nret',
    'GetStringWidth': 'ldp x24, x23, [sp, #0x30]\nldp x26, x25, [sp, #0x20]\nldp x28, x27, [sp, #0x10]\nldp d9, d8, [sp], #0x70\nfmov s0, #2.5\nret',
}
# dl_iterate_phdr: cb(info, size, data) for every module of the table at DATA (count at DATA+0x800)
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
TAIL_CODE = {k: assemble(v) for k, v in TAILS.items()}

class Emu:
    def __init__(self, page=4096, tweak=None, with_cleo=True, deny=()):
        self.page, self.deny = page, deny
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.imports, self.fs, self.fds, self.mprotects, self.conts = {}, {}, {}, [], []
        self.gta_img = None
        self.load(GTA, GTA_BASE, tweak, keep=True)
        self.load(MOD, MOD_BASE)
        uc.mem_map(STACK, 0x100000); uc.mem_map(SENT, 0x1000); uc.mem_write(SENT, u32(RET) * 4)
        uc.mem_map(DATA, 0x4000)
        # fake CLEO: 3 segments; the middle page of the second one is not readable (as a protector may leave it)
        uc.mem_map(CLEO_BASE, 0x10000, UC_PROT_READ | UC_PROT_EXEC)
        self.cleo_bytes = bytes((i * 7 + 3) & 0xff for i in range(0x10000))
        uc.mem_write(CLEO_BASE, self.cleo_bytes)
        self.unreadable = (CLEO_BASE + 0x5000, CLEO_BASE + 0x6000)
        uc.mem_map(ANON, 0x100000, UC_PROT_READ | UC_PROT_EXEC)           # unpacked code that belongs to no file
        self.anon_bytes = bytes((i * 13 + 1) & 0xff for i in range(0x100000)); uc.mem_write(ANON, self.anon_bytes)
        names = [b'/data/app/x/lib/arm64/libGTASA.so\0', b'/data/app/x/lib/arm64/libSAcleo64.so\0']
        ph = lambda t, fl, va, sz: struct.pack('<IIQQQQQQ', t, fl, va, va, va, sz, sz, 0x1000)
        f = ELFFile(open(GTA, 'rb'))
        gph = b''.join(ph(1, s['p_flags'], s['p_vaddr'], s['p_memsz']) for s in f.iter_segments() if s['p_type'] == 'PT_LOAD')
        cph = ph(6, 4, 0x40, 0x200) + ph(1, 5, 0, 0x3000) + ph(1, 6, 0x4000, 0x3800) + ph(1, 6, 0x9000, 0x6800)
        uc.mem_write(DATA + 0x1000, names[0]); uc.mem_write(DATA + 0x1100, names[1])
        uc.mem_write(DATA + 0x2000, gph); uc.mem_write(DATA + 0x3000, cph)
        uc.mem_write(DATA, struct.pack('<QQQHxxxxxx', GTA_BASE, DATA + 0x1000, DATA + 0x2000, len(gph) // 56))
        uc.mem_write(DATA + 0x20, struct.pack('<QQQHxxxxxx', CLEO_BASE, DATA + 0x1100, DATA + 0x3000, 4))
        uc.mem_write(DATA + 0x800, struct.pack('<Q', 2 if with_cleo else 1))
        self.fs_in = {'/proc/self/maps': b'7000000000-7000810000 r-xp 00000000 fd:01 1 /data/app/x/lib/arm64/libGTASA.so\n' * 300}
        self.font = DATA + 0x3800; uc.mem_write(self.font, bytes(range(0x40)))
        uc.mem_protect(GTA_BASE + (OFF['FONT_DETAILS_GOT'] & ~0xffff), 0x10000, UC_PROT_READ | UC_PROT_WRITE)
        uc.mem_write(GTA_BASE + OFF['FONT_DETAILS_GOT'], struct.pack('<Q', self.font))
        uc.mem_protect(GTA_BASE + (OFF['FONT_DETAILS_GOT'] & ~0xffff), 0x10000, UC_PROT_READ)
        for name, off in HOOKS:                                             # the rest of each function -> tail + recorder
            self.poke(GTA_BASE + off + 16, TAIL_CODE[name])
            uc.hook_add(UC_HOOK_CODE, self.on_cont, begin=GTA_BASE + off + 16, end=GTA_BASE + off + 16)
        uc.hook_add(UC_HOOK_MEM_WRITE_PROT, self.on_bad, None); uc.hook_add(UC_HOOK_MEM_FETCH_PROT, self.on_bad, None)
        self.snapshot = bytes(uc.mem_read(GTA_BASE, self.gta_size))

    def poke(self, addr, data):
        a = addr & ~0xffff; self.uc.mem_protect(a, 0x20000, UC_PROT_ALL); self.uc.mem_write(addr, data); self.uc.mem_protect(a, 0x20000, UC_PROT_READ | UC_PROT_EXEC)
    def on_bad(self, uc, access, addr, size, value, data):
        print('  protection fault at', hex(addr), 'pc', hex(uc.reg_read(UC_ARM64_REG_PC))); return False
    def on_cont(self, uc, addr, size, _):
        self.conts.append(dict(at=addr - GTA_BASE - 16, x=[uc.reg_read(r) for r in XREG[:5]], s0=uc.reg_read(UC_ARM64_REG_S0), s1=uc.reg_read(UC_ARM64_REG_S1), sp=uc.reg_read(UC_ARM64_REG_SP)))

    def load(self, path, base, tweak=None, keep=False):
        uc = self.uc; f = ELFFile(open(path, 'rb'))
        loads = [s for s in f.iter_segments() if s['p_type'] == 'PT_LOAD']
        size = (max(s['p_vaddr'] + s['p_memsz'] for s in loads) + 0xffff) & ~0xffff
        img = bytearray(size)
        for s in loads:
            d = s.data(); img[s['p_vaddr']:s['p_vaddr'] + len(d)] = d
        dsym = f.get_section_by_name('.dynsym')
        for sec in f.iter_sections():
            if not isinstance(sec, RelocationSection): continue
            for r in sec.iter_relocations():
                t, off = r['r_info_type'], r['r_offset']
                if t == R_RELATIVE: img[off:off + 8] = struct.pack('<Q', base + r['r_addend'])
                elif t in (R_GLOB_DAT, R_JUMP_SLOT, R_ABS64):
                    sym = dsym.get_symbol(r['r_info_sym'])
                    img[off:off + 8] = struct.pack('<Q', base + sym['st_value'] + (r['r_addend'] or 0) if sym['st_shndx'] != 'SHN_UNDEF' else self.stub_for(sym.name))
        if tweak: tweak(img)
        uc.mem_map(base, size, UC_PROT_ALL); uc.mem_write(base, bytes(img))
        P = self.page
        for s in loads:
            a = (s['p_vaddr'] // P) * P; e = -(-(s['p_vaddr'] + s['p_memsz']) // P) * P
            uc.mem_protect(base + a, e - a, (UC_PROT_READ if s['p_flags'] & 4 else 0) | (UC_PROT_WRITE if s['p_flags'] & 2 else 0) | (UC_PROT_EXEC if s['p_flags'] & 1 else 0))
        if keep: self.gta_size = size
        self.syms = {sym.name: sym['st_value'] for sym in dsym.iter_symbols()}

    def stub_for(self, name):
        if name not in self.imports:
            if not self.imports:
                self.uc.mem_map(STUB, 0x400000, UC_PROT_ALL)
                self.uc.hook_add(UC_HOOK_CODE, self.on_stub, begin=STUB, end=STUB + 0x3fffff)
            addr = STUB + 0x100 * len(self.imports); self.imports[name] = addr
            self.uc.mem_write(addr, ITER if name == 'dl_iterate_phdr' else u32(RET))
        return self.imports[name]
    def cstr(self, a): return bytes(self.uc.mem_read(a, 300)).split(b'\0')[0].decode()
    def readable(self, a, n):
        if self.unreadable[0] < a + n and a < self.unreadable[1]: return None
        try: return bytes(self.uc.mem_read(a, n))
        except UcError: return None
    def on_stub(self, uc, addr, size, _):
        names = {v: k for k, v in self.imports.items()}
        if addr not in names: return
        n = names[addr]; x = [uc.reg_read(r) for r in XREG]; ret = 0
        if n == 'dl_iterate_phdr': return
        if n == 'getpagesize': ret = self.page
        elif n == 'mprotect':
            assert x[0] % self.page == 0 and x[1] % self.page == 0, ('unaligned mprotect', hex(x[0]), hex(x[1]))
            assert GTA_BASE <= x[0] < GTA_BASE + self.gta_size, 'mprotect outside the game'
            self.mprotects.append((x[0], x[1], x[2]))
            uc.mem_protect(x[0], x[1], (UC_PROT_READ if x[2] & 1 else 0) | (UC_PROT_WRITE if x[2] & 2 else 0) | (UC_PROT_EXEC if x[2] & 4 else 0))
        elif n == 'open':
            path = self.cstr(x[0])
            if x[1] & 3 == 0:
                if path in self.fs_in: ret = 100 + len(self.fds); self.fds[ret] = [path, 0]
                else: ret = (1 << 64) - 1
            elif any(d in path for d in self.deny): ret = (1 << 64) - 1
            else:
                assert path.startswith(MODS), 'writes outside the mods folder: ' + path
                ret = 100 + len(self.fds); self.fds[ret] = [path, None]; self.fs[path] = b''
        elif n == 'read':
            path, pos = self.fds[x[0]]; d = self.fs_in[path][pos:pos + x[2]]; uc.mem_write(x[1], d); self.fds[x[0]][1] = pos + len(d); ret = len(d)
        elif n == 'write':
            d = self.readable(x[1], x[2])
            if d is None: ret = (1 << 64) - 14                              # -EFAULT, as the kernel does
            else: self.fs[self.fds[x[0]][0]] += d; ret = x[2]
        elif n == 'close': pass
        elif n == 'dladdr':
            a = x[0]; ret = 0
            for base, sz, nm in ((GTA_BASE, self.gta_size, DATA + 0x1000), (CLEO_BASE, 0x10000, DATA + 0x1100)):
                if base <= a < base + sz: uc.mem_write(x[1], struct.pack('<QQQQ', nm, base, 0, 0)); ret = 1
        else: raise AssertionError('unexpected import ' + n)
        uc.reg_write(UC_ARM64_REG_X0, ret)

    def call(self, addr, x=(), s=(), lr=SENT):
        uc = self.uc
        for i, v in enumerate(x): uc.reg_write(XREG[i], v)
        for i, v in enumerate(s): uc.reg_write([UC_ARM64_REG_S0, UC_ARM64_REG_S1][i], v)
        uc.reg_write(UC_ARM64_REG_SP, STACK + 0x80000); uc.reg_write(UC_ARM64_REG_X30, lr)
        uc.reg_write(UC_ARM64_REG_X19, 0x1919); uc.reg_write(UC_ARM64_REG_X20, 0x2020)
        uc.emu_start(addr, lr, count=3000000)
        assert uc.reg_read(UC_ARM64_REG_PC) == lr, 'did not return'
        assert uc.reg_read(UC_ARM64_REG_SP) == STACK + 0x80000 and uc.reg_read(UC_ARM64_REG_X19) == 0x1919 and uc.reg_read(UC_ARM64_REG_X20) == 0x2020, 'stack or callee-saved registers not restored'
        return uc.reg_read(UC_ARM64_REG_X0)
    def load_mod(self): self.call(MOD_BASE + self.syms['OnModLoad'])
    def log(self): return self.fs.get(MODS + 'cleoui_log.txt', b'').decode()
    def changed(self):
        now = bytes(self.uc.mem_read(GTA_BASE, self.gta_size)); out = []; i = 0
        while True:
            i = next((k for k in range(i, self.gta_size, 4) if now[k:k + 4] != self.snapshot[k:k + 4]), None) if now != self.snapshot else None
            if i is None: break
            j = i
            while now[j:j + 4] != self.snapshot[j:j + 4]: j += 4
            out.append((i, j - i)); i = j
        return out

def fbits(f): return struct.unpack('<I', struct.pack('<f', f))[0]
passed = []
def ok(t): passed.append(t); print('PASS:', t)

def main():
    for page in (4096, 16384):
        e = Emu(page); e.load_mod(); log = e.log()
        assert e.changed() == [(off, 16) for _, off in sorted(HOOKS, key=lambda h: h[1])], e.changed()
        for name, off in HOOKS:
            words = struct.unpack('<IIQ', bytes(e.uc.mem_read(GTA_BASE + off, 16)))
            assert words[0] == 0x58000051 and words[1] == 0xd61f0220 and MOD_BASE <= words[2] < MOD_BASE + 0x100000, name
            assert name + ': recording' in log
        assert all(p[2] in (5, 7) for p in e.mprotects) and [p[2] for p in e.mprotects][-1] == 5, e.mprotects
        assert 'hooks: 4 of 4' in log and 'changes nothing' in log
        ok('page %d: exactly the four function entries are redirected (16 bytes each), memory protection is put back' % page)
    e = Emu(); e.load_mod()
    d1 = e.fs[MODS + 'cleoui_dump_1.bin']
    assert len(d1) == 0xf800 and d1[:0x5000] == e.cleo_bytes[:0x5000] and d1[0x5000:0x6000] == bytes(0x1000) and d1[0x6000:] == e.cleo_bytes[0x6000:0xf800]
    assert 'unreadable pages 1' in e.log() and 'libSAcleo64.so base' in e.log()
    assert e.fs[MODS + 'cleoui_maps.txt'] == e.fs_in['/proc/self/maps']
    assert all(p.startswith(MODS + 'cleoui_') for p in e.fs)
    ok('At load: a copy of CLEO as it is in memory (a page that cannot be read becomes zeros, no crash), the memory map, all files in the mods folder')

    rect, rgba = DATA + 0x3900, DATA + 0x3920
    e.uc.mem_write(rect, struct.pack('<4f', 10.5, 200.0, 300.25, 20.0)); e.uc.mem_write(rgba, bytes([55, 127, 175, 150]))
    base_log = e.log()
    e.call(GTA_BASE + HOOKS[0][1], x=(rect, rgba), lr=SENT)                  # SENT stands for "somewhere" - set as inside the game below
    # a call from the game itself: lr inside libGTASA
    e2 = Emu(); e2.load_mod(); n0 = len(e2.log()); e2.conts.clear()
    inner = GTA_BASE + 0x51f700
    e2.poke(inner, u32(RET))
    e2.uc.mem_write(rect, struct.pack('<4f', 1, 2, 3, 4)) if False else None
    e2.uc.mem_write(DATA + 0x3900, struct.pack('<4f', 10.5, 200.0, 300.25, 20.0)); e2.uc.mem_write(DATA + 0x3920, bytes([55, 127, 175, 150]))
    for name, off in HOOKS[:2]:
        e2.call(GTA_BASE + off, x=(rect, rgba, 0x33, 0x44, 0x55), lr=inner)
    assert [c['at'] for c in e2.conts] == [HOOKS[0][1], HOOKS[1][1]] and all(c['x'] == [rect, rgba, 0x33, 0x44, 0x55] for c in e2.conts), e2.conts
    assert len(e2.log()) == n0 and MODS + 'cleoui_dump_2.bin' not in e2.fs
    ok('A call from the game itself reaches the original function with its arguments and is not recorded')

    # calls from CLEO
    cl = CLEO_BASE + 0x1234
    e3 = Emu(); e3.load_mod(); e3.conts.clear()
    e3.uc.mem_write(rect, struct.pack('<4f', 10.5, 200.0, 300.25, 20.0)); e3.uc.mem_write(rgba, bytes([55, 127, 175, 150]))
    for k in range(9): e3.call(GTA_BASE + HOOKS[0][1], x=(rect, rgba), lr=cl)
    lines = [l for l in e3.log().split('\n') if l.startswith('DrawRect <- ')]
    want = 'DrawRect <- libSAcleo64.so+0x0000000000001234 : rect %08x %08x %08x %08x rgba 377faf96' % tuple(fbits(v) for v in (10.5, 200.0, 300.25, 20.0))
    assert lines == [want] * 6, lines
    assert len(e3.conts) == 9 and all(c['x'][:2] == [rect, rgba] for c in e3.conts)
    assert e3.fs[MODS + 'cleoui_dump_2.bin'][:0x100] == e3.cleo_bytes[:0x100] and 'first call from outside the game' in e3.log()
    ok('A call from CLEO is logged with the rectangle and the colour (6 samples per call site), still reaches the original, and triggers a second copy of CLEO')
    text = DATA + 0x3a00; s = 'Helicover Ж"'.encode('utf-16le') + b'\0\0'; e3.uc.mem_write(text, s)
    e3.conts.clear(); e3.call(GTA_BASE + HOOKS[2][1], x=(text,), s=(fbits(320.0), fbits(48.5)), lr=CLEO_BASE + 0x2000)
    c = e3.conts[-1]; assert c['at'] == HOOKS[2][1] and c['x'][0] == text and c['s0'] == fbits(320.0) and c['s1'] == fbits(48.5), c
    line = [l for l in e3.log().split('\n') if l.startswith('PrintString <- ')][-1]
    assert ' xy %08x %08x text "Helicover \\0416\\0022"' % (fbits(320.0), fbits(48.5)) in line and ' font 00010203 04050607' in line, line
    ok('PrintString from CLEO: position, text (non-ASCII as codes) and the font state are logged; x, y and the text reach the original')
    e3.uc.reg_write(UC_ARM64_REG_S0, 0)
    e3.call(GTA_BASE + HOOKS[3][1], x=(text, 1, 0), lr=CLEO_BASE + 0x2400)
    assert e3.uc.reg_read(UC_ARM64_REG_S0) == fbits(2.5) and 'GetStringWidth <- libSAcleo64.so+0x0000000000002400 : text "Helicover' in e3.log()
    e3.call(GTA_BASE + HOOKS[1][1], x=(rect, rgba, rgba, rgba, rgba), lr=CLEO_BASE + 0x2800)
    assert 'DrawRect4 <- libSAcleo64.so+0x0000000000002800 : rect' in e3.log() and e3.log().count('rgba 377faf96') >= 10
    ok('GetStringWidth passes the result of the original back; the four-colour rectangle is logged too')

    # a caller that belongs to no file (code the protector unpacked)
    e4 = Emu(); e4.load_mod(); e4.uc.mem_write(rect, bytes(16)); e4.uc.mem_write(rgba, bytes(4))
    for k in range(5): e4.call(GTA_BASE + HOOKS[0][1], x=(rect, rgba), lr=ANON + 0x50000 + 0x100 * k)
    assert 'DrawRect <- (no file) 0x%016x' % (ANON + 0x50000) in e4.log()
    a1 = e4.fs[MODS + 'cleoui_anon_1.bin']
    assert len(a1) == 0x80000 and a1 == e4.anon_bytes[0x10000:0x90000] and 'anon 1: file offset 0 = address 0x%016x' % (ANON + 0x10000) in e4.log()
    assert sorted(p for p in e4.fs if 'anon' in p) == [MODS + 'cleoui_anon_%d.bin' % i for i in (1, 2, 3)], 'at most three such copies'
    e5 = Emu(); e5.load_mod(); e5.uc.mem_write(rect, bytes(16)); e5.uc.mem_write(rgba, bytes(4))
    e5.call(GTA_BASE + HOOKS[0][1], x=(rect, rgba), lr=ANON + 0x1000)       # 256 KB before it is not mapped at all
    a = e5.fs[MODS + 'cleoui_anon_1.bin']; assert len(a) == 0x80000 and a[:0x3f000] == bytes(0x3f000) and a[0x3f000:] == e5.anon_bytes[:0x41000]
    ok('A caller in unpacked code (no file): logged by address, the memory around it is copied; unmapped pages become zeros without a crash')

    # null arguments, many call sites
    e6 = Emu(); e6.load_mod()
    e6.call(GTA_BASE + HOOKS[0][1], x=(0, 0), lr=CLEO_BASE + 0x100); e6.call(GTA_BASE + HOOKS[2][1], x=(0,), s=(0, 0), lr=CLEO_BASE + 0x104)
    assert 'rect=null rgba=null' in e6.log() and 'text=null' in e6.log()
    for k in range(60): e6.call(GTA_BASE + HOOKS[0][1], x=(0, 0), lr=CLEO_BASE + 0x4000 + 4 * k)
    assert e6.log().count('DrawRect <- ') == 40, e6.log().count('DrawRect <- ')
    e6.uc.mem_write(rect, bytes(16)); e6.uc.mem_write(rgba, bytes(4))
    for k in range(3200): e6.call(GTA_BASE + HOOKS[2][1], x=(0,), s=(0, 0), lr=CLEO_BASE + 0x104)
    assert '--- calls so far' in e6.log() and 'PrintString <- libSAcleo64.so+0x0000000000000104 x' in e6.log() and 'after 400 calls' in e6.log()
    assert len(e6.log()) < 100000
    ok('Null arguments are survived; at most 40 call sites per function are kept; a summary with call counts and a third copy of CLEO follow')

    # CLEO loaded later than the mod
    e7 = Emu(with_cleo=False); e7.load_mod()
    assert 'not loaded yet' in e7.log() and MODS + 'cleoui_dump_1.bin' not in e7.fs and 'hooks: 4 of 4' in e7.log()
    e7.uc.mem_write(DATA + 0x800, struct.pack('<Q', 2))
    e7.call(GTA_BASE + HOOKS[0][1], x=(0, 0), lr=CLEO_BASE + 0x500)
    assert 'DrawRect <- libSAcleo64.so+0x0000000000000500' in e7.log() and MODS + 'cleoui_dump_1.bin' in e7.fs
    ok('CLEO loaded after the mod is found at the first recorded call')

    # other game code: that hook is skipped, the rest work; no game at all: nothing
    for k, (name, off) in enumerate(HOOKS):
        def tweak(img, off=off): img[off + 8:off + 12] = u32(0xd503201f)
        e8 = Emu(tweak=tweak); e8.load_mod()
        assert name + ': the game code differs' in e8.log() and 'hooks: 3 of 4' in e8.log()
        assert e8.changed() == [(o, 16) for _, o in sorted(HOOKS, key=lambda h: h[1]) if o != off]
    ok('A function whose first instructions differ (another mod, another game version) is left alone; the other three are recorded')
    e9 = Emu(deny=('cleoui_',)); e9.load_mod(); e9.call(GTA_BASE + HOOKS[0][1], x=(0, 0), lr=CLEO_BASE + 0x100)
    assert not e9.fs and len(e9.conts) == 1
    ok('If the mods folder cannot be written the game still runs: calls pass through, nothing else happens')
    print('%d checks passed' % len(passed))

if __name__ == '__main__':
    if not GTA: sys.exit('usage: test_probe.py path/to/libGTASA.so')
    main()
