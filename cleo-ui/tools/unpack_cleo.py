"""Run the loader of libSAcleo64.so in unicorn to let it unpack itself. Imports and JNI are done in Python."""
import struct, sys, zlib, hashlib, collections
from unicorn import *
from unicorn.arm64_const import *
P = sys.argv[1]; d = open(P, 'rb').read()
BASE, HEAP, STACK, STUB, JNI, MMAP = 0x7200000000, 0x7400000000, 0x7500000000, 0x7600000000, 0x7700000000, 0x7800000000
uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
SEG = [(0, 0, 0x37160, 0x37160), (0x3f830, 0x4f830, 0x38762, 0x2bf790)]
top = (0x4f830 + 0x2bf790 + 0xffff) & ~0xffff
uc.mem_map(BASE, top, UC_PROT_ALL)
for off, va, fs, ms in SEG: uc.mem_write(BASE + va, d[off:off + fs])
uc.mem_map(HEAP, 0x8000000); uc.mem_map(STACK, 0x400000); uc.mem_map(STUB, 0x100000); uc.mem_map(JNI, 0x100000); uc.mem_map(MMAP, 0x10000000)
uc.mem_write(STUB, struct.pack('<I', 0xd65f03c0) * (0x100000 // 4))
def cs(o): return d[o:d.index(b'\0', o)].decode('latin1')
SYM, STR = 0x17a8, 0x6b30
syms = []
for i in range((STR - SYM) // 24):
    nm, info, oth, shndx, val, sz = struct.unpack_from('<IBBHQQ', d, SYM + 24 * i); syms.append((cs(STR + nm), shndx, val))
stubs = {}; names = {}
def stub(name):
    if name not in stubs: stubs[name] = STUB + 16 * (len(stubs) + 1); names[stubs[name]] = name
    return stubs[name]
for tab, size in ((0xd008, 0xaf8), (0xdb00, 0x5a0)):
    for i in range(0, size, 24):
        o, info, add = struct.unpack_from('<QQq', d, tab + i); t, s = info & 0xffffffff, info >> 32
        if t == 1027: uc.mem_write(BASE + o, struct.pack('<Q', BASE + add))
        elif t in (1025, 1026, 257):
            n, sh, v = syms[s]
            uc.mem_write(BASE + o, struct.pack('<Q', BASE + v + add if sh else stub(n)))
        else: print('reloc type', t, hex(o))
R = lambda r: uc.reg_read(r); X = [UC_ARM64_REG_X0 + i for i in range(8)]
def rs(a, n=400): return bytes(uc.mem_read(a, n)).split(b'\0')[0]
heap = [HEAP + 0x1000]; mm = [MMAP]
def malloc(n):
    a = heap[0]; heap[0] += (n + 0x2f) & ~0xf; return a
zs = {}
log = []
objs = {}; nobj = [0x1000]
def obj(desc):
    nobj[0] += 8; objs[nobj[0]] = desc; return nobj[0]
CERT = open(sys.argv[2], 'rb').read() if len(sys.argv) > 2 else b''
def jni(slot, x):
    N = lambda a: rs(a).decode('latin1')
    if slot == 6: r = obj(('class', N(x[1])))
    elif slot in (33, 113): r = obj(('method', objs.get(x[1]), N(x[2]), N(x[3])))
    elif slot in (94, 144): r = obj(('field', objs.get(x[1]), N(x[2]), N(x[3])))
    elif slot in (34, 35, 36, 114, 115, 116):
        m = objs.get(x[2]); r = obj(('result', m, x[3:6]))
        if m and m[2] == 'toByteArray': r = obj(('bytes', CERT))
        if m and m[2] == 'digest': r = obj(('bytes', objs['md'].digest()))
        if m and m[2] == 'getInstance': objs['md'] = hashlib.new(objs[x[3]][1].replace('-', '').lower()) if x[3] in objs and objs[x[3]][0] == 'str' else None
    elif slot in (61, 62, 63): # CallVoidMethod
        m = objs.get(x[2]); r = 0
        if m and m[2] == 'update': objs['md'].update(objs[x[3]][1])
    elif slot == 95: r = obj(('fieldval', objs.get(x[2])))
    elif slot in (150, 100): r = 30
    elif slot == 167: r = obj(('str', N(x[1])))
    elif slot == 169:
        s = objs[x[1]][1] if objs.get(x[1], ('',))[0] == 'str' else 'com.rockstargames.gtasa'
        r = malloc(len(s) + 1); uc.mem_write(r, s.encode() + b'\0')
    elif slot == 171: o = objs.get(x[1]); r = len(o[1]) if o and o[0] == 'bytes' else 1
    elif slot == 173: r = obj(('elem', objs.get(x[1]), x[2]))
    elif slot == 184:
        b = objs[x[1]][1]; r = malloc(len(b) + 1); uc.mem_write(r, b)
    elif slot == 200:
        b = objs[x[1]][1]; uc.mem_write(x[4], b[x[2]:x[2] + x[3]]); r = 0
    elif slot in (228, 15, 17, 23, 170, 192, 21, 22, 16): r = 0
    else: r = obj(('unknown', slot))
    log.append('jni %d %s -> %s' % (slot, [objs.get(v, hex(v)) if v in objs else hex(v) for v in x[1:5]], objs.get(r, r)))
    return r
def on_stub(uc_, addr, size, _):
    if addr not in names: return
    n = names[addr]; x = [R(r) for r in X]; r = 0
    if n in ('malloc', '_Znwm', '_Znam'): r = malloc(x[0])
    elif n == 'calloc': r = malloc(x[0] * x[1]); uc.mem_write(r, bytes(x[0] * x[1]))
    elif n in ('free', '_ZdlPv', '_ZdaPv', '__cxa_finalize', 'puts', 'fprintf', 'sigaction'): r = 0
    elif n == 'memcpy': uc.mem_write(x[0], bytes(uc.mem_read(x[1], x[2]))); r = x[0]
    elif n == 'memset': uc.mem_write(x[0], bytes([x[1] & 255]) * x[2]); r = x[0]
    elif n == 'strlen': r = len(rs(x[0], 4096))
    elif n == 'strcmp': a, b = rs(x[0]), rs(x[1]); r = (a > b) - (a < b)
    elif n == 'strncmp': a, b = rs(x[0])[:x[2]], rs(x[1])[:x[2]]; r = (a > b) - (a < b)
    elif n == 'strstr': a, b = rs(x[0], 4096), rs(x[1]); i = a.find(b); r = x[0] + i if i >= 0 else 0
    elif n == 'strncpy': s = rs(x[1])[:x[2]]; uc.mem_write(x[0], s + bytes(x[2] - len(s))); r = x[0]
    elif n == 'sysconf': r = 4096
    elif n == 'mmap':
        ln = (x[1] + 0xfff) & ~0xfff; r = mm[0]; mm[0] += ln + 0x10000; log.append('mmap %x len %x prot %d -> %x' % (x[0], x[1], x[2], r))
    elif n in ('munmap', 'mprotect'): log.append('%s %x %x %d' % (n, x[0], x[1], x[2])); r = 0
    elif n == 'inflateInit_': zs[x[0]] = zlib.decompressobj(); r = 0
    elif n == 'inflate':
        z = x[0]; nin, avin, tin, nout, avout = struct.unpack_from('<QIxxxxQQI', bytes(uc.mem_read(z, 40)))
        data = bytes(uc.mem_read(nin, avin)); out = zs[z].decompress(data, avout); used = avin - len(zs[z].unconsumed_tail)
        uc.mem_write(nout, out)
        uc.mem_write(z, struct.pack('<QIxxxxQQIxxxxQ', nin + used, avin - used, tin + used, nout + len(out), avout - len(out), struct.unpack_from('<Q', bytes(uc.mem_read(z + 40, 8)))[0] + len(out)))
        r = 1 if zs[z].eof else 0; log.append('inflate in %d out %d eof %s' % (used, len(out), zs[z].eof))
    elif n == 'inflateEnd': r = 0
    elif n == 'dlopen': r = obj(('lib', rs(x[0]).decode() if x[0] else None)); log.append('dlopen %s' % (objs[r],))
    elif n == 'dlsym': nm = rs(x[1]).decode(); r = stub('dyn:' + nm); log.append('dlsym %s' % nm)
    elif n == 'dladdr': r = 0
    elif n == 'dl_iterate_phdr': log.append('dl_iterate_phdr'); r = 0
    elif n == 'dlerror': r = 0
    elif n == 'fopen': log.append('fopen %s' % rs(x[0])); r = 0
    elif n.startswith('jni:'): r = jni(int(n[4:]), x)
    elif n == 'vm:6': uc.mem_write(x[1], struct.pack('<Q', JNI)); r = 0
    elif n.startswith('vm:'): r = 0
    elif n in ('abort', 'raise', '__stack_chk_fail'): log.append('!! ' + n); uc.emu_stop(); return
    else: log.append('?? ' + n + ' ' + ' '.join(hex(v) for v in x[:4]))
    uc.reg_write(UC_ARM64_REG_X0, r & (2 ** 64 - 1))
uc.hook_add(UC_HOOK_CODE, on_stub, begin=STUB, end=STUB + 0xfffff)
uc.mem_write(JNI, struct.pack('<Q', JNI + 0x100)); uc.mem_write(JNI + 0x100, b''.join(struct.pack('<Q', stub('jni:%d' % i)) for i in range(232)))
VM = JNI + 0x2000; uc.mem_write(VM, struct.pack('<Q', VM + 0x100)); uc.mem_write(VM + 0x100, b''.join(struct.pack('<Q', stub('vm:%d' % i)) for i in range(8)))
TLS = HEAP; uc.mem_write(TLS + 0x28, struct.pack('<Q', 0x1122334455667788)); uc.reg_write(UC_ARM64_REG_TPIDR_EL0, TLS)
uc.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
def bad(uc_, access, addr, size, value, _):
    log.append('!! bad access %x at pc %x' % (addr, R(UC_ARM64_REG_PC))); return False
uc.hook_add(UC_HOOK_MEM_UNMAPPED, bad)
def call(addr, *args, count=400000000):
    for i, a in enumerate(args): uc.reg_write(X[i], a)
    uc.reg_write(UC_ARM64_REG_SP, STACK + 0x300000); uc.reg_write(UC_ARM64_REG_X30, STUB)
    try: uc.emu_start(addr, STUB, count=count)
    except UcError as e: log.append('!! %s pc %x' % (e, R(UC_ARM64_REG_PC)))
    return R(UC_ARM64_REG_X0)
print('init ->', hex(call(BASE + 100264)))
print('JNI_OnLoad ->', hex(call(BASE + 0x18828, VM, 0)), 'pc', hex(R(UC_ARM64_REG_PC)))
c = collections.Counter(l.split(' -> ')[0][:60] for l in log)
for l in log[:150]: print(' ', l[:230])
print(len(log), 'events; tail:'); [print(' ', l[:230]) for l in log[-25:]]
open(P + '.image', 'wb').write(bytes(uc.mem_read(BASE, top)))
used = mm[0] - MMAP
if used: open(P + '.mmap', 'wb').write(bytes(uc.mem_read(MMAP, used)))
print('mmap used', hex(used), 'heap used', hex(heap[0] - HEAP))
