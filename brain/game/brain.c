/*
 * Helicover Brain - AML mod for GTA San Andreas Android (arm64, the build described by gta_words.h).
 * Stage 2: FIRE CONTROL. Ten to twenty times a second it reads the world around CJ (people, vehicles, shots,
 * damage), lets the core judge who is a threat and decide who of ours fires at whom, and records everything in the
 * black box. Helicover's CLEO scripts ask it through a private CLEO opcode (0E48): every frame for the order of each
 * shooter, and for every single round of a door gunner at the moment it is to leave - the brain answers with the
 * exact line or with "no". The scripts are the body; nothing here moves a ped.
 *
 * What is touched, only if every instruction word in gta_words.h matches the game in memory:
 *   three GOT slots of libGTASA (CTheScripts::Process, CHud::Draw, CEventGunShot::CEventGunShot) are pointed at
 *   functions of this mod, which call the original; CWorld::pIgnoreEntity is set and put back around a ray;
 *   one opcode is registered through CLEO's own plugin interface (only for the known CLEO build), and one of CLEO's
 *   shared values that the scripts created is written (the handshake). No code is patched.
 * If anything does not match, nothing is changed and the log says what differed.
 * Files (AML mods folder): hcbrain_log.txt, hcbrain_report_NN.bin. Settings: configs/net.helicover.brain.ini.
 */
#include "../core/hcb.h"
#include "gta_words.h"

typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

#define PROT_READ 1
#define PROT_WRITE 2
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
struct phdr { u32 type, flags; u64 offset, vaddr, paddr, filesz, memsz, align; };
struct dl_phdr_info { u64 dlpi_addr; const char *dlpi_name; const struct phdr *dlpi_phdr; u16 dlpi_phnum; };
extern int dl_iterate_phdr(int (*cb)(struct dl_phdr_info *, u64, void *), void *data);
typedef struct { const char *dli_fname; void *dli_fbase; const char *dli_sname; void *dli_saddr; } Dl_info;
extern int dladdr(const void *addr, Dl_info *info);
extern void *dlopen(const char *name, int flags);
extern void *dlsym(void *handle, const char *name);
extern int pthread_create(u64 *thread, const void *attr, void *(*fn)(void *), void *arg);
extern int usleep(u32 usec);
extern long syscall(long number, ...);
struct sigact { int flags; int pad; void *handler; u64 mask; void *restorer; };   /* bionic's struct sigaction on arm64 */
extern int sigaction(int sig, const struct sigact *act, struct sigact *old);
struct timespec { long tv_sec, tv_nsec; };
extern int clock_gettime(int clock, struct timespec *t);
extern void *memcpy(void *d, const void *s, u64 n);
extern void *memset(void *d, int c, u64 n);

#define HIDDEN __attribute__((visibility("hidden")))
#define EXPORT __attribute__((visibility("default")))
#define VERSION "0.4 (eight-man detail, the commander leads CJ, the gunners fire their own weapons, crash recorder)"
#define GAME_DIR "/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/"

/* ---------- the game (offsets from libGTASA base; see brain/research/game_facts.md) ---------- */
#define PED_POOL 0xbc3bb8UL
#define VEH_POOL 0xbc3bc0UL
#define PED_STRIDE 0x9c8U
#define VEH_STRIDE 0xc68U
#define PLAYERS 0xbdc738UL
#define PLAYER_INFO 0x1d8U
#define PLAYER_FOCUS 0xbdcae8UL
#define TIME_MS 0xbdc558UL
#define USER_PAUSE 0xbdc594UL
#define CODE_PAUSE 0xbdc595UL
#define FRAME_COUNTER 0xbdc590UL         /* CTimer::m_FrameCounter: goes up once a frame, also in the pause menu */
#define CUTSCENE 0xba8925UL
#define MISSION_FLAG 0x9f83f8UL
#define SCRIPT_SPACE 0x9a2038UL
#define SCRIPT_SPACE_SIZE 339000U
#define GROUPS 0xc89c20UL
#define GROUP_SIZE 0x4a0U
#define RSGLOBAL 0xc9b320UL
#define VT_USE_GUN (0x8338c8UL + 0x10)      /* object vptr of CTaskSimpleUseGun: target entity at +0x28 */
#define VT_FIGHT (0x8337f8UL + 0x10)        /* CTaskSimpleFight: target entity at +0x20 */
#define VT_KILL_PED (0x833c80UL + 0x10)     /* CTaskComplexKillPedOnFoot: target ped at +0x20 */
/* the scripts of Helicover (shared values of CLEO opcodes 0DDC / 0DDD) */
#define HC_STATE 0x48456A00U
#define HC_FIRE (HC_STATE + 7)
#define HC_PUB (HC_STATE + 20)              /* +0 CJ, +1 helicopter, +2 pilot, +3..6 gunners */
#define HC_PHASE (HC_STATE + 27)            /* 1 = the crew has left the helicopter after a landing and are guards on foot; else they are in its doors */
#define HC_GROUND (HC_STATE + 71)           /* +0..3 ground team (guards 1-4), +4 the rope actor */
#define HC_GROUND2 (HC_STATE + 480)         /* +0..3 ground team, guards 5-8 (1.4.1) */
#define HC_LEAVE (HC_STATE + 416)           /* +0..7 guards who were let go and walk away: still ours (never a target, never in a line of fire) */
#define HC_HELLO (HC_STATE + 440)           /* the scripts create it with 0; the brain answers with HELLO_MAGIC */
#define HC_POLICE (HC_STATE + 441)          /* 0 answer policemen who fire, 1 never fire at the police */
#define HC_TACTICS (HC_STATE + 156)         /* the squad's tactics: 0 GUARD, 1 ASSAULT */
#define HC_MISSION (HC_STATE + 442)         /* 0 defensive in missions, 1 as usual */
#define HELLO_MAGIC 0x42520021U             /* "BR", interface 2, the opcode is registered */
#define BRAIN_OPCODE 0x0E48
#define CMD_GUNNER 1                        /* 9 variables: in handle; out state (0 rest, 1 aim, 2 fire this round), target, muzzle xyz, end xyz */
#define CMD_SQUAD 2                         /* 3 variables: in handle; out state (0 nothing, 1 cover, 2 fire, 3 cease fire now), target */
#define CMD_POST 4                          /* 10 variables: in handle; out move (-1 no post, 0 stay, 1 walk, 2 run, 3 sprint), x y z, crouch, look x y z, duty */
#define CMD_DETAIL 5                        /* 9 variables: out what the commander said last (seq, HCB_SAY_*, direction), duty, cover for CJ (ok, x y z), commander */
#define CMD_PILOT 6                         /* 6 variables: in helicopter, point x y, roofs z, flags (1 stop, 2 the last step was refused); out x y z, metres left, speed (-1 = no pilot) */
#define CMD_STATUS 3                        /* 5 variables: out alert, threats, attackers, kills, the most dangerous man; 8: + ms since CJ fired, direction x, y; 9: + ms since a stranger fired at our helicopter; 10: + the gunners' pose (0 stand, 1 kneel, 2 sit); 13: + the helicopter's spot x y z (0 0 0 = none) */
#define IGNORE_ENTITY 0xbdcaf8UL            /* CWorld::pIgnoreEntity */
#define GOT_IGNORE 0x84b180UL               /* the GOT entry the line-of-sight code reads its address from */
/* CLEO (offsets from the start of libSAcleo64.so; the unpacked library is at +0x88000) */
#define CLEO_IMAGE 0x88000UL
#define CLEO_VERSION (CLEO_IMAGE + 0x1bc30UL)
#define CLEO_SHARED (CLEO_IMAGE + 0x7d1f8UL)    /* std::vector<{u32 key, u32 value}>: begin, end, end of capacity */
#define CLEO_MIN_SIZE (CLEO_IMAGE + 0x27e000UL)
#define CLEO_IFS (CLEO_IMAGE + 0x27d9b8UL)      /* the plugin interface: 28 function pointers */
#define CLEO_SCRIPTS (CLEO_IMAGE + 0x7d188UL)   /* std::vector<obj*> of CLEO's scripts: obj+0x20 CRunningScript*, obj+0x28 code base */
#define CLEO_REGISTER (CLEO_IMAGE + 0x38a58UL)  /* slot 17: int RegisterOpcode(u16, handler) */
#define CLEO_READ_PARAM (CLEO_IMAGE + 0x38e84UL)    /* slot 19 */
#define CLEO_VAR_PTR (CLEO_IMAGE + 0x38e9cUL)   /* slot 20 */
#define CLEO_G_COLLECT (CLEO_IMAGE + 0x7d248UL) /* what CLEO resolved in the game: CRunningScript::CollectParameters */
#define CLEO_G_VARPTR (CLEO_IMAGE + 0x7d240UL)  /* ... GetPointerToScriptVariable */
#define CLEO_G_BASE (CLEO_IMAGE + 0x7d1a0UL)    /* ... the load address of libGTASA */
#define G_COLLECT 0x3f1fccUL
#define G_VARPTR 0x3f2654UL
static const struct { u32 at, word; } CLEO_WORDS[] = {     /* first instructions of the three interface functions and of the dispatcher */
    {0x38a58, 0xa9bc7bfdU}, {0x38a5c, 0xa9015ff8U}, {0x38e84, 0xa9bf7bfdU}, {0x38e88, 0x910003fdU}, {0x38e8c, 0x52800021U},
    {0x38e9c, 0x2a1f03e1U}, {0x37904, 0xd10343ffU}, {0x37908, 0xa9087bfdU}};
static const char CLEO_VERSION_TEXT[] = "CLEO ANDROID (64-260403)";

#define RD(type, addr) (*(type *)(addr))
/* A ped and a vehicle can have the same pool handle: in everything handed to the core a vehicle's id carries bit 31. */
#define VID(h) ((h) ? ((h) | 0x80000000u) : 0)
#define VHANDLE(id) ((id) & 0x7fffffffu)
static u64 G, g_cleo;           /* libGTASA base; libSAcleo64 base when it is the known build, else 0 */
static u64 slen(const char *s) { u64 n = 0; while (s[n]) n++; return n; }

/* ---------- text building: the log and the text part of the report ---------- */
struct text { char *buf; u32 cap, len; };
static char g_logbuf[6144], g_notebuf[2048];
static struct text g_log = {g_logbuf, sizeof g_logbuf, 0}, g_note = {g_notebuf, sizeof g_notebuf, 0};
static void ts(struct text *t, const char *s) { while (*s && t->len < t->cap - 1) t->buf[t->len++] = *s++; t->buf[t->len] = 0; }
static void tu(struct text *t, u64 v) { char b[24]; int n = 23; b[n] = 0; do { b[--n] = (char)('0' + v % 10); v /= 10; } while (v); ts(t, b + n); }
static void ti(struct text *t, long v) { if (v < 0) { ts(t, "-"); v = -v; } tu(t, (u64)v); }
static void tx(struct text *t, u64 v) { char b[19]; int i; b[0] = '0'; b[1] = 'x'; for (i = 0; i < 16; i++) { int d = (int)((v >> (60 - 4 * i)) & 15); b[2 + i] = (char)(d < 10 ? '0' + d : 'a' + d - 10); } b[18] = 0; ts(t, b); }
#define lg(s) ts(&g_log, s)

static char g_dir[512];         /* the folder the files go to, with a trailing slash */
static void path_of(char *path, u32 cap, const char *name) {
    u32 n = 0; const char *p;
    for (p = g_dir; *p && n < cap - 64; p++) path[n++] = *p;
    for (p = name; *p && n < cap - 1; p++) path[n++] = *p;
    path[n] = 0;
}
static int file_exists(const char *name) { char path[640]; int fd; path_of(path, sizeof path, name); fd = open(path, O_RDONLY); if (fd < 0) return 0; close(fd); return 1; }
static int write_file4(const char *name, const void *a, u64 an, const void *b, u64 bn, const void *c, u64 cn, const void *d, u64 dn) {
    char path[640]; int fd;
    path_of(path, sizeof path, name);
    fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return 0;
    if (an) write(fd, a, an);
    if (bn) write(fd, b, bn);
    if (cn) write(fd, c, cn);
    if (dn) write(fd, d, dn);
    close(fd);
    return 1;
}
static int write_file(const char *name, const void *a, u64 an, const void *b, u64 bn, const void *c, u64 cn) { return write_file4(name, a, an, b, bn, c, cn, 0, 0); }
static void set_dir(const char *d) { u32 i = 0; while (d[i] && i < sizeof(g_dir) - 1) { g_dir[i] = d[i]; i++; } g_dir[i] = 0; }
static int g_log_lock;          /* the waiting thread and the game thread both write the log */
static void log_begin(void) { while (__atomic_exchange_n(&g_log_lock, 1, __ATOMIC_ACQUIRE)) usleep(1000); }
static void log_end(void) { __atomic_store_n(&g_log_lock, 0, __ATOMIC_RELEASE); }
static void flush_log(void) {
    Dl_info di; u32 n = 0, cut = 0; const char *f; char own[512];
    if (g_dir[0] && write_file("hcbrain_log.txt", g_log.buf, g_log.len, 0, 0, 0, 0)) return;       /* the folder that worked before */
    /* AML's mods folder first (visible in a file manager), then next to the loaded .so, then the game's files dir */
    set_dir(GAME_DIR "mods/");
    if (write_file("hcbrain_log.txt", g_log.buf, g_log.len, 0, 0, 0, 0)) return;
    if (dladdr((const void *)&flush_log, &di) && di.dli_fname) {
        for (f = di.dli_fname; *f && n < sizeof(own) - 2; f++) { own[n++] = *f; if (*f == '/') cut = n; }
        own[cut] = 0;
        if (cut) { set_dir(own); if (write_file("hcbrain_log.txt", g_log.buf, g_log.len, 0, 0, 0, 0)) return; }
    }
    set_dir("/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/");
    write_file("hcbrain_log.txt", g_log.buf, g_log.len, 0, 0, 0, 0);
}

/* ---------- settings ---------- */
#define CFG GAME_DIR "configs/net.helicover.brain.ini"
static int g_marks = 0;         /* debug markers: off unless the player turns them on */
static u32 g_last_crash;        /* 1.4.1: the brain's step when the last game crashed inside it (0 = none); 20 = a gunner's shot */
static int g_fire_off;          /* 1.4.1: the game's own weapon fire for the gunners is off (it crashed once, or the words differ) */
static int key_at(const char *b, const char *key) { int i, k; for (i = 0; b[i]; i++) { for (k = 0; key[k] && b[i + k] == key[k]; k++) {} if (!key[k]) { i += k; while (b[i] == ' ' || b[i] == '\t' || b[i] == '=') i++; return i; } } return -1; }
static void load_config(void) {
    char b[256]; long n; int fd = open(CFG, O_RDONLY), i;
    if (fd < 0) return;
    n = read(fd, b, sizeof(b) - 1); close(fd);
    if (n <= 0) return;
    b[n] = 0;
    if ((i = key_at(b, "Markers")) >= 0 && (b[i] == '0' || b[i] == '1')) g_marks = b[i] == '1';
    if ((i = key_at(b, "FireOff")) >= 0 && b[i] == '1') g_fire_off = 1;
    if ((i = key_at(b, "LastCrash")) >= 0) for (g_last_crash = 0; b[i] >= '0' && b[i] <= '9'; i++) g_last_crash = g_last_crash * 10 + (u32)(b[i] - '0');
}
static void save_config_with(u32 crash) {
    char b[96]; struct text t = {b, sizeof b, 0};
    int fd = open(CFG, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    ts(&t, g_marks ? "[Preferences]\nMarkers = 1\n" : "[Preferences]\nMarkers = 0\n");
    if (crash) { ts(&t, "LastCrash = "); tu(&t, crash); ts(&t, "\n"); }
    if (g_fire_off || crash == 20) ts(&t, "FireOff = 1\n");
    write(fd, b, t.len); close(fd);
}
static void crash_settings(u32 where) { save_config_with(where ? where : 99); }
static void save_config(void) {
    save_config_with(g_last_crash);
}

/* ---------- the brain and its black box ---------- */
#define BRAIN_BYTES (96 * 1024)
#ifndef BOX_BYTES
#define BOX_BYTES (10 * 1024 * 1024)    /* (the emulator test builds a copy with small halves to watch them change over) */
#endif
static u8 g_brain[BRAIN_BYTES] __attribute__((aligned(16)));
/* The black box is two halves: one fills, and when it is full the other is wiped and takes over - nothing is ever
   moved, so there is no pause. A report is the older half followed by the current one (about ten minutes). */
static u8 g_box[2][BOX_BYTES];
static hcb_rec g_rec[2];
static int g_cur;
static hcb_snapshot g_snap;
static hcb_out g_out, g_shown;
static u32 g_ticks, g_last_think, g_dumps, g_peds_max, g_tick_us_max, g_events_lost, g_rounds, g_rounds_refused, g_rays;
static u64 g_tick_us_sum;
/* the brain's share of the game's time. A ray of the game costs tens to hundreds of microseconds in a busy street; asked
   for every pair on every look (stage 2 as first released) they could take most of a frame, the frames grew longer, the
   brain looked again in every frame - and the game all but stopped. Now the rays of a frame have a time budget, a look
   answers a limited number of questions (the most important first, the rest in turn), and the brain never takes more
   than a quarter of the real time. */
#define RAY_FRAME_US 2500U              /* rays (looks and rounds together) per frame */
#define RAY_CJ_LOOK 10U                 /* "does this armed man see CJ?" per look */
#define RAY_ASK_LOOK 32U                /* the core's questions answered per look: the first 8 always, the rest in turn */
#define RAY_ASK_FIRST 8U
static u64 g_frame_ray_us, g_ray_us_max, g_think_cost_us, g_think_end_us, g_frame_at_us, g_gap_max_us, g_frame_brain_us_max;
static u32 g_rays_bad, g_rays_skipped, g_rounds_bad, g_looks_skipped, g_rays_look_max, g_ask_cursor, g_slow_run, g_crawls;
static u16 g_say_seq; static u8 g_say, g_say_dir;   /* the commander's last words (the scripts poll them every frame) */
static volatile u32 g_where;            /* where the game thread is inside the brain (for the hang recorder): 0 outside */
static volatile long g_main_tid;
static int g_ready, g_dump_request, g_was_alive, g_busy, g_urgent, g_ignore_ok, g_bridge;     /* g_bridge: 0 not yet, 1 opcode registered, -1 cannot */
static const u8 *g_our_ent[HCB_MAX_OURS + 2];   /* CJ, the helicopter and our people as the gunshot hook sees them */
static u32 g_heli_shot_t;                       /* when a stranger's round last passed within 6 m of our helicopter */
static u32 g_cj_shot_t;                         /* when CJ last fired, and in which direction (unit vector in the plane) */
static float g_cj_shot_dir[2];
#define BRAIN ((hcb_brain *)g_brain)

/* ---------- reading the game ---------- */
struct pool { u8 *objs, *flags; u32 size; };
static int get_pool(u64 slot, struct pool *p) {
    u8 *pp = RD(u8 *, G + slot);
    if (!pp) return 0;
    p->objs = RD(u8 *, pp); p->flags = RD(u8 *, pp + 8); p->size = (u32)RD(int, pp + 0x10);
    return p->objs && p->flags && p->size > 0 && p->size <= 8192;
}
static u32 handle_of(const struct pool *p, const u8 *obj, u32 stride) {
    u64 off; u32 i;
    if (!obj || obj < p->objs) return 0;
    off = (u64)(obj - p->objs); i = (u32)(off / stride);
    if (off % stride || i >= p->size || (p->flags[i] & 0x80)) return 0;
    return (i << 8) | p->flags[i];
}
static u8 *obj_of(const struct pool *p, u32 handle, u32 stride) {
    u32 i = handle >> 8;
    if (!handle || i >= p->size || p->flags[i] != (handle & 0xff)) return 0;
    return p->objs + (u64)i * stride;
}
static const float *pos_of(const u8 *ent) { const u8 *m = RD(const u8 *, ent + 0x18); return m ? (const float *)(m + 0x30) : (const float *)(ent + 8); }
static int ent_type(const u8 *ent) { return RD(u8, ent + 0x5a) & 7; }       /* 2 vehicle, 3 ped */
static u8 *player_ped(void) {
    u32 f = RD(u8, G + PLAYER_FOCUS);
    return f < 2 ? RD(u8 *, G + PLAYERS + (u64)f * PLAYER_INFO) : 0;
}
static void set_vec(hcb_vec *v, const float *p, float k) { v->x = p[0] * k; v->y = p[1] * k; v->z = p[2] * k; }

/* a ped from an entity that may be a ped or a vehicle (then its driver) */
static u32 ped_handle_of_entity(const struct pool *pp, const struct pool *vp, const u8 *ent) {
    u32 h = handle_of(pp, ent, PED_STRIDE);
    if (h) return h;
    if (handle_of(vp, ent, VEH_STRIDE)) return handle_of(pp, RD(const u8 *, ent + 0x5a0), PED_STRIDE);
    return 0;
}

/* whom an NPC is aiming at or fighting: read from his tasks (there is no such field in the ped) */
static u32 target_of(const struct pool *pp, const struct pool *vp, const u8 *ped, int *aiming) {
    const u8 *intel = RD(const u8 *, ped + 0x538), *t, *e = 0;
    int i;
    *aiming = 0;
    if (!intel) return 0;
    t = RD(const u8 *, intel + 0x30);                                  /* secondary slot 0: the attack task */
    if (t && RD(u64, t) == G + VT_USE_GUN) { e = RD(const u8 *, t + 0x28); *aiming = 1; }
    else if (t && RD(u64, t) == G + VT_FIGHT) e = RD(const u8 *, t + 0x20);
    for (i = 1; !e && i <= 3; i++) {                                   /* event response and primary slots */
        t = RD(const u8 *, intel + 0x8 + 8 * i);
        if (t && RD(u64, t) == G + VT_KILL_PED) e = RD(const u8 *, t + 0x20);
    }
    return e ? ped_handle_of_entity(pp, vp, e) : 0;
}

static void fill_ped(hcb_ped *o, const u8 *ped, u32 handle, const struct pool *pp, const struct pool *vp, const u8 *cj) {
    const u8 *m = RD(const u8 *, ped + 0x18), *pdata;
    u32 state = RD(u32, ped + 0x54c), acq_good, acq_bad, i;
    int slot = (signed char)RD(u8, ped + 0x8dc), aiming = 0;
    memset(o, 0, sizeof *o);
    o->id = handle;
    set_vec(&o->pos, pos_of(ped), 1.0f);
    set_vec(&o->vel, (const float *)(ped + 0x68), 50.0f);
    if (m) set_vec(&o->fwd, (const float *)(m + 0x10), 1.0f); else o->fwd.y = 1.0f;
    o->health = RD(float, ped + 0x6ac); o->armour = RD(float, ped + 0x6b4);
    o->model = (u16)RD(short, ped + 0x32);
    o->pedtype = (u8)RD(u32, ped + 0x720);
    o->weapon = slot >= 0 && slot < 13 ? (u8)RD(u32, ped + 0x730 + (u64)slot * 0x20) : 0;
    if (state == 54 || state == 55) o->flags |= HCB_PF_DEAD;
    if (RD(u8, ped + 0x586) & 1) o->flags |= HCB_PF_SHOOTING;
    if (RD(u32, ped + 0x584) & (1u << 26)) o->flags |= HCB_PF_DUCKING;
    if (RD(u8, ped + 0x548) == 2) o->flags |= HCB_PF_MISSION;
    acq_good = RD(u32, ped + 0x63c) | RD(u32, ped + 0x63c + 4); acq_bad = RD(u32, ped + 0x63c + 12) | RD(u32, ped + 0x63c + 16);
    if (acq_good & 1) o->flags |= HCB_PF_RESPECTS;                    /* bit 0 = ped type PLAYER1 */
    if (acq_bad & 1) o->flags |= HCB_PF_HATES;
    if (ped != cj) {
        o->target = target_of(pp, vp, ped, &aiming);
        if (aiming) o->flags |= HCB_PF_AIMING;
        pdata = cj ? RD(const u8 *, cj + 0x540) : 0;                  /* the player's group: recruited homies */
        if (pdata) {
            u32 grp = RD(u32, pdata + 0x4c);
            if (grp < 8) for (i = 0; i < 7; i++) if (RD(const u8 *, G + GROUPS + (u64)grp * GROUP_SIZE + 0x18 + 8 * i) == ped) o->flags |= HCB_PF_IN_GROUP;
        }
    } else o->target = handle_of(pp, RD(const u8 *, ped + 0x8e0), PED_STRIDE);     /* CJ: his lock-on target */
    if (RD(u8, ped + 0x585) & 1) {
        const u8 *veh = RD(const u8 *, ped + 0x708);
        o->vehicle = VID(handle_of(vp, veh, VEH_STRIDE));
        if (o->vehicle) { if (RD(const u8 *, veh + 0x5a0) == ped) o->flags2 |= HCB_PF2_DRIVER; else o->seat = 1; }
    }
    if (RD(const u8 *, ped + 0x900)) o->flags2 |= HCB_PF2_ON_FIRE;
}
static int law_model(int m) {       /* police, FBI, SWAT, army: cars, bikes, the Maverick */
    return (m >= 596 && m <= 599) || m == 523 || m == 497 || m == 427 || m == 490 || m == 528 || m == 601 || m == 432 || m == 433 || m == 470;
}
static void fill_veh(hcb_veh *o, const u8 *veh, u32 handle, const struct pool *pp) {
    const u8 *m = RD(const u8 *, veh + 0x18);
    u32 type = RD(u32, veh + 0x738);
    memset(o, 0, sizeof *o);
    o->id = VID(handle);
    o->driver = handle_of(pp, RD(const u8 *, veh + 0x5a0), PED_STRIDE);
    set_vec(&o->pos, pos_of(veh), 1.0f);
    set_vec(&o->vel, (const float *)(veh + 0x68), 50.0f);
    if (m) set_vec(&o->fwd, (const float *)(m + 0x10), 1.0f); else o->fwd.y = 1.0f;
    o->health = RD(float, veh + 0x634);
    o->model = (u16)RD(short, veh + 0x32);
    o->cls = type <= 2 || type == 11 ? HCB_VC_CAR : type == 9 || type == 10 ? HCB_VC_BIKE : type == 3 ? HCB_VC_HELI : type == 4 ? HCB_VC_PLANE : type == 5 ? HCB_VC_BOAT : HCB_VC_OTHER;
    if (RD(const u8 *, veh + 0x5f8) || o->health < 250.0f) o->flags |= HCB_VF_BURNING;
    if ((RD(u8, veh + 0x5a) >> 3) == 5) o->flags |= HCB_VF_WRECKED;
    if (RD(u8, veh + 0x610) == 2) o->flags |= HCB_VF_MISSION;
    if ((RD(u32, veh + 0x568) & 1) || law_model(o->model)) o->flags |= HCB_VF_EMERGENCY;
    o->passengers = RD(u8, veh + 0x5e8); o->max_passengers = RD(u8, veh + 0x5ec);
}

/* Helicover's scripts publish the handles of our people in CLEO's shared values */
static int shared_get(u32 key, u32 *val) {
    u64 b, e, cap, p;
    if (!g_cleo) return 0;
    b = RD(u64, g_cleo + CLEO_SHARED); e = RD(u64, g_cleo + CLEO_SHARED + 8); cap = RD(u64, g_cleo + CLEO_SHARED + 16);
    if (!b || b > e || e > cap || ((e - b) & 7) || e - b > 8 * 4096) return 0;
    for (p = b; p < e; p += 8) if (RD(u32, p) == key) { *val = RD(u32, p + 4); return 1; }
    return 0;
}

/* (the brain only changes a value the scripts have created: CLEO's buffer is never grown from here) */
static int shared_set(u32 key, u32 val) {
    u64 b, e, cap, p;
    if (!g_cleo) return 0;
    b = RD(u64, g_cleo + CLEO_SHARED); e = RD(u64, g_cleo + CLEO_SHARED + 8); cap = RD(u64, g_cleo + CLEO_SHARED + 16);
    if (!b || b > e || e > cap || ((e - b) & 7) || e - b > 8 * 4096) return 0;
    for (p = b; p < e; p += 8) if (RD(u32, p) == key) { RD(u32, p + 4) = val; return 1; }
    return 0;
}

/* ---------- gunshots, seen by the hook as they happen ---------- */
struct shot { const u8 *ent; float o[3], t[3]; u32 time; };
#define SHOTS 64
static struct shot g_shots[SHOTS];
static u32 g_shot_head, g_shot_tail;
typedef void *(*gunshot_fn)(void *self, const u8 *ent, float ox, float oy, float oz, float tx, float ty, float tz, int silent);
static gunshot_fn g_gunshot_orig;
HIDDEN void *brain_gunshot(void *self, const u8 *ent, float ox, float oy, float oz, float tx, float ty, float tz, int silent) {
    if (g_ready) {
        struct shot *s = &g_shots[g_shot_head % SHOTS];
        if (g_shot_head - g_shot_tail >= SHOTS) { g_shot_tail++; g_events_lost++; }
        int i;
        s->ent = ent; s->o[0] = ox; s->o[1] = oy; s->o[2] = oz; s->t[0] = tx; s->t[1] = ty; s->t[2] = tz; s->time = RD(u32, G + TIME_MS);
        g_shot_head++;
        /* somebody who is not ours has fired: the brain looks again at once instead of waiting for its next turn */
        for (i = 0; i < HCB_MAX_OURS + 2; i++) if (g_our_ent[i] == ent) break;
        if (i == HCB_MAX_OURS + 2 && ent) g_urgent = 1;     /* (a round without a shooter - a scripted one - is no reason to hurry) */
    }
    return g_gunshot_orig(self, ent, ox, oy, oz, tx, ty, tz, silent);
}

/* ---------- damage to CJ and ours, found by watching their health ---------- */
struct watch { u32 id, stamp; float hp; };
static struct watch g_watch[HCB_MAX_OURS + 2];
static void add_event(hcb_snapshot *s, int type, u32 src, u32 dst, float value, int weapon, const float *a, const float *b) {
    hcb_event *e;
    if (s->n_events >= HCB_MAX_EVENTS) { s->events_lost++; g_events_lost++; return; }
    e = &s->events[s->n_events++];
    memset(e, 0, sizeof *e);
    e->time = s->time; e->src = src; e->dst = dst; e->value = value; e->type = (u8)type; e->weapon = (u8)weapon;
    if (a) set_vec(&e->a, a, 1.0f);
    if (b) set_vec(&e->b, b, 1.0f);
}
static void watch_damage(hcb_snapshot *s, u32 id, float hp, u32 stamp, const u8 *by, int weapon, const struct pool *pp, const struct pool *vp) {
    int i, free_i = -1;
    for (i = 0; i < (int)(sizeof g_watch / sizeof g_watch[0]); i++) {
        if (g_watch[i].id == id) break;
        if (!g_watch[i].id && free_i < 0) free_i = i;
    }
    if (i == (int)(sizeof g_watch / sizeof g_watch[0])) {
        if (free_i < 0) return;
        i = free_i; g_watch[i].id = id; g_watch[i].hp = hp; g_watch[i].stamp = stamp;
        return;
    }
    if (hp < g_watch[i].hp - 0.5f) add_event(s, HCB_EV_DAMAGE, by && stamp != g_watch[i].stamp ? ped_handle_of_entity(pp, vp, by) : 0, id, g_watch[i].hp - hp, weapon, 0, 0);
    g_watch[i].hp = hp; g_watch[i].stamp = stamp;
}

/* ---------- one look at the world ---------- */
typedef int (*los_fn)(const float *a, const float *b, int buildings, int vehicles, int peds, int objects, int dummies, int see_through, int camera);
/* Buildings, vehicles and objects block; people do not. `ignore` (may be 0) is one entity the ray passes through:
   the vehicle the target sits in - otherwise a man in a car is always "behind something". */
/* A point the game may be given: a number (not NaN, not infinite) inside the map. The game's own search through the
   map's sectors never ends for a point that is not a number - the whole game hangs (the old freeze over the marker). */
static int sane(const float *p) {
    int i;
    for (i = 0; i < 3; i++) if (!(p[i] - p[i] == 0.0f)) return 0;
    return p[0] > -4000.0f && p[0] < 4000.0f && p[1] > -4000.0f && p[1] < 4000.0f && p[2] > -300.0f && p[2] < 3000.0f;
}
static u64 now_us(void);
static int ray_budget_left(void) { return g_frame_ray_us < RAY_FRAME_US; }
static int ray(const float *p, const float *q, const u8 *ignore) {
    const u8 **slot = (const u8 **)(G + IGNORE_ENTITY), *old = 0;
    int r;
    u64 t0, dt;
    u32 was = g_where;
    float dx = p[0] - q[0], dy = p[1] - q[1], dz = p[2] - q[2];
    if (!sane(p) || !sane(q) || dx * dx + dy * dy + dz * dz > 400.0f * 400.0f) { g_rays_bad++; return 0; }   /* never given to the game */
    g_where = 2;
    t0 = now_us();
    if (g_ignore_ok) { old = *slot; *slot = ignore; }
    r = ((los_fn)(G + G_LOS_CLEAR))(p, q, 1, 1, 0, 1, 0, 0, 0) != 0;
    if (g_ignore_ok) *slot = old;
    dt = now_us() - t0;
    g_frame_ray_us += dt;
    if (dt > g_ray_us_max) g_ray_us_max = dt;
    g_rays++;
    g_where = was;
    return r;
}
static const u8 *vehicle_of(const u8 *ped) { return (RD(u8, ped + 0x585) & 1) ? RD(const u8 *, ped + 0x708) : 0; }
static int sees(const u8 *a, const u8 *b) {              /* chest to chest, through the car the other man sits in */
    const float *pa = pos_of(a), *pb = pos_of(b);
    float p[3], q[3];
    p[0] = pa[0]; p[1] = pa[1]; p[2] = pa[2] + 0.6f; q[0] = pb[0]; q[1] = pb[1]; q[2] = pb[2] + 0.6f;
    return ray(p, q, vehicle_of(b));
}
static int is_dead(const u8 *ped) { u32 st = RD(u32, ped + 0x54c); return st == 54 || st == 55; }

static float f_sqrt(float x) {
    union { float f; u32 i; } u; float y;
    if (x <= 0) return 0;
    u.f = x; u.i = 0x1fbd1df5u + (u.i >> 1); y = u.f;
    y = 0.5f * (y + x / y); y = 0.5f * (y + x / y); y = 0.5f * (y + x / y); y = 0.5f * (y + x / y);
    return y;
}
static float dist2(const float *a, const float *b) { float x = a[0] - b[0], y = a[1] - b[1], z = a[2] - b[2]; return x * x + y * y + z * z; }

static int build_snapshot(hcb_snapshot *s, const hcb_out *prev) {
    struct pool pp, vp;
    const u8 *cj = player_ped(), *wanted, *e;
    const float *cjp;
    u32 cj_h, i, n, k, v, flag, mounted, los_left = RAY_CJ_LOOK, rays0 = g_rays;   /* rays per look: a few here + the core's questions, within the frame's budget */
    float best[HCB_MAX_PEDS], d;
    u32 idx[HCB_MAX_PEDS];

    if (!cj || !get_pool(PED_POOL, &pp) || !get_pool(VEH_POOL, &vp)) return 0;
    cj_h = handle_of(&pp, cj, PED_STRIDE);
    if (!cj_h) return 0;
    memset(s, 0, sizeof *s);
    s->time = RD(u32, G + TIME_MS); s->frame = g_ticks;
    fill_ped(&s->player, cj, cj_h, &pp, &vp, cj);
    cjp = pos_of(cj);
    if (!sane(cjp)) return 0;
    wanted = RD(const u8 *, G + PLAYERS + (u64)RD(u8, G + PLAYER_FOCUS) * PLAYER_INFO + 8);
    s->wanted = wanted ? (u8)RD(u32, wanted + 0x2c) : 0;
    flag = RD(u32, G + MISSION_FLAG);
    s->on_mission = flag && flag < SCRIPT_SPACE_SIZE - 4 && RD(u32, G + SCRIPT_SPACE + flag) == 1;
    s->cutscene = RD(u8, G + CUTSCENE) != 0;
    s->roe = HCB_ROE_DEFEND;
    if (shared_get(HC_FIRE, &v) && v <= 4) s->roe = (u8)v;
    if (shared_get(HC_POLICE, &v)) s->police = v == 1 ? HCB_POLICE_EVADE : HCB_POLICE_ANSWER;
    if (shared_get(HC_MISSION, &v)) s->mission_free = v == 1;
    if (shared_get(HC_TACTICS, &v)) s->tactics = (u8)(v <= 2 ? v : 0);   /* 0 AUTO, 1 ASSAULT, 2 GUARD */

    /* ours: what the scripts have published (a handle that no longer names a live ped is dropped) */
    if (shared_get(HC_PUB + 1, &v) && obj_of(&vp, v, VEH_STRIDE)) s->heli = VID(v);
    /* (the four of the crew are door gunners - their rounds are made by the script along a checked line - only while they are mounted;
       on foot they fire the game's own weapon like the ground team, and are judged like it) */
    mounted = !(shared_get(HC_PHASE, &v) && v == 1);
    /* (k: 0 pilot, 1-4 the crew, 5-8 guards 1-4, 9-12 guards 5-8, 13 the rope actor, 14-21 guards let go) */
    for (k = 0; k < 22 && s->n_ours < HCB_MAX_OURS; k++) {
        u32 key = k < 5 ? HC_PUB + 2 + k : k < 9 ? HC_GROUND + (k - 5) : k < 13 ? HC_GROUND2 + (k - 9) : k == 13 ? HC_GROUND + 4 : HC_LEAVE + (k - 14), n;
        if (!shared_get(key, &v) || !obj_of(&pp, v, PED_STRIDE) || v == cj_h) continue;
        for (n = 0; n < s->n_ours && s->ours[n] != v; n++) {}
        if (n < s->n_ours) continue;                    /* the same man published twice */
        s->ours[s->n_ours] = v;
        s->our_role[s->n_ours] = (u8)(k == 0 ? HCB_ROLE_PILOT : k < 5 ? (mounted ? HCB_ROLE_GUNNER : HCB_ROLE_SQUAD) + (k - 1) : k < 13 ? HCB_ROLE_SQUAD + (k - 5) : HCB_ROLE_NONE);
        s->n_ours++;
    }

    /* the nearest people within 150 m (ours always) */
    n = 0;
    for (i = 0; i < pp.size; i++) {
        const u8 *ped;
        int ours = 0;
        if (pp.flags[i] & 0x80) continue;
        ped = pp.objs + (u64)i * PED_STRIDE;
        if (ped == cj || !sane(pos_of(ped))) continue;
        d = dist2(pos_of(ped), cjp);
        for (k = 0; k < s->n_ours; k++) if (s->ours[k] == ((i << 8) | pp.flags[i])) ours = 1;
        if (ours) d = 0;
        else if (d > 150.0f * 150.0f) continue;
        if (n == HCB_MAX_PEDS) { s->peds_lost++; if (d >= best[n - 1]) continue; n--; }
        for (k = n; k > 0 && d < best[k - 1]; k--) { best[k] = best[k - 1]; idx[k] = idx[k - 1]; }
        best[k] = d; idx[k] = i; n++;
    }
    for (k = 0; k < n; k++) {
        const u8 *ped = pp.objs + (u64)idx[k] * PED_STRIDE;
        hcb_ped *o = &s->peds[k];
        fill_ped(o, ped, (idx[k] << 8) | pp.flags[idx[k]], &pp, &vp, cj);
        /* can he see CJ? asked only for people with a firearm in their hands, a few per look */
        if (los_left && ray_budget_left() && !(o->flags & HCB_PF_DEAD) && hcb_weapon_class(o->weapon) >= HCB_WC_PISTOL && best[k] > 0 && best[k] < 70.0f * 70.0f) {
            o->flags2 |= HCB_PF2_LOS_KNOWN | (sees(ped, cj) ? HCB_PF2_LOS_CLEAR : 0);
            los_left--;
        }
    }
    s->n_peds = (u16)n;
    if (n > g_peds_max) g_peds_max = n;

    n = 0;
    for (i = 0; i < vp.size; i++) {
        const u8 *veh;
        if (vp.flags[i] & 0x80) continue;
        veh = vp.objs + (u64)i * VEH_STRIDE;
        if (!sane(pos_of(veh))) continue;
        d = dist2(pos_of(veh), cjp);
        if (d > 150.0f * 150.0f) continue;
        if (n == HCB_MAX_VEHS) { if (d >= best[n - 1]) continue; n--; }
        for (k = n; k > 0 && d < best[k - 1]; k--) { best[k] = best[k - 1]; idx[k] = idx[k - 1]; }
        best[k] = d; idx[k] = i; n++;
    }
    for (k = 0; k < n; k++) fill_veh(&s->vehs[k], vp.objs + (u64)idx[k] * VEH_STRIDE, (idx[k] << 8) | vp.flags[idx[k]], &pp);
    s->n_vehs = (u16)n;

    /* shots since the last look */
    while (g_shot_tail != g_shot_head) {
        struct shot *q = &g_shots[g_shot_tail % SHOTS];
        u32 src = ped_handle_of_entity(&pp, &vp, q->ent);
        const u8 *who = obj_of(&pp, src, PED_STRIDE);
        int slot = who ? (signed char)RD(u8, who + 0x8dc) : -1;
        add_event(s, HCB_EV_SHOT, src, 0, 0, slot >= 0 && slot < 13 ? (int)RD(u32, who + 0x730 + (u64)slot * 0x20) : 0, q->o, q->t);
        if (src == cj_h) {
            float dx = q->t[0] - q->o[0], dy = q->t[1] - q->o[1], len2 = dx * dx + dy * dy;
            if (len2 > 0.04f) { float len = f_sqrt(len2); g_cj_shot_t = q->time; g_cj_shot_dir[0] = dx / len; g_cj_shot_dir[1] = dy / len; }
        } else {
            /* a stranger's round that passes close to our helicopter (the pilot, still flying by the scripts' rules, breaks away) */
            const u8 *hl = obj_of(&vp, VHANDLE(s->heli), VEH_STRIDE);
            for (k = 0; k < s->n_ours && s->ours[k] != src; k++) {}
            if (hl && k == s->n_ours) {
                const float *h = pos_of(hl);
                float d[3], ap[3], l2 = 0, t = 0, dist = 0;
                for (i = 0; i < 3; i++) { d[i] = q->t[i] - q->o[i]; ap[i] = h[i] - q->o[i]; l2 += d[i] * d[i]; t += ap[i] * d[i]; }
                t = l2 > 0.01f ? t / l2 : 0; t = t < 0 ? 0 : t > 1.2f ? 1.2f : t;
                for (i = 0; i < 3; i++) { float e = ap[i] - d[i] * t; dist += e * e; }
                if (dist < 36.0f && l2 > 1.0f) g_heli_shot_t = q->time;
            }
        }
        g_shot_tail++;
    }
    /* damage: CJ, ours, the helicopter */
    watch_damage(s, cj_h, s->player.health + s->player.armour, RD(u32, cj + 0x948), RD(const u8 *, cj + 0x940), (signed char)RD(u8, cj + 0x93c), &pp, &vp);
    for (k = 0; k < s->n_ours; k++) {
        e = obj_of(&pp, s->ours[k], PED_STRIDE);
        if (e) watch_damage(s, s->ours[k], RD(float, e + 0x6ac) + RD(float, e + 0x6b4), RD(u32, e + 0x948), RD(const u8 *, e + 0x940), (signed char)RD(u8, e + 0x93c), &pp, &vp);
    }
    e = obj_of(&vp, VHANDLE(s->heli), VEH_STRIDE);
    if (e) watch_damage(s, s->heli, RD(float, e + 0x634), (u32)(u64)RD(const u8 *, e + 0x698), RD(const u8 *, e + 0x698), (signed char)RD(u8, e + 0x694), &pp, &vp);

    /* the lines of sight the core asked for on the previous look. They come most important first: the first few are
       answered on every look, the rest in turn, as far as the frame's budget goes. A question left for the next look
       is no harm: the core keeps an answer 0.6 s, and a man it has no fresh answer for is aimed at, not fired at. */
    {
        u32 nq = prev->n_queries < HCB_MAX_LOS ? prev->n_queries : HCB_MAX_LOS, first = nq < RAY_ASK_FIRST ? nq : RAY_ASK_FIRST;
        u32 rest = nq - first, asked = 0, m, r = 0;
        for (m = 0; m < nq && asked < RAY_ASK_LOOK && ray_budget_left(); m++) {
            u32 q = m < first ? m : first + (g_ask_cursor + r++) % rest;
            const u8 *a = obj_of(&pp, prev->queries[q].from, PED_STRIDE), *b = obj_of(&pp, prev->queries[q].to, PED_STRIDE);
            hcb_los *l = &s->los[s->n_los++];
            l->from = prev->queries[q].from; l->to = prev->queries[q].to;
            l->clear = (u8)(a && b && sees(a, b));
            asked++;
        }
        if (rest) g_ask_cursor = (g_ask_cursor + r) % rest;
        g_rays_skipped += nq - asked;
    }
    /* the cover questions of the protective detail: is a man crouching at `at` hidden from the threat's chest, and is there
       ground just under the spot? (two rays each, within the same budget) */
    {
        u32 nq = prev->n_probe_q < HCB_MAX_PROBES ? prev->n_probe_q : HCB_MAX_PROBES;
        for (i = 0; i < nq && ray_budget_left(); i++) {
            const hcb_probe *q = &prev->probe_q[i];
            hcb_probe *a = &s->probes[s->n_probes++];
            float from[3], low[3], up[3], down[3];
            *a = *q;
            from[0] = q->from.x; from[1] = q->from.y; from[2] = q->from.z;
            low[0] = q->at.x; low[1] = q->at.y; low[2] = q->at.z - 0.3f;
            up[0] = q->at.x; up[1] = q->at.y; up[2] = q->at.z + 0.5f;
            down[0] = q->at.x; down[1] = q->at.y; down[2] = q->at.z - 1.9f;
            a->hidden = (u8)!ray(from, low, 0);
            a->ground = (u8)!ray(up, down, 0);
        }
        g_rays_skipped += nq - i;
    }
    if (g_rays - rays0 > g_rays_look_max) g_rays_look_max = g_rays - rays0;
    /* who is ours, for the gunshot hook */
    g_our_ent[0] = cj; g_our_ent[1] = obj_of(&vp, VHANDLE(s->heli), VEH_STRIDE);
    for (k = 0; k < HCB_MAX_OURS; k++) g_our_ent[2 + k] = k < s->n_ours ? obj_of(&pp, s->ours[k], PED_STRIDE) : 0;
    return 1;
}

/* ---------- the report ---------- */
static u64 now_us(void) { struct timespec t; t.tv_sec = 0; t.tv_nsec = 0; clock_gettime(1, &t); return (u64)t.tv_sec * 1000000UL + (u64)t.tv_nsec / 1000UL; }
static void first_line_of(struct text *t, const char *path, const char *key) {
    char b[2048]; long n; int fd = open(path, O_RDONLY), i, j, k;
    if (fd < 0) return;
    n = read(fd, b, sizeof(b) - 1); close(fd);
    if (n <= 0) return;
    b[n] = 0;
    for (i = 0; b[i]; i++) {
        for (k = 0; key[k] && b[i + k] == key[k]; k++) {}
        if (!key[k]) { for (j = i; b[j] && b[j] != '\n'; j++) {} b[j] = 0; ts(t, b + i); ts(t, "\n"); return; }
        while (b[i] && b[i] != '\n') i++;
        if (!b[i]) return;
    }
}
static void save_report(const char *why) {
    hcb_box_head head;
    const hcb_rec *old = &g_rec[g_cur ^ 1], *cur = &g_rec[g_cur];
    char name[32] = "hcbrain_report_00.bin";
    int n;
    g_note.len = 0;
    ts(&g_note, "Helicover Brain " VERSION "\nsaved: "); ts(&g_note, why);
    ts(&g_note, "\nticks "); tu(&g_note, g_ticks); ts(&g_note, ", think time avg "); tu(&g_note, g_ticks ? g_tick_us_sum / g_ticks : 0);
    ts(&g_note, " us, max "); tu(&g_note, g_tick_us_max); ts(&g_note, " us\nmost peds in a look "); tu(&g_note, g_peds_max);
    ts(&g_note, ", events lost "); tu(&g_note, g_events_lost); ts(&g_note, ", rays "); tu(&g_note, g_rays);
    ts(&g_note, " (most in a look "); tu(&g_note, g_rays_look_max); ts(&g_note, ", longest "); tu(&g_note, g_ray_us_max); ts(&g_note, " us, left for a later look ");
    tu(&g_note, g_rays_skipped); ts(&g_note, ", points refused as not a number or off the map "); tu(&g_note, g_rays_bad); ts(&g_note, ")");
    ts(&g_note, "\nlooks put off to keep the brain under a quarter of the time "); tu(&g_note, g_looks_skipped); ts(&g_note, ", brain in one frame at most ");
    tu(&g_note, g_frame_brain_us_max); ts(&g_note, " us, longest frame "); tu(&g_note, g_gap_max_us / 1000); ts(&g_note, " ms, crawls "); tu(&g_note, g_crawls);
    ts(&g_note, "\nrounds let go "); tu(&g_note, g_rounds); ts(&g_note, ", refused "); tu(&g_note, g_rounds_refused); ts(&g_note, ", with a bad point "); tu(&g_note, g_rounds_bad);
    ts(&g_note, "\nscripts bridge: "); ts(&g_note, g_bridge == 1 ? "opcode 0E48" : g_cleo ? "CLEO recognised, opcode not registered" : "none (CLEO not recognised)");
    ts(&g_note, "\nscreen "); ti(&g_note, RD(int, G + RSGLOBAL + 8)); ts(&g_note, "x"); ti(&g_note, RD(int, G + RSGLOBAL + 12)); ts(&g_note, "\n");
    first_line_of(&g_note, "/proc/meminfo", "MemTotal");
    first_line_of(&g_note, "/proc/meminfo", "MemAvailable");
    first_line_of(&g_note, "/proc/cpuinfo", "Hardware");
    first_line_of(&g_note, "/sys/devices/system/cpu/present", "0");
    hcb_box_head_fill(&head, cur, BRAIN, g_note.len);
    head.records += old->records; head.data_len += old->end - old->start;
    /* a new file every time: the first free number (the last one is reused when all 99 are taken) */
    for (n = 1; n < 99; n++) { name[15] = (char)('0' + n / 10); name[16] = (char)('0' + n % 10); if (!file_exists(name)) break; }
    name[15] = (char)('0' + n / 10); name[16] = (char)('0' + n % 10);
    if (write_file4(name, &head, sizeof head, g_box[g_cur ^ 1] + old->start, old->end - old->start, g_box[g_cur] + cur->start, cur->end - cur->start, g_note.buf, g_note.len)) g_dumps++;
}

/* ---------- the two per-frame entries ---------- */
typedef void (*void_fn)(void);
static void_fn g_scripts_orig, g_hud_orig;
static void journal(u32 now);
static void think(void) {
    u32 now = RD(u32, G + TIME_MS), every = g_out.alert >= HCB_ALERT_THREAT ? 50 : 100, fresh = 0;
    u64 t0;
    /* ten looks a second of game time, twenty while there is a threat, and at once (but not more often than every
       40 ms) when somebody who is not ours has just fired */
    if (now >= g_last_think && now - g_last_think < every && !(g_urgent && now - g_last_think >= 40)) return;
    t0 = now_us();
    /* never more than a quarter of the real time: a look that cost 6 ms waits at least 18 ms before the next one, so a
       slow game is never made slower by the brain looking again in every one of its (longer) frames */
    if (g_think_end_us && t0 - g_think_end_us < 3 * g_think_cost_us) { g_looks_skipped++; return; }
    g_urgent = 0;
    if (!build_snapshot(&g_snap, &g_out)) return;
    g_last_think = now;
    if (g_rec[g_cur].end + hcb_brain_size() + sizeof(hcb_snapshot) + 4096 > BOX_BYTES) {   /* this half is full: the other takes over */
        g_cur ^= 1; hcb_rec_init(&g_rec[g_cur], BOX_BYTES); fresh = 1;
    }
    if (fresh || g_ticks % 50 == 0) hcb_rec_push_state(&g_rec[g_cur], g_box[g_cur], BRAIN);
    hcb_think(BRAIN, &g_snap, &g_out);
    if (g_out.say) { g_say_seq = g_out.say_seq; g_say = g_out.say; g_say_dir = g_out.say_dir; }
    journal(now);
    hcb_rec_push(&g_rec[g_cur], g_box[g_cur], &g_snap, g_out.digest);
    memcpy(&g_shown, &g_out, sizeof g_shown);
    g_ticks++;
    g_think_end_us = now_us();
    t0 = g_think_end_us - t0;
    g_think_cost_us = t0;
    g_tick_us_sum += t0;
    if (t0 > g_tick_us_max) g_tick_us_max = (u32)t0;
    /* a report on request, and by itself when CJ dies: those are the moments worth looking at */
    if (g_snap.player.health <= 0 && g_was_alive) save_report("CJ died");
    g_was_alive = g_snap.player.health > 0;
    if (__atomic_exchange_n(&g_dump_request, 0, __ATOMIC_ACQ_REL)) save_report("asked for in Mods Settings");
}
/* ---------- 1.4.1: the door gunners fire their own weapons through the game's weapon code ----------
   CWeapon::Fire (+ CPed::DoGunFlash, as the game's own gun task does): the sound, the muzzle flash, the tracer and the hit
   are the game's. The brain still decides every round and checks its line first (hcb_gunner_round, then a ray); the
   gunner's script only keeps his weapon on the man. brain/research/weapon_fire_facts.md has the proofs. */
#define WEAPON_FIRE 0x700c64UL
#define PED_GUNFLASH 0x59bcb0UL
static const struct { u32 at, word; } FIRE_WORDS[] = {
    {0x700c64, 0xd10243ffU}, {0x700c68, 0x6d0223e9U}, {0x700dc4, 0xb9400668U}, {0x700dd0, 0xb9400a68U},
    {0x700e64, 0x9400018cU}, {0x7011a0, 0x9111c2a0U}, {0x7013a0, 0xb9001268U}, {0x7016c8, 0xb9469ac8U},
    {0x7016cc, 0x370018c8U}, {0x59bcb0, 0xf81e0ff3U}, {0x59bcc8, 0xf9432e68U}, {0x70157c, 0x3d637a60U},
};
typedef int (*weapon_fire_fn)(void *weapon, void *firer, float *start, float *barrel, void *target_ent, float *target_pos, float *alt);
typedef int (*gunflash_fn)(void *ped, int divisor, int left);
static void cmd_gunner(int *v);
static float get_f(const int *v);
static int g_fire_ready;                /* the words match and it was not turned off */
static u32 g_own_shots, g_own_refused;
static void fire_setup(void) {
    u32 i;
    if (g_fire_off) { lg("the gunners' own weapon fire is off (the game crashed in it once): they fire by the drive-by task\n"); return; }
    for (i = 0; i < sizeof FIRE_WORDS / sizeof FIRE_WORDS[0]; i++)
        if (RD(u32, G + FIRE_WORDS[i].at) != FIRE_WORDS[i].word) { lg("the game's weapon code differs at "); tx(&g_log, FIRE_WORDS[i].at); lg(": the gunners fire by the drive-by task\n"); return; }
    g_fire_ready = 1;
    hcb_config(BRAIN)->gunner_weapon = 0.0f;   /* every round is the brain's, checked on its own line */
    lg("the gunners fire their own weapons through the game's weapon code (12 words match)\n");
}
/* one round of one mounted gunner, if the brain lets it go now (called after the scripts, every frame) */
static void gunner_shot(u32 who) {
    struct pool pp;
    int v[9];
    u8 *ped, *w;
    float s[3], bpos[3], t[3], d[3], len;
    u32 old, cur;
    v[0] = (int)who;
    cmd_gunner(v);
    if (v[1] != 2 || !get_pool(PED_POOL, &pp) || !(ped = obj_of(&pp, who, PED_STRIDE)) || is_dead(ped)) return;
    t[0] = get_f(v + 6); t[1] = get_f(v + 7); t[2] = get_f(v + 8);
    memcpy(s, pos_of(ped), 12); s[2] += 0.5f;                          /* from the gunner's own gun, not 5.5 m out */
    d[0] = t[0] - s[0]; d[1] = t[1] - s[1]; d[2] = t[2] - s[2]; len = f_sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
    if (!(len > 2.0f) || !sane(s) || !sane(t)) { g_own_refused++; return; }
    s[0] += d[0] / len * 0.8f; s[1] += d[1] / len * 0.8f; s[2] += d[2] / len * 0.8f;   /* clear of his own hands and the skid */
    cur = (u32)(int)RD(signed char, ped + 0x8dc);
    if (cur > 12) return;
    w = ped + 0x730 + (u64)cur * 0x20;
    if (RD(u32, w) < 22 || RD(u32, w) > 38 || (RD(u32, w) > 34 && RD(u32, w) != 38)) { g_own_refused++; return; }   /* instant-hit guns only */
    if (RD(int, w + 4) > 1) RD(int, w + 4) = 0;                        /* never stalled by a reload */
    if (RD(int, w + 8) < 2) RD(int, w + 8) = 2;
    if (RD(int, w + 0xc) < 25000) RD(int, w + 0xc) = 30000;            /* an NPC's ammo above 25000 is never used up */
    RD(u8, ped + 0x8de) = 100;                                          /* the brain scattered the round already: no second spread */
    old = RD(u32, ped + 0x698); RD(u32, ped + 0x698) = old | 1;        /* the IK bit: the round goes to the target point */
    memcpy(bpos, s, 12);
    g_where = 20;
    if (((weapon_fire_fn)(G + WEAPON_FIRE))(w, ped, s, bpos, 0, t, 0)) {
        g_own_shots++;
        if (RD(int, w + 4) == 1) ((gunflash_fn)(G + PED_GUNFLASH))(ped, 250, 0);
    } else g_own_refused++;
    g_where = 4;
    RD(u32, ped + 0x698) = old;
}
static void gunners_fire(void) {
    u32 k, v;
    if (!g_fire_ready || !g_ticks || !(shared_get(HC_PHASE, &v) && v == 2)) return;   /* (PHASE 2: the crew is in its doors) */
    for (k = 0; k < g_snap.n_ours; k++)
        if (g_snap.our_role[k] >= HCB_ROLE_GUNNER && g_snap.our_role[k] < HCB_ROLE_SQUAD) gunner_shot(g_snap.ours[k]);
}
/* ---------- the journal (1.4.1): what the brain decided, in plain words, for the diagnosis from the log ----------
   Changes of the alert, of the detail's duty and mode, every word of the commander, and every 30 s a summary: how much of
   the fight the gunners and the guards fired and what held them, how many posts were not reached. At most 40 lines a
   minute (a busy fight is summarised, not written out). */
static u32 j_alert = 99, j_duty = 99, j_at, j_lines, j_lines_at, j_combat, j_looks, j_fire[2], j_seen[2], j_hold[2][32], j_stuck, j_lead;
static void jline(u32 now) {
    if (now - j_lines_at > 60000) { j_lines_at = now; j_lines = 0; }
    j_lines++;
    lg("["); tu(&g_log, now / 1000); lg("s] ");
}
static void journal(u32 now) {
    static const char *ALERT[] = {"calm", "wary", "threat", "COMBAT", "EVACUATE"};
    static const char *DUTY[] = {"calm", "watch", "shield", "cover", "bound", "hold", "ring"};
    static const char *SAY[] = {"", "into cover", "CJ is in cover", "stay with me", "we pull out", "I have command", "clear"};
    u32 i, k, g, top;
    j_looks++;
    if (g_out.alert >= HCB_ALERT_COMBAT) {
        j_combat++;
        for (i = 0; i < g_out.n_orders; i++) {
            const hcb_order *o = &g_out.orders[i];
            for (k = 0; k < g_snap.n_ours && g_snap.ours[k] != o->who; k++) {}
            if (k == g_snap.n_ours) continue;
            g = g_snap.our_role[k] >= HCB_ROLE_GUNNER && g_snap.our_role[k] < HCB_ROLE_SQUAD ? 0 : 1;
            j_seen[g]++;
            if (o->fire) j_fire[g]++; else if (o->hold < 32) j_hold[g][o->hold]++;
        }
    }
    for (i = 0; i < g_out.n_posts; i++) if (g_out.posts[i].stuck) j_stuck++;
    if (j_lines > 40 && now - j_lines_at <= 60000) goto summary;
    log_begin();
    if (g_out.alert != j_alert && g_out.alert < 5) { jline(now); lg("alert "); lg(ALERT[g_out.alert]); lg(", CJ health "); ti(&g_log, (long)g_snap.player.health); lg("\n"); j_alert = g_out.alert; }
    if (g_out.duty != j_duty && g_out.duty < 7) { jline(now); lg("detail: "); lg(DUTY[g_out.duty]); lg(", mode "); tu(&g_log, g_out.mode); lg(", "); tu(&g_log, g_out.n_posts); lg(" posts\n"); j_duty = g_out.duty; }
    if (g_out.say && g_out.say < 7) { jline(now); lg("commander: \""); lg(SAY[g_out.say]); lg("\" (direction "); tu(&g_log, g_out.say_dir); lg(")\n"); }
    if (g_out.leading != j_lead) { jline(now); lg(g_out.leading ? "commander leads CJ to cover\n" : "commander stops leading\n"); j_lead = g_out.leading; }
    log_end();
summary:
    if (!j_at) j_at = now;
    if (now - j_at < 30000) return;
    log_begin();
    jline(now); lg("30 s: looks "); tu(&g_log, j_looks); lg(", in combat "); tu(&g_log, j_combat);
    for (g = 0; g < 2; g++) {
        lg(g ? " | guards: " : " | gunners: ");
        if (!j_seen[g]) { lg("-"); continue; }
        lg("fire "); tu(&g_log, j_fire[g] * 100 / j_seen[g]); lg("%");
        for (k = 0; k < 2; k++) {                                   /* the two commonest reasons not to fire */
            top = 0;
            for (i = 1; i < 32; i++) if (j_hold[g][i] > j_hold[g][top]) top = i;
            if (!j_hold[g][top]) break;
            lg(", hold "); tu(&g_log, top); lg(" "); tu(&g_log, j_hold[g][top] * 100 / j_seen[g]); lg("%");
            j_hold[g][top] = 0;
        }
    }
    lg(" | posts not reached (looks) "); tu(&g_log, j_stuck); lg(" | gunners' own shots "); tu(&g_log, g_own_shots); lg(" (refused "); tu(&g_log, g_own_refused); lg(")"); lg(" | CJ health "); ti(&g_log, (long)g_snap.player.health); lg("\n");
    flush_log();
    log_end();
    j_at = now; j_looks = j_combat = j_stuck = 0; memset(j_fire, 0, sizeof j_fire); memset(j_seen, 0, sizeof j_seen); memset(j_hold, 0, sizeof j_hold);
}
/* ---------- the bridge to Helicover's scripts: one private CLEO opcode ---------- */
typedef void *(*script_fn)(void *script);
typedef int (*register_fn)(u16 opcode, void *handler);
static script_fn g_read_param, g_var_ptr;
static u32 g_bridge_try, g_bridge_note;

static void put_f(int *v, float f) { memcpy(v, &f, 4); }
/* the positions of this frame for one question about one of ours and his man */
static void fill_shot(hcb_shot *q, u32 who, u32 target, const struct pool *pp, const u8 *cj, const u8 *me, const u8 *him, float up_me, float up_him) {
    u32 k;
    memset(q, 0, sizeof *q);
    q->who = who; q->target = target; q->time = RD(u32, G + TIME_MS);
    set_vec(&q->cj, pos_of(cj), 1.0f);
    set_vec(&q->from, pos_of(me), 1.0f); q->from.z += up_me; q->muzzle = q->from;
    set_vec(&q->to, pos_of(him), 1.0f); q->to.z += up_him;
    for (k = 0; k < g_snap.n_ours && q->n_friends < HCB_MAX_OURS; k++) {
        const u8 *e = g_snap.ours[k] != who ? obj_of(pp, g_snap.ours[k], PED_STRIDE) : 0;
        if (e && !is_dead(e)) set_vec(&q->friends[q->n_friends++], pos_of(e), 1.0f);
    }
}

/* A door gunner. His rounds are made by the script (they are not the game's weapon fire), so the brain paces them and
   gives each one its line: from just outside the helicopter to a point scattered round the man, ending 0.6 m past it
   (the core: hcb_gunner_round). The line is checked against the hard rules with the positions of this very frame, then
   by a ray here. */
static void cmd_gunner(int *v) {
    struct pool pp, vp;
    u32 who = (u32)v[0];
    const u8 *cj = player_ped(), *me, *him, *heli;
    hcb_order o;
    hcb_shot q;
    hcb_round r;
    float speed = 0;
    int near_heli;

    v[1] = 0; v[2] = 0;
    if (!hcb_order_get(BRAIN, who, &o) || !o.target || !cj || !get_pool(PED_POOL, &pp) || !get_pool(VEH_POOL, &vp)) return;
    me = obj_of(&pp, who, PED_STRIDE); him = obj_of(&pp, o.target, PED_STRIDE);
    if (!me || !him || is_dead(him) || is_dead(me)) return;
    v[2] = (int)o.target; v[1] = o.ready ? 1 : 0;
    if (!o.fire) return;
    if (!ray_budget_left()) return;                    /* this frame's rays are spent: the round waits a frame (its pace is kept) */
    heli = obj_of(&vp, VHANDLE(g_snap.heli), VEH_STRIDE);
    near_heli = heli && dist2(pos_of(heli), pos_of(me)) < 36.0f;
    if (near_heli) { const float *hv = (const float *)(heli + 0x68); speed = 50.0f * f_sqrt(hv[0] * hv[0] + hv[1] * hv[1] + hv[2] * hv[2]); }
    if (!(speed >= 0.0f && speed < 150.0f)) speed = 0.0f;   /* a helicopter moved by the scripts may carry anything in its speed */
    fill_shot(&q, who, o.target, &pp, cj, me, him, 0.3f, 0.2f);
    if (!sane(&q.from.x) || !sane(&q.to.x) || !sane(&q.cj.x)) { g_rounds_bad++; return; }
    if (!hcb_gunner_round(BRAIN, &q, speed, near_heli, &r)) return;
    if (r.verdict == HCB_HOLD_NONE && (!sane(&r.muzzle.x) || !sane(&r.end.x) || !sane(&r.to.x))) { g_rounds_bad++; hcb_gunner_blocked(BRAIN, who, q.time); return; }
    if (r.verdict == HCB_HOLD_NONE) {
        r.ray = (u8)ray(&r.muzzle.x, &r.to.x, vehicle_of(him));
        if (!r.ray) hcb_gunner_blocked(BRAIN, who, q.time);
    }
    if (r.verdict == HCB_HOLD_NONE && r.ray) {
        v[1] = 2;
        put_f(v + 3, r.muzzle.x); put_f(v + 4, r.muzzle.y); put_f(v + 5, r.muzzle.z);
        put_f(v + 6, r.end.x); put_f(v + 7, r.end.y); put_f(v + 8, r.end.z);
        g_rounds++;
    } else g_rounds_refused++;
    if ((r.note || (r.verdict == HCB_HOLD_NONE && !r.ray)) && g_rec[g_cur].end + sizeof r + 64 <= BOX_BYTES) hcb_rec_push_round(&g_rec[g_cur], g_box[g_cur], &r);
}
/* A guard on foot fires the game's own weapon: the brain says at whom and whether, and takes the permission back in
   the same frame when CJ or one of ours has come into his line. */
static void cmd_squad(int *v) {
    struct pool pp;
    u32 who = (u32)v[0];
    const u8 *cj = player_ped(), *me, *him;
    hcb_order o;
    hcb_shot q;

    v[1] = 0; v[2] = 0;
    if (!hcb_order_get(BRAIN, who, &o) || !o.target || !cj || !get_pool(PED_POOL, &pp)) return;
    me = obj_of(&pp, who, PED_STRIDE); him = obj_of(&pp, o.target, PED_STRIDE);
    if (!me || !him || is_dead(him) || is_dead(me)) return;
    v[2] = (int)o.target;
    fill_shot(&q, who, o.target, &pp, cj, me, him, 0, 0);
    v[1] = hcb_squad_state(BRAIN, &q);
    if (g_fire_ready && v[1] == 2) {                                   /* a mounted gunner: weapon on the man, the brain fires */
        u32 k;
        for (k = 0; k < g_snap.n_ours; k++) if (g_snap.ours[k] == who && g_snap.our_role[k] >= HCB_ROLE_GUNNER && g_snap.our_role[k] < HCB_ROLE_SQUAD) v[1] = 4;
    }
}
/* A guard of the detail: where to be and how (the fire order is asked for separately, command 2) */
static void cmd_post(int *v) {
    u32 who = (u32)v[0], i;
    v[1] = -1;
    for (i = 0; i < g_out.n_posts; i++) {
        const hcb_post *p = &g_out.posts[i];
        if (p->who != who) continue;
        v[1] = p->move; put_f(v + 2, p->at.x); put_f(v + 3, p->at.y); put_f(v + 4, p->at.z);
        v[5] = p->crouch; put_f(v + 6, p->look.x); put_f(v + 7, p->look.y); put_f(v + 8, p->look.z); v[9] = p->duty;
        return;
    }
}
static void cmd_detail(int *v) {
    v[0] = g_say_seq; v[1] = g_say; v[2] = g_say_dir; v[3] = g_out.duty; v[4] = g_out.cover_ok;
    put_f(v + 5, g_out.cover_at.x); put_f(v + 6, g_out.cover_at.y); put_f(v + 7, g_out.cover_at.z); v[8] = (int)g_out.lead;
}
/* 1.4: the pilot (core/hcb_pilot.c). It keeps its own state for Helicover's helicopter; the position on the ground plane is
   read back every frame (whatever moved it), the height is its own (SET_CAR_COORDINATES puts a helicopter a little higher
   than asked: read back, it would creep up). The turn it wants is written into the helicopter's matrix after the scripts
   have run (pilot_turn), so nothing the script does in the same frame can undo it. */
static hcb_pilot g_pilot;
static u32 g_pilot_heli;
static struct { u32 heli; hcb_vec right, fwd, up; u8 on; } g_turn;
static float get_f(const int *v) { float f; memcpy(&f, v, 4); return f; }
static void zero_mem(void *d, u32 n) { u8 *q = d; while (n--) *q++ = 0; }
static int unit_ok(hcb_vec a) { float l = a.x * a.x + a.y * a.y + a.z * a.z; return l > 0.9f && l < 1.1f; }
static void cmd_pilot(int *v) {
    struct pool vp;
    u32 heli = (u32)v[0], now = RD(u32, G + TIME_MS), mine;
    const u8 *e, *m;
    const float *mp;
    float t[3];
    hcb_vec pos, vel, fwd;
    hcb_pilot_in in;
    hcb_pilot_out o;
    v[5] = -1;
    if (!shared_get(HC_PUB + 1, &mine) || mine != heli || !get_pool(VEH_POOL, &vp)) return;   /* only Helicover's own helicopter */
    e = obj_of(&vp, heli, VEH_STRIDE);
    m = e ? RD(const u8 *, e + 0x18) : 0;
    if (!m) return;
    mp = (const float *)(m + 0x30);
    t[0] = get_f(v + 1); t[1] = get_f(v + 2); t[2] = get_f(v + 3);
    if (!sane(mp) || !sane(t)) return;
    pos.x = mp[0]; pos.y = mp[1]; pos.z = mp[2];
    fwd.x = RD(float, m + 0x10); fwd.y = RD(float, m + 0x14); fwd.z = 0;
    vel.x = RD(float, e + 0x68) * 50.0f; vel.y = RD(float, e + 0x6c) * 50.0f; vel.z = RD(float, e + 0x70) * 50.0f;
    if (!g_pilot.used || g_pilot_heli != heli || now - g_pilot.last > 500) {
        hcb_pilot_reset(&g_pilot, pos, vel, fwd);
        g_pilot.last = now - 16; g_pilot_heli = heli;
    }
    g_pilot.pos.x = pos.x; g_pilot.pos.y = pos.y;
    if (!(g_pilot.pos.z - pos.z < 8.0f && pos.z - g_pilot.pos.z < 8.0f)) g_pilot.pos.z = pos.z;
    zero_mem(&in, sizeof in);
    in.target.x = t[0]; in.target.y = t[1]; in.ground = t[2];
    in.dt = (float)(now - g_pilot.last) * 0.001f;
    in.stop = (u8)(v[4] & 1); in.blocked = (u8)((v[4] >> 1) & 1);
    hcb_pilot_step(&g_pilot, &in, &o);
    g_pilot.last = now;
    put_f(v + 1, o.pos.x); put_f(v + 2, o.pos.y); put_f(v + 3, o.pos.z); put_f(v + 4, o.dist); put_f(v + 5, o.speed);
    g_turn.heli = heli; g_turn.right = o.right; g_turn.fwd = o.fwd; g_turn.up = o.up; g_turn.on = 1;
}
static void pilot_turn(void) {
    struct pool vp;
    u8 *e, *m;
    u32 mine;
    if (!g_turn.on) return;
    g_turn.on = 0;
    if (!unit_ok(g_turn.right) || !unit_ok(g_turn.fwd) || !unit_ok(g_turn.up)) return;
    if (!shared_get(HC_PUB + 1, &mine) || mine != g_turn.heli || !get_pool(VEH_POOL, &vp)) return;
    e = obj_of(&vp, g_turn.heli, VEH_STRIDE);
    m = e ? RD(u8 *, e + 0x18) : 0;
    if (!m) return;
    RD(float, m + 0x00) = g_turn.right.x; RD(float, m + 0x04) = g_turn.right.y; RD(float, m + 0x08) = g_turn.right.z;
    RD(float, m + 0x10) = g_turn.fwd.x; RD(float, m + 0x14) = g_turn.fwd.y; RD(float, m + 0x18) = g_turn.fwd.z;
    RD(float, m + 0x20) = g_turn.up.x; RD(float, m + 0x24) = g_turn.up.y; RD(float, m + 0x28) = g_turn.up.z;
}
/* v[5] = ms since CJ last fired (-1 = long ago), v[6], v[7] = the direction of that shot (unit vector, floats): the
   squad steps out of his line of fire */
static void cmd_status(int *v, int count) {
    struct pool pp;
    u32 i, now = RD(u32, G + TIME_MS);
    v[0] = g_out.alert; v[1] = g_out.n_threats; v[2] = g_out.n_attackers; v[3] = g_out.kills; v[4] = 0;
    if (count >= 8) {
        v[5] = g_cj_shot_t && now - g_cj_shot_t < 60000 ? (int)(now - g_cj_shot_t) : -1;
        put_f(v + 6, g_cj_shot_dir[0]); put_f(v + 7, g_cj_shot_dir[1]);
    }
    if (count >= 9) v[8] = g_heli_shot_t && now - g_heli_shot_t < 60000 ? (int)(now - g_heli_shot_t) : -1;
    if (count >= 10) v[9] = g_out.gunner_pose;                                     /* 1.4.1: how the gunners hold (the brain's) */
    if (count >= 13) { if (g_out.heli_ok) { put_f(v + 10, g_out.heli_at.x); put_f(v + 11, g_out.heli_at.y); put_f(v + 12, g_out.heli_at.z); } else v[10] = v[11] = v[12] = 0; }
    if (!get_pool(PED_POOL, &pp)) return;
    for (i = 0; i < g_out.n_marks; i++) {
        const hcb_mark *m = &g_out.marks[i];
        const u8 *e = m->kind == HCB_KIND_PED && m->cls >= HCB_CLS_THREAT ? obj_of(&pp, m->id, PED_STRIDE) : 0;
        if (e && !is_dead(e)) { v[4] = (int)m->id; return; }
    }
}
/* 0E48 first_variable count command. Called by CLEO inside the script's turn (game thread). All three parameters are
   always consumed, whatever happens next: a parameter left unread would be run as an opcode. */
HIDDEN void brain_opcode(void *script, u8 **ip, u16 opcode, const char *name) {
    int *vars = (int *)g_var_ptr(script);
    int count = *(int *)g_read_param(script);
    int cmd = *(int *)g_read_param(script);
    u8 *first = (u8 *)script + 0x6c;
    (void)ip; (void)opcode; (void)name;
    /* only a block of the script's own 32 local variables is ever written */
    if (!vars || (u8 *)vars < first || (u8 *)vars >= first + 32 * 4 || (((u8 *)vars - first) & 3) || count < 1 || ((u8 *)vars - first) / 4 + count > 32) return;
    if (!g_ready || g_busy || !g_ticks) { if (cmd != CMD_STATUS && count >= 3) { vars[1] = 0; vars[2] = 0; } return; }
    g_busy = 1; g_where = 10 + (u32)(cmd & 7);
    if (cmd == CMD_GUNNER && count >= 9) cmd_gunner(vars);
    else if (cmd == CMD_SQUAD && count >= 3) cmd_squad(vars);
    else if (cmd == CMD_STATUS && count >= 5) cmd_status(vars, count);
    else if (cmd == CMD_POST && count >= 10) cmd_post(vars);
    else if (cmd == CMD_DETAIL && count >= 9) cmd_detail(vars);
    else if (cmd == CMD_PILOT && count >= 6) cmd_pilot(vars);
    g_busy = 0; g_where = 0;
}
/* Is this the CLEO the bridge was studied on, and has it found the same game? 0 = yes, else what is wrong. */
static u32 cleo_refuses(void) {
    u32 i;
    for (i = 0; i < sizeof CLEO_WORDS / sizeof CLEO_WORDS[0]; i++) if (RD(u32, g_cleo + CLEO_IMAGE + CLEO_WORDS[i].at) != CLEO_WORDS[i].word) return 1;
    if (RD(u64, g_cleo + CLEO_IFS + 8 * 17) != g_cleo + CLEO_REGISTER || RD(u64, g_cleo + CLEO_IFS + 8 * 19) != g_cleo + CLEO_READ_PARAM
        || RD(u64, g_cleo + CLEO_IFS + 8 * 20) != g_cleo + CLEO_VAR_PTR) return 2;
    if (RD(u64, g_cleo + CLEO_G_COLLECT) != G + G_COLLECT || RD(u64, g_cleo + CLEO_G_VARPTR) != G + G_VARPTR || RD(u64, g_cleo + CLEO_G_BASE) != G) return 3;
    return 0;
}
static void bridge(void) {
    static const char *const WHY[4] = {"", "CLEO's code is not the build the bridge was made for", "CLEO's plugin table is not where it should be",
                                       "CLEO has not found the game's script functions (yet)"};
    u32 now = RD(u32, G + TIME_MS), v, why;
    if (!g_cleo) return;
    if (g_bridge == 1) {                       /* the handshake: the scripts create the value with 0 after every (re)start */
        if (shared_get(HC_HELLO, &v) && v != HELLO_MAGIC) shared_set(HC_HELLO, HELLO_MAGIC);
        return;
    }
    if (g_bridge || (g_bridge_try && now - g_bridge_try < 1000)) return;
    g_bridge_try = now ? now : 1;
    why = cleo_refuses();
    if (!why) {
        g_read_param = (script_fn)(g_cleo + CLEO_READ_PARAM); g_var_ptr = (script_fn)(g_cleo + CLEO_VAR_PTR);
        g_bridge = ((register_fn)(g_cleo + CLEO_REGISTER))(BRAIN_OPCODE, (void *)&brain_opcode) ? 1 : -1;
    }
    if (why == g_bridge_note && !g_bridge) return;                     /* said already; keep trying quietly */
    g_bridge_note = why;
    log_begin();
    if (g_bridge == 1) lg("bridge: opcode 0E48 registered with CLEO - Helicover's scripts can ask the brain\n");
    else if (g_bridge == -1) lg("bridge: CLEO refused opcode 0E48 (the number is taken) - Helicover will not work\n");
    else { lg("bridge: not yet - "); lg(WHY[why]); lg("\n"); }
    flush_log();
    log_end();
}
/* "The game is crawling": twenty frames in a row each longer than a quarter of a second (a pause, a menu or a switch to
   another app does not count: the frames do not run then, and a gap over 5 s is not counted). One report is saved
   by itself the first time, with what the brain cost in those frames. */
static void watch_frames(u64 t, u64 brain_us) {
    u64 gap = g_frame_at_us ? t - g_frame_at_us : 0;
    if (gap > 250000 && gap < 5000000) g_slow_run++; else g_slow_run = 0;
    if (gap < 5000000 && gap > g_gap_max_us) g_gap_max_us = gap;
    if (brain_us > g_frame_brain_us_max) g_frame_brain_us_max = brain_us;
    if (g_slow_run == 20) {
        g_crawls++;
        log_begin();
        lg("the game crawled: 20 frames in a row over 0.25 s (the last "); tu(&g_log, gap / 1000); lg(" ms); the brain took ");
        tu(&g_log, brain_us); lg(" us of it, rays this frame "); tu(&g_log, g_frame_ray_us); lg(" us\n");
        flush_log(); log_end();
        if (g_crawls == 1) save_report("the game crawled (20 frames in a row over 0.25 s)");
    }
}
HIDDEN void brain_scripts(void) {
    u64 t = now_us();
    if (!g_main_tid) g_main_tid = syscall(178);        /* gettid: the game's thread, for the hang recorder */
    g_frame_ray_us = 0;
    if (g_ready && !g_busy) { g_busy = 1; g_where = 1; bridge(); think(); g_where = 0; g_busy = 0; watch_frames(t, now_us() - t); }
    g_frame_at_us = t;
    g_scripts_orig();
    if (g_ready && !g_busy) { g_busy = 1; g_where = 4; pilot_turn(); gunners_fire(); g_where = 0; g_busy = 0; }
}

typedef void (*poly_fn)(float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4, const u8 *rgba);
typedef int (*screen_fn)(const float *in, float *out, float *w, float *h, int far_clip, int near_clip);
static void square(float x, float y, float r, const u8 *c) { ((poly_fn)(G + G_DRAW_POLY))(x - r, y - r, x + r, y - r, x - r, y + r, x + r, y + r, c); }
/* Where CJ is to go (the commander's "into cover"): a pulsing green chevron over the spot and a dot on it, drawn whatever the
   debug markers setting is - it is the detail's sign to the player, the way a bodyguard points. */
static void draw(void) {
    static const u8 COL[5][4] = {{60, 200, 90, 220}, {150, 150, 150, 0}, {250, 220, 40, 230}, {255, 140, 0, 240}, {240, 40, 40, 255}};
    static const u8 ALLY[4] = {70, 150, 255, 220}, EDGE[4] = {0, 0, 0, 200}, BAR[5][4] = {{90, 90, 90, 150}, {250, 220, 40, 220}, {255, 140, 0, 230}, {240, 40, 40, 240}, {255, 255, 255, 255}};
    struct pool pp, vp;
    float W = (float)RD(int, G + RSGLOBAL + 8), H = (float)RD(int, G + RSGLOBAL + 12), in[3], out[3], w, h, r;
    u32 i, k;
    if (!g_marks || !g_ticks || RD(u8, G + USER_PAUSE) || W < 100 || H < 100) return;
    /* a small strip at the top of the screen: the alert level (and proof that the brain is running) */
    {
        const u8 *c = BAR[g_shown.alert <= 4 ? g_shown.alert : 4];
        float x1 = W * 0.47f, x2 = W * 0.53f, y1 = H * 0.012f, y2 = H * 0.022f + 3;
        ((poly_fn)(G + G_DRAW_POLY))(x1, y1, x2, y1, x1, y2, x2, y2, c);
    }
    if (!get_pool(PED_POOL, &pp) || !get_pool(VEH_POOL, &vp)) return;
    for (i = 0; i < g_shown.n_marks; i++) {
        const hcb_mark *m = &g_shown.marks[i];
        const u8 *e = m->kind == HCB_KIND_PED ? obj_of(&pp, m->id, PED_STRIDE) : obj_of(&vp, VHANDLE(m->id), VEH_STRIDE), *c;
        const float *p;
        if (!e || !m->seen || m->cls > HCB_CLS_ATTACKER || m->cls == HCB_CLS_NEUTRAL) continue;
        p = pos_of(e);
        in[0] = p[0]; in[1] = p[1]; in[2] = p[2] + (m->kind == HCB_KIND_PED ? 1.25f : 1.8f);
        if (!((screen_fn)(G + G_CALC_SCREEN))(in, out, &w, &h, 1, 1)) continue;
        if (out[0] < 0 || out[0] > W || out[1] < 0 || out[1] > H) continue;
        r = h * 0.11f; r = r < H * 0.004f ? H * 0.004f : r > H * 0.014f ? H * 0.014f : r;
        if (m->kind == HCB_KIND_VEH) r *= 1.6f;
        c = m->cls == HCB_CLS_FRIEND ? (m->why == HCB_WHY_OURS ? COL[0] : ALLY) : COL[m->cls];
        for (k = 0; k < g_shown.n_orders; k++)          /* a white frame: ours are firing at him */
            if (g_shown.orders[k].fire && g_shown.orders[k].target == m->id) { square(out[0], out[1], r + H * 0.0046f, BAR[4]); break; }
        square(out[0], out[1], r + H * 0.0016f, EDGE);
        square(out[0], out[1], r, c);
    }
}
HIDDEN void brain_hud(void) {
    g_hud_orig();
    if (g_ready && !g_busy) { g_busy = 1; g_where = 3; draw(); g_where = 0; g_busy = 0; }   /* (1.4.1: no cover mark - the commander walks CJ there) */
}

/* ---------- Mods Settings (SAUtils) ---------- */
static const char *g_onoff[2] = {"Off", "On"};
static const char *g_save[2] = {"Tap to save", "Tap to save again"};
static void set_marks(int o, int v, void *d) { (void)o; (void)d; g_marks = v != 0; save_config(); }
static void ask_report(int o, int v, void *d) { (void)o; (void)v; (void)d; __atomic_store_n(&g_dump_request, 1, __ATOMIC_RELEASE); }
static void add_menu_items(void) {
    typedef void *(*getif_fn)(const char *);
    typedef int (*add_fn)(void *self, int type, const char *name, int init, int min, int max, const char **sw, void (*cb)(int, int, void *));
    void *aml = dlopen("libAML.so", RTLD_NOW), *sa; getif_fn getif = aml ? (getif_fn)dlsym(aml, "GetInterface") : 0; add_fn add;
    sa = getif ? getif("SAUtils") : 0;
    if (!sa) { lg("SAUtils not found - no settings items (a report is still saved when CJ dies)\n"); return; }
    add = (add_fn)((*(void ***)sa)[3]);   /* ISAUtils::AddClickableItem, as Touch x4 and CLEO UI use it */
    add(sa, 5, "Brain markers", g_marks, 0, 1, g_onoff, set_marks);
    add(sa, 5, "Brain report", 0, 0, 1, g_save, ask_report);
    lg("Mods Settings: Brain markers, Brain report\n");
}

/* ---------- install ---------- */
static u64 g_page, g_cleo_base, g_cleo_size;
static int g_slots;
static int ends_with(const char *s, const char *tail) {
    u64 n, m = slen(tail), i;
    if (!s) return 0;
    n = slen(s);
    if (n < m) return 0;
    for (i = 0; i < m; i++) if (s[n - m + i] != tail[i]) return 0;
    return 1;
}
static int find_modules(struct dl_phdr_info *info, u64 size, void *data) {
    int i; u64 hi = 0;
    (void)size; (void)data;
    if (ends_with(info->dlpi_name, "libGTASA.so")) G = info->dlpi_addr;
    else if (ends_with(info->dlpi_name, "libSAcleo64.so")) {
        for (i = 0; i < info->dlpi_phnum; i++) if (info->dlpi_phdr[i].type == 1 && info->dlpi_phdr[i].vaddr + info->dlpi_phdr[i].memsz > hi) hi = info->dlpi_phdr[i].vaddr + info->dlpi_phdr[i].memsz;
        g_cleo_base = info->dlpi_addr; g_cleo_size = hi;
    }
    return 0;
}
static int got_swap(u64 slot, u64 expect, u64 mine, u64 *orig) {
    volatile u64 *p = (volatile u64 *)(G + slot);
    u64 page = (G + slot) & ~(g_page - 1);
    if (*p != G + expect) return 0;
    *orig = *p;
    if (mprotect((void *)page, g_page, PROT_READ | PROT_WRITE)) return 0;
    __atomic_store_n((u64 *)p, mine, __ATOMIC_RELEASE);
    mprotect((void *)page, g_page, PROT_READ);
    return 1;
}
/* 0 = the game is not loaded yet, 1 = running, -1 = this is not the game build the brain was made for */
static int try_install(void) {
    u32 i; const char *v; u64 a, b, c;
    G = 0; g_cleo_base = 0;
    dl_iterate_phdr(find_modules, 0);
    if (!G) return 0;
    for (i = 0; i < sizeof GTA_WORDS / sizeof GTA_WORDS[0]; i++)
        if (RD(u32, G + GTA_WORDS[i].at) != GTA_WORDS[i].word) {
            lg("libGTASA.so differs from the build the brain was made for at "); tx(&g_log, GTA_WORDS[i].at); lg(": found "); tx(&g_log, RD(u32, G + GTA_WORDS[i].at));
            lg(", expected "); tx(&g_log, GTA_WORDS[i].word); lg("\nnothing changed. Helicover Brain does not run on this game.\n");
            return -1;
        }
    if (RD(u64, G + GOT_SCRIPTS) != G + GOT_SCRIPTS_TARGET) {
        lg("the GOT slot of CTheScripts::Process is not what it should be (another mod has taken it?): "); tx(&g_log, RD(u64, G + GOT_SCRIPTS) - G);
        lg("\nnothing changed. Helicover Brain cannot run beside that mod.\n");
        return -1;
    }
    /* CLEO: only its shared values are read, and only when it is the known build */
    g_cleo = 0;
    if (g_cleo_base && g_cleo_size >= CLEO_MIN_SIZE) {
        v = (const char *)(g_cleo_base + CLEO_VERSION);
        for (i = 0; CLEO_VERSION_TEXT[i] && v[i] == CLEO_VERSION_TEXT[i]; i++) {}
        if (!CLEO_VERSION_TEXT[i]) g_cleo = g_cleo_base;
    }
    lg(g_cleo ? "CLEO recognised\n" : "CLEO not recognised (or not started yet): without it Helicover's scripts cannot ask the brain\n");
    if (hcb_brain_size() > BRAIN_BYTES) { lg("internal: brain larger than its buffer\n"); return -1; }
    hcb_init(BRAIN, 1);
    hcb_rec_init(&g_rec[0], BOX_BYTES); hcb_rec_init(&g_rec[1], BOX_BYTES); g_cur = 0;
    g_ignore_ok = RD(u64, G + GOT_IGNORE) == G + IGNORE_ENTITY;
    if (!g_ignore_ok) lg("the line-of-sight code does not read its ignore pointer where expected: a man in a car will count as hidden\n");
    /* the per-frame slot is what the brain cannot do without; without the other two it still watches and records */
    if (!got_swap(GOT_SCRIPTS, GOT_SCRIPTS_TARGET, (u64)&brain_scripts, &c)) { lg("could not change the scripts slot - nothing changed\n"); return -1; }
    g_scripts_orig = (void_fn)c; g_slots = 1;
    if (got_swap(GOT_GUNSHOT, GOT_GUNSHOT_TARGET, (u64)&brain_gunshot, &a)) { g_gunshot_orig = (gunshot_fn)a; g_slots++; }
    else { lg("the gunshot slot is taken or could not be changed: shots will not be seen (damage still is)\n"); }
    if (got_swap(GOT_HUD, GOT_HUD_TARGET, (u64)&brain_hud, &b)) { g_hud_orig = (void_fn)b; g_slots++; }
    else { lg("the HUD slot is taken or could not be changed: no markers on screen (the report still works)\n"); }
    __atomic_store_n(&g_ready, 1, __ATOMIC_RELEASE);
    lg("libGTASA.so base "); tx(&g_log, G); lg("\n"); tu(&g_log, sizeof GTA_WORDS / sizeof GTA_WORDS[0]); lg(" instruction words match; GOT slots pointing at the brain: "); tu(&g_log, (u64)g_slots); lg(" of 3 (no code changed)\nthe brain is running\n");
    fire_setup();
    return 1;
}
static void *waiter(void *arg) {
    int i, r = (int)(long)arg;                                          /* the state OnModLoad reached */
    for (i = 0; i < 600 && !r; i++) { usleep(200000); r = try_install(); }   /* up to two minutes */
    if (!r) lg("libGTASA.so did not appear within two minutes - nothing changed\n");
    /* CLEO starts later than the game: look for it for a while longer */
    for (i = 0; r == 1 && !g_cleo && i < 150; i++) {
        usleep(200000);
        g_cleo_base = 0; dl_iterate_phdr(find_modules, 0);
        if (g_cleo_base && g_cleo_size >= CLEO_MIN_SIZE) {
            const char *v = (const char *)(g_cleo_base + CLEO_VERSION); u32 k;
            for (k = 0; CLEO_VERSION_TEXT[k] && v[k] == CLEO_VERSION_TEXT[k]; k++) {}
            if (!CLEO_VERSION_TEXT[k]) { __atomic_store_n(&g_cleo, g_cleo_base, __ATOMIC_RELEASE); log_begin(); lg("CLEO recognised later\n"); log_end(); }
        }
    }
    log_begin(); flush_log(); log_end();
    return 0;
}

/* ---------- the hang recorder ----------
   A thread of its own looks at the game's frame counter twice a second. When no frame has come for 6 s and the game
   is not paused, the game's thread is stuck. Then, once (twice at most in a session), it writes to the log where that
   thread is - six looks 0.3 s apart: the address it runs at, the calls that led there (function names of libGTASA where
   the library has them) and where each CLEO script stands - and saves the black box. The game hangs either way; this
   is so the next fix is made from facts. The thread only reads, except one signal that makes the stuck thread tell its
   registers (only when it is running, not when it sleeps in the kernel). Memory is read through process_vm_readv, so a
   bad address is an error, never a crash. */
struct iovec_ { void *base; u64 len; };
static int safe_read(void *dst, u64 src, u64 n) {
    struct iovec_ l, r;
    if (src < 0x1000 || src > 0x0000ffffffffffffUL) return 0;
    l.base = dst; l.len = n; r.base = (void *)src; r.len = n;
    return syscall(270, syscall(172), &l, 1L, &r, 1L, 0L) == (long)n;      /* process_vm_readv(getpid(), ...) */
}
static volatile int g_smp_ready;
static volatile u64 g_smp_regs[4];      /* pc, lr, fp, sp */
HIDDEN void brain_on_sample(int sig, void *info, void *ucv) {
    const u8 *uc = (const u8 *)ucv;     /* arm64 ucontext: uc_mcontext at 176 (regs[29] 416, regs[30] 424, sp 432, pc 440) */
    (void)sig; (void)info;
    g_smp_regs[0] = RD(u64, uc + 440); g_smp_regs[1] = RD(u64, uc + 424); g_smp_regs[2] = RD(u64, uc + 416); g_smp_regs[3] = RD(u64, uc + 432);
    __atomic_store_n(&g_smp_ready, 1, __ATOMIC_RELEASE);
}
static void task_path(char *b, long tid, const char *leaf) {
    char d[24]; int n = 0, k = 0; const char *pre = "/proc/self/task/";
    while (*pre) b[k++] = *pre++;
    do { d[n++] = (char)('0' + tid % 10); tid /= 10; } while (tid && n < 20);
    while (n) b[k++] = d[--n];
    b[k++] = '/';
    while (*leaf) b[k++] = *leaf++;
    b[k] = 0;
}
static long read_small(const char *path, char *b, long cap) {
    int fd = open(path, O_RDONLY); long n;
    if (fd < 0) return 0;
    n = read(fd, b, (u64)cap - 1); close(fd);
    if (n < 0) n = 0;
    b[n] = 0;
    return n;
}
static u64 hexnum(const char **p) {
    u64 v = 0; const char *s = *p;
    while (*s == ' ') s++;
    if (s[0] == '0' && s[1] == 'x') s += 2;
    for (;; s++) { char c = *s; u32 d = c >= '0' && c <= '9' ? (u32)(c - '0') : c >= 'a' && c <= 'f' ? (u32)(c - 'a' + 10) : 99; if (d > 15) break; v = v * 16 + d; }
    *p = s;
    return v;
}
static void addr_name(u64 a) {
    Dl_info di; const char *f, *base;
    tx(&g_log, a);
    if (!dladdr((const void *)a, &di) || !di.dli_fname) return;
    for (f = base = di.dli_fname; *f; f++) if (*f == '/') base = f + 1;
    lg(" "); lg(base); lg("+"); tx(&g_log, a - (u64)di.dli_fbase);
    if (di.dli_sname) { lg(" "); lg(di.dli_sname); lg("+"); tx(&g_log, a - (u64)di.dli_saddr); }
}
static int is_code(u64 w) { return (w >= G && w < G + 0x900000UL) || (g_cleo_base && w >= g_cleo_base && w < g_cleo_base + g_cleo_size); }
static void one_look(long tid, int k, int running) {
    char path[64], b[512]; u64 pc = 0, lr = 0, fp = 0, sp = 0, a, w, fr[2]; u32 i, n;
    if (running) {
        __atomic_store_n(&g_smp_ready, 0, __ATOMIC_RELEASE);
        syscall(131, syscall(172), tid, 27L);                          /* tgkill(getpid(), tid, SIGPROF) */
        for (i = 0; i < 40 && !__atomic_load_n(&g_smp_ready, __ATOMIC_ACQUIRE); i++) usleep(5000);
        if (g_smp_ready) { pc = g_smp_regs[0]; lr = g_smp_regs[1]; fp = g_smp_regs[2]; sp = g_smp_regs[3]; }
    } else {                                                           /* asleep in the kernel: /proc tells the stack and pc */
        const char *q = b;
        task_path(path, tid, "syscall");
        if (read_small(path, b, sizeof b) && b[0] >= '0' && b[0] <= '9') { for (i = 0; i < 7; i++) hexnum(&q); sp = hexnum(&q); pc = hexnum(&q); }
    }
    lg("look "); tu(&g_log, (u64)k + 1); lg(": pc "); addr_name(pc); lg("\n  lr "); addr_name(lr); lg("\n");
    for (n = 0; fp && n < 16 && safe_read(fr, fp, 16); n++) {          /* the chain of frames */
        if (!fr[1]) break;
        lg("  called from "); addr_name(fr[1]); lg("\n");
        if (fr[0] <= fp) break;
        fp = fr[0];
    }
    for (a = sp, n = 0; sp && a < sp + 4096 && n < 14; a += 8)         /* return addresses left on the stack */
        if (safe_read(&w, a, 8) && is_code(w)) { lg("  on the stack "); addr_name(w); lg("\n"); n++; }
    if (g_cleo) {                                                      /* where every CLEO script stands */
        u64 be[2], obj, rs, base, ip; char nm[9];
        if (safe_read(be, g_cleo + CLEO_SCRIPTS, 16) && be[1] >= be[0] && be[1] - be[0] <= 64 * 8)
            for (a = be[0]; a < be[1]; a += 8) {
                if (!safe_read(&obj, a, 8) || !safe_read(&rs, obj + 0x20, 8) || !safe_read(&base, obj + 0x28, 8) || !safe_read(&ip, rs + 0x20, 8) || !safe_read(nm, rs + 0x10, 8)) continue;
                nm[8] = 0;
                for (i = 0; i < 8; i++) if (nm[i] && (nm[i] < 32 || nm[i] > 126)) nm[i] = '?';
                lg("  script "); lg(nm); lg(" at "); tx(&g_log, ip - base); lg("\n");
            }
    }
}
static void hang_dump(u32 secs) {
    static const u32 KEYS[] = {0, 1, 7, 20, 21, 27, 29, 440, 451, 452, 454, 455};
    char path[64], st[256]; const char *q; long tid = g_main_tid; u32 i, v, tries; int running = 0, locked = 0;
    struct sigact act, old;
    task_path(path, tid, "stat");
    if (read_small(path, st, sizeof st)) { for (q = st; *q && *q != ')'; q++) {} if (*q) running = q[2] == 'R'; }
    for (tries = 0; tries < 2000 && !locked; tries++) { if (!__atomic_exchange_n(&g_log_lock, 1, __ATOMIC_ACQUIRE)) locked = 1; else usleep(1000); }
    lg("\nHANG: no new frame for "); tu(&g_log, secs); lg(" s and the game is not paused. The game's thread is ");
    lg(running ? "running (a loop that does not end)" : "asleep (waiting for something)"); lg("; inside the brain: ");
    tu(&g_log, g_where); lg(" (0 = outside, 1 = a look, 2 = a ray, 3 = markers, 11-13 = a script's question)\nHelicover:");
    for (i = 0; i < sizeof KEYS / sizeof KEYS[0]; i++) if (shared_get(HC_STATE + KEYS[i], &v)) { lg(" +"); tu(&g_log, KEYS[i]); lg("="); ti(&g_log, (int)v); }
    lg("\n(if you had switched to another app, this is not a hang - ignore it)\n");
    memset(&act, 0, sizeof act); act.flags = 4 | 0x10000000; act.handler = (void *)&brain_on_sample;   /* SA_SIGINFO | SA_RESTART */
    if (running && sigaction(27, &act, &old)) running = 0;
    for (i = 0; i < 6; i++) { one_look(tid, (int)i, running); if (i < 5) usleep(300000); }
    if (running) sigaction(27, &old, 0);
    flush_log();
    if (locked) log_end();
    save_report("the game hung (see hcbrain_log.txt for where)");
}
/* ---------- the crash recorder (1.4.1): a crash of the game is written to the log before the game's own handler runs ----------
   Where (pc, lr, the fault address, the frames on the stack with their names), what the brain was doing (g_where) and
   what Helicover was doing; then a report is saved (once) and the previous handler takes over as if we were not there. */
static struct sigact g_crash_old[32];
static volatile u32 g_crashing;
static u32 g_crash_where;                 /* g_where at the crash, kept for the next start (written into the settings) */
static void crash_settings(u32 where);
HIDDEN void brain_on_crash(int sig, void *info, void *ucv) {
    static const u32 KEYS[] = {0, 1, 7, 20, 21, 27, 29, 440, 451, 452, 454, 455};
    const u8 *uc = (const u8 *)ucv;
    u64 pc = uc ? RD(u64, uc + 440) : 0, lr = uc ? RD(u64, uc + 424) : 0, sp = uc ? RD(u64, uc + 432) : 0, fp = uc ? RD(u64, uc + 416) : 0;
    u64 fault = info ? RD(u64, (const u8 *)info + 16) : 0, a, w, fr[2];
    u32 i, n, v, tries;
    if (__atomic_exchange_n(&g_crashing, 1, __ATOMIC_ACQ_REL)) goto pass;   /* a crash inside the recorder: let the game have it */
    for (tries = 0; tries < 200 && __atomic_exchange_n(&g_log_lock, 1, __ATOMIC_ACQUIRE); tries++) usleep(1000);
    g_crash_where = g_where;
    lg("\nCRASH: signal "); tu(&g_log, (u64)sig);
    lg(sig == 11 ? " (bad memory access)" : sig == 7 ? " (bus error)" : sig == 4 ? " (illegal instruction)" : sig == 8 ? " (arithmetic)" : sig == 6 ? " (abort)" : "");
    lg("\n  pc "); addr_name(pc); lg("\n  lr "); addr_name(lr); lg("\n  fault address "); tx(&g_log, fault);
    lg("\n  inside the brain: "); tu(&g_log, g_where);
    lg(" (0 outside, 1 a look, 2 a ray, 3 markers, 4 the pilot's turn, 11-16 a script's question, 20 a gunner's shot)\n");
    for (n = 0; fp && n < 16 && safe_read(fr, fp, 16); n++) { if (!fr[1]) break; lg("  called from "); addr_name(fr[1]); lg("\n"); if (fr[0] <= fp) break; fp = fr[0]; }
    for (a = sp, n = 0; sp && a < sp + 2048 && n < 10; a += 8) if (safe_read(&w, a, 8) && is_code(w)) { lg("  on the stack "); addr_name(w); lg("\n"); n++; }
    lg("  Helicover:");
    for (i = 0; i < sizeof KEYS / sizeof KEYS[0]; i++) if (shared_get(HC_STATE + KEYS[i], &v)) { lg(" +"); tu(&g_log, KEYS[i]); lg("="); ti(&g_log, (int)v); }
    lg("\n  brain looks "); tu(&g_log, g_ticks); lg("\n");
    flush_log();
    write_file("hcbrain_crash.txt", g_log.buf, g_log.len, 0, 0, 0, 0);   /* kept: the next start writes a new log */
    __atomic_store_n(&g_log_lock, 0, __ATOMIC_RELEASE);
    crash_settings(g_crash_where);
    if (g_ready && g_where != 5) save_report("the game crashed (see hcbrain_log.txt)");
pass:
    if (sig > 0 && sig < 32) sigaction(sig, &g_crash_old[sig], 0);     /* the game's (or AML's) own handler, as before */
    if (sig == 6) syscall(131, syscall(172), syscall(178), 6L);         /* abort is raised again; a fault repeats by itself */
}
static void crash_recorder_on(void) {
    static const int SIGS[] = {11, 7, 4, 8, 6};
    struct sigact act;
    u32 i;
    memset(&act, 0, sizeof act); act.flags = 4;                        /* SA_SIGINFO */
    act.handler = (void *)&brain_on_crash;
    for (i = 0; i < sizeof SIGS / sizeof SIGS[0]; i++) sigaction(SIGS[i], &act, &g_crash_old[SIGS[i]]);
}
static void *watchdog(void *arg) {
    u32 last = 0, still = 0, dumps = 0, fc;
    (void)arg;
    for (;;) {
        usleep(500000);
        if (!__atomic_load_n(&g_ready, __ATOMIC_ACQUIRE) || !g_main_tid) continue;
        fc = RD(u32, G + FRAME_COUNTER);
        if (fc != last || RD(u8, G + USER_PAUSE) || RD(u8, G + CODE_PAUSE)) { last = fc; still = 0; continue; }
        if (++still == 12 && dumps < 2) { dumps++; hang_dump(still / 2); }
    }
    return 0;
}

struct ModInfo { char guid[48]; char name[48]; char version[24]; char author[48]; u16 ver[4]; u8 reserved[336]; };
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.brain", "Helicover Brain", "0.4", "Helicover", {0, 4, 0, 0}, {0}};
static int g_done;
EXPORT struct ModInfo *__GetModInfo(void) { return &g_info; }
EXPORT void OnModPreLoad(void) {}
EXPORT void OnModLoad(void) {
    u64 th; int r;
    if (g_done) return;
    g_done = 1;
    g_page = (u64)getpagesize();
    if (g_page < 4096 || (g_page & (g_page - 1))) g_page = 4096;
    lg("Helicover Brain " VERSION "\n");
    load_config();
    add_menu_items();
    r = try_install();
    if (r != -1 && (r == 0 || !g_cleo)) { if (pthread_create(&th, 0, waiter, (void *)(long)r)) lg("cannot start the waiting thread\n"); else lg("waiting (for the game or for CLEO)\n"); }
    if (r != -1) { if (pthread_create(&th, 0, watchdog, 0)) lg("cannot start the hang recorder\n"); else lg("hang recorder on\n"); }
    if (r != -1) { crash_recorder_on(); lg("crash recorder on\n"); if (g_last_crash == 20) { g_fire_off = 1; lg("the last game crashed in a gunner's shot: the game's weapon fire stays off from now on\n"); }
        if (g_last_crash) { if (g_last_crash == 99) lg("the last game crashed outside the brain"); else { lg("the last game crashed inside the brain at step "); tu(&g_log, g_last_crash); } lg(" (the CRASH block was in the log of that game)\n"); g_last_crash = 0; save_config(); } }
    ti(&g_log, r); lg(" = state at load\n");
    flush_log();
}
