#!/usr/bin/env python3
"""Runs libCleoUI64.so together with the REAL menu-drawing code of the unpacked CLEO library on an emulated arm64 CPU.

usage: python3 cleo-ui/test_cleoui.py path/to/libSAcleo64.so.image [path/to/libCleoUI64.so]
(the .image file is written by cleo-ui/tools/unpack_cleo.py from the user's libSAcleo64.so)

CLEO's own function that draws a script menu is executed; what finally reaches the game (CSprite2d::Draw2DPolygon and
CFont::PrintString, replaced by recorders) is compared with and without the mod.
"""
import os, struct, subprocess, sys, tempfile
from unicorn import *
from unicorn.arm64_const import *
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE = sys.argv[1] if len(sys.argv) > 1 else ''
MOD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'build', 'cleo-ui', 'libCleoUI64.so')
CLEO, IMG = 0x7200000000, 0x88000              # the image was produced at this base; the unpacked library starts at +0x88000
OLDSTUB = 0x7600000000                         # where the unpacker's import stubs were (addresses baked into the image)
GTA, MODB, STUB, STACK, DATA, SENT = 0x7000000000, 0x7100000000, 0x6000000000, 0x6100000000, 0x6300000000, 0x6200000000
G = lambda off: CLEO + IMG + off
RECT_PTR, TEXT_PTR, RECT_FN, TEXT_FN, MENU_FN = G(0x27d3b8), G(0x27d3c0), G(0x3659c), G(0x365dc), G(0x36d70)
P_POLY, P_DETAILS, P_STYLE, P_PRINT, P_RS = G(0x27d3d8), G(0x27d3f0), G(0x27d3f8), G(0x27d400), G(0x27d408)
TITLE, CLOSE, ROWS, PAGES, SELECTED, FLASH, PAGE = G(0x27d820), G(0x27d838), G(0x27d850), G(0x27d868), G(0x27d86c), G(0x27d87c), G(0x7cfcc)
W, H = 1920, 1080
MODS = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/mods/'
CFG = '/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/configs/net.helicover.cleoui.ini'
RET = struct.pack('<I', 0xd65f03c0)
X = [UC_ARM64_REG_X0 + i for i in range(8)]; S = [UC_ARM64_REG_S0 + i for i in range(8)]
def fl(v): return struct.unpack('<f', struct.pack('<I', v & 0xffffffff))[0]

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
IMG_BYTES = open(IMAGE, 'rb').read() if IMAGE else b''

class Emu:
    def __init__(self, cfg=None, started=True, tweak=None, sautils=True, size=None, measure=True):
        self.W, self.H = size or (W, H); self.measure = measure
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.imports, self.fs, self.fds, self.polys, self.prints, self.items, self.threads = {}, {}, {}, [], [], [], []
        self.style = 0
        self.now, self.sautils, self.sleeps, self.on_sleep = 100000, sautils, 0, None
        if cfg is not None: self.fs[CFG] = cfg
        size = (len(IMG_BYTES) + 0xffff) & ~0xffff
        uc.mem_map(CLEO, size); uc.mem_write(CLEO, IMG_BYTES); self.cleo_size = size
        uc.mem_map(OLDSTUB, 0x100000); uc.mem_write(OLDSTUB, RET * (0x100000 // 4))
        uc.mem_map(GTA, 0xd00000); uc.mem_write(GTA + 0x6cdeb0, struct.pack('<II', 0xd10143ff, 0x6d0223e9))
        if measure: uc.mem_write(GTA + 0x6ce760, struct.pack('<II', 0x6db923e9, 0xa9016ffc)); uc.hook_add(UC_HOOK_CODE, self.on_width, begin=GTA + 0x6ce760, end=GTA + 0x6ce760)
        uc.mem_map(STUB, 0x10000); uc.mem_map(STACK, 0x100000); uc.mem_map(DATA, 0x10000); uc.mem_map(SENT, 0x1000); uc.mem_write(SENT, RET * 4)
        uc.hook_add(UC_HOOK_CODE, self.on_stub, begin=STUB, end=STUB + 0xffff)
        # what CLEO's start-up would have filled in
        if started:
            for ptr, val in ((RECT_PTR, RECT_FN), (TEXT_PTR, TEXT_FN)): uc.mem_write(ptr, struct.pack('<Q', val))
        else:
            uc.mem_write(RECT_PTR, bytes(16))
        uc.mem_write(G(0x27d3d0), bytes([0x28, 0xeb, 0x18, 0xff])); uc.mem_write(G(0x27d3c8), bytes([0x37, 0x7f, 0xaf, 0x64, 0xb4]))   # colours CLEO's start-up sets
        uc.mem_write(P_POLY, struct.pack('<Q', self.stub('game:poly'))); uc.mem_write(P_PRINT, struct.pack('<Q', self.stub('game:print')))
        uc.mem_write(P_STYLE, struct.pack('<Q', self.stub('game:style')))
        self.details = DATA + 0x4000; uc.mem_write(P_DETAILS, struct.pack('<Q', self.details))
        self.rs = DATA + 0x4100; uc.mem_write(self.rs + 8, struct.pack('<ii', self.W, self.H)); uc.mem_write(P_RS, struct.pack('<Q', self.rs))
        if tweak: tweak(self)
        names = [b'/data/app/x/lib/arm64/libGTASA.so\0', b'/data/app/x/lib/arm64/libSAcleo64.so\0']
        ph = lambda va, sz: struct.pack('<IIQQQQQQ', 1, 6, va, va, va, sz, sz, 0x1000)
        uc.mem_write(DATA + 0x1000, names[0]); uc.mem_write(DATA + 0x1100, names[1])
        uc.mem_write(DATA + 0x2000, ph(0, 0xd00000)); uc.mem_write(DATA + 0x3000, ph(0, 0x37160) + ph(0x4f830, getattr(self, 'cleo_memsz', 0x2bf790)))
        uc.mem_write(DATA, struct.pack('<QQQHxxxxxx', GTA, DATA + 0x1000, DATA + 0x2000, 1) + struct.pack('<QQQHxxxxxx', CLEO, DATA + 0x1100, DATA + 0x3000, 2))
        uc.mem_write(DATA + 0x800, struct.pack('<Q', 2))
        self.tls = DATA + 0x5000; uc.mem_write(self.tls + 0x28, struct.pack('<Q', 0x1122334455667788)); uc.reg_write(UC_ARM64_REG_TPIDR_EL0, self.tls)
        uc.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
        self.sau = DATA + 0x6000; uc.mem_write(self.sau, struct.pack('<Q', self.sau + 0x100)); uc.mem_write(self.sau + 0x100, b''.join(struct.pack('<Q', self.stub('sau:%d' % i)) for i in range(8)))
        self.heap = DATA + 0x8000
        self.load_mod()
        self.before = bytes(uc.mem_read(CLEO, size))

    def load_mod(self):
        uc = self.uc; f = ELFFile(open(MOD, 'rb')); loads = [s for s in f.iter_segments() if s['p_type'] == 'PT_LOAD']
        size = (max(s['p_vaddr'] + s['p_memsz'] for s in loads) + 0xffff) & ~0xffff; img = bytearray(size)
        for s in loads: d = s.data(); img[s['p_vaddr']:s['p_vaddr'] + len(d)] = d
        dsym = f.get_section_by_name('.dynsym')
        for sec in f.iter_sections():
            if not isinstance(sec, RelocationSection): continue
            for r in sec.iter_relocations():
                t, off = r['r_info_type'], r['r_offset']
                if t == 1027: img[off:off + 8] = struct.pack('<Q', MODB + r['r_addend'])
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
    def cstr(self, a): return bytes(self.uc.mem_read(a, 300)).split(b'\0')[0].decode()
    def wstr(self, a):
        out = []
        while True:
            c, = struct.unpack('<H', bytes(self.uc.mem_read(a + 2 * len(out), 2)))
            if not c or len(out) > 300: return out
            out.append(c)
    def on_stub(self, uc, addr, size, _):
        names = {v: k for k, v in self.imports.items()}
        if addr not in names: return
        n = names[addr]; x = [uc.reg_read(r) for r in X]; ret = x[0]
        if n == 'dl_iterate_phdr': return
        if n == 'game:poly':
            self.polys.append(dict(c=tuple(uc.mem_read(x[0], 4)), p=[round(fl(uc.reg_read(r)), 2) for r in S]))
        elif n == 'game:print':
            det = bytes(uc.mem_read(self.details, 0x40))
            self.prints.append(dict(x=round(fl(uc.reg_read(S[0])), 1), y=round(fl(uc.reg_read(S[1])), 1), t=self.wstr(x[0]), c=tuple(det[0:4]), scale=struct.unpack('<ff', det[4:12]),
                                    align='left' if det[0x18] else 'right' if det[0x1a] else 'centre', style=self.style, w=self.width_px(self.wstr(x[0]), struct.unpack('<f', det[4:8])[0])))
        elif n == 'game:style': self.style = x[0] & 0xff
        elif n == 'open':
            path = self.cstr(x[0])
            if x[1] & 3 == 0: ret = (1 << 64) - 1 if path not in self.fs else self._fd(path, 0)
            else: self.fs[path] = b''; ret = self._fd(path, None)
        elif n == 'read':
            path, pos = self.fds[x[0]]; d = self.fs[path][pos:pos + x[2]]; uc.mem_write(x[1], d); self.fds[x[0]][1] = pos + len(d); ret = len(d)
        elif n == 'write': self.fs[self.fds[x[0]][0]] += bytes(uc.mem_read(x[1], x[2])); ret = x[2]
        elif n == 'close': ret = 0
        elif n == 'dlopen': ret = 0xa31 if self.cstr(x[0]) == 'libAML.so' else 0
        elif n == 'dlsym': assert self.cstr(x[1]) == 'GetInterface'; ret = self.stub('aml:GetInterface')
        elif n == 'aml:GetInterface': ret = self.sau if self.cstr(x[0]) == 'SAUtils' and self.sautils else 0
        elif n == 'sau:3':
            sw = [self.cstr(struct.unpack('<Q', bytes(uc.mem_read(x[6] + 8 * i, 8)))[0]) for i in range(x[5] + 1)]
            self.items.append(dict(type=x[1], name=self.cstr(x[2]), init=x[3], lo=x[4], hi=x[5], sw=sw, cb=x[7])); ret = 40 + len(self.items)
        elif n == 'pthread_create': self.threads.append((x[2], x[3])); ret = 0
        elif n == 'usleep':
            self.sleeps += 1; self.now += x[0] // 1000; ret = 0
            if self.on_sleep: self.on_sleep(self)
        elif n == 'clock_gettime': uc.mem_write(x[1], struct.pack('<qq', self.now // 1000, (self.now % 1000) * 1000000)); ret = 0
        else: raise AssertionError('unexpected import ' + n)
        uc.reg_write(UC_ARM64_REG_X0, ret & (2 ** 64 - 1))
    # the game's font, as measured on the user's screenshots: advance per character in 640-wide units at scale 1
    def width_px(self, chars, sx):
        adv = lambda c: 2.9 if c == 32 else 5.4 if c >= 0x80 or 65 <= c <= 90 else 4.2 if 48 <= c <= 57 else 2.4 if 97 <= c <= 122 else 2.8
        return sum(adv(c) for c in chars) * sx * self.W / 640.0
    def on_width(self, uc, addr, size, _):
        sx, = struct.unpack('<f', bytes(uc.mem_read(self.details + 4, 4)))
        self.measured = getattr(self, 'measured', 0) + 1
        uc.reg_write(S[0], struct.unpack('<I', struct.pack('<f', self.width_px(self.wstr(uc.reg_read(X[0])), sx)))[0])
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
    def _fd(self, path, pos):
        fd = 100 + len(self.fds); self.fds[fd] = [path, pos]; return fd
    def call(self, addr, x=(), s=()):
        uc = self.uc
        for i, v in enumerate(x): uc.reg_write(X[i], v)
        for i, v in enumerate(s): uc.reg_write(S[i], struct.unpack('<I', struct.pack('<f', v))[0])
        uc.reg_write(UC_ARM64_REG_SP, STACK + 0x80000); uc.reg_write(UC_ARM64_REG_X30, SENT)
        uc.emu_start(addr, SENT, count=5000000)
        assert uc.reg_read(UC_ARM64_REG_PC) == SENT and uc.reg_read(UC_ARM64_REG_SP) == STACK + 0x80000
        return uc.reg_read(UC_ARM64_REG_X0)
    def load(self): self.call(MODB + self.syms['OnModLoad'])
    def log(self): return self.fs.get(MODS + 'cleoui_log.txt', b'').decode()
    def changed(self):
        now = bytes(self.uc.mem_read(CLEO, self.cleo_size))
        return [i for i in range(0, self.cleo_size, 8) if now[i:i + 8] != self.before[i:i + 8]]
    def ptrs(self): return struct.unpack('<QQ', bytes(self.uc.mem_read(RECT_PTR, 16)))
    # ----- a script menu, the way CLEO keeps it: std::string title / close caption, vector<std::u16string> rows
    def alloc(self, data):
        a = self.heap; self.heap += (len(data) + 0x1f) & ~0xf; self.uc.mem_write(a, data); return a
    def set_menu(self, title, close, rows, selected=-1, flash=0):
        uc = self.uc
        for where, text in ((TITLE, title), (CLOSE, close)):
            p = self.alloc(text + b'\0'); uc.mem_write(where, struct.pack('<QQQ', 0x41, len(text), p))            # long form
        vec = b''
        for r in rows:
            p = self.alloc(b''.join(struct.pack('<H', c) for c in r) + b'\0\0'); vec += struct.pack('<QQQ', 0x41, len(r), p)
        v = self.alloc(vec); uc.mem_write(ROWS, struct.pack('<QQQ', v, v + len(vec), v + len(vec)))
        uc.mem_write(PAGES, struct.pack('<i', 1)); uc.mem_write(SELECTED, struct.pack('<i', selected)); uc.mem_write(FLASH, struct.pack('<i', flash)); uc.mem_write(PAGE, struct.pack('<i', 0))
    def draw(self):
        self.polys, self.prints = [], []; self.call(MENU_FN); return self.polys, self.prints
    def setting(self, name, value):
        it = [i for i in self.items if i['name'] == name][0]; self.call(it['cb'], x=(it['init'], value, 0)); it['init'] = value

def A(s): return [ord(c) for c in s]
passed = []
def ok(t): passed.append(t); print('PASS:', t)
ROWS3 = [A('FOLLOW ME [X]'), A('HOLD HERE'), A('DISMISS HELICOPTER')]
ROWS8 = ROWS3 + [A('ROW %d' % i) for i in range(4, 9)]
BLUE, ORANGE = (55, 127, 175), (255, 140, 0)
TAP_FN, CLOSE_BOX = G(0x36b1c), G(0x27d880)
SIZES = ((2000, 1250), (2400, 1080), (1280, 720), (1024, 768))

def steady(e, extra=()):
    """a menu that has been open for a while: frames 120 ms apart (less than the 250 ms that count as closing)"""
    for dt in (0, 120, 120, 160) + tuple(extra): e.now += dt; out = e.draw()
    return out
def body(p): return max((q for q in p if q['c'][:3] in ((27, 29, 40), (8, 9, 13), (21, 23, 32))), key=lambda q: q['p'][2] - q['p'][0])
def panel_box(p):
    qs = [q for q in p if q['c'][:3] in ((27, 29, 40), (8, 9, 13), (21, 23, 32)) and q['c'][3] > 200]
    main = max(qs, key=lambda q: q['p'][2] - q['p'][0]); L, R = main['p'][0], main['p'][2]
    qs = [q for q in qs if abs(q['p'][0] - L) < 2 or abs(q['p'][2] - R) < 2]
    return L, min(q['p'][1] for q in qs), R, max(q['p'][7] for q in qs)
def glyph_h(x, H): return (0.0089 / 1.3 if x['style'] == 2 else 0.0108 / 1.5) * x['scale'][1] * H
def tap(e, x, y): e.call(TAP_FN, s=(round(x, 2), round(y, 2)))                    # CLEO rounds a tap to whole per cent
def selected(e): return struct.unpack('<i', bytes(e.uc.mem_read(SELECTED, 4)))[0]
def close_box(e): return struct.unpack('<4f', bytes(e.uc.mem_read(CLOSE_BOX, 16)))

def main():
    # ---- what CLEO draws by itself (the reference), and the mod switched off
    ref = Emu(cfg=b'[Preferences]\nEnabled = 0\n'); ref.load(); ref_changed = ref.changed(); ref.set_menu(b'HELICOVER / FOLLOWING', b'CLOSE', ROWS3)
    rp, rt = ref.draw()
    assert len(rp) == 1 and rp[0]['c'] == BLUE + (150,) and rp[0]['p'] == [0.35 * W, 0.12 * H, 0.65 * W, 0.12 * H, 0.35 * W, 0.92 * H, 0.65 * W, 0.92 * H], rp
    assert [x['t'] for x in rt] == [A('HELICOVER / FOLLOWING'), A('CLOSE')] + ROWS3 and [x['y'] for x in rt[2:]] == [round(H * y, 1) for y in (0.2, 0.29, 0.38)], rt
    ok('The emulator runs CLEO\'s real menu code: one blue panel (55,127,175,150) and title, close caption and rows as texts')
    assert ref_changed == [RECT_PTR - CLEO, TEXT_PTR - CLEO] and all(MODB <= q < MODB + ref.mod_size for q in ref.ptrs())
    assert [round(v, 2) for v in close_box(ref)] == [0.2, 0.87, 0.3, 0.97]
    ok('Switched off in the settings, the mod passes everything through: the same calls reach the game, CLEO\'s touch box of CLOSE is untouched')

    e = Emu(); e.load()
    assert e.changed() == [RECT_PTR - CLEO, TEXT_PTR - CLEO], [hex(x) for x in e.changed()]
    assert 'new look installed' in e.log() and not e.threads and 'CLEO UI 0.2' in e.log()
    assert [i['name'] for i in e.items] == ['CLEO UI', 'CLEO UI Colour', 'CLEO UI Animation', 'CLEO UI Dim'] and e.items[1]['sw'] == ['Orange', 'Blue', 'Green', 'Red', 'White'] and all(i['type'] == 5 for i in e.items)
    ok('Install: exactly two pointers in CLEO\'s data are replaced (no code is written anywhere); four items in Mods Settings')

    # ---- the look
    e.set_menu(b'HELICOVER / FOLLOWING', b'CLOSE', ROWS3); p, t = steady(e)
    assert not [q for q in p if q['c'][:3] == BLUE], 'no blue rectangle is left'
    assert p[0]['c'][:3] == (0, 0, 0) and p[0]['p'] == [0, 0, W, 0, 0, H, W, H] and 90 <= p[0]['c'][3] <= 110, ('the screen behind the menu is dimmed', p[0])
    L, top, R, bot = panel_box(p)
    assert L <= 0.38 * W - 20 and R >= 0.62 * W + 20 and L >= 0.335 * W - 1 and R <= 0.665 * W + 1, (L, R)
    assert abs(bot - (0.21 + 0.09 * 3) * H) < 2 and abs(top - 0.075 * H) < 2, (top, bot)
    assert len([q for q in p if q['c'][:3] == ORANGE]) > 20 and [q for q in p if q['c'][:3] == ORANGE and q['c'][3] < 40], 'accent outline with a soft glow'
    cut = [q for q in p if q['p'][0] != q['p'][4] or q['p'][2] != q['p'][6]]
    assert len(cut) >= 8, 'slanted shapes: cut corners, header wedge and stripes'
    assert [x['t'] for x in t] == [x['t'] for x in rt]
    for x, r, y in zip(t[2:], rt[2:], (0.2, 0.29, 0.38)):
        assert x['x'] == W / 2 and x['align'] == 'centre'
        gt = x['y'] + 0.003 * H; gb = gt + glyph_h(x, H)
        assert (y + 0.01) * H <= gt and gb <= (y + 0.08) * H and abs((gt + gb) / 2 - (y + 0.045) * H) < 3, ('row text is centred in CLEO\'s touch cell', y, gt, gb)
    assert t[2]['c'][:3] == ORANGE and t[3]['c'][:3] == (238, 238, 240), 'the row marked [X] is accent-coloured'
    title = t[0]; gt = title['y'] + 0.003 * H; assert abs(gt + glyph_h(title, H) / 2 - 0.125 * H) < 3 and title['x'] == W / 2
    ok('New look: dimmed screen, dark panel with cut corners, accent outline with glow, header wedge and stripes; the title is centred in the header, each row text in its touch cell; the [X] row is accent-coloured')

    # ---- every screen shape
    for size in SIZES:
        w, h = size; s = Emu(size=size); s.load(); s.set_menu(b'HELICOVER / FOLLOWING', b'CLOSE', ROWS8); p, t = steady(s)
        L, top, R, bot = panel_box(p)
        assert L < 0.38 * w - 0.01 * w and R > 0.62 * w + 0.01 * w and L >= 0.335 * w - 1 and R <= 0.665 * w + 1, (size, L, R)
        assert 0.48 * h <= R - L <= 0.72 * h or R - L >= 0.27 * w - 1, (size, R - L)
        assert top >= 0.05 * h and bot <= 0.95 * h, (size, top, bot)
        for q in p:
            x = q['p']
            if q['c'][:3] == (255, 255, 255) or x[0] != x[4] or x[2] != x[6]: continue          # hairlines (1 px by design) and slanted shapes
            assert x[2] - x[0] >= 1.9 and x[5] - x[1] >= 1.9, ('nothing thinner than 2 px', size, q)
        for x in t: assert x['x'] - x['w'] / 2 >= L - w * 0.3 and (x['align'] != 'centre' or (x['x'] - x['w'] / 2 >= L and x['x'] + x['w'] / 2 <= R) or x is t[1]), (size, x)
        s.now += 16; tab = close_box(s); cx, cy = (tab[0] + tab[2]) / 2, (tab[1] + tab[3]) / 2
        assert tab[0] >= R / w - 0.01 and tab[2] <= 0.99 and 0.05 <= tab[1] < tab[3] <= 0.20, (size, tab)
        tap(s, cx, cy); assert selected(s) == -2, ('a tap on the CLOSE tab closes (CLEO\'s own tap code decides)', size, tab)
        s.uc.mem_write(SELECTED, struct.pack('<i', -1)); tap(s, 0.25, 0.92); assert selected(s) == -1, 'nothing is left at the old place of CLOSE'
        tap(s, 0.5, 0.2 + 0.09 * 3 + 0.045); assert selected(s) == 3, 'rows are taken where CLEO has them'
    ok('2000x1250, 2400x1080, 1280x720 and 1024x768: the panel keeps CLEO\'s touch columns inside and its page arrows outside, nothing is thinner than 2 px, texts stay inside; the CLOSE tab sits beside the header and CLEO\'s own tap code closes the menu there')

    # ---- height follows the number of rows, smoothly
    h2 = Emu(); h2.load(); h2.set_menu(b'CLEO MENU', b'CLOSE', [A('helicover'), A('vehiclespawn')]); p, t = steady(h2)
    assert abs(panel_box(p)[3] - (0.21 + 0.18) * H) < 2
    h2.set_menu(b'CLEO MENU', b'CLOSE', ROWS8); h2.now += 16; b1 = panel_box(h2.draw()[0])[3]; h2.now += 16; b2 = panel_box(h2.draw()[0])[3]
    p, t = steady(h2, (120, 120)); b3 = panel_box(p)[3]
    assert (0.21 + 0.18) * H < b1 < b2 < b3 and abs(b3 - 0.93 * H) < 2, (b1, b2, b3)
    ok('The panel is as tall as its rows need (2 rows: short, 8 rows: full) and grows smoothly when the number of rows changes')

    # ---- text fitting
    longrow = [0x8f] * 44
    f = Emu(); f.load(); f.set_menu(bytes([0x8f] * 26), b'CLOSE', [longrow, A('OK')]); p, t = steady(f); L, top, R, bot = panel_box(p)
    assert t[2]['w'] <= 0.845 * (R - L) and t[2]['scale'][0] < 0.75 * 1.4 and t[0]['w'] <= 0.805 * (R - L), (t[2]['w'], R - L, t[0]['w'])
    assert abs(t[3]['scale'][0] - 0.75 * 1.4 * 1.12) < 0.01 and f.measured <= 12, ('short rows are a little larger; widths are measured once and remembered', t[3]['scale'], f.measured)
    n = Emu(measure=False); n.load(); n.set_menu(bytes([0x8f] * 40), b'CLOSE', [longrow, A('OK')]); p, t = steady(n)
    assert 'text measuring is not the expected code' in n.log() and abs(t[2]['scale'][0] - 0.75 * 1.4 * 1.12) < 0.01 and len(t) == 4
    ok('A title or row that is too wide is shrunk to fit the panel (the game measures it); if the game\'s measuring code is not the known one, texts simply keep one size')

    # ---- opening, page change
    a = Emu(); a.load(); a.set_menu(b'T', b'CLOSE', ROWS8); frames = []
    for dt in (0, 30, 30, 30, 30, 200): a.now += dt; frames.append(a.draw())
    al = lambda fr: body(fr[0])['c'][3]
    assert al(frames[0]) >= 130 and frames[0][1][0]['c'][3] == 255, 'first frame: the header and the title are already there'
    assert all(x['c'][3] >= 50 for x in frames[0][1][2:]) and frames[0][1][2]['c'][3] > frames[0][1][9]['c'][3], 'first frame: every row is readable, upper rows ahead of lower ones'
    assert al(frames[0]) < al(frames[2]) <= al(frames[5]) and al(frames[5]) > 230 and all(x['c'][3] == 255 for x in frames[5][1])
    assert frames[0][0][0]['c'][3] < frames[2][0][0]['c'][3] < frames[5][0][0]['c'][3], 'the dimming fades in'
    assert frames[4][1][9]['c'][3] == 255, 'everything is in place 120 ms after the first frame'
    a.set_menu(b'OTHER PAGE', b'CLOSE', ROWS8); a.now += 16; sw = a.draw(); a.now += 100; sw2 = a.draw()
    assert al(sw) > 230 and 60 < sw[1][2]['c'][3] < 255 and all(x['c'][3] == 255 for x in sw2[1]), 'page change: the panel stays, the rows blink in within 90 ms'
    a.setting('CLEO UI Animation', 0); a.now += 3000; q = a.draw(); assert al(q) > 230 and all(x['c'][3] == 255 for x in q[1]) and q[0][0]['c'][3] >= 100
    assert b'Animation = 0' in a.fs[CFG]
    ok('Opening takes 140 ms with no empty frame (header at once, rows one after another); a page change is a 90 ms blink of the rows, not a new opening; "CLEO UI Animation: Off" shows everything at once')

    # ---- the pressed row (CLEO marks it for 3 frames only)
    s = Emu(); s.load(); s.set_menu(b'T', b'CLOSE', ROWS3); steady(s)
    def bar(p): return [q for q in p if q['c'][:3] == ORANGE and q['c'][3] > 60 and abs(q['p'][1] - (0.29 + 0.010) * H) < 1.5 and q['p'][5] - q['p'][1] > 0.05 * H]
    s.uc.mem_write(SELECTED, struct.pack('<i', 1)); s.uc.mem_write(FLASH, struct.pack('<i', 3)); s.now += 16; p0, t0 = s.draw()
    assert bar(p0) and not [x for x in t0 if x['c'][:3] == (40, 235, 24)], 'CLEO\'s green letters are gone'
    s.now += 100; p1, t1 = s.draw(); w0 = bar(p0)[0]['p'][2] - bar(p0)[0]['p'][0]; w1 = bar(p1)[0]['p'][2] - bar(p1)[0]['p'][0]
    assert w0 < w1 and w1 > 0.8 * (panel_box(p1)[2] - panel_box(p1)[0]) and t1[3]['c'][:3] == (14, 14, 18), ('the bar shoots across in 90 ms, the text on it is dark', w0, w1)
    assert struct.unpack('<i', bytes(s.uc.mem_read(FLASH, 4)))[0] <= 1, 'CLEO\'s own mark is nearly over'
    s.now += 100; p2, t2 = s.draw(); s.now += 150; p3, t3 = s.draw(); s.now += 150; p4, t4 = s.draw()
    assert bar(p2) and bar(p2)[0]['c'][3] > 200 and (not bar(p3) or bar(p3)[0]['c'][3] < bar(p2)[0]['c'][3]) and not bar(p4) and t4[3]['c'][:3] == (238, 238, 240), 'it holds, fades and is gone after 0.43 s'
    ok('A pressed row: an accent bar shoots from the left (90 ms), holds and fades - visible for 0.4 s although CLEO marks the row for 3 frames; dark text on the bar, no green letters')

    # ---- settings
    s.setting('CLEO UI Colour', 1); s.now += 100; p, t = s.draw()
    assert [q for q in p if q['c'][:3] == (60, 160, 255)] and not [q for q in p if q['c'][:3] == ORANGE] and b'Accent = 1' in s.fs[CFG]
    s.setting('CLEO UI Dim', 0); s.now += 100; p, t = s.draw(); assert not [q for q in p if q['p'] == [0, 0, W, 0, 0, H, W, H]] and b'Dim = 0' in s.fs[CFG]
    s.setting('CLEO UI', 0); p, t = s.draw(); assert len(p) == 1 and p[0]['c'] == BLUE + (150,)
    c2 = Emu(cfg=b'[Preferences]\nEnabled = 1\nAccent = 2\nAnimation = 0\nDim = 0\n'); c2.load(); c2.set_menu(b'T', b'CLOSE', ROWS3); p, t = c2.draw()
    assert [q for q in p if q['c'][:3] == (70, 220, 90)] and [i['init'] for i in c2.items] == [1, 2, 0, 0]
    ok('Settings: accent colour (5 choices), dimming, animation and On / Off work at once, are saved and read back at the next start')

    # ---- page arrows and the OPEN CLEO MENU hint, through CLEO's pointer
    b = Emu(); b.load(); b.set_menu(b'T', b'CLOSE', ROWS3); steady(b); b.polys = []
    col = b.alloc(bytes([55, 127, 175, 100])); b.call(b.ptrs()[0], x=(col,), s=(0.255, 0.5, 0.335, 0.4, 0.255, 0.5, 0.335, 0.6))
    assert b.polys[-1]['c'] == ORANGE + (205,) and b.polys[-1]['p'] == [round(v, 2) for v in (0.255 * W, 0.5 * H, 0.335 * W, 0.4 * H, 0.255 * W, 0.5 * H, 0.335 * W, 0.6 * H)] and b.polys[-2]['c'][3] < 60
    col = b.alloc(bytes([55, 127, 175, 180])); b.call(b.ptrs()[0], x=(col,), s=(0.255, 0.5, 0.335, 0.4, 0.255, 0.5, 0.335, 0.6)); assert b.polys[-1]['c'] == ORANGE + (255,)
    b.polys = []; col = b.alloc(bytes([255, 10, 10, 190])); b.call(b.ptrs()[0], x=(col,), s=(0.46, 0.15, 0.54, 0.15, 0.46, 0.4, 0.54, 0.4))
    assert len(b.polys) == 1 and b.polys[0]['c'] == ORANGE + (190,) and b.polys[0]['p'][:4] == [round(v, 2) for v in (0.46 * W, 0.15 * H, 0.54 * W, 0.15 * H)]
    col = b.alloc(bytes([1, 2, 3, 4])); b.polys = []; b.call(b.ptrs()[0], x=(col,), s=(0.1, 0.1, 0.2, 0.1, 0.1, 0.2, 0.2, 0.2)); assert b.polys[0]['c'] == (1, 2, 3, 4)
    ok('Page arrows become accent-coloured with a glow (brighter while pressed), the arrow of the OPEN CLEO MENU hint takes the accent colour; anything else is drawn unchanged')

    # ---- Russian
    def titles(russian, title, close=b'CLOSE', rows=ROWS3):
        r = Emu(); r.uc.mem_write(GTA + 0xce1771, bytes([1 if russian else 0])); r.load(); r.set_menu(title, close, rows)
        return [x['t'] for x in steady(r)[1]]
    game = lambda s: [0x80 + 'АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'.index(c) if 'А' <= c <= 'Я' else 0xa0 + 'абвгдежзийклмнопрстуфхцчшщъыьэюя'.index(c) if 'а' <= c <= 'я' else ord(c) for c in s.replace('Ё', 'Е').replace('ё', 'е')]
    word = 'Вертолёт: ЁЖ 12'
    t = titles(True, word.encode('utf-8')); assert t[0] == game(word), (t[0], game(word))
    t = titles(True, word.encode('cp1251')); assert t[0] == game(word)
    t = titles(True, bytes(game(word))); assert t[0] == game(word), 'text already in the game\'s codes (Helicover) passes unchanged'
    assert t[1] == game('ЗАКРЫТЬ')
    t = titles(True, b'HELLO', rows=[[0xd0, 0x9f, 0xd1, 0x80], game('Летит')]); assert t[2:] == [game('Пр'), game('Летит')]
    t = titles(False, word.encode('utf-8')); assert t[0] == list(word.encode('utf-8')) and t[1] == A('CLOSE')
    ok('Game in Russian: script text in UTF-8 or CP1251 is turned into the game font\'s codes, CLOSE becomes ЗАКРЫТЬ; text already in game codes and any text in other game languages pass unchanged')

    # ---- CLEO not started yet -> a waiting thread installs later
    w = Emu(started=False); w.load()
    assert w.changed() == [] and len(w.threads) == 1 and 'waiting for CLEO' in w.log()
    def start(emu):
        if emu.sleeps == 5: emu.uc.mem_write(RECT_PTR, struct.pack('<QQ', RECT_FN, TEXT_FN))
    w.on_sleep = start; w.call(w.threads[0][0], x=(w.threads[0][1],))
    assert w.sleeps == 5 and all(MODB <= q < MODB + w.mod_size for q in w.ptrs()) and 'new look installed' in w.log()
    n = Emu(started=False); n.load(); n.call(n.threads[0][0], x=(n.threads[0][1],))
    assert n.sleeps == 600 and n.changed() == [] and 'did not start within two minutes' in n.log()
    ok('If CLEO starts after the mod, a waiting thread installs the look when CLEO is ready (and gives up after two minutes)')

    # ---- anything unexpected -> nothing changed
    def other_version(emu): emu.uc.mem_write(G(0x1bc30) + 18, b'7')
    def other_ptr(emu): emu.uc.mem_write(TEXT_PTR, struct.pack('<Q', TEXT_FN + 4))
    def other_code(emu): emu.uc.mem_write(TEXT_FN + 8, struct.pack('<I', 0xd503201f))
    def small(emu): emu.cleo_memsz = 0x100000
    for tw, msg in ((other_version, 'another CLEO version'), (other_ptr, 'not the expected ones'), (other_code, 'drawing code differs'), (small, 'smaller than the known build')):
        x = Emu(tweak=tw); x.load(); assert x.changed() == [] and msg in x.log() and not x.threads, (msg, x.log())
        if tw in (other_version, small): x.set_menu(b'T', b'CLOSE', ROWS3); p, t = x.draw(); assert len(p) == 1 and p[0]['c'] == BLUE + (150,)   # (the other two tweaks break CLEO's own code, so it is not run)
    ok('Another CLEO version, changed pointers, different code or a smaller library: nothing is touched, the log says why, the menu stays CLEO\'s')
    q = Emu(sautils=False); q.load(); assert 'SAUtils not found' in q.log() and 'new look installed' in q.log()
    ok('Without SAUtils the look still works (no settings items)')
    # ---- cost
    c = Emu(); c.load(); c.set_menu(b'HELICOVER / FOLLOWING', b'CLOSE', ROWS8); p, t = steady(c)
    assert len(p) < 140 and c.measured <= 12, (len(p), c.measured)
    ok('A full menu is %d shapes and %d texts per frame; text widths are asked from the game once per text, not every frame' % (len(p), len(t)))
    print('%d checks passed' % len(passed))

if __name__ == '__main__':
    if not IMAGE: sys.exit('usage: test_cleoui.py path/to/libSAcleo64.so.image')
    main()
