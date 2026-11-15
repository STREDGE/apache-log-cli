/*
 * CLEO UI probe - step 1 of the "new CLEO interface" project. AML mod for GTA San Andreas Android (arm64).
 *
 * The CLEO library of this game build (libSAcleo64.so, inside the APK) is protected: its strings are encrypted and
 * its code is unpacked in memory, so it cannot be studied from the file. This mod changes nothing in how the game or
 * CLEO behave; it only records, on the phone, what is needed to restyle the CLEO menu later:
 *   1. cleoui_dump_N.bin - a copy of libSAcleo64.so as it is in memory (after the protector unpacked it);
 *   2. cleoui_maps.txt   - the process memory map;
 *   3. cleoui_log.txt    - who calls four drawing functions of the game from outside libGTASA (CLEO draws its menu
 *      with the game's own functions), with the arguments of the first calls from every call site;
 *   4. cleoui_anon_N.bin - the memory around a caller that belongs to no library file (unpacked code).
 * All files go to the AML mods folder. Memory is copied with write(), which returns an error for an unreadable page
 * instead of crashing. A function is hooked only if its first four instructions are exactly the expected ones;
 * otherwise that hook is skipped and the log says so.
 */
typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

#define PROT_READ 1
#define PROT_WRITE 2
#define PROT_EXEC 4
#define O_RDONLY 0
#define O_WRONLY 01
#define O_CREAT 0100
#define O_TRUNC 01000

extern int mprotect(void *addr, u64 len, int prot);
extern int getpagesize(void);
extern int open(const char *path, int flags, ...);
extern long read(int fd, void *buf, u64 n);
extern long write(int fd, const void *buf, u64 n);
extern int close(int fd);
struct phdr { u32 type, flags; u64 offset, vaddr, paddr, filesz, memsz, align; };
struct dl_phdr_info { u64 dlpi_addr; const char *dlpi_name; const struct phdr *dlpi_phdr; u16 dlpi_phnum; };
extern int dl_iterate_phdr(int (*cb)(struct dl_phdr_info *, u64, void *), void *data);
typedef struct { const char *dli_fname; void *dli_fbase; const char *dli_sname; void *dli_saddr; } Dl_info;
extern int dladdr(const void *addr, Dl_info *info);

#define HIDDEN __attribute__((visibility("hidden")))
#define EXPORT __attribute__((visibility("default")))
HIDDEN void *memcpy(void *d, const void *s, u64 n) { u8 *a = d; const u8 *b = s; while (n--) *a++ = *b++; return d; }
HIDDEN void *memset(void *d, int c, u64 n) { u8 *a = d; while (n--) *a++ = (u8)c; return d; }

#define MODS_DIR "/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/mods/"

/* game build: the user's arm64 libGTASA.so (the same file Touch x4 and Helicover were made for) */
#define OFF_DRAWRECT 0x6ee91cUL    /* CSprite2d::DrawRect(CRect const&, CRGBA const&) */
#define OFF_DRAWRECT4 0x6eecc0UL   /* CSprite2d::DrawRect(CRect const&, CRGBA const& x4) */
#define OFF_PRINTSTRING 0x6cdeb0UL /* CFont::PrintString(float, float, unsigned short*) */
#define OFF_STRWIDTH 0x6ce760UL    /* CFont::GetStringWidth(unsigned short*, bool, bool) */
#define OFF_FONT_DETAILS_GOT 0x850ff0UL
enum { H_RECT, H_RECT4, H_PRINT, H_WIDTH, NHOOKS };
static const char *const HOOK_NAME[NHOOKS] = {"DrawRect", "DrawRect4", "PrintString", "GetStringWidth"};
static const u64 HOOK_OFF[NHOOKS] = {OFF_DRAWRECT, OFF_DRAWRECT4, OFF_PRINTSTRING, OFF_STRWIDTH};
static const u32 PROLOGUE[NHOOKS][4] = {
    {0xa9be4ff4U, 0xa9017bfdU, 0x910043fdU, 0xaa0103f3U},
    {0xf81c0ff7U, 0xa90157f6U, 0xa9024ff4U, 0xa9037bfdU},
    {0xd10143ffU, 0x6d0223e9U, 0xa9034ff4U, 0xa9047bfdU},
    {0x6db923e9U, 0xa9016ffcU, 0xa90267faU, 0xa9035ff8U}};

/* ---------- log ---------- */
static char g_log[120000];
static u32 g_loglen, g_dirty;
static void lg(const char *s) { while (*s && g_loglen < sizeof(g_log) - 1) g_log[g_loglen++] = *s++; g_dirty = 1; }
static void lghexn(u64 v, int digits) { char b[17]; int i; for (i = 0; i < digits; i++) { int d = (int)((v >> (4 * (digits - 1 - i))) & 15); b[i] = (char)(d < 10 ? '0' + d : 'a' + d - 10); } b[digits] = 0; lg(b); }
static void lghex(u64 v) { lg("0x"); lghexn(v, 16); }
static void lgint(u64 v) { char b[24]; int n = 23; b[n] = 0; do { b[--n] = (char)('0' + v % 10); v /= 10; } while (v && n); lg(b + n); }
static void flush_log(void) {
    int fd;
    if (!g_dirty) return;
    fd = open(MODS_DIR "cleoui_log.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, g_log, g_loglen); close(fd); g_dirty = 0;
}

/* ---------- modules ---------- */
#define MAXSEG 12
struct module { u64 base, lo, hi; int nseg; struct { u64 vaddr, memsz; u32 flags; } seg[MAXSEG]; };
static struct module g_gta, g_cleo;
static u64 g_page;
static int ends_with(const char *s, const char *tail) {
    u64 n = 0, m = 0, i;
    if (!s) return 0;
    while (s[n]) n++;
    while (tail[m]) m++;
    if (n < m) return 0;
    for (i = 0; i < m; i++) if (s[n - m + i] != tail[i]) return 0;
    return 1;
}
static void take_module(struct module *m, struct dl_phdr_info *info) {
    int i;
    m->base = info->dlpi_addr; m->lo = ~0UL; m->hi = 0; m->nseg = 0;
    for (i = 0; i < info->dlpi_phnum; i++) {
        const struct phdr *p = &info->dlpi_phdr[i];
        if (p->type != 1 /* PT_LOAD */) continue;
        if (p->vaddr < m->lo) m->lo = p->vaddr;
        if (p->vaddr + p->memsz > m->hi) m->hi = p->vaddr + p->memsz;
        if (m->nseg < MAXSEG) { m->seg[m->nseg].vaddr = p->vaddr; m->seg[m->nseg].memsz = p->memsz; m->seg[m->nseg].flags = p->flags; m->nseg++; }
    }
}
static int find_modules(struct dl_phdr_info *info, u64 size, void *data) {
    (void)size; (void)data;
    if (ends_with(info->dlpi_name, "libGTASA.so")) take_module(&g_gta, info);
    else if (ends_with(info->dlpi_name, "libSAcleo64.so")) take_module(&g_cleo, info);
    return 0;
}
static int inside(const struct module *m, u64 a) { return m->base && m->hi && a >= m->base + m->lo && a < m->base + m->hi; }

/* ---------- copies of memory (write() refuses an unreadable page instead of crashing) ---------- */
static u8 g_zero[4096];
static void name_n(char *dst, const char *stem, int n, const char *ext) {
    const char *d = MODS_DIR; u32 k = 0;
    while (*d) dst[k++] = *d++;
    while (*stem) dst[k++] = *stem++;
    dst[k++] = (char)('0' + n % 10);
    while (*ext) dst[k++] = *ext++;
    dst[k] = 0;
}
static u64 copy_range(int fd, u64 from, u64 to) { /* page by page; returns the number of pages that could not be read */
    u64 a, bad = 0;
    for (a = from; a < to; a += 4096) {
        u64 n = to - a < 4096 ? to - a : 4096;
        if (write(fd, (const void *)a, n) != (long)n) { write(fd, g_zero, n); bad++; }
    }
    return bad;
}
static int g_dumps;
static void dump_cleo(const char *why) {
    char path[256]; int fd, i; u64 bad;
    if (!g_cleo.base || g_dumps >= 3) return;
    if (g_cleo.hi - g_cleo.lo > 16UL * 1024 * 1024) { lg("CLEO image too large to copy\n"); g_dumps = 3; return; }
    g_dumps++;
    name_n(path, "cleoui_dump_", g_dumps, ".bin");
    fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) { lg("cannot create the dump file\n"); return; }
    bad = copy_range(fd, g_cleo.base + (g_cleo.lo & ~4095UL), g_cleo.base + g_cleo.hi);
    close(fd);
    lg("dump "); lgint((u64)g_dumps); lg(" ("); lg(why); lg("): file offset 0 = vaddr "); lghex(g_cleo.lo & ~4095UL);
    lg(", unreadable pages "); lgint(bad); lg(", segments:");
    for (i = 0; i < g_cleo.nseg; i++) { lg(" ["); lghex(g_cleo.seg[i].vaddr); lg("+"); lghex(g_cleo.seg[i].memsz); lg(" f"); lgint(g_cleo.seg[i].flags); lg("]"); }
    lg("\n");
}
static int g_anons;
static void dump_anon(u64 around) {
    char path[256]; int fd; u64 from = (around & ~4095UL) - 0x40000UL, to = (around & ~4095UL) + 0x40000UL, bad;
    if (g_anons >= 3) return;
    g_anons++;
    name_n(path, "cleoui_anon_", g_anons, ".bin");
    fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    bad = copy_range(fd, from, to);
    close(fd);
    lg("anon "); lgint((u64)g_anons); lg(": file offset 0 = address "); lghex(from); lg(", unreadable pages "); lgint(bad); lg("\n");
}
static void copy_maps(void) {
    static char buf[4096]; long n; int in = open("/proc/self/maps", O_RDONLY), out;
    if (in < 0) { lg("cannot read the memory map\n"); return; }
    out = open(MODS_DIR "cleoui_maps.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (out >= 0) { while ((n = read(in, buf, sizeof(buf))) > 0) write(out, buf, (u64)n); close(out); }
    close(in);
}

/* ---------- originals: the first four instructions (checked against the game) + a jump back ---------- */
HIDDEN u64 g_cont[NHOOKS];
extern const char tramp_rect[], tramp_rect4[], tramp_print[], tramp_width[];
#define TRAMP(name, i0, i1, i2, i3, slot) \
    ".p2align 2\n.hidden " name "\n.type " name ",%function\n" name ":\n" \
    ".inst " i0 "\n.inst " i1 "\n.inst " i2 "\n.inst " i3 "\n" \
    "adrp x17, g_cont\nadd x17, x17, #:lo12:g_cont\nldr x17, [x17, #" slot "]\nbr x17\n"
__asm__(".text\n"
        TRAMP("tramp_rect", "0xa9be4ff4", "0xa9017bfd", "0x910043fd", "0xaa0103f3", "0")
        TRAMP("tramp_rect4", "0xf81c0ff7", "0xa90157f6", "0xa9024ff4", "0xa9037bfd", "8")
        TRAMP("tramp_print", "0xd10143ff", "0x6d0223e9", "0xa9034ff4", "0xa9047bfd", "16")
        TRAMP("tramp_width", "0x6db923e9", "0xa9016ffc", "0xa90267fa", "0xa9035ff8", "24"));
static const char *const g_tramp[NHOOKS] = {tramp_rect, tramp_rect4, tramp_print, tramp_width};

/* ---------- the record ---------- */
#define MAXSITES 40
#define SAMPLES 6 /* argument samples kept per call site */
struct site { u64 lr; u32 calls, shown; };
static struct site g_site[NHOOKS][MAXSITES];
static int g_nsite[NHOOKS];
static u32 g_foreign, g_ticks;
static void lgcaller(u64 lr) {
    Dl_info di; const char *f, *b;
    if (inside(&g_cleo, lr)) { lg("libSAcleo64.so+"); lghex(lr - g_cleo.base); return; }
    di.dli_fname = 0; di.dli_fbase = 0;
    if (dladdr((const void *)lr, &di) && di.dli_fname) {
        for (f = b = di.dli_fname; *f; f++) if (*f == '/') b = f + 1;
        lg(b); lg("+"); lghex(lr - (u64)di.dli_fbase);
    } else { lg("(no file) "); lghex(lr); }
}
/* returns the call site if this call comes from outside libGTASA and one more sample of it is wanted */
static struct site *foreign(int h, u64 lr) {
    int i; struct site *s;
    if (inside(&g_gta, lr)) return 0;
    for (i = 0; i < g_nsite[h] && g_site[h][i].lr != lr; i++) {}
    if (i == g_nsite[h]) {
        Dl_info di;
        if (i == MAXSITES) return 0;
        if (!g_cleo.base) dl_iterate_phdr(find_modules, 0); /* CLEO may have been loaded after this mod */
        g_nsite[h]++; g_site[h][i].lr = lr; g_site[h][i].calls = 0; g_site[h][i].shown = 0;
        di.dli_fname = 0;
        if (!inside(&g_cleo, lr) && !(dladdr((const void *)lr, &di) && di.dli_fname)) dump_anon(lr);
    }
    s = &g_site[h][i]; s->calls++;
    if (!g_foreign++) dump_cleo("first call from outside the game");
    if (g_foreign == 400) dump_cleo("after 400 calls");
    if (s->shown >= SAMPLES) return 0;
    s->shown++;
    lg(HOOK_NAME[h]); lg(" <- "); lgcaller(lr); lg(" :");
    return s;
}
static u32 fbits(float f) { u32 u; memcpy(&u, &f, 4); return u; }
static void lgf(float f) { lg(" "); lghexn(fbits(f), 8); }
static void lgrect(const float *r) { if (!r) { lg(" rect=null"); return; } lg(" rect"); lgf(r[0]); lgf(r[1]); lgf(r[2]); lgf(r[3]); }
static void lgrgba(const u8 *c) { if (!c) { lg(" rgba=null"); return; } lg(" rgba "); lghexn(c[0], 2); lghexn(c[1], 2); lghexn(c[2], 2); lghexn(c[3], 2); }
static void lgtext(const u16 *t) {
    int i; char one[2] = {0, 0};
    if (!t) { lg(" text=null"); return; }
    lg(" text \"");
    for (i = 0; i < 60 && t[i]; i++) {
        if (t[i] >= 0x20 && t[i] < 0x7f && t[i] != '\\' && t[i] != '"') { one[0] = (char)t[i]; lg(one); }
        else { lg("\\"); lghexn(t[i], 4); }
    }
    lg("\"");
}
static void lgfont(void) {
    const u8 *d = *(const u8 *volatile *)(g_gta.base + OFF_FONT_DETAILS_GOT); int i;
    if (!d) return;
    lg(" font");
    for (i = 0; i < 0x40; i++) { if (!(i & 3)) lg(" "); lghexn(d[i], 2); }
}
static void tick(void) { /* called from the hooks: write out what is new; one more copy of CLEO after a while */
    ++g_ticks;
    if (g_ticks == 20000) {
        if (!g_cleo.base) dl_iterate_phdr(find_modules, 0);
        if (g_dumps < 2) dump_cleo("some time after the start");
    }
    flush_log(); /* only writes when something new was recorded: at most 40 call sites x 6 samples per function */
}
static void summary(void) {
    int h, i;
    lg("--- calls so far\n");
    for (h = 0; h < NHOOKS; h++) for (i = 0; i < g_nsite[h]; i++) { lg(HOOK_NAME[h]); lg(" <- "); lgcaller(g_site[h][i].lr); lg(" x"); lgint(g_site[h][i].calls); lg("\n"); }
}
static u32 g_last_summary;

typedef void (*rect_fn)(const float *rect, const u8 *rgba);
typedef void (*rect4_fn)(const float *rect, const u8 *c0, const u8 *c1, const u8 *c2, const u8 *c3);
typedef void (*print_fn)(float x, float y, const u16 *text);
typedef float (*width_fn)(const u16 *text, u8 a, u8 b);

HIDDEN void probe_rect(const float *rect, const u8 *rgba) {
    if (foreign(H_RECT, (u64)__builtin_return_address(0))) { lgrect(rect); lgrgba(rgba); lg("\n"); }
    tick();
    ((rect_fn)(u64)g_tramp[H_RECT])(rect, rgba);
}
HIDDEN void probe_rect4(const float *rect, const u8 *c0, const u8 *c1, const u8 *c2, const u8 *c3) {
    if (foreign(H_RECT4, (u64)__builtin_return_address(0))) { lgrect(rect); lgrgba(c0); lgrgba(c1); lgrgba(c2); lgrgba(c3); lg("\n"); }
    tick();
    ((rect4_fn)(u64)g_tramp[H_RECT4])(rect, c0, c1, c2, c3);
}
HIDDEN void probe_print(float x, float y, const u16 *text) {
    if (foreign(H_PRINT, (u64)__builtin_return_address(0))) { lg(" xy"); lgf(x); lgf(y); lgtext(text); lgfont(); lg("\n"); }
    tick();
    if (g_foreign && g_foreign - g_last_summary >= 3000) { g_last_summary = g_foreign; summary(); flush_log(); }
    ((print_fn)(u64)g_tramp[H_PRINT])(x, y, text);
}
HIDDEN float probe_width(const u16 *text, u8 a, u8 b) {
    if (foreign(H_WIDTH, (u64)__builtin_return_address(0))) { lgtext(text); lg(" flags "); lgint(a); lg(" "); lgint(b); lg("\n"); }
    tick();
    return ((width_fn)(u64)g_tramp[H_WIDTH])(text, a, b);
}
static void *const g_probe[NHOOKS] = {(void *)probe_rect, (void *)probe_rect4, (void *)probe_print, (void *)probe_width};

/* ---------- install ---------- */
static int set_prot(u64 addr, u64 len, int prot) {
    u64 start = addr & ~(g_page - 1), end = (addr + len + g_page - 1) & ~(g_page - 1);
    return mprotect((void *)start, end - start, prot);
}
static void sync_icache(u64 start, u64 len) {
    u64 ctr, dline, iline, a, end = start + len;
    __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
    dline = 4UL << ((ctr >> 16) & 15); iline = 4UL << (ctr & 15);
    for (a = start & ~(dline - 1); a < end; a += dline) __asm__ volatile("dc cvau, %0" ::"r"(a) : "memory");
    __asm__ volatile("dsb ish" ::: "memory");
    for (a = start & ~(iline - 1); a < end; a += iline) __asm__ volatile("ic ivau, %0" ::"r"(a) : "memory");
    __asm__ volatile("dsb ish\n isb" ::: "memory");
}
static int hook(int h) {
    u64 at = g_gta.base + HOOK_OFF[h], target = (u64)g_probe[h]; u32 jump[4]; int i;
    for (i = 0; i < 4; i++) {
        if (*(volatile u32 *)(at + 4 * i) != PROLOGUE[h][i]) { lg(HOOK_NAME[h]); lg(": the game code differs (another mod hooked it, or another game version) - not hooked\n"); return 0; }
        if (((const u32 *)(u64)g_tramp[h])[i] != PROLOGUE[h][i]) { lg(HOOK_NAME[h]); lg(": internal copy differs - not hooked\n"); return 0; }
    }
    g_cont[h] = at + 16;
    jump[0] = 0x58000051U; jump[1] = 0xd61f0220U; jump[2] = (u32)target; jump[3] = (u32)(target >> 32); /* ldr x17,#8; br x17; .quad */
    if (set_prot(at, 16, PROT_READ | PROT_WRITE | PROT_EXEC)) { lg(HOOK_NAME[h]); lg(": cannot write - not hooked\n"); return 0; }
    memcpy((void *)at, jump, 16);
    sync_icache(at, 16);
    set_prot(at, 16, PROT_READ | PROT_EXEC);
    lg(HOOK_NAME[h]); lg(": recording\n");
    return 1;
}
static int g_done;
static void install(void) {
    int h, n = 0;
    g_page = (u64)getpagesize();
    lg("CLEO UI probe 0.1 - records only, changes nothing\n");
    dl_iterate_phdr(find_modules, 0);
    if (!g_gta.base) { lg("libGTASA.so not loaded - nothing done\n"); flush_log(); return; }
    lg("libGTASA base "); lghex(g_gta.base); lg("\n");
    if (g_cleo.base) { lg("libSAcleo64.so base "); lghex(g_cleo.base); lg(" size "); lghex(g_cleo.hi); lg("\n"); dump_cleo("at load"); }
    else lg("libSAcleo64.so is not loaded yet (it will be looked for again at the first recorded call)\n");
    copy_maps();
    for (h = 0; h < NHOOKS; h++) n += hook(h);
    lg("hooks: "); lgint((u64)n); lg(" of "); lgint(NHOOKS); lg("\nNow open the CLEO menu, then the Helicover menu, press a few rows, close it, and send the files.\n");
    flush_log();
}

struct ModInfo { char guid[48]; char name[48]; char version[24]; char author[48]; u16 ver[4]; u8 reserved[336]; };
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.cleouiprobe", "CLEO UI probe", "0.1", "Helicover", {0, 1, 0, 0}, {0}};
EXPORT struct ModInfo *__GetModInfo(void) { return &g_info; }
EXPORT void OnModPreLoad(void) {}
EXPORT void OnModLoad(void) {
    if (g_done) return;
    g_done = 1;
    install();
}
