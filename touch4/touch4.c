/*
 * Touch x4 - AML mod for GTA San Andreas Android (arm64, the build in gtasa_offsets.h).
 *
 * Why the game only knows two fingers (found in libGTASA.so):
 *  - OS_PointerGetNumber() returns 2, so CTouchInterface::m_nMaxTouches = min(2, 4) = 2;
 *  - LIB_PointerGet* / OS_PointerGetType reject pointer index > 1;
 *  - AND_TouchEvent() stores touches in Points[2] (0x1c bytes each);
 *  - the 4-finger JNI entry NVEventMultiTouchEvent4 is an empty stub (return 1), and the
 *    event queue carries only two fingers, so ProcessEvents() dispatches ids 0 and 1 only.
 *  (The Java side can send four fingers once NvEventQueueActivity.Use2Touches is false.)
 *
 * What this mod does on load, only if every instruction it changes matches the expected one:
 *  1. points the GOT entry of Points at a 4-entry copy;
 *  2. lifts the 2-finger limits (OS_PointerGetNumber -> 4, index checks -> 3);
 *  3. replaces the NVEventMultiTouchEvent4 stub: fingers 1-2 go through the original
 *     2-finger handler, fingers 3-4 are queued;
 *  4. hooks ProcessEvents() (game thread) to deliver the queued fingers 3-4 through the
 *     game's own AND_TouchEvent(type, id, x, y) before the normal event processing;
 *  5. hooks the 2-finger JNI entry NVEventMultiTouchEvent: Java calls it only while
 *     Use2Touches is true, so the hook sets the activity's Use2Touches = false through JNI and
 *     from the next touch on Java sends up to four fingers to multiTouchEvent4. No APK change.
 * If anything does not match, nothing is changed and the game keeps its 2-finger input.
 * A text log is written to the AML mods folder (touch4_log.txt).
 */
#include "gtasa_offsets.h"

typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned short u16;

#define PROT_READ 1
#define PROT_WRITE 2
#define PROT_EXEC 4
#define MAP_PRIVATE 0x02
#define MAP_ANONYMOUS 0x20
#define O_WRONLY 01
#define O_CREAT 0100
#define O_TRUNC 01000

extern int mprotect(void *addr, u64 len, int prot);
extern void *mmap(void *addr, u64 len, int prot, int flags, int fd, long off);
extern int munmap(void *addr, u64 len);
extern int getpagesize(void);
extern int open(const char *path, int flags, ...);
extern long write(int fd, const void *buf, u64 n);
extern int close(int fd);
struct dl_phdr_info { u64 dlpi_addr; const char *dlpi_name; const void *dlpi_phdr; u16 dlpi_phnum; };
extern int dl_iterate_phdr(int (*cb)(struct dl_phdr_info *, u64, void *), void *data);
typedef struct { const char *dli_fname; void *dli_fbase; const char *dli_sname; void *dli_saddr; } Dl_info;
extern int dladdr(const void *addr, Dl_info *info);

#define HIDDEN __attribute__((visibility("hidden")))
#define EXPORT __attribute__((visibility("default")))

HIDDEN void *memcpy(void *d, const void *s, u64 n) { unsigned char *a = d; const unsigned char *b = s; while (n--) *a++ = *b++; return d; }
HIDDEN void *memset(void *d, int c, u64 n) { unsigned char *a = d; while (n--) *a++ = (unsigned char)c; return d; }

/* ---------- tiny log ---------- */
static char g_log[2048];
static u32 g_loglen;
static void lg(const char *s) { while (*s && g_loglen < sizeof(g_log) - 1) g_log[g_loglen++] = *s++; }
static void lghex(u64 v) { char b[19]; int i; b[0] = '0'; b[1] = 'x'; for (i = 0; i < 16; i++) { int d = (v >> (60 - 4 * i)) & 15; b[2 + i] = (char)(d < 10 ? '0' + d : 'a' + d - 10); } b[18] = 0; lg(b); }
static int try_log(const char *path) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return 0;
    write(fd, g_log, g_loglen); close(fd); return 1;
}
static void flush_log(void) {
    Dl_info di; char path[512]; u32 n = 0, cut = 0; const char *f;
    /* AML's mods folder first (visible in a file manager), then next to the loaded .so, then the game's files dir */
    if (try_log("/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/mods/touch4_log.txt")) return;
    if (dladdr((const void *)&flush_log, &di) && di.dli_fname) {
        for (f = di.dli_fname; *f && n < sizeof(path) - 32; f++) { path[n++] = *f; if (*f == '/') cut = n; }
        n = cut; { const char *nm = "touch4_log.txt"; while (*nm) path[n++] = *nm++; } path[n] = 0;
        if (cut && try_log(path)) return;
    }
    try_log("/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/touch4_log.txt");
}

/* ---------- memory helpers ---------- */
static u64 g_page;
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
static int write_code(u64 addr, const void *src, u64 len) {
    if (set_prot(addr, len, PROT_READ | PROT_WRITE | PROT_EXEC)) return 0;
    memcpy((void *)addr, src, len);
    sync_icache(addr, len);
    set_prot(addr, len, PROT_READ | PROT_EXEC);
    return 1;
}
#define LDR_X17_8 0x58000051U /* ldr x17, #8 */
#define BR_X17 0xd61f0220U    /* br x17 */
static void abs_jump(u32 *p, u64 target) { p[0] = LDR_X17_8; p[1] = BR_X17; p[2] = (u32)target; p[3] = (u32)(target >> 32); }

/* ---------- game functions and hooks ---------- */
typedef int (*mt2_fn)(void *env, void *thiz, int action, int count, int x0, int y0, int x1, int y1);
typedef void (*touch_fn)(int type, int id, int x, int y);
typedef long (*pe_fn)(int b);
static mt2_fn g_mt2; /* original 2-finger handler (relocated prologue) */
static touch_fn g_touch;
static pe_fn g_pe_orig;
static unsigned char g_points[4 * POINT_STRIDE] __attribute__((aligned(16)));

/* AND_TouchEvent types, as ProcessEvents maps the per-finger codes: 1 up, 2 down, 3 move, 4 cancel. */
enum { T_UP = 1, T_DOWN = 2, T_MOVE = 3, T_CANCEL = 4 };
struct ev { int type, id, x, y; };
#define QN 512
static struct ev g_q[QN];
static u32 g_qhead, g_qtail; /* UI thread produces, game thread consumes */
static void push(int type, int id, int x, int y) {
    u32 h = __atomic_load_n(&g_qhead, __ATOMIC_RELAXED), t = __atomic_load_n(&g_qtail, __ATOMIC_ACQUIRE);
    if (h - t >= (type == T_MOVE ? QN / 2 : QN)) return; /* keep room for down/up while the game is paused */
    g_q[h % QN].type = type; g_q[h % QN].id = id; g_q[h % QN].x = x; g_q[h % QN].y = y;
    __atomic_store_n(&g_qhead, h + 1, __ATOMIC_RELEASE);
}
HIDDEN long touch4_process_events(int b) {
    u32 t = __atomic_load_n(&g_qtail, __ATOMIC_RELAXED), h = __atomic_load_n(&g_qhead, __ATOMIC_ACQUIRE);
    while (t != h) { struct ev e = g_q[t % QN]; g_touch(e.type, e.id, e.x, e.y); t++; }
    __atomic_store_n(&g_qtail, t, __ATOMIC_RELEASE);
    return g_pe_orig(b);
}

static int g_down[4], g_lx[4], g_ly[4];
/* Android: ACTION_DOWN 0, UP 1, MOVE 2, CANCEL 3, POINTER_DOWN 5, POINTER_UP 6; index in bits 8-15.
   Fingers are tracked by pointer index, like the game's own 2-finger code. When a finger at a
   lower index goes up or down, the fingers above it change index, so this slot gets a different
   finger: it is ended (up) and started again (down) instead of jumping across the screen. */
static void touch4_extra(int k, int masked, int pidx, int count, int x, int y) {
    int present = count > k;
    int lifting = (masked == 6 && pidx <= k) || masked == 1 || masked == 3;
    int fresh = masked == 5 && pidx <= k; /* a new finger took this index or pushed ours up */
    int want = present && !lifting;
    if (g_down[k] && (!want || fresh)) {
        int here = present && lifting;
        push(masked == 3 ? T_CANCEL : T_UP, k, here ? x : g_lx[k], here ? y : g_ly[k]);
        g_down[k] = 0;
    }
    if (!want) return;
    if (!g_down[k]) { push(T_DOWN, k, x, y); g_down[k] = 1; g_lx[k] = x; g_ly[k] = y; return; }
    if (x != g_lx[k] || y != g_ly[k]) { push(T_MOVE, k, x, y); g_lx[k] = x; g_ly[k] = y; }
}
/* Replaces the empty NVEventMultiTouchEvent4(env, thiz, action, count, x0..y3) JNI stub. */
HIDDEN int touch4_multitouch4(void *env, void *thiz, int action, int count, int x0, int y0, int x1, int y1, int x2, int y2, int x3, int y3) {
    int masked = action & 0xff, pidx = (action >> 8) & 0xff, a2 = action, c2 = count > 2 ? 2 : count, r;
    if ((masked == 5 || masked == 6) && pidx >= 2) a2 = 2; /* finger 3/4 changes are a MOVE for fingers 1-2 */
    r = g_mt2(env, thiz, a2, c2, x0, y0, x1, y1);
    touch4_extra(2, masked, pidx, count, x2, y2);
    touch4_extra(3, masked, pidx, count, x3, y3);
    return r;
}

/* JNIEnv function table slots (jni.h order; the game itself calls FindClass = 6, GetStaticFieldID = 144) */
#define JNI_EXCEPTION_CLEAR 17
#define JNI_DELETE_LOCAL_REF 23
#define JNI_GET_OBJECT_CLASS 31
#define JNI_GET_FIELD_ID 94
#define JNI_SET_BOOLEAN_FIELD 105
#define JNI_EXCEPTION_CHECK 228
static int g_flips, g_flip_failed;
static int use4_touches(void *env, void *thiz) {
    void **fn = *(void ***)env;
    void *cls, *fid = 0;
    cls = ((void *(*)(void *, void *))fn[JNI_GET_OBJECT_CLASS])(env, thiz);
    if (!cls) return 0;
    fid = ((void *(*)(void *, void *, const char *, const char *))fn[JNI_GET_FIELD_ID])(env, cls, "Use2Touches", "Z");
    if (((unsigned char (*)(void *))fn[JNI_EXCEPTION_CHECK])(env)) { ((void (*)(void *))fn[JNI_EXCEPTION_CLEAR])(env); fid = 0; }
    if (fid) ((void (*)(void *, void *, void *, unsigned char))fn[JNI_SET_BOOLEAN_FIELD])(env, thiz, fid, 0);
    ((void (*)(void *, void *))fn[JNI_DELETE_LOCAL_REF])(env, cls);
    return fid != 0;
}
/* Java reaches the 2-finger entry only while Use2Touches is true: the first touch of each
   activity instance. Switch that instance to 4 fingers and handle this touch as usual. */
HIDDEN int touch4_multitouch2(void *env, void *thiz, int action, int count, int x0, int y0, int x1, int y1) {
    if (!g_flip_failed) {
        if (use4_touches(env, thiz)) {
            if (!g_flips++) { lg("Use2Touches = false: the game now gets up to 4 fingers\n"); flush_log(); }
        } else {
            g_flip_failed = 1; lg("Use2Touches field not found - staying with 2 fingers\n"); flush_log();
        }
    }
    return g_mt2(env, thiz, action, count, x0, y0, x1, y1);
}

/* ---------- install ---------- */
static u64 g_base;
static int find_gtasa(struct dl_phdr_info *info, u64 size, void *data) {
    const char *n = info->dlpi_name, *e; (void)size; (void)data;
    if (!n) return 0;
    for (e = n; *e; e++) {}
    if (e - n >= 11) { const char *t = e - 11, *want = "libGTASA.so"; int i; for (i = 0; i < 11 && t[i] == want[i]; i++) {} if (i == 11) { g_base = info->dlpi_addr; return 1; } }
    return 0;
}
static u32 rd32(u64 off) { return *(volatile u32 *)(g_base + off); }

static int g_done;
static void install(void) {
    u64 stub, pe, mt2, i, page = 0, tr;
    u32 *t, jump[4], b;
    if (g_done) return;
    g_done = 1;
    g_page = (u64)getpagesize();
    lg("Touch x4 1.0\n");
    dl_iterate_phdr(find_gtasa, 0);
    if (!g_base) { lg("libGTASA.so not loaded - nothing changed\n"); flush_log(); return; }
    lg("libGTASA base "); lghex(g_base); lg("\n");
    /* verify everything first */
    for (i = 0; i < NPATCHES; i++) if (rd32(PATCHES[i].off) != PATCHES[i].expect) { lg("unexpected code at "); lghex(PATCHES[i].off); lg(" - other game version, nothing changed\n"); flush_log(); return; }
    if (rd32(OFF_MT4_STUB) != MT4_STUB_EXPECT[0] || rd32(OFF_MT4_STUB + 4) != MT4_STUB_EXPECT[1]) { lg("multitouch4 stub differs - nothing changed\n"); flush_log(); return; }
    for (i = 0; i < 4; i++) if (rd32(OFF_PROCESS_EVENTS + 4 * i) != PE_PROLOGUE[i]) { lg("ProcessEvents differs - nothing changed\n"); flush_log(); return; }
    for (i = 0; i < 4; i++) if (rd32(OFF_MT2 + 4 * i) != MT2_PROLOGUE[i]) { lg("multitouch handler differs - nothing changed\n"); flush_log(); return; }
    if (*(volatile u64 *)(g_base + OFF_POINTS_GOT) != g_base + OFF_POINTS) { lg("Points GOT differs - nothing changed\n"); flush_log(); return; }
    /* executable page within +-128 MB of the stub for a 4-byte branch */
    stub = g_base + OFF_MT4_STUB;
    for (i = 0; i < 96 && !page; i++) {
        u64 hint = (i < 48) ? g_base + 0x1300000UL + i * 0x100000UL : g_base - (i - 47) * 0x100000UL;
        void *p = mmap((void *)hint, g_page, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (p == (void *)-1L || !p) continue;
        if ((u64)p - stub + 0x7f00000UL < 0xfe00000UL) page = (u64)p; else munmap(p, g_page);
    }
    if (!page) { lg("no executable page near libGTASA - nothing changed\n"); flush_log(); return; }
    lg("trampoline page "); lghex(page); lg("\n");
    g_touch = (touch_fn)(g_base + OFF_AND_TOUCH);
    pe = g_base + OFF_PROCESS_EVENTS;
    mt2 = g_base + OFF_MT2;
    t = (u32 *)page;
    abs_jump(t, (u64)&touch4_multitouch4);                       /* [0..3]   entry for the stub */
    for (i = 0; i < 4; i++) t[4 + i] = PE_PROLOGUE[i];           /* [4..11]  original ProcessEvents */
    abs_jump(t + 8, pe + 16);
    for (i = 0; i < 4; i++) t[12 + i] = MT2_PROLOGUE[i];         /* [12..19] original 2-finger handler */
    abs_jump(t + 16, mt2 + 16);
    sync_icache(page, 80);
    mprotect((void *)page, g_page, PROT_READ | PROT_EXEC);
    g_pe_orig = (pe_fn)(page + 16);
    g_mt2 = (mt2_fn)(page + 48);
    /* 1. Points -> 4 entries */
    memcpy(g_points, (void *)(g_base + OFF_POINTS), POINTS_BYTES);
    if (set_prot(g_base + OFF_POINTS_GOT, 8, PROT_READ | PROT_WRITE)) { lg("cannot write GOT - nothing changed\n"); flush_log(); return; }
    *(volatile u64 *)(g_base + OFF_POINTS_GOT) = (u64)g_points;
    set_prot(g_base + OFF_POINTS_GOT, 8, PROT_READ);
    lg("Points -> 4 entries\n");
    /* 2. limits */
    for (i = 0; i < NPATCHES; i++) write_code(g_base + PATCHES[i].off, &PATCHES[i].patch, 4);
    *(volatile int *)(g_base + OFF_MAX_TOUCHES) = 4;
    lg("limits lifted (OS_PointerGetNumber=4, index checks<=3, m_nMaxTouches=4)\n");
    /* 4. ProcessEvents hook (game thread) */
    abs_jump(jump, (u64)&touch4_process_events);
    write_code(pe, jump, 16);
    /* 3. stub -> branch to the trampoline entry */
    tr = page;
    b = 0x14000000U | (u32)(((tr - stub) >> 2) & 0x3ffffffU);
    write_code(stub, &b, 4);
    /* 5. last: the 2-finger entry switches Java to 4 fingers, everything above is ready for it */
    abs_jump(jump, (u64)&touch4_multitouch2);
    write_code(mt2, jump, 16);
    lg("4-finger input enabled (switches on at the first touch)\n");
    flush_log();
}

/* ---------- AML entry points ---------- */
/* AML's ModInfo starts with these fields; the loader may store more after them (handle, dependencies),
   so the object is padded with zeros. */
struct ModInfo { char guid[48]; char name[48]; char version[24]; char author[48]; u16 ver[4]; unsigned char reserved[336]; };
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.touch4", "Touch x4", "1.0", "Helicover", {1, 0, 0, 0}, {0}};
EXPORT struct ModInfo *__GetModInfo(void) { return &g_info; }
EXPORT void OnModPreLoad(void) {}
EXPORT void OnModLoad(void) { install(); }
