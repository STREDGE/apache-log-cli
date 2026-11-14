/*
 * Touch x4 - AML mod for GTA San Andreas Android (arm64, the build in gtasa_offsets.h).
 *
 * Why the game only knows two fingers (found in libGTASA.so):
 *  - OS_PointerGetNumber() returns 2, so CTouchInterface::m_nMaxTouches = min(2, 4) = 2;
 *  - LIB_PointerGet* / OS_PointerGetType reject pointer index > 1;
 *  - AND_TouchEvent() stores touches in Points[2] (0x1c bytes each);
 *  - the 4-finger JNI entry NVEventMultiTouchEvent4 is an empty stub (return 1), and the
 *    event queue carries only two fingers, so ProcessEvents() dispatches ids 0 and 1 only;
 *  - the Java side sends four fingers only once NvEventQueueActivity.Use2Touches is false.
 *
 * What this mod does on load, only if every instruction it relies on matches the expected one:
 *  1. points the GOT entry of Points at a 4-entry copy;
 *  2. lifts the 2-finger limits (OS_PointerGetNumber -> 4, index checks -> 3);
 *  3. hooks ProcessEvents() (game thread) to deliver queued touches through the game's own
 *     AND_TouchEvent(type, slot, x, y) before the normal event processing;
 *  4. replaces the NVEventMultiTouchEvent4 stub (8 bytes: ldr x16 from a pointer stored in the patched
 *     2-finger entry; br x16) and hooks the 2-finger JNI entry. No new executable memory is needed. The first
 *     touch switches the activity to Use2Touches = false through JNI; from then on Java sends
 *     up to four fingers and the mod handles all of them itself. Each finger is followed by its
 *     Android pointer id (MotionEvent.getPointerId), so it keeps its slot until it is lifted,
 *     even when other fingers go up or down (Android re-numbers pointer indexes then);
 *  5. adds "4-Finger Touch: On/Off" to SAUtils' Mods Settings (if SAUtils is installed). Off
 *     hands touches back to the game's own 2-finger code. Saved in configs/net.helicover.touch4.ini.
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
#define O_RDONLY 0
#define O_WRONLY 01
#define O_CREAT 0100
#define O_TRUNC 01000
#define RTLD_NOW 2

extern int mprotect(void *addr, u64 len, int prot);
extern int getpagesize(void);
extern int open(const char *path, int flags, ...);
extern long read(int fd, void *buf, u64 n);
extern long write(int fd, const void *buf, u64 n);
extern int close(int fd);
struct dl_phdr_info { u64 dlpi_addr; const char *dlpi_name; const void *dlpi_phdr; u16 dlpi_phnum; };
extern int dl_iterate_phdr(int (*cb)(struct dl_phdr_info *, u64, void *), void *data);
typedef struct { const char *dli_fname; void *dli_fbase; const char *dli_sname; void *dli_saddr; } Dl_info;
extern int dladdr(const void *addr, Dl_info *info);
extern void *dlopen(const char *name, int flags);
extern void *dlsym(void *handle, const char *name);

#define HIDDEN __attribute__((visibility("hidden")))
#define EXPORT __attribute__((visibility("default")))

HIDDEN void *memcpy(void *d, const void *s, u64 n) { unsigned char *a = d; const unsigned char *b = s; while (n--) *a++ = *b++; return d; }
HIDDEN void *memset(void *d, int c, u64 n) { unsigned char *a = d; while (n--) *a++ = (unsigned char)c; return d; }
static u64 slen(const char *s) { u64 n = 0; while (s[n]) n++; return n; }

#define GAME_DIR "/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/"

/* ---------- tiny log ---------- */
static char g_log[2048];
static u32 g_loglen;
static void lg(const char *s) { while (*s && g_loglen < sizeof(g_log) - 1) g_log[g_loglen++] = *s++; }
static void lghex(u64 v) { char b[19]; int i; b[0] = '0'; b[1] = 'x'; for (i = 0; i < 16; i++) { int d = (v >> (60 - 4 * i)) & 15; b[2 + i] = (char)(d < 10 ? '0' + d : 'a' + d - 10); } b[18] = 0; lg(b); }
static void lgint(int v) { char b[12]; int n = 11; b[n] = 0; if (v < 0) { lg("-"); v = -v; } do { b[--n] = (char)('0' + v % 10); v /= 10; } while (v && n); lg(b + n); }
static int try_log(const char *path) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return 0;
    write(fd, g_log, g_loglen); close(fd); return 1;
}
static void flush_log(void) {
    Dl_info di; char path[512]; u32 n = 0, cut = 0; const char *f;
    /* AML's mods folder first (visible in a file manager), then next to the loaded .so, then the game's files dir */
    if (try_log(GAME_DIR "mods/touch4_log.txt")) return;
    if (dladdr((const void *)&flush_log, &di) && di.dli_fname) {
        for (f = di.dli_fname; *f && n < sizeof(path) - 32; f++) { path[n++] = *f; if (*f == '/') cut = n; }
        n = cut; { const char *nm = "touch4_log.txt"; while (*nm) path[n++] = *nm++; } path[n] = 0;
        if (cut && try_log(path)) return;
    }
    try_log("/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/touch4_log.txt");
}

/* ---------- settings file ---------- */
#define CFG_MAIN GAME_DIR "configs/net.helicover.touch4.ini"
#define CFG_ALT GAME_DIR "mods/touch4.ini"
static int g_enabled = 1;
static void load_config(void) {
    char b[256]; long n; int fd = open(CFG_MAIN, O_RDONLY), i;
    if (fd < 0) fd = open(CFG_ALT, O_RDONLY);
    if (fd < 0) return;
    n = read(fd, b, sizeof(b) - 1); close(fd);
    if (n <= 0) return;
    b[n] = 0;
    for (i = 0; b[i]; i++) {
        if (b[i] == 'E' && b[i + 1] == 'n' && b[i + 2] == 'a' && b[i + 3] == 'b' && b[i + 4] == 'l' && b[i + 5] == 'e' && b[i + 6] == 'd') {
            for (i += 7; b[i] == ' ' || b[i] == '\t' || b[i] == '='; i++) {}
            if (b[i] == '0' || b[i] == '1') g_enabled = b[i] == '1';
            return;
        }
    }
}
static void save_config(void) {
    const char *t = g_enabled ? "[Preferences]\nEnabled = 1\n" : "[Preferences]\nEnabled = 0\n";
    int fd = open(CFG_MAIN, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) fd = open(CFG_ALT, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, t, slen(t)); close(fd);
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

/* ---------- game functions ---------- */
typedef int (*mt2_fn)(void *env, void *thiz, int action, int count, int x0, int y0, int x1, int y1);
typedef void (*touch_fn)(int type, int id, int x, int y);
typedef long (*pe_fn)(int b);
static u64 g_base;
static mt2_fn g_mt2; /* original 2-finger handler (relocated prologue) */
static touch_fn g_touch;
static pe_fn g_pe_orig;
static unsigned char g_points[4 * POINT_STRIDE] __attribute__((aligned(16)));
/* The original ProcessEvents / NVEventMultiTouchEvent: their first instructions (no PC-relative
   code; checked word by word against the game at install) followed by a jump back into the game. */
HIDDEN u64 g_pe_cont, g_mt2_cont;
extern const char pe_orig_tramp[], mt2_orig_tramp[];
__asm__(".text\n.p2align 2\n.hidden pe_orig_tramp\n.type pe_orig_tramp,%function\npe_orig_tramp:\n"
        ".inst 0xd10203ff\n.inst 0xa9026ffc\n.inst 0xa90367fa\n.inst 0xa9045ff8\n"
        "adrp x17, g_pe_cont\nldr x17, [x17, #:lo12:g_pe_cont]\nbr x17\n"
        ".p2align 2\n.hidden mt2_orig_tramp\n.type mt2_orig_tramp,%function\nmt2_orig_tramp:\n"
        ".inst 0xd101c3ff\n.inst 0xf90013f9\n.inst 0xa9035ff8\n.inst 0xa90457f6\n.inst 0xa9054ff4\n.inst 0xa9067bfd\n"
        "adrp x17, g_mt2_cont\nldr x17, [x17, #:lo12:g_mt2_cont]\nbr x17\n");

/* ---------- queue: UI thread -> game thread ---------- */
/* AND_TouchEvent types, as ProcessEvents maps the per-finger codes: 1 up, 2 down, 3 move, 4 cancel. */
enum { T_UP = 1, T_DOWN = 2, T_MOVE = 3, T_CANCEL = 4 };
struct ev { int type, id, x, y; };
#define QN 512
static struct ev g_q[QN];
static u32 g_qhead, g_qtail;
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

/* ---------- finger tracking (UI thread) ---------- */
/* Android: ACTION_DOWN 0, UP 1, MOVE 2, CANCEL 3, POINTER_DOWN 5, POINTER_UP 6; index in bits 8-15.
   A finger keeps its game slot (0-3) for as long as its pointer id is on screen. */
struct slot { int id, down, x, y; };
static struct slot g_s[4];
static void end_slot(int s, int type, int x, int y) { push(type, s, x, y); g_s[s].down = 0; }
static void release_all(void) { int s; for (s = 0; s < 4; s++) if (g_s[s].down) end_slot(s, T_UP, g_s[s].x, g_s[s].y); }
static void track(int action, int count, const int *xs, const int *ys, const int *ids) {
    int masked = action & 0xff, pidx = (action >> 8) & 0xff, n = count < 0 ? 0 : count > 4 ? 4 : count, i, s, lift[4];
    int endtype = masked == 3 ? T_CANCEL : T_UP;
    if (masked == 0) release_all(); /* a new gesture: nothing can still be down */
    for (i = 0; i < n; i++) lift[i] = masked == 1 || masked == 3 || (masked == 6 && pidx == i);
    for (s = 0; s < 4; s++) {
        if (!g_s[s].down) continue;
        for (i = 0; i < n && ids[i] != g_s[s].id; i++) {}
        if (i == n) end_slot(s, endtype, g_s[s].x, g_s[s].y);           /* gone (or pushed past the 4th index) */
        else if (lift[i]) end_slot(s, endtype, xs[i], ys[i]);           /* this finger goes up */
        else if (masked == 5 && pidx == i) end_slot(s, T_UP, g_s[s].x, g_s[s].y); /* id reused by a new finger */
    }
    for (i = 0; i < n; i++) {
        if (lift[i]) continue;
        for (s = 0; s < 4 && !(g_s[s].down && g_s[s].id == ids[i]); s++) {}
        if (s < 4) {
            if (xs[i] != g_s[s].x || ys[i] != g_s[s].y) { push(T_MOVE, s, xs[i], ys[i]); g_s[s].x = xs[i]; g_s[s].y = ys[i]; }
            continue;
        }
        for (s = 0; s < 4 && g_s[s].down; s++) {}
        if (s == 4) continue;
        g_s[s].id = ids[i]; g_s[s].down = 1; g_s[s].x = xs[i]; g_s[s].y = ys[i];
        push(T_DOWN, s, xs[i], ys[i]);
    }
}

/* ---------- JNI ---------- */
/* JNIEnv function table slots (jni.h order; the game itself calls FindClass = 6, GetStaticFieldID = 144) */
#define JNI_EXCEPTION_CLEAR 17
#define JNI_DELETE_LOCAL_REF 23
#define JNI_GET_OBJECT_CLASS 31
#define JNI_GET_METHOD_ID 33
#define JNI_CALL_INT_METHOD_A 51
#define JNI_GET_FIELD_ID 94
#define JNI_SET_BOOLEAN_FIELD 105
#define JNI_EXCEPTION_CHECK 228
#define JNI(env, slot, type) ((type)((*(void ***)(env))[slot]))
static int jni_threw(void *env) {
    if (!JNI(env, JNI_EXCEPTION_CHECK, unsigned char (*)(void *))(env)) return 0;
    JNI(env, JNI_EXCEPTION_CLEAR, void (*)(void *))(env);
    return 1;
}
/* NvEventQueueActivity.Use2Touches: true = Java sends 2 fingers to multiTouchEvent, false = 4 to multiTouchEvent4 */
static int set_use2(void *env, void *thiz, int value) {
    void *cls = JNI(env, JNI_GET_OBJECT_CLASS, void *(*)(void *, void *))(env, thiz), *fid;
    if (!cls) { jni_threw(env); return 0; }
    fid = JNI(env, JNI_GET_FIELD_ID, void *(*)(void *, void *, const char *, const char *))(env, cls, "Use2Touches", "Z");
    if (jni_threw(env)) fid = 0;
    if (fid) JNI(env, JNI_SET_BOOLEAN_FIELD, void (*)(void *, void *, void *, unsigned char))(env, thiz, fid, (unsigned char)value);
    JNI(env, JNI_DELETE_LOCAL_REF, void (*)(void *, void *))(env, cls);
    return fid != 0;
}
static void *g_mid_pid;
static int g_pid_state; /* 0 not looked up, 1 ok, -1 unavailable: pointer index is used as id */
static void pointer_ids(void *env, void *event, int n, int *ids) {
    int i;
    for (i = 0; i < n; i++) ids[i] = i;
    if (!event || g_pid_state < 0) return;
    if (!g_pid_state) {
        void *cls = JNI(env, JNI_GET_OBJECT_CLASS, void *(*)(void *, void *))(env, event);
        if (cls) {
            g_mid_pid = JNI(env, JNI_GET_METHOD_ID, void *(*)(void *, void *, const char *, const char *))(env, cls, "getPointerId", "(I)I");
            if (jni_threw(env)) g_mid_pid = 0;
            JNI(env, JNI_DELETE_LOCAL_REF, void (*)(void *, void *))(env, cls);
        } else jni_threw(env);
        g_pid_state = g_mid_pid ? 1 : -1;
        if (g_pid_state < 0) { lg("MotionEvent.getPointerId not available - fingers follow their index\n"); flush_log(); return; }
    }
    for (i = 0; i < n; i++) {
        u64 arg = (u32)i; /* jvalue { jint i } */
        ids[i] = JNI(env, JNI_CALL_INT_METHOD_A, int (*)(void *, void *, void *, const u64 *))(env, event, g_mid_pid, &arg);
    }
    if (jni_threw(env)) for (i = 0; i < n; i++) ids[i] = i;
}

/* ---------- JNI entries ---------- */
static int g_flips, g_flip_failed;
static int enabled(void) { return __atomic_load_n(&g_enabled, __ATOMIC_ACQUIRE) && !g_flip_failed; }
/* Java reaches the 2-finger entry only while Use2Touches is true (the first touch of each activity,
   or while the mod is switched off). The 9th argument is the MotionEvent. */
HIDDEN int touch4_multitouch2(void *env, void *thiz, int action, int count, int x0, int y0, int x1, int y1, void *event) {
    if (enabled()) {
        if (set_use2(env, thiz, 0)) {
            int xs[4] = {x0, x1, 0, 0}, ys[4] = {y0, y1, 0, 0}, ids[4], n = count > 2 ? 2 : count;
            if (!g_flips++) { lg("Use2Touches = false: the game now gets up to 4 fingers\n"); flush_log(); }
            pointer_ids(env, event, n, ids);
            track(action, n, xs, ys, ids);
            return 1;
        }
        g_flip_failed = 1; lg("Use2Touches field not found - staying with 2 fingers\n"); flush_log();
    }
    return g_mt2(env, thiz, action, count, x0, y0, x1, y1);
}
/* Replaces the empty NVEventMultiTouchEvent4(env, thiz, action, count, x0..y3, MotionEvent) JNI stub. */
HIDDEN int touch4_multitouch4(void *env, void *thiz, int action, int count, int x0, int y0, int x1, int y1, int x2, int y2, int x3, int y3, void *event) {
    int xs[4] = {x0, x1, x2, x3}, ys[4] = {y0, y1, y2, y3}, ids[4], n = count < 0 ? 0 : count > 4 ? 4 : count;
    if (!enabled()) {
        /* switched off: release our fingers and give touches back to the game's 2-finger code */
        release_all();
        set_use2(env, thiz, 1);
        ((int *)(g_base + OFF_LAST_ACTION))[0] = ((int *)(g_base + OFF_LAST_ACTION))[1] = 1;
        ((int *)(g_base + OFF_LAST_X))[0] = ((int *)(g_base + OFF_LAST_X))[1] = 0;
        ((int *)(g_base + OFF_LAST_Y))[0] = ((int *)(g_base + OFF_LAST_Y))[1] = 0;
        return g_mt2(env, thiz, action, n > 2 ? 2 : n, x0, y0, x1, y1);
    }
    pointer_ids(env, event, n, ids);
    track(action, n, xs, ys, ids);
    return 1;
}

/* ---------- SAUtils menu item ---------- */
static const char *g_onoff[2] = {"Off", "On"};
static void on_setting(int oldv, int newv, void *data) { /* game thread, when the settings screen closes */
    (void)oldv; (void)data;
    __atomic_store_n(&g_enabled, newv != 0, __ATOMIC_RELEASE);
    save_config();
    lg(newv ? "menu: 4-Finger Touch On\n" : "menu: 4-Finger Touch Off\n"); flush_log();
}
static void add_menu_item(void) {
    typedef void *(*getif_fn)(const char *);
    /* ISAUtils vtable slot 3 (since SAUtils 1.1): AddClickableItem(type, name, init, min, max, switches, onChange) */
    typedef int (*add_fn)(void *self, int type, const char *name, int init, int min, int max, const char **sw, void (*cb)(int, int, void *));
    void *aml = dlopen("libAML.so", RTLD_NOW), *sa;
    getif_fn getif = aml ? (getif_fn)dlsym(aml, "GetInterface") : 0;
    int id;
    sa = getif ? getif("SAUtils") : 0;
    if (!sa) { lg("SAUtils not found - no menu item\n"); return; }
    id = ((add_fn)((*(void ***)sa)[3]))(sa, 5 /* SetType_Mods */, "4-Finger Touch", g_enabled, 0, 1, g_onoff, on_setting);
    lg("Mods Settings item id "); lgint(id); lg("\n");
}

/* ---------- install ---------- */
static int find_gtasa(struct dl_phdr_info *info, u64 size, void *data) {
    const char *n = info->dlpi_name, *e; (void)size; (void)data;
    if (!n) return 0;
    for (e = n; *e; e++) {}
    if (e - n >= 11) { const char *t = e - 11, *want = "libGTASA.so"; int i; for (i = 0; i < 11 && t[i] == want[i]; i++) {} if (i == 11) { g_base = info->dlpi_addr; return 1; } }
    return 0;
}
static u32 rd32(u64 off) { return *(volatile u32 *)(g_base + off); }
static int refuse(const char *why) { lg(why); lg(" - nothing changed\n"); flush_log(); return 0; }

static int g_done;
static int install(void) {
    u64 stub, pe, mt2, i;
    u32 jump[6], ldr16[2];
    g_page = (u64)getpagesize();
    lg("Touch x4 1.2\n");
    dl_iterate_phdr(find_gtasa, 0);
    if (!g_base) return refuse("libGTASA.so not loaded");
    lg("libGTASA base "); lghex(g_base); lg("\n");
    /* verify everything first */
    for (i = 0; i < NPATCHES; i++) if (rd32(PATCHES[i].off) != PATCHES[i].expect) { lg("at "); lghex(PATCHES[i].off); return refuse(": unexpected code, other game version"); }
    if (rd32(OFF_MT4_STUB) != MT4_STUB_EXPECT[0] || rd32(OFF_MT4_STUB + 4) != MT4_STUB_EXPECT[1]) return refuse("multitouch4 stub differs");
    for (i = 0; i < 4; i++) if (rd32(OFF_PROCESS_EVENTS + 4 * i) != PE_PROLOGUE[i]) return refuse("ProcessEvents differs");
    for (i = 0; i < 6; i++) if (rd32(OFF_MT2 + 4 * i) != MT2_PROLOGUE[i]) return refuse("multitouch handler differs");
    for (i = 0; i < NSTATE_REFS; i++) if (rd32(STATE_REFS[i].off) != STATE_REFS[i].expect) return refuse("ProcessEvents state differs");
    if (*(volatile u64 *)(g_base + OFF_POINTS_GOT) != g_base + OFF_POINTS) return refuse("Points GOT differs");
    /* v1.2: no new executable memory (Android may refuse it). The relocated prologues live in this
       module's own code (pe_orig_tramp / mt2_orig_tramp below); check they match the game first. */
    for (i = 0; i < 4; i++) if (((const u32 *)(u64)&pe_orig_tramp)[i] != PE_PROLOGUE[i]) return refuse("ProcessEvents trampoline differs");
    for (i = 0; i < 6; i++) if (((const u32 *)(u64)&mt2_orig_tramp)[i] != MT2_PROLOGUE[i]) return refuse("multitouch trampoline differs");
    stub = g_base + OFF_MT4_STUB;
    g_touch = (touch_fn)(g_base + OFF_AND_TOUCH);
    pe = g_base + OFF_PROCESS_EVENTS;
    mt2 = g_base + OFF_MT2;
    g_pe_cont = pe + 16;
    g_mt2_cont = mt2 + 24;
    g_pe_orig = (pe_fn)(u64)&pe_orig_tramp;
    g_mt2 = (mt2_fn)(u64)&mt2_orig_tramp;
    /* 1. Points -> 4 entries */
    memcpy(g_points, (void *)(g_base + OFF_POINTS), POINTS_BYTES);
    if (set_prot(g_base + OFF_POINTS_GOT, 8, PROT_READ | PROT_WRITE)) return refuse("cannot write GOT");
    *(volatile u64 *)(g_base + OFF_POINTS_GOT) = (u64)g_points;
    set_prot(g_base + OFF_POINTS_GOT, 8, PROT_READ);
    lg("Points -> 4 entries\n");
    /* 2. limits */
    for (i = 0; i < NPATCHES; i++) write_code(g_base + PATCHES[i].off, &PATCHES[i].patch, 4);
    *(volatile int *)(g_base + OFF_MAX_TOUCHES) = 4;
    lg("limits lifted (OS_PointerGetNumber=4, index checks<=3, m_nMaxTouches=4)\n");
    /* 3. ProcessEvents hook (game thread) */
    abs_jump(jump, (u64)&touch4_process_events);
    write_code(pe, jump, 16);
    /* 4. the 2-finger entry: 24 bytes = jump to our handler + the address of our 4-finger handler,
       which the 8-byte multitouch4 stub then loads PC-relative (ldr x16, mt2+16; br x16) */
    abs_jump(jump, (u64)&touch4_multitouch2);
    jump[4] = (u32)(u64)&touch4_multitouch4; jump[5] = (u32)((u64)&touch4_multitouch4 >> 32);
    write_code(mt2, jump, 24);
    ldr16[0] = 0x58000010U | (u32)((((mt2 + 16) - stub) >> 2) & 0x7ffffU) << 5;
    ldr16[1] = 0xd61f0200U; /* br x16 */
    write_code(stub, ldr16, 8);
    lg("4-finger input enabled (switches on at the first touch)\n");
    return 1;
}

/* ---------- AML entry points ---------- */
/* AML's ModInfo starts with these fields; the loader may store more after them (handle, dependencies),
   so the object is padded with zeros. */
struct ModInfo { char guid[48]; char name[48]; char version[24]; char author[48]; u16 ver[4]; unsigned char reserved[336]; };
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.touch4", "Touch x4", "1.2", "Helicover", {1, 2, 0, 0}, {0}};
EXPORT struct ModInfo *__GetModInfo(void) { return &g_info; }
EXPORT void OnModPreLoad(void) {}
EXPORT void OnModLoad(void) {
    if (g_done) return;
    g_done = 1;
    load_config();
    if (install()) {
        if (!g_enabled) lg("switched off in Mods Settings - the game keeps 2 fingers\n");
        add_menu_item();
        flush_log();
    }
}
