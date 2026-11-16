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
#define O_APPEND 02000
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
#define VERSION "1.1 (places by weights, corners and doorways, tokens; the mod keeps the game AI off its men, fires their weapons, holds their ropes; map cache, path thread, numbers in the settings)"
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
#define HC_MODE (HC_STATE + 573)            /* 1.0: the player's mode on the menu: 0 PROTECT, 1 ASSAULT */
#define HC_RECALL (HC_STATE + 574)          /* 1.0: the menu's "to me": the scripts write 1, the brain takes it (10 s) and writes 0 */
#define HC_NATIVE (HC_STATE + 575)          /* 1.0: written by the brain: 1 = it walks the guards itself (the scripts leave their legs alone) */
#define HELLO_MAGIC 0x42520021U             /* "BR", interface 2, the opcode is registered */
#define BRAIN_OPCODE 0x0E48
#define CMD_GUNNER 1                        /* 9 variables: in handle; out state (0 rest, 1 aim, 2 fire this round), target, muzzle xyz, end xyz */
#define CMD_SQUAD 2                         /* 3 variables: in handle; out state (0 nothing, 1 cover, 2 fire, 3 cease fire now), target */
#define CMD_POST 4                          /* 10 variables: in handle; out move (-1 no post, 0 stay, 1 walk, 2 run, 3 sprint), x y z, crouch, look x y z, duty */
#define CMD_DETAIL 5                        /* 9 variables: out what the commander said last (seq, HCB_SAY_*, direction), duty, cover for CJ (ok, x y z), commander */
#define CMD_PLAN 7                          /* 1.0, 10 variables: out mode, the squad's task (HCB_TASK_*), a high place for the marksman (1 = there is one), the helicopter
                                               hangs over it steady (1), its x y z, metres to the squad's target, men on the move, the body (1 = the mod walks them) */
#define CMD_PILOT 6                         /* 6 variables: in helicopter, point x y, roofs z, flags (1 stop, 2 the last step was refused, 4 on station in a fight); out x y z, metres left, speed (-1 = no pilot) */
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

/* ---------- text building: the log and the text part of the report ----------
   0.4.1: the log is one file for the whole game (hcbrain_log.txt), written as it goes: the text gathers in g_log and a
   thread of the brain adds it to the end of the file twice a second, so when the game is swiped away (killed) at most the
   last half second is missing; a crash and a hang are written at once. Every thread may write: g_log has a lock, and the
   thread that holds it may take it again (a crash in the middle of a line still gets its block written). */
struct text { char *buf; u32 cap, len; };
#define LOG_BYTES (512 * 1024)
static char g_logbuf[LOG_BYTES], g_notebuf[2048];
static struct text g_log = {g_logbuf, sizeof g_logbuf, 0}, g_note = {g_notebuf, sizeof g_notebuf, 0};
static int g_log_lock;
static volatile long g_log_owner;
static u32 g_log_depth, g_log_dropped;
static volatile u32 g_crashing;
static int log_begin(void) {
    long me = syscall(178); u32 i;                                      /* gettid */
    if (__atomic_load_n(&g_log_owner, __ATOMIC_ACQUIRE) == me) { g_log_depth++; return 1; }
    for (i = 0; i < (g_crashing ? 200U : 3000U); i++) {
        if (!__atomic_exchange_n(&g_log_lock, 1, __ATOMIC_ACQUIRE)) { __atomic_store_n(&g_log_owner, me, __ATOMIC_RELEASE); g_log_depth = 1; return 1; }
        usleep(1000);
    }
    return 0;                                                           /* the thread that holds it is stuck: write anyway */
}
static void log_end(void) {
    if (__atomic_load_n(&g_log_owner, __ATOMIC_ACQUIRE) != syscall(178)) return;
    if (--g_log_depth == 0) { __atomic_store_n(&g_log_owner, 0, __ATOMIC_RELEASE); __atomic_store_n(&g_log_lock, 0, __ATOMIC_RELEASE); }
}
static void ts(struct text *t, const char *s) {
    int held = t == &g_log ? log_begin() : 0;
    while (*s && t->len < t->cap - 1) t->buf[t->len++] = *s++;
    if (*s && t == &g_log) g_log_dropped++;                             /* full (the file could not be written for a while) */
    t->buf[t->len] = 0;
    if (held) log_end();
}
static void tu(struct text *t, u64 v) { char b[24]; int n = 23; b[n] = 0; do { b[--n] = (char)('0' + v % 10); v /= 10; } while (v); ts(t, b + n); }
static void ti(struct text *t, long v) { if (v < 0) { ts(t, "-"); v = -v; } tu(t, (u64)v); }
static void tx(struct text *t, u64 v) { char b[19]; int i; b[0] = '0'; b[1] = 'x'; for (i = 0; i < 16; i++) { int d = (int)((v >> (60 - 4 * i)) & 15); b[2 + i] = (char)(d < 10 ? '0' + d : 'a' + d - 10); } b[18] = 0; ts(t, b); }
static void tf(struct text *t, float f) {                               /* one decimal */
    long w; u32 d;
    if (!(f == f) || f > 1e9f || f < -1e9f) { ts(t, "?"); return; }
    if (f < 0) { ts(t, "-"); f = -f; }
    w = (long)f; d = (u32)((f - (float)w) * 10.0f + 0.5f);
    if (d >= 10) { w++; d = 0; }
    tu(t, (u64)w); ts(t, "."); tu(t, d);
}
static void stamp(struct text *t, u32 now) { ts(t, "["); tu(t, now / 1000); ts(t, "."); tu(t, (now / 100) % 10); ts(t, "s] "); }
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
/* Adding to the end of the log file. At the start of a game a log over 24 MB is renamed hcbrain_log_old.txt (the one
   before it is lost) and a new one begun; during a game the same happens at 64 MB. Otherwise every game is added to the
   end, so the game that crashed is still there when the next one starts. */
#define LOG_NAME "hcbrain_log.txt"
#define LOG_OLD "hcbrain_log_old.txt"
#define LOG_KEEP (24UL << 20)
#define LOG_MAX (64UL << 20)
static u64 g_log_size, g_flush_us, g_log_written;
static int g_log_sized, g_flush_lock;
static u64 now_us(void);
static int append_here(const char *b, u32 n) {
    static const char MOVED[] = "(the log grew over 64 MB: the part before this line is in hcbrain_log_old.txt)\n";
    char path[640], old[640]; int fd, moved = 0; long size = (long)g_log_size, w;
    path_of(path, sizeof path, LOG_NAME);
    if (!g_log_sized || g_log_size > LOG_MAX) {
        size = 0;
        fd = open(path, O_RDONLY);
        if (fd >= 0) { size = syscall(62, (long)fd, 0L, 2L); close(fd); if (size < 0) size = 0; }   /* lseek(fd, 0, SEEK_END) */
        if ((u64)size > (g_log_sized ? LOG_MAX : LOG_KEEP)) {
            path_of(old, sizeof old, LOG_OLD);
            if (!syscall(38, -100L, path, -100L, old)) { size = 0; moved = g_log_sized; }                /* renameat */
        }
    }
    fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return 0;
    if (moved) size += write(fd, MOVED, sizeof MOVED - 1);
    w = write(fd, b, n); close(fd);
    if (w < 0) w = 0;
    g_log_size = (u64)size + (u64)w; g_log_sized = 1; g_log_written += (u64)w;
    return 1;
}
static int log_append(const char *b, u32 n) {
    Dl_info di; u32 k = 0, cut = 0; const char *f; char own[512];
    if (g_dir[0] && append_here(b, n)) return 1;                        /* the folder that worked before */
    /* AML's mods folder first (visible in a file manager), then next to the loaded .so, then the game's files dir */
    g_log_sized = 0; set_dir(GAME_DIR "mods/");
    if (append_here(b, n)) return 1;
    if (dladdr((const void *)&log_append, &di) && di.dli_fname) {
        for (f = di.dli_fname; *f && k < sizeof(own) - 2; f++) { own[k++] = *f; if (*f == '/') cut = k; }
        own[cut] = 0;
        if (cut) { g_log_sized = 0; set_dir(own); if (append_here(b, n)) return 1; }
    }
    g_log_sized = 0; set_dir("/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/");
    return append_here(b, n);
}
/* Never called while holding the log's lock (the writer thread takes this one first, then the log's). */
static void flush_log(void) {
    static char wbuf[LOG_BYTES];
    u32 n, i; int held;
    for (i = 0; __atomic_exchange_n(&g_flush_lock, 1, __ATOMIC_ACQUIRE); i++) { if (i >= 3000) return; usleep(1000); }
    held = log_begin();
    n = g_log.len; memcpy(wbuf, g_log.buf, n); g_log.len = 0; g_log.buf[0] = 0;
    if (held) log_end();
    if (n) log_append(wbuf, n);
    g_flush_us = now_us();
    __atomic_store_n(&g_flush_lock, 0, __ATOMIC_RELEASE);
}

/* ---------- settings ---------- */
#define CFG GAME_DIR "configs/net.helicover.brain.ini"
static int g_marks = 0;         /* debug markers: off unless the player turns them on */
static u32 g_last_crash;        /* 1.4.1: the brain's step when the last game crashed inside it (0 = none); 20 = a gunner's shot */
static int g_voice_off, g_water_off;   /* 0.8: the commander's voice (CPed::Say) / the water level call are off: the game crashed in them once */
static int g_mind_off, g_gun_off, g_rope_off;   /* 1.1: keeping the game AI off the guards / the mod's own gun task / holding the ropes are off (a crash there once, or the player's choice) */
static int g_body_off, g_map_off;      /* 1.0: the mod's own walking of the guards / its questions about the ground are off (the game crashed there once) */
static int g_fire_off;          /* 1.4.1: the game's own weapon fire for the gunners is off (it crashed once, or the words differ) */
static int key_at(const char *b, const char *key) { int i, k; for (i = 0; b[i]; i++) { if (i && b[i - 1] != '\n') continue; for (k = 0; key[k] && b[i + k] == key[k]; k++) {} if (!key[k] && (b[i + k] == ' ' || b[i + k] == '\t' || b[i + k] == '=')) { i += k; while (b[i] == ' ' || b[i] == '\t' || b[i] == '=') i++; return i; } } return -1; }
/* 1.1: the tactical numbers. Each one is a field of the core's hcb_cfg; the settings file may set any of them
   (configs/net.helicover.brain.ini, section [Tactics]). A value that is not a number or lies outside its limits is ignored -
   the built-in one stays - and the file is written back with what is in force, so it always shows every number there is. */
#define CFG_OFF(f) ((u32)__builtin_offsetof(hcb_cfg, f))
static const struct { const char *key; u32 off; float lo, hi; const char *what; } TUNE[] = {
    {"OuterPeaceM", CFG_OFF(outer_peace_m), 8, 30, "PROTECT: how far out the four outer men stand in peace, metres"},
    {"OuterFightM", CFG_OFF(outer_fight_m), 10, 40, "... and in a fight"},
    {"CjLowHealth", CFG_OFF(cj_low_hp), 0, 100, "CJ under this health: armed men near him are targets at once, the bodyguards come back"},
    {"GatherM", CFG_OFF(gather_m), 15, 60, "ASSAULT: the squad gathers this far short of the target, metres"},
    {"RushM", CFG_OFF(rush_m), 3, 15, "... the length of one rush of an assault pair"},
    {"AssaultNearM", CFG_OFF(assault_near_m), 4, 25, "... nobody goes nearer to the target than this"},
    {"FireFirstMs", CFG_OFF(fire_first_ms), 0, 10000, "... the fire team fires this long before a pair moves, ms"},
    {"SearchMs", CFG_OFF(search_ms), 1000, 30000, "... a target unseen this long is searched for"},
    {"TargetKeepMs", CFG_OFF(target_keep_ms), 3000, 120000, "... and dropped after this long"},
    {"ConsolidateMs", CFG_OFF(consolidate_ms), 0, 60000, "... all-round watch for this long after the target is down"},
    {"WithdrawDown", CFG_OFF(withdraw_down), 1, 8, "... this many of ours down since the task began: fall back"},
    {"RoofMinM", CFG_OFF(ow_min_h), 2, 20, "the marksman's roof: at least this high above CJ's feet"},
    {"RoofMaxM", CFG_OFF(ow_max_h), 5, 80, "... and at most this high"},
    {"RoofNearM", CFG_OFF(ow_min_d), 0, 40, "... at least this far from CJ"},
    {"RoofFarM", CFG_OFF(ow_max_d), 20, 150, "... and at most this far"},
    {"RoofTryMs", CFG_OFF(ow_try_ms), 5000, 120000, "... one try of this long for each commander"},
    {"PlaceFire", CFG_OFF(place_w_fire), 0, 2, "a firing place: worth of low cover with a line of fire on the main threat"},
    {"PlaceOpen", CFG_OFF(place_w_open), 0, 2, "... of a line of fire with no cover"},
    {"PlaceOthers", CFG_OFF(place_w_others), 0, 2, "... of being hidden from the other threats"},
    {"PlaceRange", CFG_OFF(place_w_dist), 0, 2, "... of a good range (15-35 m)"},
    {"PlaceNear", CFG_OFF(place_w_near), 0, 2, "... of being near the man"},
    {"PlaceCrowd", CFG_OFF(place_w_crowd), 0, 2, "... taken off when another of ours is within 3 m"},
    {"PlacePath", CFG_OFF(place_w_path), 0, 2, "... taken off when the way there lies open to the threat"},
    {"PlaceBetter", CFG_OFF(place_better), 1, 5, "a new place must be this many times better than the one he holds"},
    {"PlaceKeepMs", CFG_OFF(place_keep_ms), 0, 60000, "... and he keeps a place at least this long"},
    {"RiflesPerTarget", CFG_OFF(shooters_per_target), 1, 4, "tokens: how many of ours fire at one man at a time"},
    {"MoversMax", CFG_OFF(movers_max), 1, 8, "... how many of the outer men / the squad move at a time in a fight"},
    {"ReloadAtRounds", CFG_OFF(reload_clip), 0, 50, "... a man with this many rounds left changes his magazine (one man at a time)"},
    {"CornerMs", CFG_OFF(corner_ms), 0, 5000, "a man stops this long short of a blind corner and looks round it"},
    {"DoorMs", CFG_OFF(door_ms), 0, 5000, "nobody stands in a doorway longer than this"},
    {"NearM", CFG_OFF(near_m), 10, 100, "an armed hostile man inside this range and turned to CJ is a threat"},
    {"ReactMinMs", CFG_OFF(react_min_ms), 0, 2000, "how a human shoots: the reaction time, at least"},
    {"ReactMaxMs", CFG_OFF(react_max_ms), 0, 3000, "... and at most"},
};
#define N_TUNE (sizeof TUNE / sizeof TUNE[0])
static float g_tune[N_TUNE];            /* what the file asked for (NaN = nothing) */
static u32 g_tuned, g_tune_bad;
static int parse_f(const char *p, float *out) {
    float v, mant = 0, div = 1; int neg = 0, any = 0;            /* (digits / power of ten: "0.55" reads as exactly the 0.55 of the code) */
    if (*p == '-') { neg = 1; p++; }
    while (*p >= '0' && *p <= '9') { mant = mant * 10.0f + (float)(*p - '0'); p++; any = 1; }
    if (*p == '.') { p++; while (*p >= '0' && *p <= '9') { if (div < 100000.0f) { mant = mant * 10.0f + (float)(*p - '0'); div *= 10.0f; } p++; any = 1; } }
    v = mant / div;
    if (!any || !(*p == '\n' || *p == '\r' || *p == 0 || *p == ' ' || *p == '\t' || *p == ';' || *p == '#')) return 0;
    *out = neg ? -v : v;
    return 1;
}
static char g_cfg_text[8192];
static void load_config(void) {
    char *b = g_cfg_text; long n; int fd = open(CFG, O_RDONLY), i; u32 k;
    for (k = 0; k < N_TUNE; k++) g_tune[k] = -1e30f;
    if (fd < 0) return;
    n = read(fd, b, sizeof(g_cfg_text) - 1); close(fd);
    if (n <= 0) return;
    b[n] = 0;
    if ((i = key_at(b, "Markers")) >= 0 && (b[i] == '0' || b[i] == '1')) g_marks = b[i] == '1';
    if ((i = key_at(b, "FireOff")) >= 0 && b[i] == '1') g_fire_off = 1;
    if ((i = key_at(b, "VoiceOff")) >= 0 && b[i] == '1') g_voice_off = 1;
    if ((i = key_at(b, "WaterOff")) >= 0 && b[i] == '1') g_water_off = 1;
    if ((i = key_at(b, "BodyOff")) >= 0 && b[i] == '1') g_body_off = 1;
    if ((i = key_at(b, "MapOff")) >= 0 && b[i] == '1') g_map_off = 1;
    if ((i = key_at(b, "MindOff")) >= 0 && b[i] == '1') g_mind_off = 1;
    if ((i = key_at(b, "GunOff")) >= 0 && b[i] == '1') g_gun_off = 1;
    if ((i = key_at(b, "RopeOff")) >= 0 && b[i] == '1') g_rope_off = 1;
    if ((i = key_at(b, "LastCrash")) >= 0) for (g_last_crash = 0; b[i] >= '0' && b[i] <= '9'; i++) g_last_crash = g_last_crash * 10 + (u32)(b[i] - '0');
    for (k = 0; k < N_TUNE; k++) if ((i = key_at(b, TUNE[k].key)) >= 0) {
        float v;
        if (parse_f(b + i, &v) && v >= TUNE[k].lo && v <= TUNE[k].hi) g_tune[k] = v; else g_tune_bad++;
    }
}
/* the numbers of the file go into the brain (after hcb_init has set the built-in ones) */
static void tune_apply(hcb_cfg *c) {
    u32 k;
    g_tuned = 0;
    for (k = 0; k < N_TUNE; k++) if (g_tune[k] > -1e29f) { float *f = (float *)((u8 *)c + TUNE[k].off); if (*f != g_tune[k]) { *f = g_tune[k]; g_tuned++; } }
}
static const hcb_cfg *g_cfg_now;
static void save_config_with(u32 crash) {
    static char b[8192]; struct text t = {b, sizeof b, 0};
    int fd = open(CFG, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    u32 k;
    if (fd < 0) return;
    ts(&t, g_marks ? "[Preferences]\nMarkers = 1\n" : "[Preferences]\nMarkers = 0\n");
    if (crash) { ts(&t, "LastCrash = "); tu(&t, crash); ts(&t, "\n"); }
    if (g_fire_off || crash == 20) ts(&t, "FireOff = 1\n");
    if (g_voice_off || crash == 21) ts(&t, "VoiceOff = 1\n");
    if (g_water_off || crash == 22) ts(&t, "WaterOff = 1\n");
    if (g_body_off || crash == 23) ts(&t, "BodyOff = 1\n");
    if (g_map_off || crash == 24) ts(&t, "MapOff = 1\n");
    if (g_mind_off || crash == 25) ts(&t, "MindOff = 1\n");
    if (g_gun_off || crash == 26) ts(&t, "GunOff = 1\n");
    if (g_rope_off || crash == 27) ts(&t, "RopeOff = 1\n");
    if (g_cfg_now) {
        ts(&t, "\n[Tactics]\n; every number of the detail and the squad; change a value and start the game again. A value outside its limits is ignored.\n");
        for (k = 0; k < N_TUNE; k++) {
            float v = *(const float *)((const u8 *)g_cfg_now + TUNE[k].off);
            long whole = (long)v; long frac = (long)((v - (float)whole) * 100.0f + 0.5f);
            if (frac >= 100) { whole++; frac -= 100; }
            ts(&t, TUNE[k].key); ts(&t, " = "); ti(&t, whole);
            if (frac) { ts(&t, "."); if (frac < 10) ts(&t, "0"); tu(&t, (u64)frac); }
            ts(&t, "    ; "); ts(&t, TUNE[k].what); ts(&t, " ("); ti(&t, (long)TUNE[k].lo); ts(&t, " - "); ti(&t, (long)TUNE[k].hi); ts(&t, ")\n");
        }
    }
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
/* 0.4.1: for the session log (the counters are per second) */
static hcb_pilot_out g_pilot_out;
static u32 g_pilot_at, g_pilot_flags, s_calls[8], s_calls_early, s_frames;
static float g_pilot_to[3];
static u64 s_gap_max, g_start_us;
static void session_look(u32 now, u64 cost);
static int safe_read(void *dst, u64 src, u64 n);
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
static int g_ray_cars = 1;          /* 1.1: 0 for the map's rays (what stands between two cells for good: buildings and objects, not a parked car) */
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
    r = ((los_fn)(G + G_LOS_CLEAR))(p, q, 1, g_ray_cars, 0, 1, 0, 0, 0) != 0;
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

/* ---------- 0.8: more of what the game itself knows (found in the player's libGTASA.so; the words below are checked at
   the start and each part is left out when they differ) ----------
   - explosions: CExplosion's table, 16 x 0x88 (+0 type, +4 position, +0x10 radius, +0x30 active)
   - thrown and launched things: gaProjectileInfo, 32 x 0x38 (+0 weapon, +0x1c active, +0x20 position)
   - the game's own cover points: CCover::m_aPoints, 100 x 0x28 (+0 type, 0 = none; +4 position; +0x10 the thing it is on)
   - CWaterLevel::GetWaterLevel(x, y, z, float *level, bool, CVector *): is there water here and how high
   - CPed::Say(context, delay, probability, ...): the game's own voice lines (the commander speaks) */
#define EXPLOSIONS 0xd28c78UL
#define PROJ_INFO 0xd29508UL
#define GOT_PROJ_INFO 0x84e270UL
#define COVER_POINTS 0xc9b390UL
#define WATER_LEVEL 0x6ba834UL
#define PED_SAY 0x5a57c4UL
static const struct { u32 at, word; } TABLE_WORDS[] = {{0x6fcf80, 0x90003169U}, {0x6fcf84, 0x9131e129U}, {0x6fcec0, 0x3900c19fU}, {0x6fe510, 0x321d0be9U}, {0x5d676c, 0x39c00008U}, {0x5d6770, 0x34000128U}};
static const struct { u32 at, word; } WATER_WORDS[] = {{0x6ba834, 0xd10143ffU}, {0x6ba838, 0xfd000beaU}};
static const struct { u32 at, word; } SAY_WORDS[] = {{0x5a57c4, 0x2a0103ecU}, {0x5a57c8, 0x2a0503e8U}};
typedef int (*water_fn)(float x, float y, float z, float *level, int touching, void *normal);
typedef void (*say_fn)(void *ped, u32 context, u32 delay, float probability, u32 a, u32 b, u32 c);
static int g_tables_ok, g_water_ok, g_say_ok;
static hcb_vec g_hints[HCB_MAX_HINTS];
static u32 g_n_hints, g_hints_at, g_said_voice;
static u32 g_water_calls, g_water_yes, g_cover_live, g_cover_ok;   /* 0.9: counters for the log: the water question asked / answered "in water"; cover points in the game's table / of them read */
static void more_setup(void) {
    u32 i;
    g_tables_ok = RD(u64, G + GOT_PROJ_INFO) == G + PROJ_INFO;
    for (i = 0; i < sizeof TABLE_WORDS / sizeof TABLE_WORDS[0]; i++) if (RD(u32, G + TABLE_WORDS[i].at) != TABLE_WORDS[i].word) g_tables_ok = 0;
    g_water_ok = !g_water_off;
    for (i = 0; i < sizeof WATER_WORDS / sizeof WATER_WORDS[0]; i++) if (RD(u32, G + WATER_WORDS[i].at) != WATER_WORDS[i].word) g_water_ok = 0;
    g_say_ok = !g_voice_off;
    for (i = 0; i < sizeof SAY_WORDS / sizeof SAY_WORDS[0]; i++) if (RD(u32, G + SAY_WORDS[i].at) != SAY_WORDS[i].word) g_say_ok = 0;
    lg("the game's own knowledge: grenades, explosions and cover points "); lg(g_tables_ok ? "read" : "NOT read (the tables are not where expected)");
    lg("; water level "); lg(g_water_ok ? "asked" : g_water_off ? "off (the game crashed in it once)" : "NOT asked (the code differs)");
    lg("; the commander's voice "); lg(g_say_ok ? "on" : g_voice_off ? "off (the game crashed in it once)" : "off (the code differs)"); lg("\n");
}
/* ---------- 1.0: the body and the map ----------
   Until 0.9 the scripts were the whole body: they gave a guard a new "go there" ten times a second, and the game began the walk
   anew each time - the men were late everywhere (the sixth log: farther than 8 m from the post 65 % of the time). Now the mod
   gives a guard the game's own task ONCE (CTaskComplexGoToPointAndStandStill, made with the game's CTask::operator new and put
   in his main slot with CTaskManager::SetTask - what the script command does in the end) and afterwards only moves its target
   (the task's own "new target" flag, read by its ControlSubTask). The scripts still seat him in cars, crouch him and fire from
   his post; while the mod walks him they leave his legs alone (the post command answers 5).
   The map: the core asks for the height of the ground cell by cell (CWorld::FindGroundZFor3DCoord) with what stands between a
   cell and the next (a level ray), and whether a man can walk straight from a to b (two rays). All of it has a time budget of
   its own. brain/research/game_facts.md has the proofs; every function is checked by its first words before it is ever called. */
#define TASK_NEW 0x5d7414UL                 /* CTask::operator new(unsigned long) */
#define GOTO_CTOR 0x632400UL                /* CTaskComplexGoToPointAndStandStill(int moveState, const CVector&, float radius, float slowDown, bool, bool); 0x38 bytes */
#define SHOOT_CTOR 0x633510UL               /* CTaskComplexGoToPointShooting(int moveState, const CVector&, CEntity *aim, CVector aimPos, float radius, float slowDown); 0x50 bytes */
#define SET_TASK 0x64e084UL                 /* CTaskManager::SetTask(CTask *, int slot, bool) */
#define FIND_GROUND 0x50f408UL              /* CWorld::FindGroundZFor3DCoord(float, float, float, bool *, CEntity **) */
#define VT_GOTO (0x839040UL + 0x10)
#define VT_GOTO_SHOOT (0x839b98UL + 0x10)
#define VT_ROPE (0x8381f8UL + 0x10)         /* CTaskComplexUseSwatRope: a man coming down the rope */
#define MAP_LOOK_US 1200U                   /* the map's questions per look */
static const struct { u32 at, word; } BODY_WORDS[] = {{0x5d7414, 0xf0001388U}, {0x5d7418, 0xf9419908U}, {0x632400, 0x6dbb23e9U}, {0x632404, 0xf9000bf7U},
    {0x64e084, 0xa9bd57f6U}, {0x64e088, 0xa9014ff4U}, {0x633510, 0xfc1a0fecU}, {0x633514, 0x6d012bebU}, {0x632938, 0x3940c009U}, {0x63293c, 0x52801f6aU},
    {0x632988, 0x37100388U} /* ControlSubTask: "tbnz w8, #2": bit 2 of +0x30 is the new-target flag */};
static const struct { u32 at, word; } GROUND_WORDS[] = {{0x50f408, 0xd10203ffU}, {0x50f40c, 0xa9064ff4U}};
typedef void *(*task_new_fn)(u64 size);
typedef void (*goto_ctor_fn)(void *task, int move_state, const float *target, float radius, float slow_down, int overshoot, int stop_exactly);
typedef void (*shoot_ctor_fn)(void *task, int move_state, const float *target, const void *aim, float ax, float ay, float az, float radius, float slow_down);
typedef void (*set_task_fn)(void *mgr, void *task, int slot, int unused);
typedef float (*ground_fn)(float x, float y, float z, u8 *found, void **ent);
typedef int (*abort_fn)(void *task, void *ped, int priority, const void *event);
typedef int (*type_fn)(const void *task);
struct bod { u32 who, at, target; const u8 *task; float via[3]; u8 kind, ms; };
static struct bod g_bod[16];
static struct { u32 who, target, at; u8 state; } g_sq[16];             /* each guard's last fire order as the script was told it */
static int g_body_ok, g_map_ok, g_gun_ok;
static u32 g_soft_falls, g_body_new, g_body_turn, g_body_refused, g_body_nomem, g_body_kept, g_recall_until;
static u32 g_map_ground, g_map_ground_ok, g_map_segs, g_map_left, g_map_us_max, g_high_i;
static u64 g_map_us;
static struct { hcb_vec at; float height; u32 time; u8 sees, ok; } g_high[32];
static void body_setup(void) {
    u32 i;
    g_body_ok = !g_body_off; g_map_ok = !g_map_off;
    for (i = 0; i < sizeof BODY_WORDS / sizeof BODY_WORDS[0]; i++) if (RD(u32, G + BODY_WORDS[i].at) != BODY_WORDS[i].word) g_body_ok = 0;
    for (i = 0; i < sizeof GROUND_WORDS / sizeof GROUND_WORDS[0]; i++) if (RD(u32, G + GROUND_WORDS[i].at) != GROUND_WORDS[i].word) g_map_ok = 0;
    if (!g_map_ok) g_body_ok = 0;                                       /* no map, no way-finding: the scripts walk them as before */
    lg("the body: "); lg(g_body_ok ? "the mod walks the guards itself (the game's go-to task, given once)" : g_body_off ? "off (the game crashed in it once): the scripts walk the guards" :
        g_map_off ? "off with the map (the game crashed in a ground question once): the scripts walk the guards" : "off (the code differs): the scripts walk the guards");
    lg("; the map: "); lg(g_map_ok ? "on" : "off"); lg("\n");
}
static struct bod *bod_of(u32 who) {
    u32 i, old = 0;
    for (i = 0; i < 16; i++) if (g_bod[i].who == who) return &g_bod[i];
    for (i = 1; i < 16; i++) if (g_bod[i].at < g_bod[old].at) old = i;
    memset(&g_bod[old], 0, sizeof g_bod[old]); g_bod[old].who = who;
    return &g_bod[old];
}
static void sq_note(u32 who, int state, u32 target) {
    u32 i, old = 0, now = RD(u32, G + TIME_MS);
    for (i = 0; i < 16; i++) { if (g_sq[i].who == who) { old = i; break; } if (g_sq[i].at < g_sq[old].at) old = i; }
    g_sq[old].who = who; g_sq[old].state = (u8)state; g_sq[old].target = target; g_sq[old].at = now;
}
static u8 *task_slot(const u8 *ped, u32 slot) {                         /* 0-4 the main tasks, 5-10 the secondary ones (5 attack, 6 duck) */
    const u8 *intel = RD(const u8 *, ped + 0x538);
    u8 *t = intel ? RD(u8 *, intel + 8 + (u64)slot * 8) : 0;
    u64 vt = t ? RD(u64, t) : 0;
    return vt >= G + 0x800000UL && vt < G + 0x880000UL ? t : 0;         /* (a task whose table is not in the game's data is not looked into) */
}
static int task_type(const u8 *t) { return t ? ((type_fn)RD(u64, RD(u64, t) + 0x28))(t) : -1; }
static int on_rope(const u8 *ped) {                                     /* coming down the rope, or in the air */
    const u8 *t = task_slot(ped, 3);
    return (t && RD(u64, t) == G + VT_ROPE) || (RD(u8, ped + 0x585) & 2);
}
/* Walk this guard to the next point of his way. 1 = the mod has his legs (the script leaves them alone), 0 = it has not
   (the script walks him as before 1.0). Called from the script's own question about his post, in the script's turn - where
   the game's own task commands run. */
static int body_walk(u32 who, const hcb_post *p) {
    struct pool pp;
    u8 *me, *intel, *mgr, *t3, *task;
    const u8 *him = 0;
    struct bod *b;
    u32 now = RD(u32, G + TIME_MS), k, tgt = 0, was = g_where;
    int ms, kind = 1, final;
    float via[3], dx, dy, d;
    if (!g_body_ok || !g_snap.body || p->phase > HCB_PH_MOVING) return 0;
    if (!(p->act >= HCB_ACT_WALK && p->act <= HCB_ACT_SPRINT) && p->act != HCB_ACT_SIDESTEP) return 0;
    if (!get_pool(PED_POOL, &pp) || !(me = obj_of(&pp, who, PED_STRIDE)) || is_dead(me) || vehicle_of(me)) return 0;
    intel = RD(u8 *, me + 0x538);
    via[0] = p->via.x; via[1] = p->via.y; via[2] = p->via.z;
    if (!intel || !sane(via) || !sane(pos_of(me))) return 0;
    if (on_rope(me)) return 1;                                          /* the game has him: wait */
    mgr = intel + 8;
    dx = via[0] - pos_of(me)[0]; dy = via[1] - pos_of(me)[1]; d = f_sqrt(dx * dx + dy * dy);
    dx = p->via.x - p->at.x; dy = p->via.y - p->at.y;
    final = dx * dx + dy * dy < 0.01f;
    ms = p->act == HCB_ACT_SPRINT ? 7 : p->act == HCB_ACT_RUN || (p->act == HCB_ACT_FASTWALK && d > 4.0f) ? 6 : 4;
    /* (1.0: fire on the move by the game's go-and-shoot task; 1.1: the mod's own gun task fires while he walks - a plain walk is enough) */
    for (k = 0; k < 16 && !g_gun_ok; k++) if (g_sq[k].who == who && g_sq[k].state == 2 && now >= g_sq[k].at && now - g_sq[k].at < 400 && g_sq[k].target) {
        him = obj_of(&pp, g_sq[k].target, PED_STRIDE);
        if (him && !is_dead(him)) { kind = 2; tgt = g_sq[k].target; } else him = 0;
    }
    b = bod_of(who);
    t3 = RD(u8 *, mgr + 24);
    if (t3 && t3 == b->task && b->kind == kind && RD(u64, t3) == G + (kind == 1 ? VT_GOTO : VT_GOTO_SHOOT)) {
        if (kind == 1) {                                                /* still on his way: only the target moves */
            int ch = 0;
            if (dist2((const float *)(t3 + 0x1c), via) > 0.09f) { memcpy(t3 + 0x1c, via, 12); ch = 1; }
            if (RD(int, t3 + 0x18) != ms) { RD(int, t3 + 0x18) = ms; ch = 1; }
            RD(float, t3 + 0x2c) = final ? 2.0f : 0.2f;
            if (ch) { RD(u8, t3 + 0x30) |= 4; g_body_turn++; memcpy(b->via, via, 12); b->ms = (u8)ms; } else g_body_kept++;
            return 1;
        }
        if (tgt == b->target && ms == b->ms && dist2(via, b->via) < 2.25f) { g_body_kept++; return 1; }
    }
    if (b->at && now >= b->at && now - b->at < 300) return 1;           /* never more than three new tasks a second for one man */
    g_where = 23;
    if (t3) {                                                           /* what he is doing now is asked to stop, as the game does it */
        u64 vt = RD(u64, t3);
        if (vt < G + 0x800000UL || vt >= G + 0x880000UL) { g_where = was; return 0; }
        if (!((abort_fn)RD(u64, vt + 0x38))(t3, me, 1, 0)) { g_body_refused++; g_where = was; return 1; }
    }
    task = ((task_new_fn)(G + TASK_NEW))(kind == 1 ? 0x38 : 0x50);
    if (!task) { g_body_nomem++; g_where = was; return 0; }
    if (kind == 1) ((goto_ctor_fn)(G + GOTO_CTOR))(task, ms, via, 0.5f, final ? 2.0f : 0.2f, 0, 0);
    else ((shoot_ctor_fn)(G + SHOOT_CTOR))(task, ms, via, him, 0.0f, 0.0f, 0.0f, 0.5f, 1.0f);
    if (RD(u64, task) != G + (kind == 1 ? VT_GOTO : VT_GOTO_SHOOT)) {   /* not the task this was made for: never again */
        g_body_ok = 0; g_where = was;
        log_begin(); lg("the body: the game made another task than expected - the mod stops walking the guards (the scripts do it)\n"); log_end();
        return 0;
    }
    ((set_task_fn)(G + SET_TASK))(mgr, task, 3, 0);
    b->task = task; b->kind = (u8)kind; b->ms = (u8)ms; b->target = tgt; b->at = now ? now : 1; memcpy(b->via, via, 12);
    g_body_new++;
    g_where = was;
    return 1;
}
/* ---------- 1.1: the game's own AI is kept off the guards; their weapons; their ropes ----------
   - The decision maker: Helicover's scripts give every guard an empty one when they make him (so that he does not run from
     fire or after an attacker by himself). The mod remembers which one that is and puts it back whenever the game or
     another script has changed it (CPedIntelligence::SetPedDecisionMakerType: plain field logic, read from the code).
   - A reaction of the game's AI that has got into a guard's event slot all the same (flight, a chase, an investigation,
     cowering - the list is by task type, from the game's debug info) is asked to stop (MakeAbortable, urgent) and removed
     (CTaskManager::ClearTaskEventResponse). Falling, getting up, burning, a hit, a dodge, death, water, cars are left alone.
   - The weapon: with the brain's leave to fire, the guard gets the game's own gun task ONCE in his attack slot
     (CTaskSimpleUseGun through CTaskManager::SetTaskSecondary) and after that only its command is set every look
     (ControlGun: aim / fire a burst / stop) - the main slot is not touched, so he can walk and fire, and nothing restarts.
     The script is told 6 = "his weapon is the mod's". Self-check: if in 3 s of fire orders no round has left any guard's
     weapon, the game does not fire for this task here - the mod says so in the log and the scripts fire as before.
   - Magazines: the man whose turn it is (the core's token) gets CWeapon::Reload.
   - Ropes: a rope made by the script command lives 4 s and hangs where it was made. While one of ours is on it the mod
     keeps it alive (CRope::TimeToBeKeptAliveTill) and moves its top with the helicopter (the first node, as the game's own
     helicopter code does every frame). Plain memory of the game's rope table - no call. */
#define DM_SET 0x5ba338UL                   /* CPedIntelligence::SetPedDecisionMakerType(int) */
#define EV_CLEAR 0x64e734UL                 /* CTaskManager::ClearTaskEventResponse() */
#define SET_SECONDARY 0x64e5c8UL            /* CTaskManager::SetTaskSecondary(CTask *, int slot) */
#define GUN_CTOR 0x5dd83cUL                 /* CTaskSimpleUseGun(CEntity *target, CVector pos, signed char command, short burst, bool aimNow); 0x58 bytes */
#define GUN_CONTROL 0x5dfb64UL              /* CTaskSimpleUseGun::ControlGun(CPed *, CEntity *target, signed char command) */
#define WEAPON_RELOAD 0x700a2cUL            /* CWeapon::Reload(CPed *) */
#define ROPES 0xbd3e50UL                    /* CRopes::aRopes: 8 x 0x340 (+0 node positions, +0x180 node speeds, +0x300 id, +0x334 alive till, +0x339 type) */
static const struct { u32 at, word; } MIND_WORDS[] = {{0x5ba338, 0xb9416008U}, {0x5ba33c, 0x34000128U}, {0x64e734, 0xa9be4ff4U}, {0x64e738, 0xa9017bfdU}};
static const struct { u32 at, word; } GUN_WORDS[] = {{0x64e5c8, 0xa9bd57f6U}, {0x64e5cc, 0xa9014ff4U}, {0x5dd83c, 0xfc1b0feaU}, {0x5dd840, 0x6d00a3e9U},
    {0x5dfb64, 0xf81c0ff7U}, {0x5dfb68, 0xa90157f6U}};
static const struct { u32 at, word; } RELOAD_WORDS[] = {{0x700a2c, 0xa9be4ff4U}, {0x700a30, 0xa9017bfdU}};
static int g_reload_ok;
static struct { u32 who, at; } g_reloaded[16];
static const struct { u32 at, word; } ROPE_WORDS[] = {{0x4fa678, 0xa9be4ff4U}, {0x4fa67c, 0xa9017bfdU}, {0x4f7d1c, 0xd10603ffU}, {0x4f7d20, 0x6d0e3befU}};
typedef void (*dm_fn)(void *intel, int type);
typedef void (*mgr_fn)(void *mgr);
typedef void (*sec_fn)(void *mgr, void *task, int slot);
typedef void (*gun_ctor_fn)(void *task, const void *target, float x, float y, float z, int command, int burst, int aim_now);
typedef int (*gun_ctl_fn)(void *task, void *ped, const void *target, int command);
typedef void (*reload_fn)(void *weapon, void *ped);
static int g_mind_ok, g_rope_ok, g_dm = -1, g_gun_proved;
static u32 g_dm_fixed, g_ev_cleared, g_ev_refused, g_ev_last, g_gun_new, g_gun_cmd, g_reloads, g_ropes_kept;
static struct { u32 who, target, ammo, fire_ms, at, reload_at; const u8 *task; u8 cmd; } g_gun[16];
static struct { u64 id; float off[3]; u8 follow; } g_rope[8];
static void mind_setup(void) {
    u32 i;
    g_mind_ok = !g_mind_off; g_gun_ok = !g_gun_off; g_rope_ok = !g_rope_off;
    for (i = 0; i < sizeof MIND_WORDS / sizeof MIND_WORDS[0]; i++) if (RD(u32, G + MIND_WORDS[i].at) != MIND_WORDS[i].word) g_mind_ok = 0;
    for (i = 0; i < sizeof GUN_WORDS / sizeof GUN_WORDS[0]; i++) if (RD(u32, G + GUN_WORDS[i].at) != GUN_WORDS[i].word) g_gun_ok = 0;
    for (i = 0; i < sizeof ROPE_WORDS / sizeof ROPE_WORDS[0]; i++) if (RD(u32, G + ROPE_WORDS[i].at) != ROPE_WORDS[i].word) g_rope_ok = 0;
    g_reload_ok = !g_gun_off;
    for (i = 0; i < sizeof RELOAD_WORDS / sizeof RELOAD_WORDS[0]; i++) if (RD(u32, G + RELOAD_WORDS[i].at) != RELOAD_WORDS[i].word) g_reload_ok = 0;
    if (!g_body_ok) g_gun_ok = 0;                                        /* (the scripts walk them: the scripts fire too) */
    lg("the game AI kept off the guards: "); lg(g_mind_ok ? "yes" : g_mind_off ? "off in the settings" : "no (the code differs)");
    lg("; their weapons: "); lg(g_gun_ok ? "the mod's own gun task" : g_gun_off ? "the scripts (off in the settings)" : "the scripts");
    lg("; their ropes: "); lg(g_rope_ok ? "held by the mod" : g_rope_off ? "the game's (off in the settings)" : "the game's (the code differs)"); lg("\n");
}
/* a reaction of the game AI that takes a guard away from his orders (by task type; the numbers are eTaskType of this build) */
static int wanders(int t) { return t == 412 || t == 413 || (t >= 600 && t < 700) || (t >= 905 && t <= 940) || (t >= 1000 && t < 1300) || (t >= 1500 && t < 1600); }
static void mind_keep(u8 *ped) {
    u8 *intel = RD(u8 *, ped + 0x538), *t1, *t2;
    u32 was = g_where;
    int dm;
    if (!g_mind_ok || !intel) return;
    g_where = 25;
    dm = RD(int, intel + 0x160);
    if (g_dm == -1) { g_dm = dm; log_begin(); lg("the guards' decision maker (the scripts' empty one): "); ti(&g_log, dm); lg("\n"); log_end(); }
    else if (dm != g_dm) { ((dm_fn)(G + DM_SET))(intel, g_dm); g_dm_fixed++; }
    t1 = task_slot(ped, 1); t2 = task_slot(ped, 2);
    if (!RD(u8 *, intel + 8 + 8) && t2 && wanders(task_type(t2))) {
        g_ev_last = (u32)task_type(t2);
        if (((abort_fn)RD(u64, RD(u64, t2) + 0x38))(t2, ped, 1, 0)) { ((mgr_fn)(G + EV_CLEAR))(intel + 8); g_ev_cleared++; } else g_ev_refused++;
    }
    (void)t1;
    g_where = was;
}
static u8 *weapon_of(const u8 *ped) { int slot = (signed char)RD(u8, ped + 0x8dc); return slot >= 0 && slot < 13 ? (u8 *)ped + 0x730 + (u64)slot * 0x20 : 0; }
static u8 clip_of(const u8 *ped) {
    const u8 *w = weapon_of(ped);
    u32 type, clip;
    if (!w) return 255;
    type = RD(u32, w); clip = RD(u32, w + 8);
    return type >= 22 && type <= 38 ? (u8)(clip > 254 ? 254 : clip) : 255;       /* (pistols to the minigun: weapons with a magazine) */
}
/* the core's token says it is this man's turn to change his magazine: once a turn (whoever fires his weapon, the mod or the script) */
static void reload_now(u32 who) {
    struct pool pp;
    u8 *me, *w;
    u32 now = RD(u32, G + TIME_MS), i, old = 0, was = g_where;
    if (!g_reload_ok || !get_pool(PED_POOL, &pp) || !(me = obj_of(&pp, who, PED_STRIDE)) || is_dead(me) || !(w = weapon_of(me))) return;
    for (i = 0; i < 16; i++) { if (g_reloaded[i].who == who) { old = i; break; } if (g_reloaded[i].at < g_reloaded[old].at) old = i; }
    if (g_reloaded[old].who == who && now >= g_reloaded[old].at && now - g_reloaded[old].at < 1500) return;
    g_reloaded[old].who = who; g_reloaded[old].at = now ? now : 1;
    g_where = 26;
    ((reload_fn)(G + WEAPON_RELOAD))(w, me);
    g_reloads++;
    g_where = was;
}
/* The guard's weapon for this look. state: what the core said (0 nothing, 1 cover, 2 fire, 3 his man - no fire, 5 by hand).
   Returns 1 when the mod has his weapon (the script is told 6), 0 when the script is to do it as before. */
static int body_gun(u32 who, int state, u32 target, int reload) {
    struct pool pp;
    u8 *me, *intel, *mgr, *t, *w;
    const u8 *him;
    u32 now = RD(u32, G + TIME_MS), i, old = 0, was = g_where, ammo;
    int cmd;
    if (!g_gun_ok || !g_snap.body || state == 5 || state == 4) return 0;
    for (i = 0; i < g_snap.n_ours && g_snap.ours[i] != who; i++) {}
    if (i == g_snap.n_ours || g_snap.our_role[i] < HCB_ROLE_SQUAD) return 0;
    if (!get_pool(PED_POOL, &pp) || !(me = obj_of(&pp, who, PED_STRIDE)) || is_dead(me) || vehicle_of(me) || on_rope(me)) return 0;
    intel = RD(u8 *, me + 0x538); w = weapon_of(me);
    if (!intel || !w || RD(u32, w) < 22 || RD(u32, w) > 38) return 0;    /* (no firearm in his hands: nothing for the gun task) */
    him = target ? obj_of(&pp, target, PED_STRIDE) : 0;
    if (him && is_dead(him)) him = 0;
    for (i = 0; i < 16; i++) { if (g_gun[i].who == who) { old = i; break; } if (g_gun[i].at < g_gun[old].at) old = i; }
    if (g_gun[old].who != who) { memset(&g_gun[old], 0, sizeof g_gun[old]); g_gun[old].who = who; g_gun[old].ammo = RD(u32, w + 0xc) + RD(u32, w + 8); }
    mgr = intel + 8;
    t = RD(u8 *, mgr + 0x28);
    cmd = !him || state == 0 ? 6 /* END_LEISURE */ : state == 2 && !reload ? 3 /* FIREBURST */ : 1 /* AIM */;
    g_where = 26;
    /* the self-check: fire ordered, and rounds leaving the weapon? */
    ammo = RD(u32, w + 0xc) + RD(u32, w + 8);
    if (ammo != g_gun[old].ammo) { if (g_gun[old].cmd == 3) g_gun_proved = 1; g_gun[old].ammo = ammo; g_gun[old].fire_ms = 0; }
    else if (g_gun[old].cmd == 3 && cmd == 3 && g_gun[old].at && now > g_gun[old].at && now - g_gun[old].at < 500) g_gun[old].fire_ms += now - g_gun[old].at;
    if (!g_gun_proved && g_gun[old].fire_ms > 3000) {
        g_gun_ok = 0; g_where = was;
        log_begin(); lg("the guards' weapons: 3 s of fire orders and no round has left the weapon - the game does not fire for the mod's gun task here; the scripts fire from now on\n"); log_end();
        if (t && t == g_gun[old].task && RD(u64, t) == G + VT_USE_GUN) ((gun_ctl_fn)(G + GUN_CONTROL))(t, me, 0, 7);
        return 0;
    }
    if (t && RD(u64, t) == G + VT_USE_GUN) {                             /* a gun task is there: only its command */
        if (cmd != 6 || t == g_gun[old].task) { ((gun_ctl_fn)(G + GUN_CONTROL))(t, me, cmd == 6 ? 0 : him, cmd); g_gun_cmd++; }
    } else if (cmd != 6 && !t) {
        u8 *task = ((task_new_fn)(G + TASK_NEW))(0x58);
        if (!task) { g_body_nomem++; g_where = was; return 0; }
        ((gun_ctor_fn)(G + GUN_CTOR))(task, him, 0.0f, 0.0f, 0.0f, cmd, 6, 0);
        if (RD(u64, task) != G + VT_USE_GUN) { g_gun_ok = 0; g_where = was; log_begin(); lg("the guards' weapons: the game made another task than expected - the scripts fire from now on\n"); log_end(); return 0; }
        ((sec_fn)(G + SET_SECONDARY))(mgr, task, 0);
        g_gun[old].task = task; g_gun_new++;
    } else if (t) { g_where = was; g_gun[old].at = now ? now : 1; g_gun[old].cmd = (u8)cmd; return 0; }   /* another secondary task of the game's: the script's turn */
    g_gun[old].cmd = (u8)cmd; g_gun[old].target = target; g_gun[old].at = now ? now : 1;
    g_where = was;
    return 1;
}
/* every frame, after the scripts: the ropes our men are on */
static void ropes_keep(void) {
    u32 k, r, now = RD(u32, G + TIME_MS);
    const u8 *heli = g_our_ent[1];
    if (!g_rope_ok) return;
    g_where = 27;
    for (k = 0; k < HCB_MAX_OURS; k++) {
        const u8 *e = g_our_ent[2 + k], *t;
        u64 id;
        if (!e || is_dead(e) || !(t = task_slot(e, 3)) || RD(u64, t) != G + VT_ROPE) continue;
        id = (u64)(long)RD(int, t + 0x18);
        for (r = 0; r < 8; r++) {
            u8 *rope = (u8 *)(G + ROPES + (u64)r * 0x340);
            float *top = (float *)rope;
            if (!RD(u8, rope + 0x339) || RD(u64, rope + 0x300) != id) continue;
            if (RD(u32, rope + 0x334) < now + 3000) g_ropes_kept++;
            RD(u32, rope + 0x334) = now + 4000;
            if (heli && sane(pos_of(heli)) && sane(top)) {
                const float *h = pos_of(heli);
                if (g_rope[r].id != id) {
                    g_rope[r].id = id; g_rope[r].off[0] = top[0] - h[0]; g_rope[r].off[1] = top[1] - h[1]; g_rope[r].off[2] = top[2] - h[2];
                    g_rope[r].follow = (u8)(g_rope[r].off[0] * g_rope[r].off[0] + g_rope[r].off[1] * g_rope[r].off[1] < 64.0f && g_rope[r].off[2] < 3.0f && g_rope[r].off[2] > -8.0f);
                }
                if (g_rope[r].follow) { top[0] = h[0] + g_rope[r].off[0]; top[1] = h[1] + g_rope[r].off[1]; top[2] = h[2] + g_rope[r].off[2]; memset(rope + 0x180, 0, 12); }
            }
            break;
        }
    }
    g_where = 4;
}
/* ---------- 1.1: the map kept between games, and the ways found by a thread of the mod's own ----------
   The map's answers (height of the ground in a cell, what stands between it and the next one) are kept in a table - 16384
   cells, the last ones asked - and in a file (configs/net.helicover.brain.map). A cell that is in the table is answered
   from it without a single ray of the game's, so a place CJ has been to is known at once, in this game and the next.
   (That is why the map's rays do not count cars: a wall is still there tomorrow, a parked car is not. A car in the way is
   seen by the "straight leg" rays when a man walks.) The file is written by the thread, never by the game's thread.
   The ways: the core asks (hcb_out.path_q), the game's thread copies the brain's map (38 KB) and the questions, the thread
   runs the search and the answers go into the next look as inputs (hcb_snapshot.paths) - so they are in the black box and
   a report replays exactly, whatever the thread's timing was. No thread (it could not be started): the search is done
   at once, in the look, as in 1.0. */
#define MAP_FILE GAME_DIR "configs/net.helicover.brain.map"
#define MAP_MAGIC 0x504d4348U           /* "HCMP" */
#define MCACHE 16384U
struct mcell { short x, y; float z; u8 wall, used, pad[2]; };
static struct mcell g_mc[MCACHE], g_mc_copy[MCACHE];
static u32 g_mc_n, g_mc_dirty, g_mc_hits, g_mc_loaded, g_mc_saved, g_mc_save_at;
static volatile int g_map_save, g_path_job;                              /* job: 0 none, 1 for the thread, 2 answers ready */
static u8 g_nav_copy[48 * 1024] __attribute__((aligned(16)));
static hcb_pathq g_pq[HCB_MAX_PATHQ];
static hcb_patha g_pa[HCB_MAX_PATHQ];
static u32 g_pq_n, g_pq_now, g_pa_n, g_paths_asked, g_paths_found, g_paths_dropped, g_path_us_max;
static int g_path_thread;
static u32 mc_slot(int x, int y) { return ((u32)x * 73856093U ^ (u32)y * 19349663U) & (MCACHE - 1); }
static struct mcell *mc_find(int x, int y) {
    u32 h = mc_slot(x, y), k;
    for (k = 0; k < 16; k++) { struct mcell *c = &g_mc[(h + k) & (MCACHE - 1)]; if (!c->used) return 0; if (c->x == x && c->y == y) return c; }
    return 0;
}
static void mc_put(int x, int y, float z, u8 wall) {
    u32 h = mc_slot(x, y), k;
    struct mcell *c = 0;
    if (x < -4000 || x > 4000 || y < -4000 || y > 4000) return;
    for (k = 0; k < 16 && !c; k++) { struct mcell *q = &g_mc[(h + k) & (MCACHE - 1)]; if (!q->used || (q->x == x && q->y == y)) c = q; }
    if (!c) c = &g_mc[h];                                               /* (the neighbourhood is full: the oldest habit goes) */
    if (!c->used) g_mc_n++;
    if (!c->used || c->x != x || c->y != y || c->z != z || c->wall != wall) g_mc_dirty++;
    c->x = (short)x; c->y = (short)y; c->z = z; c->wall = wall; c->used = 1;
}
static void map_load(void) {
    u32 head[3], i; int fd = open(MAP_FILE, O_RDONLY);
    struct { short x, y; float z; u8 wall, pad[3]; } r;
    if (fd < 0) { lg("the map of earlier games: none yet\n"); return; }
    if (read(fd, head, 12) == 12 && head[0] == MAP_MAGIC && head[1] == 1 && head[2] <= MCACHE)
        for (i = 0; i < head[2] && read(fd, &r, 12) == 12; i++) {
            if (!(r.z == r.z) || r.z < -200.0f || r.z > 2000.0f || r.wall > 3) continue;       /* (a damaged file: such a cell is left out) */
            mc_put(r.x, r.y, r.z, r.wall); g_mc_loaded++;
        }
    close(fd);
    g_mc_dirty = 0;
    lg("the map of earlier games: "); tu(&g_log, g_mc_loaded); lg(" cells of ground known from the start\n");
}
static void map_write(void) {                                           /* (the thread's: from the copy the game's thread made) */
    static struct { short x, y; float z; u8 wall, pad[3]; } out[MCACHE];
    u32 head[3], i, n = 0; int fd;
    for (i = 0; i < MCACHE; i++) if (g_mc_copy[i].used) { out[n].x = g_mc_copy[i].x; out[n].y = g_mc_copy[i].y; out[n].z = g_mc_copy[i].z; out[n].wall = g_mc_copy[i].wall; out[n].pad[0] = out[n].pad[1] = out[n].pad[2] = 0; n++; }
    head[0] = MAP_MAGIC; head[1] = 1; head[2] = n;
    fd = open(MAP_FILE, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, head, 12); write(fd, out, (u64)n * 12); close(fd);
    g_mc_saved = n;
}
/* one turn of the thread's work (also called by the tests, and by the game's thread itself when there is no thread) */
EXPORT void hcb_path_work(void) {
    if (__atomic_load_n(&g_path_job, __ATOMIC_ACQUIRE) == 1) {
        u32 i; u64 t0 = now_us();
        for (i = 0; i < g_pq_n && i < HCB_MAX_PATHQ; i++) {
            g_pa[i].from = g_pq[i].from; g_pa[i].to = g_pq[i].to; g_pa[i].key = g_pq[i].key;
            g_pa[i].n = hcb_nav_solve(g_nav_copy, g_pq[i].from, g_pq[i].to, g_pa[i].wp, 10, g_pq_now);
        }
        g_pa_n = i;
        t0 = now_us() - t0;
        if (t0 > g_path_us_max) g_path_us_max = (u32)t0;
        __atomic_store_n(&g_path_job, 2, __ATOMIC_RELEASE);
    }
    if (__atomic_exchange_n(&g_map_save, 0, __ATOMIC_ACQ_REL)) map_write();
}
static void *path_thread(void *arg) {
    (void)arg;
    for (;;) { hcb_path_work(); usleep(__atomic_load_n(&g_ready, __ATOMIC_ACQUIRE) && g_snap.n_ours ? 3000 : 100000); }
    return 0;
}
/* after a look: the core's questions go to the thread (with a copy of the map as it is now); every 30 s a changed map is handed over to be written */
static void path_post(u32 now) {
    if (g_out.n_path_q) {
        if (__atomic_load_n(&g_path_job, __ATOMIC_ACQUIRE) == 0 && hcb_nav_size() <= sizeof g_nav_copy) {
            u32 i;
            hcb_nav_copy(BRAIN, g_nav_copy);
            g_pq_n = g_out.n_path_q < HCB_MAX_PATHQ ? g_out.n_path_q : HCB_MAX_PATHQ;
            for (i = 0; i < g_pq_n; i++) g_pq[i] = g_out.path_q[i];
            g_pq_now = now; g_paths_asked += g_pq_n;
            __atomic_store_n(&g_path_job, 1, __ATOMIC_RELEASE);
            if (!g_path_thread) hcb_path_work();
        } else g_paths_dropped += g_out.n_path_q;                        /* (the thread is still on the last ones: the core asks again) */
    }
    if (g_mc_dirty && (now < g_mc_save_at || now - g_mc_save_at >= 30000) && !__atomic_load_n(&g_map_save, __ATOMIC_ACQUIRE)) {
        memcpy(g_mc_copy, g_mc, sizeof g_mc); g_mc_dirty = 0; g_mc_save_at = now ? now : 1;
        __atomic_store_n(&g_map_save, 1, __ATOMIC_RELEASE);
        if (!g_path_thread) hcb_path_work();
    }
}
/* before a look: the ways the thread has found */
static void path_collect(hcb_snapshot *s) {
    s->n_paths = 0;
    if (__atomic_load_n(&g_path_job, __ATOMIC_ACQUIRE) == 2) {
        u32 i;
        for (i = 0; i < g_pa_n && i < HCB_MAX_PATHQ; i++) { s->paths[i] = g_pa[i]; if (g_pa[i].n > 0) g_paths_found++; }
        s->n_paths = i;
        __atomic_store_n(&g_path_job, 0, __ATOMIC_RELEASE);
    }
}
static float ground_z(float x, float y, float z, int *found) {
    u8 f = 0; float g; u64 t0 = now_us(); u32 was = g_where;
    g_where = 24;
    g = ((ground_fn)(G + FIND_GROUND))(x, y, z, &f, 0);
    g_where = was;
    g_map_us += now_us() - t0;
    *found = f && g == g && g <= z + 0.01f && g > z - 60.0f;
    return g;
}
static int map_ray(const float *p, const float *q) { u64 t0 = now_us(); int r = ray(p, q, 0); g_map_us += now_us() - t0; return r; }
/* the map's answers for this look: the straight legs first (a man is waiting for them), then the ground, then one more spot
   in the search for a high place */
static void fill_map(hcb_snapshot *s, const hcb_out *prev, const float *cjp) {
    u32 i, n, k;
    g_map_us = 0;
    if (!g_map_ok) return;
    n = prev->n_seg_q < HCB_MAX_SEGS ? prev->n_seg_q : HCB_MAX_SEGS;
    for (i = 0; i < n && g_map_us < MAP_LOOK_US; i++) {
        hcb_seg *a = &s->segs[s->n_segs++];
        float p[3], q[3];
        *a = prev->seg_q[i];
        p[0] = a->a.x; p[1] = a->a.y; p[2] = a->a.z - 0.4f; q[0] = a->b.x; q[1] = a->b.y; q[2] = a->b.z - 0.4f;
        a->clear = (u8)map_ray(p, q);
        if (a->clear) { p[2] += 0.7f; q[2] += 0.7f; a->clear = (u8)map_ray(p, q); }
        g_map_segs++;
    }
    g_map_left += n - i;
    /* a high place for the marksman: one spot every other look (before the ground, which takes all the time there is while the map is new), on four rings round CJ. It must be 4-35 m above his feet, flat (the
       ground a metre to each side is level with it) - whether CJ is seen from it is told with it */
    if (g_map_us < MAP_LOOK_US && !(g_ticks & 1) && !s->player.vehicle && !s->interior && s->n_ours) {
        static const float RING[4] = {14.0f, 22.0f, 32.0f, 45.0f};
        static const float DIR[8][2] = {{1, 0}, {0.7071f, 0.7071f}, {0, 1}, {-0.7071f, 0.7071f}, {-1, 0}, {-0.7071f, -0.7071f}, {0, -1}, {0.7071f, -0.7071f}};
        u32 c = g_high_i++ % 32;
        float r = RING[c / 8], x = cjp[0] + DIR[c % 8][0] * r, y = cjp[1] + DIR[c % 8][1] * r, feet = cjp[2] - 1.0f, g, g2, g3, eye[3], cj[3];
        int f, f2, f3;
        g_high[c].ok = 0;
        g = ground_z(x, y, feet + 38.0f, &f);
        if (f && g >= feet + 4.0f && g <= feet + 35.0f) {
            g2 = ground_z(x + 1.0f, y, g + 1.5f, &f2); g3 = ground_z(x, y + 1.0f, g + 1.5f, &f3);
            if (f2 && f3 && g2 - g < 0.4f && g - g2 < 0.4f && g3 - g < 0.4f && g - g3 < 0.4f) {
                eye[0] = x; eye[1] = y; eye[2] = g + 1.6f; cj[0] = cjp[0]; cj[1] = cjp[1]; cj[2] = cjp[2] + 0.3f;
                g_high[c].at.x = x; g_high[c].at.y = y; g_high[c].at.z = g + 1.0f; g_high[c].height = g - feet;
                g_high[c].sees = (u8)map_ray(eye, cj); g_high[c].time = s->time; g_high[c].ok = 1;
            }
        }
    }
    n = prev->n_ground_q < HCB_MAX_GROUND ? prev->n_ground_q : HCB_MAX_GROUND;
    for (i = 0; i < n; i++) {
        hcb_ground q0 = prev->ground_q[i], *a;
        struct mcell *mc;
        int f, f2, cx, cy;
        float g, p[3], q[3];
        if (q0.x != q0.x || q0.y != q0.y || q0.z != q0.z || q0.x < -4000.0f || q0.x > 4000.0f || q0.y < -4000.0f || q0.y > 4000.0f || q0.z < -200.0f || q0.z > 2000.0f) continue;
        cx = (int)q0.x - (q0.x < 0.0f); cy = (int)q0.y - (q0.y < 0.0f);
        /* 1.1: known from before (this game or an earlier one), on the level asked about: answered without the game */
        mc = mc_find(cx, cy);
        if (mc && mc->z <= q0.z + 0.01f && q0.z - mc->z < 6.0f) {
            a = &s->ground[s->n_ground++]; *a = q0; a->found = 1; a->z = mc->z; a->wall = mc->wall;
            g_map_ground++; g_map_ground_ok++; g_mc_hits++;
            continue;
        }
        if (g_map_us >= MAP_LOOK_US) { g_map_left++; continue; }
        a = &s->ground[s->n_ground++];
        *a = q0; a->found = 0; a->wall = 0;
        g_map_ground++;
        g = ground_z(a->x, a->y, a->z, &f);
        if (!f) continue;
        p[0] = a->x; p[1] = a->y; p[2] = g + 0.7f;
        g_ray_cars = 0;
        for (k = 0; k < 2; k++) {                                       /* what stands between this cell and the next one to +x, to +y */
            float g2;
            q[0] = a->x + (k == 0 ? 1.0f : 0.0f); q[1] = a->y + (k == 1 ? 1.0f : 0.0f);
            g2 = ground_z(q[0], q[1], g + 1.2f, &f2);
            q[2] = (f2 && g2 - g < 0.8f && g - g2 < 0.8f ? g2 : g) + 0.7f;
            if (!map_ray(p, q)) a->wall |= (u8)(1 << k);
        }
        g_ray_cars = 1;
        a->found = 1; a->z = g;
        g_map_ground_ok++;
        mc_put(cx, cy, g, a->wall);
    }
    for (i = 0; i < 32 && s->n_high < HCB_MAX_HIGH; i++) {
        float at[3];
        if (!g_high[i].ok || s->time < g_high[i].time || s->time - g_high[i].time > 20000) continue;
        at[0] = g_high[i].at.x; at[1] = g_high[i].at.y; at[2] = g_high[i].at.z;
        if (dist2(at, cjp) > 75.0f * 75.0f || !g_high[i].sees) continue;
        s->high[s->n_high].at = g_high[i].at; s->high[s->n_high].height = g_high[i].at.z - 1.0f - (cjp[2] - 1.0f); s->high[s->n_high].sees_cj = 1; s->n_high++;
    }
    if (g_map_us > g_map_us_max) g_map_us_max = (u32)g_map_us;
}
/* 0.9 read the thing a cover point is on through the kernel (process_vm_readv), and on the tablet every such read was refused:
   "table: live 23-86, read 0" in the sixth log. 1.0: the pointer is checked against the game's own pools instead - a vehicle,
   an object, a building or a dummy in a slot in use (CObject 0x1f8, CBuilding and CDummy 0x60 bytes: the game's debug info). */
static int thing_ok(u64 ent) {
    static const struct { u64 slot; u32 stride; } POOLS[4] = {{VEH_POOL, VEH_STRIDE}, {0xbc3bd0UL, 0x1f8U}, {0xbc3bc8UL, 0x60U}, {0xbc3bd8UL, 0x60U}};
    u32 k;
    for (k = 0; k < 4; k++) {
        const u8 *pl = RD(const u8 *, G + POOLS[k].slot), *objs, *flags;
        u64 off; int size;
        if (!pl) continue;
        objs = RD(const u8 *, pl); flags = RD(const u8 *, pl + 8); size = RD(int, pl + 0x10);
        if (!objs || !flags || size <= 0 || size > 100000 || ent < (u64)objs) continue;
        off = ent - (u64)objs;
        if (off % POOLS[k].stride || off / POOLS[k].stride >= (u64)size) continue;
        return !(flags[off / POOLS[k].stride] & 0x80);
    }
    return 0;
}
static void fill_more(hcb_snapshot *s, const float *cjp) {
    u32 i;
    s->n_hints = 0; s->n_dangers = 0; s->in_water = 0;
    if (g_water_ok && !s->player.vehicle) {
        float level = -10000.0f;
        g_where = 22;
        g_water_calls++;
        if (((water_fn)(G + WATER_LEVEL))(cjp[0], cjp[1], cjp[2], &level, 1, 0) && level == level && level > cjp[2] - 0.2f && level < cjp[2] + 30.0f) { s->in_water = 1; g_water_yes++; }
        g_where = 1;
    }
    if (!g_tables_ok) return;
    for (i = 0; i < 32 && s->n_dangers < HCB_MAX_DANGERS; i++) {          /* in the air or lying: grenades, bottles, rockets */
        const u8 *pi = (const u8 *)(G + PROJ_INFO + (u64)i * 0x38);
        u32 w = RD(u32, pi);
        float p[3];
        hcb_danger *d;
        if (!RD(u8, pi + 0x1c)) continue;
        memcpy(p, pi + 0x20, 12);
        if (!sane(p) || dist2(p, cjp) > 60.0f * 60.0f) continue;
        if (!(w == 16 || w == 17 || w == 39 || w == 18 || w == 19 || w == 20)) continue;
        d = &s->dangers[s->n_dangers++];
        d->at.x = p[0]; d->at.y = p[1]; d->at.z = p[2];
        d->kind = w == 18 ? HCB_DG_FIRE : w == 19 || w == 20 ? HCB_DG_ROCKET : HCB_DG_GRENADE;
        d->radius = w == 18 ? 7.0f : 10.0f;
    }
    for (i = 0; i < 16 && s->n_dangers < HCB_MAX_DANGERS; i++) {          /* just gone off (for the picture and the log) */
        const u8 *e = (const u8 *)(G + EXPLOSIONS + (u64)i * 0x88);
        float p[3];
        hcb_danger *d;
        if (!RD(u8, e + 0x30)) continue;
        memcpy(p, e + 4, 12);
        if (!sane(p) || dist2(p, cjp) > 60.0f * 60.0f) continue;
        d = &s->dangers[s->n_dangers++];
        d->at.x = p[0]; d->at.y = p[1]; d->at.z = p[2]; d->kind = HCB_DG_BLAST; d->radius = RD(float, e + 0x10);
    }
    /* the game's cover points near CJ: looked up twice a second (a point on a car or an object is that thing's place - read
       through the kernel, so a pointer that has gone stale is an error, never a crash) */
    if (!g_hints_at || s->time - g_hints_at >= 500 || s->time < g_hints_at) {
        g_hints_at = s->time ? s->time : 1; g_n_hints = 0; g_cover_live = 0; g_cover_ok = 0;
        for (i = 0; i < 100 && g_n_hints < HCB_MAX_HINTS; i++) {
            const u8 *c = (const u8 *)(G + COVER_POINTS + (u64)i * 0x28);
            u64 ent = RD(u64, c + 0x10), m = 0;
            float p[3];
            if (!RD(signed char, c)) continue;
            g_cover_live++;
            memcpy(p, c + 4, 12);
            if (ent) {                                                  /* the thing it is on: only one that lies in a pool of the game, in a slot in use */
                if (!thing_ok(ent)) continue;
                m = RD(u64, ent + 0x18);
                memcpy(p, m ? (const void *)(m + 0x30) : (const void *)(ent + 8), 12);
            }
            if (!sane(p)) continue;
            g_cover_ok++;
            if (dist2(p, cjp) > 30.0f * 30.0f) continue;
            g_hints[g_n_hints].x = p[0]; g_hints[g_n_hints].y = p[1]; g_hints[g_n_hints].z = p[2]; g_n_hints++;
        }
    }
    s->n_hints = (u16)g_n_hints;
    for (i = 0; i < g_n_hints; i++) s->hints[i] = g_hints[i];
}
/* the commander says it aloud too: a line of the game's own that fits (the model has it or stays silent) */
static void speak(u8 say, u32 lead) {
    static const u16 CTX[13] = {0, 144 /* MOVE_IN */, 159 /* ORDER_WAIT_MANY */, 153 /* ORDER_FOLLOW_NEAR_MANY */, 44 /* CHASED */, 148 /* ORDER_ATTACK_SINGLE */,
                                258 /* ENEMY_GANG_WASTED */, 85 /* DUCK */, 220 /* TARGET */, 85 /* DUCK */, 40 /* CAR_WAIT_FOR_ME */, 220 /* TARGET */, 85 /* DUCK: a car is coming */};
    struct pool pp;
    u8 *ped;
    if (!g_say_ok || say >= 13 || !CTX[say] || !lead || !get_pool(PED_POOL, &pp) || !(ped = obj_of(&pp, lead, PED_STRIDE)) || is_dead(ped)) return;
    g_where = 21;
    ((say_fn)(G + PED_SAY))(ped, CTX[say], 0, 1.0f, 0, 0, 0);
    g_where = 1;
    g_said_voice++;
}

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
    /* 1.0: the player's mode; "to me" holds for ten seconds from the press */
    if (shared_get(HC_MODE, &v)) s->umode = v == 1 ? HCB_UMODE_ASSAULT : HCB_UMODE_PROTECT;
    if (shared_get(HC_RECALL, &v) && v == 1) { g_recall_until = s->time + 10000; shared_set(HC_RECALL, 0); }
    if (g_recall_until && (s->time >= g_recall_until || g_recall_until - s->time > 10000)) g_recall_until = 0;
    s->recall = g_recall_until != 0;
    s->body = (u8)(g_body_ok && g_map_ok);

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
        s->our_state[s->n_ours] = (u8)((on_rope(obj_of(&pp, v, PED_STRIDE)) ? HCB_OS_ROPING : 0) | (s->body ? HCB_OS_NATIVE : 0));
        s->our_clip[s->n_ours] = clip_of(obj_of(&pp, v, PED_STRIDE));
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
            if (a->hidden) { low[2] = q->at.z + 0.55f; a->hidden_hi = (u8)!ray(from, low, 0); }   /* standing up, can he fire over it? */
            a->ground = (u8)!ray(up, down, 0);
        }
        g_rays_skipped += nq - i;
    }
    if (g_rays - rays0 > g_rays_look_max) g_rays_look_max = g_rays - rays0;
    /* who is ours, for the gunshot hook */
    g_our_ent[0] = cj; g_our_ent[1] = obj_of(&vp, VHANDLE(s->heli), VEH_STRIDE);
    for (k = 0; k < HCB_MAX_OURS; k++) g_our_ent[2 + k] = k < s->n_ours ? obj_of(&pp, s->ours[k], PED_STRIDE) : 0;
    fill_more(s, cjp);
    fill_map(s, prev, cjp);
    path_collect(s);
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
static void wall_date(struct text *t) {                                 /* the phone's clock, as a date (UTC) */
    struct timespec now; long z, era, doe, yoe, doy, mp, d, m, y, sec;
    now.tv_sec = 0; now.tv_nsec = 0; clock_gettime(0, &now);
    sec = now.tv_sec % 86400; z = now.tv_sec / 86400 + 719468;
    era = z / 146097; doe = z - era * 146097; yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    y = yoe + era * 400; doy = doe - (365 * yoe + yoe / 4 - yoe / 100); mp = (5 * doy + 2) / 153;
    d = doy - (153 * mp + 2) / 5 + 1; m = mp < 10 ? mp + 3 : mp - 9; if (m <= 2) y++;
    ti(t, y); ts(t, m < 10 ? "-0" : "-"); ti(t, m); ts(t, d < 10 ? "-0" : "-"); ti(t, d);
    ts(t, sec / 3600 < 10 ? " 0" : " "); ti(t, sec / 3600); ts(t, (sec / 60) % 60 < 10 ? ":0" : ":"); ti(t, (sec / 60) % 60);
    ts(t, sec % 60 < 10 ? ":0" : ":"); ti(t, sec % 60);
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

/* ---------- 0.7: the places where the detail was attacked, kept between games ----------
   configs/net.helicover.brain.places: a count and up to 16 entries of x, y, z, how many times. The core owns the list. */
#define PLACES_FILE GAME_DIR "configs/net.helicover.brain.places"
struct place_rec { float x, y, z; u32 n; };
static void places_load(void) {
    struct place_rec r[HCB_MAX_PLACES]; hcb_vec at[HCB_MAX_PLACES]; u16 cnt[HCB_MAX_PLACES];
    u32 n = 0, i, k = 0; long got; int fd = open(PLACES_FILE, O_RDONLY);
    if (fd < 0) { lg("places of earlier attacks: none remembered yet\n"); return; }
    got = read(fd, &n, 4);
    if (got == 4 && n <= HCB_MAX_PLACES && read(fd, r, (u64)n * sizeof r[0]) == (long)(n * sizeof r[0]))
        for (i = 0; i < n; i++) {
            float p[3]; p[0] = r[i].x; p[1] = r[i].y; p[2] = r[i].z;
            if (!sane(p)) continue;                                     /* (a damaged file: such an entry is left out) */
            at[k].x = r[i].x; at[k].y = r[i].y; at[k].z = r[i].z; cnt[k] = (u16)(r[i].n > 60000 ? 60000 : r[i].n); k++;
        }
    close(fd);
    hcb_places_set(BRAIN, at, cnt, (int)k);
    lg("places of earlier attacks remembered: "); tu(&g_log, k); lg("\n");
}
static void places_save(void) {
    struct place_rec r[HCB_MAX_PLACES]; hcb_vec at[HCB_MAX_PLACES]; u16 cnt[HCB_MAX_PLACES];
    u32 n = (u32)hcb_places_get(BRAIN, at, cnt), i; int fd;
    for (i = 0; i < n; i++) { r[i].x = at[i].x; r[i].y = at[i].y; r[i].z = at[i].z; r[i].n = cnt[i]; }
    fd = open(PLACES_FILE, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, &n, 4); write(fd, r, (u64)n * sizeof r[0]); close(fd);
    log_begin(); stamp(&g_log, RD(u32, G + TIME_MS)); lg("a fight here: the place is remembered ("); tu(&g_log, n); lg(" places in all)\n"); log_end();
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
    path_post(now);
    if (g_out.say) { g_say_seq = g_out.say_seq; g_say = g_out.say; g_say_dir = g_out.say_dir; }
    if (hcb_places_changed(BRAIN)) places_save();
    if (g_out.say) speak(g_out.say, g_out.lead);
    journal(now);
    hcb_rec_push(&g_rec[g_cur], g_box[g_cur], &g_snap, g_out.digest);
    memcpy(&g_shown, &g_out, sizeof g_shown);
    g_ticks++;
    g_think_end_us = now_us();
    t0 = g_think_end_us - t0;
    g_think_cost_us = t0;
    g_tick_us_sum += t0;
    if (t0 > g_tick_us_max) g_tick_us_max = (u32)t0;
    session_look(now, t0);
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
    /* PHASE: 0 and 3 = the crew is in its doors, 1 = on foot after a landing, 2 = moving to the doors (the Fire script rests
       them then). 0.4.1 asked for 2 - the one phase they do not fire in - and no gunner fired a round in a whole game. */
    if (!g_fire_ready || !g_ticks || (shared_get(HC_PHASE, &v) && (v == 1 || v == 2))) return;
    for (k = 0; k < g_snap.n_ours; k++)
        if (g_snap.our_role[k] >= HCB_ROLE_GUNNER && g_snap.our_role[k] < HCB_ROLE_SQUAD) gunner_shot(g_snap.ours[k]);
}
static const char *const ROLE_NAME[] = {"let-go", "pilot", "gunner1", "gunner2", "gunner3", "gunner4",
                                        "guard1", "guard2", "guard3", "guard4", "guard5", "guard6", "guard7", "guard8"};
static const char *const JOB_NAME[] = {"-", "LEAD", "CLOSE", "POINT", "REAR", "CLOSE2", "POINT2", "REAR2", "MARKSMAN", "CLOSE3"};
static const char *const DUTY_NAME[] = {"calm", "watch", "shield", "cover", "bound", "hold", "ring"};
static const char *const HOLD_NAME[] = {"FIRE", "no-target", "rule", "CJ-in-line", "CJ-behind", "friend-in-line", "bystander", "car-near",
                                        "no-LOS", "range", "reacting", "pause", "covering", "enough-on-him", "BY-HAND"};
static const char *const CLS_NAME[] = {"friend", "neutral", "watch", "THREAT", "ATTACKER"};
static const char *const WHY_NAME[] = {"-", "ours", "ally", "hurt-CJ", "hurt-ours", "shot-at-CJ", "shot-at-ours", "aims-at-CJ", "aims-at-ours",
                                       "armed-facing", "armed-near", "hostile-near", "ramming", "burning", "melee-closing", "shooting-nearby", "air-fire"};
static const char *const MODE_NAME[] = {"HOLD", "PULLOUT", "ASSAULT"};
static const char *const MOVE_NAME[] = {"stay", "walk", "run", "sprint", "path"};
static const char *const ACT_NAME[] = {"HOLD", "WALK", "FASTWALK", "RUN", "SPRINT", "COVER", "OVERWATCH", "SIDESTEP"};
static const char *const PHASE_NAME[] = {"chosen", "moving", "arrived", "acting", "FAILED"};
static const char *const WHY2_NAME[] = {"-", "new-post", "direct", "route", "blocked", "no-progress", "no-route", "arrived", "wait-turn", "in-air"};
static const char *const UMODE_NAME[] = {"PROTECT", "ASSAULT"};
static const char *const TASK_NAME[] = {"ESCORT", "SHIELD", "EXTRACT", "APPROACH", "GATHER", "BOUND", "SEARCH", "CONSOLIDATE", "REGROUP", "WITHDRAW"};
/* 1.0: the summary of the session (mods/hcbrain_summary.txt, rewritten every ten seconds): the numbers the 2.0 plan is judged by.
   One sample a second for every guard on the ground who has a post. */
static struct { u32 samples, still, far8, far20, stuck, failed, sprint_calm, calm, changes, near4, near4_n, up, up_n, secs, assault_secs, think_max; u8 act[HCB_MAX_OURS]; u32 act_who[HCB_MAX_OURS]; } g_sum;
static const char *const ALERT_NAME[] = {"calm", "wary", "threat", "COMBAT", "EVACUATE"};
static const char *const SAY_NAME[] = {"", "into cover", "CJ is in cover", "stay with me", "we pull out", "I have command", "clear", "sniper", "we were attacked here before", "grenade", "CJ is in the water", "armed men ahead"};
static const char *const AIM_NAME[] = {"body", "driver", "tyre"};
#define NAME(arr, i) ((u32)(i) < sizeof arr / sizeof arr[0] ? arr[i] : "?")
/* ---------- the journal (1.4.1): what the brain decided, in plain words, for the diagnosis from the log ----------
   Changes of the alert, of the detail's duty and mode, every word of the commander, and every 30 s a summary: how much of
   the fight the gunners and the guards fired and what held them, how many posts were not reached. At most 600 lines a
   minute. (0.4.1: the session log below adds the full picture every second.) */
static u32 j_alert = 99, j_duty = 99, j_at, j_lines, j_lines_at, j_combat, j_looks, j_fire[2], j_seen[2], j_hold[2][32], j_stuck, j_lead;
static void jline(u32 now) {
    if (now - j_lines_at > 60000) { j_lines_at = now; j_lines = 0; }
    j_lines++;
    stamp(&g_log, now);
}
static void journal(u32 now) {
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
    if (j_lines > 600 && now - j_lines_at <= 60000) goto summary;
    log_begin();
    if (g_out.alert != j_alert && g_out.alert < 5) { jline(now); lg("alert "); lg(ALERT_NAME[g_out.alert]); lg(", CJ health "); ti(&g_log, (long)g_snap.player.health); lg("\n"); j_alert = g_out.alert; }
    if (g_out.duty != j_duty && g_out.duty < 7) { jline(now); lg("detail: "); lg(DUTY_NAME[g_out.duty]); lg(", mode "); tu(&g_log, g_out.mode); lg(", "); tu(&g_log, g_out.n_posts); lg(" posts\n"); j_duty = g_out.duty; }
    if (g_out.say && g_out.say < 12) { jline(now); lg("commander: \""); lg(SAY_NAME[g_out.say]); lg("\" (direction "); tu(&g_log, g_out.say_dir); lg(")\n"); }
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
    if (!hcb_order_get(BRAIN, who, &o) || !o.target || !cj || !get_pool(PED_POOL, &pp)) { sq_note(who, 0, 0); body_gun(who, 0, 0, 0); return; }   /* (nobody for him: the mod's gun task, if he has one, is told to stop) */
    me = obj_of(&pp, who, PED_STRIDE); him = obj_of(&pp, o.target, PED_STRIDE);
    if (!me || !him || is_dead(him) || is_dead(me)) { sq_note(who, 0, 0); body_gun(who, 0, 0, 0); return; }
    v[2] = (int)o.target;
    fill_shot(&q, who, o.target, &pp, cj, me, him, 0, 0);
    v[1] = hcb_squad_state(BRAIN, &q);
    sq_note(who, v[1], o.target);
    /* 1.1: his weapon is the mod's (6): aim, fire and cease fire by the command of one gun task - the script gives him none */
    if (o.hold == HCB_HOLD_RELOAD) reload_now(who);
    if (body_gun(who, v[1], o.target, o.hold == HCB_HOLD_RELOAD)) v[1] = 6;
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
        /* 1.0: on his way the mod walks him itself - the script is told 5 ("his legs are mine"); arrived, he stays (0) */
        if (g_snap.body) { struct pool pp_; u8 *me_ = get_pool(PED_POOL, &pp_) ? obj_of(&pp_, who, PED_STRIDE) : 0; if (me_ && !is_dead(me_) && !vehicle_of(me_) && !on_rope(me_)) mind_keep(me_); }
        v[1] = g_snap.body ? (body_walk(who, p) ? 5 : p->phase >= HCB_PH_ARRIVED ? 0 : p->move) : p->move;
        put_f(v + 2, p->at.x); put_f(v + 3, p->at.y); put_f(v + 4, p->at.z);
        v[5] = p->crouch; put_f(v + 6, p->look.x); put_f(v + 7, p->look.y); put_f(v + 8, p->look.z); v[9] = p->duty;
        return;
    }
}
static void cmd_plan(int *v) {
    v[0] = g_out.umode; v[1] = g_out.task; v[2] = g_out.ow_ok; v[3] = g_out.ow_ready;
    put_f(v + 4, g_out.ow_at.x); put_f(v + 5, g_out.ow_at.y); put_f(v + 6, g_out.ow_at.z);
    put_f(v + 7, g_out.target_dist); v[8] = g_out.n_moving; v[9] = g_snap.body;
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
    if (v[4] & 4) {
        /* 0.6, the brain's own pilot in a fight (the script asks every frame while the brain gives a spot): the height is
           the spot's (never under 12 m over the roofs below), short hops at 28 m/s, and on station side-on to the threat -
           the spot lies abeam of the line CJ - threat, so the line from CJ to it is the line to lie along */
        float h = g_out.heli_ok ? g_out.heli_at.z - t[2] : 16.0f;
        in.hover = h < 12.0f ? 12.0f : h > 40.0f ? 40.0f : h;
        in.cruise = 28.0f;
        { float dx = t[0] - pos.x, dy = t[1] - pos.y; if (dx * dx + dy * dy > 40.0f * 40.0f) in.cruise = 45.0f; }   /* (0.8: scouting ahead of CJ's car - it keeps up) */
        in.face.x = t[0] - g_snap.player.pos.x; in.face.y = t[1] - g_snap.player.pos.y; in.face.z = 0;
    }
    if (v[4] & 8) { in.land = 1; in.hover = 15.0f; }                    /* 0.8: the approach to a landing - down to 15 m over the pad on the way in; the game's pilot sets it down from there */
    hcb_pilot_step(&g_pilot, &in, &o);
    g_pilot.last = now;
    g_pilot_out = o; g_pilot_at = now; g_pilot_flags = (u32)v[4]; g_pilot_to[0] = t[0]; g_pilot_to[1] = t[1]; g_pilot_to[2] = t[2];
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
/* ---------- the session log (0.4.1): everything a diagnosis needs, written as the game goes ----------
   Every look: hits on CJ, on ours and by ours, explosions, thrown and launched weapons. Every second (while Helicover is
   out, or there is anything to be wary of; else every 10 s): CJ, the brain's picture and decisions (alert, the detail's
   duty and mode, the commander, cover, the helicopter's spot), each of ours (where, health, weapon, his post and how far,
   his order and why he holds), each contact worth an eye (class, why, distance, expected damage, where, weapon), the
   pilot, the scripts' shared values that changed, the 0E48 calls, the brain's and the game's timing; every 5 s where each
   CLEO script stands; every 30 s all of Helicover's shared values. */
#define HC_KEYS 640U
static char g_dumpbuf[64 * 1024];
static struct text g_dump = {g_dumpbuf, sizeof g_dumpbuf, 0};
static u32 s_sec_at, s_hc_at, s_scripts_at, s_ev_lines, s_ev_cut, s_shots_ours, s_shots_other, s_shots_at_us, s_looks;
static u32 s_own0, s_ref0, s_rounds0, s_rref0, s_rays0, s_skip0;
static u64 s_think_us, s_think_max, s_log_us;
static u32 hc_val[HC_KEYS];
static u8 hc_have[HC_KEYS], hc_streak[HC_KEYS];
static void th(struct text *t, u64 v) {                                 /* short hex */
    char b[20]; int n = 19; b[n] = 0;
    do { int d = (int)(v & 15); b[--n] = (char)(d < 10 ? '0' + d : 'a' + d - 10); v >>= 4; } while (v);
    ts(t, b + n);
}
static void tvec(struct text *t, float x, float y, float z) { ts(t, "("); tf(t, x); ts(t, " "); tf(t, y); ts(t, " "); tf(t, z); ts(t, ")"); }
static void up_stamp(struct text *t) { u64 u = g_start_us ? (now_us() - g_start_us) / 100000UL : 0; ts(t, "[up "); tu(t, u / 10); ts(t, "."); tu(t, u % 10); ts(t, "s] "); }
static int is_ours(u32 id) {
    u32 k;
    if (!id) return 0;
    if (id == g_snap.player.id || id == g_snap.heli) return 1;
    for (k = 0; k < g_snap.n_ours; k++) if (g_snap.ours[k] == id) return 1;
    return 0;
}
static void who(struct text *t, u32 id) {
    u32 k;
    if (!id) { ts(t, "-"); return; }
    if (id == g_snap.player.id) { ts(t, "CJ"); return; }
    if (id == g_snap.heli) { ts(t, "our-heli"); return; }
    for (k = 0; k < g_snap.n_ours; k++) if (g_snap.ours[k] == id) { ts(t, NAME(ROLE_NAME, g_snap.our_role[k])); ts(t, "#"); tu(t, id); return; }
    ts(t, id & 0x80000000u ? "car#" : "#"); tu(t, id & 0x7fffffffu);
}
static const hcb_ped *snap_ped(u32 id) { u32 i; for (i = 0; i < g_snap.n_peds; i++) if (g_snap.peds[i].id == id) return &g_snap.peds[i]; return 0; }
static const hcb_veh *snap_veh(u32 id) { u32 i; for (i = 0; i < g_snap.n_vehs; i++) if (g_snap.vehs[i].id == id) return &g_snap.vehs[i]; return 0; }
static void ped_flags(struct text *t, u32 f, u32 f2) {
    if (f & HCB_PF_DEAD) ts(t, " DEAD");
    if (f & HCB_PF_SHOOTING) ts(t, " shooting");
    if (f & HCB_PF_AIMING) ts(t, " aiming");
    if (f & HCB_PF_DUCKING) ts(t, " ducking");
    if (f & HCB_PF_MISSION) ts(t, " mission");
    if (f & HCB_PF_IN_GROUP) ts(t, " group");
    if (f2 & HCB_PF2_LOS_KNOWN) ts(t, f2 & HCB_PF2_LOS_CLEAR ? " sees-CJ" : " no-LOS-CJ");
    if (f2 & HCB_PF2_ON_FIRE) ts(t, " on-fire");
}
/* a 4-byte value as it most likely is: a whole number, or the bits of a float (a position, a speed) */
static void tval(struct text *t, u32 v) {
    float f, a;
    if ((int)v > -10000000 && (int)v < 10000000) { ti(t, (int)v); return; }
    memcpy(&f, &v, 4); a = f < 0 ? -f : f;
    if (a > 0.001f && a < 100000.0f) { tf(t, f); ts(t, "f"); } else { ts(t, "0x"); th(t, v); }
}
static void hc_scan(struct text *t, int all) {
    u64 b, e, cap, p; u32 k, v, n = 0;
    if (!g_cleo) return;
    b = RD(u64, g_cleo + CLEO_SHARED); e = RD(u64, g_cleo + CLEO_SHARED + 8); cap = RD(u64, g_cleo + CLEO_SHARED + 16);
    if (!b || b > e || e > cap || ((e - b) & 7) || e - b > 8 * 4096) return;
    for (p = b; p < e; p += 8) {
        k = RD(u32, p) - HC_STATE; v = RD(u32, p + 4);
        if (k >= HC_KEYS) continue;
        if (!hc_have[k] || hc_val[k] != v) { if (hc_streak[k] < 255) hc_streak[k]++; } else hc_streak[k] = 0;
        if (all || (hc_streak[k] && hc_streak[k] <= 3) || hc_streak[k] == 4) {
            if (!n++) ts(t, all ? "  Helicover (all):" : "  Helicover changed:");
            ts(t, " +"); tu(t, k);
            if (hc_streak[k] == 4 && !all) ts(t, " keeps changing"); else { ts(t, "="); tval(t, v); }
        }
        hc_have[k] = 1; hc_val[k] = v;
    }
    if (n) ts(t, "\n");
}
static void scripts_list(struct text *t) {
    u64 be[2], a, obj, rs, base, ip; char nm[9]; u32 i, n = 0;
    if (!g_cleo || !safe_read(be, g_cleo + CLEO_SCRIPTS, 16) || be[1] < be[0] || be[1] - be[0] > 64 * 8) return;
    for (a = be[0]; a < be[1]; a += 8) {
        if (!safe_read(&obj, a, 8) || !safe_read(&rs, obj + 0x20, 8) || !safe_read(&base, obj + 0x28, 8) || !safe_read(&ip, rs + 0x20, 8) || !safe_read(nm, rs + 0x10, 8)) continue;
        nm[8] = 0;
        for (i = 0; i < 8; i++) if (nm[i] && (nm[i] < 32 || nm[i] > 126)) nm[i] = '?';
        ts(t, n++ ? " " : "  CLEO scripts:"); ts(t, nm); ts(t, "@"); th(t, ip - base);
    }
    if (n) ts(t, "\n");
}
static void session_events(u32 now) {
    struct text *D = &g_dump;
    u32 i;
    for (i = 0; i < g_snap.n_events; i++) {
        const hcb_event *e = &g_snap.events[i];
        int src = is_ours(e->src), dst = is_ours(e->dst);
        if (e->type == HCB_EV_SHOT) { if (src) s_shots_ours++; else { s_shots_other++; if (dst) s_shots_at_us++; } continue; }
        if (e->type == HCB_EV_DAMAGE && !src && !dst) continue;                   /* strangers hurting strangers */
        if (s_ev_lines >= 80) { s_ev_cut++; continue; }
        s_ev_lines++;
        stamp(D, e->time);
        if (e->type == HCB_EV_DAMAGE) { ts(D, "hit: "); who(D, e->src); ts(D, " -> "); who(D, e->dst); ts(D, " "); tf(D, e->value); ts(D, " (weapon "); tu(D, e->weapon); ts(D, ")\n"); }
        else if (e->type == HCB_EV_EXPLOSION) { ts(D, "explosion at "); tvec(D, e->a.x, e->a.y, e->a.z); ts(D, " r "); tf(D, e->value); ts(D, " by "); who(D, e->src); ts(D, "\n"); }
        else if (e->type == HCB_EV_PROJECTILE) { ts(D, "thrown/launched weapon "); tu(D, e->weapon); ts(D, " by "); who(D, e->src); ts(D, " at "); tvec(D, e->a.x, e->a.y, e->a.z); ts(D, "\n"); }
    }
    (void)now;
}
static void session_ours(struct text *D) {
    struct pool pp;
    u32 k, i;
    int pool = get_pool(PED_POOL, &pp);
    for (k = 0; k < g_snap.n_ours; k++) {
        u32 id = g_snap.ours[k];
        const hcb_ped *p = snap_ped(id);
        const hcb_post *po = 0; const hcb_order *o = 0;
        ts(D, "  "); who(D, id);
        if (p) {
            ts(D, " hp "); tf(D, p->health); ts(D, "/"); tf(D, p->armour); ts(D, " "); tvec(D, p->pos.x, p->pos.y, p->pos.z);
            if (p->vehicle) { ts(D, " in "); who(D, p->vehicle); ts(D, " seat "); tu(D, p->seat); }
            ts(D, " w "); tu(D, p->weapon); ts(D, " target "); who(D, p->target); ped_flags(D, p->flags, 0);
        } else {
            const u8 *e = pool ? obj_of(&pp, id, PED_STRIDE) : 0;
            if (e) { const float *q = pos_of(e); ts(D, " hp "); tf(D, RD(float, e + 0x6ac)); ts(D, " "); tvec(D, q[0], q[1], q[2]); ts(D, " (not in the look)"); }
            else ts(D, " (gone)");
        }
        for (i = 0; i < g_out.n_posts; i++) if (g_out.posts[i].who == id) po = &g_out.posts[i];
        for (i = 0; i < g_out.n_orders; i++) if (g_out.orders[i].who == id) o = &g_out.orders[i];
        if (po) {
            ts(D, " | post "); ts(D, NAME(JOB_NAME, po->job)); ts(D, " "); ts(D, NAME(DUTY_NAME, po->duty)); ts(D, " "); tvec(D, po->at.x, po->at.y, po->at.z);
            if (p) { float dx = po->at.x - p->pos.x, dy = po->at.y - p->pos.y; ts(D, " "); tf(D, f_sqrt(dx * dx + dy * dy)); ts(D, "m"); }
            ts(D, " "); ts(D, NAME(MOVE_NAME, po->move));
            if (po->crouch) ts(D, " crouch");
            if (po->stuck) ts(D, " STUCK");
            ts(D, " | "); ts(D, NAME(ACT_NAME, po->act)); ts(D, " "); ts(D, NAME(PHASE_NAME, po->phase)); ts(D, " why "); ts(D, NAME(WHY2_NAME, po->why));
            if (po->phase <= HCB_PH_MOVING) { ts(D, " via "); tvec(D, po->via.x, po->via.y, po->via.z); }
        }
        if (g_snap.our_state[k] & HCB_OS_ROPING) ts(D, " ON-ROPE/IN-AIR");
        {   /* what the game itself has him doing: the task types in his event slots (1, 2), his main slot (3) and his gun slot */
            const u8 *e = pool ? obj_of(&pp, id, PED_STRIDE) : 0;
            if (e && g_body_ok) {
                ts(D, " | game tasks "); ti(D, task_type(task_slot(e, 1))); ts(D, " "); ti(D, task_type(task_slot(e, 2))); ts(D, " main "); ti(D, task_type(task_slot(e, 3)));
                ts(D, " gun "); ti(D, task_type(task_slot(e, 5)));
            }
        }
        if (o) {
            ts(D, " | order "); who(D, o->target); ts(D, " "); ts(D, NAME(HOLD_NAME, o->fire ? 0 : o->hold));
            if (o->ready) ts(D, " ready");
            if (o->target) { ts(D, " aim "); ts(D, NAME(AIM_NAME, o->aim_at)); }
        }
        ts(D, "\n");
    }
}
static void session_contacts(struct text *D) {
    u32 i, n = 0;
    for (i = 0; i < g_out.n_marks && n < 24; i++) {
        const hcb_mark *m = &g_out.marks[i];
        if (m->cls < HCB_CLS_WATCH && m->id != g_out.top) continue;
        n++;
        ts(D, "  contact "); who(D, m->id); ts(D, " "); ts(D, NAME(CLS_NAME, m->cls)); ts(D, " "); ts(D, NAME(WHY_NAME, m->why));
        ts(D, " "); tf(D, m->dist); ts(D, "m edps "); tf(D, m->edps); ts(D, m->seen ? "" : " remembered");
        if (m->kind == HCB_KIND_PED) {
            const hcb_ped *p = snap_ped(m->id);
            if (p) {
                ts(D, " "); tvec(D, p->pos.x, p->pos.y, p->pos.z); ts(D, " hp "); tf(D, p->health); ts(D, " w "); tu(D, p->weapon);
                ts(D, " type "); tu(D, p->pedtype); ts(D, " model "); tu(D, p->model); ts(D, " target "); who(D, p->target);
                if (p->vehicle) { ts(D, " in "); who(D, p->vehicle); }
                ped_flags(D, p->flags, p->flags2);
            }
        } else {
            const hcb_veh *v = snap_veh(m->id);
            if (v) {
                ts(D, " "); tvec(D, v->pos.x, v->pos.y, v->pos.z); ts(D, " speed "); tf(D, f_sqrt(v->vel.x * v->vel.x + v->vel.y * v->vel.y));
                ts(D, " hp "); tf(D, v->health); ts(D, " model "); tu(D, v->model); ts(D, " driver "); who(D, v->driver);
            }
        }
        ts(D, "\n");
    }
}
static void pct(struct text *t, const char *name, u32 a, u32 of, const char *goal) {
    ts(t, name); ts(t, ": "); if (of) { tu(t, (u64)a * 100 / of); ts(t, " %"); } else ts(t, "-"); ts(t, " ("); tu(t, a); ts(t, " of "); tu(t, of); ts(t, ")"); ts(t, goal); ts(t, "\n");
}
static void session_summary(u32 now) {
    static char buf[2048];
    struct text t = {buf, sizeof buf, 0};
    const hcb_ped *cj = &g_snap.player;
    float cv = f_sqrt(cj->vel.x * cj->vel.x + cj->vel.y * cj->vel.y);
    u32 i, k, near = 0, any = 0;
    (void)now;
    for (i = 0; i < g_out.n_posts; i++) {
        const hcb_post *po = &g_out.posts[i];
        const hcb_ped *p = snap_ped(po->who);
        float dx, dy, d;
        if (!p || (p->flags & HCB_PF_DEAD) || p->vehicle || cj->vehicle) continue;
        for (k = 0; k < g_snap.n_ours && g_snap.ours[k] != po->who; k++) {}
        if (k < g_snap.n_ours && (g_snap.our_state[k] & HCB_OS_ROPING)) continue;
        any = 1;
        dx = po->at.x - p->pos.x; dy = po->at.y - p->pos.y; d = f_sqrt(dx * dx + dy * dy);
        g_sum.samples++;
        if (cv < 0.5f) { g_sum.still++; if (d > 8.0f) g_sum.far8++; if (d > 20.0f) g_sum.far20++; }
        if (po->stuck) g_sum.stuck++;
        if (po->phase == HCB_PH_FAILED) g_sum.failed++;
        if (g_out.alert < HCB_ALERT_THREAT) { g_sum.calm++; if (po->act == HCB_ACT_SPRINT) g_sum.sprint_calm++; }
        if (k < HCB_MAX_OURS) { if (g_sum.act_who[k] == po->who && g_sum.act[k] != po->act) g_sum.changes++; g_sum.act_who[k] = po->who; g_sum.act[k] = po->act; }
        dx = cj->pos.x - p->pos.x; dy = cj->pos.y - p->pos.y;
        if (dx * dx + dy * dy < 16.0f) near++;
        if (po->job == HCB_ROLE_MARKSMAN) { g_sum.up_n++; if (p->pos.z > cj->pos.z + 4.0f) g_sum.up++; }
    }
    if (!any) return;
    g_sum.secs++;
    if (g_out.umode == HCB_UMODE_ASSAULT) g_sum.assault_secs++;
    if (g_out.umode == HCB_UMODE_PROTECT && g_out.n_posts >= 7) { g_sum.near4 += near; g_sum.near4_n++; }
    if (g_tick_us_max > g_sum.think_max) g_sum.think_max = g_tick_us_max;
    if (g_sum.secs % 10) return;
    ts(&t, "Helicover Brain " VERSION "\nSummary of this game session while the guards were on the ground (one sample a second for every guard with a post).\n");
    ts(&t, "seconds: "); tu(&t, g_sum.secs); ts(&t, ", of them in ASSAULT mode: "); tu(&t, g_sum.assault_secs); ts(&t, "; the body: "); ts(&t, g_snap.body ? "the mod" : "the scripts"); ts(&t, "\n");
    pct(&t, "guard farther than 8 m from his post while CJ stands", g_sum.far8, g_sum.still, "   [0.9: 65 %, goal: 15 % or less]");
    pct(&t, "guard farther than 20 m from his post while CJ stands", g_sum.far20, g_sum.still, "   [0.9: 45 %]");
    pct(&t, "STUCK", g_sum.stuck, g_sum.samples, "   [0.9: 21 %, goal: 5 % or less]");
    pct(&t, "gave his post up for a while (FAILED)", g_sum.failed, g_sum.samples, "");
    pct(&t, "sprinting with no threat", g_sum.sprint_calm, g_sum.calm, "   [0.9: 50 %, goal: 10 % or less]");
    ts(&t, "changes of action per guard per minute: "); if (g_sum.samples) tf(&t, (float)g_sum.changes * 60.0f / (float)g_sum.samples); ts(&t, "   [goal: 6 or less]\n");
    ts(&t, "guards within 4 m of CJ in PROTECT (average): "); if (g_sum.near4_n) tf(&t, (float)g_sum.near4 / (float)g_sum.near4_n); ts(&t, "   [0.9: 6 of 8, goal: 3]\n");
    pct(&t, "the marksman 4 m or more above CJ", g_sum.up, g_sum.up_n, "   [0.9: never]");
    ts(&t, "the mod's own tasks: new "); tu(&t, g_body_new); ts(&t, ", retargets "); tu(&t, g_body_turn); ts(&t, ", the game refused "); tu(&t, g_body_refused); ts(&t, ", no memory "); tu(&t, g_body_nomem);
    ts(&t, "\nmap: ground cells asked "); tu(&t, g_map_ground); ts(&t, ", found "); tu(&t, g_map_ground_ok); ts(&t, ", straight legs asked "); tu(&t, g_map_segs); ts(&t, ", questions left for a later look "); tu(&t, g_map_left);
    ts(&t, ", the longest look "); tu(&t, g_map_us_max); ts(&t, " us\nthink, the longest: "); tu(&t, g_sum.think_max); ts(&t, " us   [goal: 4000 or less]\n");
    write_file("hcbrain_summary.txt", buf, t.len, 0, 0, 0, 0);
}
static void session_second(u32 now) {
    struct text *D = &g_dump;
    const hcb_ped *cj = &g_snap.player;
    u32 i, rays = g_rays - s_rays0;
    ts(D, "\n"); stamp(D, now); up_stamp(D);
    ts(D, "CJ "); tvec(D, cj->pos.x, cj->pos.y, cj->pos.z); ts(D, " hp "); tf(D, cj->health); ts(D, "/"); tf(D, cj->armour);
    if (cj->vehicle) { ts(D, " in "); who(D, cj->vehicle); } else ts(D, " on foot");
    ts(D, " w "); tu(D, cj->weapon); ts(D, " stars "); tu(D, g_snap.wanted); ts(D, " mission "); tu(D, g_snap.on_mission); ts(D, " interior "); tu(D, g_snap.interior);
    if (g_snap.cutscene) ts(D, " CUTSCENE");
    if (g_snap.in_water) ts(D, " IN-WATER");
    if (g_snap.controls_off) ts(D, " controls-off");
    ped_flags(D, cj->flags, 0);
    ts(D, "\n  brain: alert "); ts(D, NAME(ALERT_NAME, g_out.alert)); ts(D, " danger "); tf(D, g_out.danger); ts(D, " threats "); tu(D, g_out.n_threats);
    ts(D, " attackers "); tu(D, g_out.n_attackers); ts(D, " top "); who(D, g_out.top); ts(D, " kills "); tu(D, g_out.kills);
    ts(D, " | rule "); tu(D, g_snap.roe); ts(D, " police "); tu(D, g_snap.police); ts(D, " tactics "); tu(D, g_snap.tactics); ts(D, " mission-free "); tu(D, g_snap.mission_free);
    ts(D, "\n  detail: "); ts(D, NAME(DUTY_NAME, g_out.duty)); ts(D, " mode "); ts(D, NAME(MODE_NAME, g_out.mode)); ts(D, " posts "); tu(D, g_out.n_posts);
    ts(D, " commander "); who(D, g_out.lead); if (g_out.leading) ts(D, " LEADS CJ");
    if (g_out.cover_ok) { ts(D, " cover for CJ "); tvec(D, g_out.cover_at.x, g_out.cover_at.y, g_out.cover_at.z); }
    if (g_say) { ts(D, " last words \""); ts(D, NAME(SAY_NAME, g_say)); ts(D, "\" #"); tu(D, g_say_seq); }
    ts(D, " | helicopter "); who(D, g_snap.heli);
    if (g_snap.heli) { const hcb_veh *h = snap_veh(g_snap.heli); if (h) { ts(D, " "); tvec(D, h->pos.x, h->pos.y, h->pos.z); ts(D, " hp "); tf(D, h->health); } }
    if (g_out.heli_ok) { ts(D, " spot "); tvec(D, g_out.heli_at.x, g_out.heli_at.y, g_out.heli_at.z); }
    ts(D, " gunners' pose "); tu(D, g_out.gunner_pose);
    ts(D, "\n  squad: mode "); ts(D, NAME(UMODE_NAME, g_out.umode)); if (g_snap.recall) ts(D, " (TO ME)"); ts(D, " task "); ts(D, NAME(TASK_NAME, g_out.task));
    ts(D, " moving "); tu(D, g_out.n_moving);
    if (g_out.target) { ts(D, " target "); who(D, g_out.target); ts(D, " "); tf(D, g_out.target_dist); ts(D, "m at "); tvec(D, g_out.target_at.x, g_out.target_at.y, g_out.target_at.z); }
    ts(D, " | high places "); tu(D, g_snap.n_high);
    if (g_out.ow_ok) { ts(D, " marksman's roof "); tvec(D, g_out.ow_at.x, g_out.ow_at.y, g_out.ow_at.z); if (g_out.ow_ready) ts(D, " HELICOPTER-READY"); }
    ts(D, " | body "); ts(D, g_snap.body ? "MOD" : "scripts"); ts(D, ": new tasks "); tu(D, g_body_new); ts(D, " retargets "); tu(D, g_body_turn); ts(D, " kept "); tu(D, g_body_kept);
    ts(D, " refused "); tu(D, g_body_refused); ts(D, " no memory "); tu(D, g_body_nomem); ts(D, " falls slowed "); tu(D, g_soft_falls);
    ts(D, "\n  mind: decision maker "); ti(D, g_dm); ts(D, " put back "); tu(D, g_dm_fixed); ts(D, " AI reactions removed "); tu(D, g_ev_cleared); ts(D, " (last type "); tu(D, g_ev_last); ts(D, ") refused "); tu(D, g_ev_refused);
    ts(D, " | weapons "); ts(D, g_gun_ok ? (g_gun_proved ? "MOD (rounds seen)" : "MOD (no round seen yet)") : "scripts"); ts(D, ": gun tasks "); tu(D, g_gun_new); ts(D, " commands "); tu(D, g_gun_cmd); ts(D, " magazines "); tu(D, g_reloads);
    ts(D, " | ropes kept alive "); tu(D, g_ropes_kept);
    ts(D, " | map: ground asked "); tu(D, g_map_ground); ts(D, " found "); tu(D, g_map_ground_ok); ts(D, " legs "); tu(D, g_map_segs); ts(D, " left for later "); tu(D, g_map_left);
    ts(D, " max "); tu(D, g_map_us_max); ts(D, " us a look; cells kept "); tu(D, g_mc_n); ts(D, " (from the file "); tu(D, g_mc_loaded); ts(D, ") answered from memory "); tu(D, g_mc_hits); ts(D, " written "); tu(D, g_mc_saved);
    ts(D, " | ways: asked "); tu(D, g_paths_asked); ts(D, " found "); tu(D, g_paths_found); ts(D, " put off "); tu(D, g_paths_dropped); ts(D, g_path_thread ? " (own thread, longest " : " (in the look, longest "); tu(D, g_path_us_max); ts(D, " us)");
    ts(D, "\n  seen: peds "); tu(D, g_snap.n_peds); ts(D, " (+"); tu(D, g_snap.peds_lost); ts(D, " left out) vehicles "); tu(D, g_snap.n_vehs);
    ts(D, " ours "); tu(D, g_snap.n_ours); ts(D, " game cover points "); tu(D, g_snap.n_hints); ts(D, " (table: live "); tu(D, g_cover_live); ts(D, " read "); tu(D, g_cover_ok); ts(D, ") water asked "); tu(D, g_water_calls); ts(D, " in water "); tu(D, g_water_yes); ts(D, " voice lines "); tu(D, g_said_voice); ts(D, " | shots: ours "); tu(D, s_shots_ours); ts(D, " others "); tu(D, s_shots_other); ts(D, " at us "); tu(D, s_shots_at_us);
    if (s_ev_cut) { ts(D, " | event lines cut "); tu(D, s_ev_cut); }
    ts(D, "\n  time: looks "); tu(D, s_looks); ts(D, " think avg "); tu(D, s_looks ? s_think_us / s_looks : 0); ts(D, " max "); tu(D, s_think_max);
    ts(D, " us, this log "); tu(D, s_log_us); ts(D, " us | frames "); tu(D, s_frames); ts(D, " longest "); tu(D, s_gap_max / 1000); ts(D, " ms | rays "); tu(D, rays); ts(D, " left for later "); tu(D, g_rays_skipped - s_skip0);
    ts(D, " | 0E48: gunner "); tu(D, s_calls[CMD_GUNNER]); ts(D, " squad "); tu(D, s_calls[CMD_SQUAD]); ts(D, " status "); tu(D, s_calls[CMD_STATUS]);
    ts(D, " post "); tu(D, s_calls[CMD_POST]); ts(D, " detail "); tu(D, s_calls[CMD_DETAIL]); ts(D, " pilot "); tu(D, s_calls[CMD_PILOT]); ts(D, " too early "); tu(D, s_calls_early);
    ts(D, " | gunners' own shots "); tu(D, g_own_shots - s_own0); ts(D, " refused "); tu(D, g_own_refused - s_ref0);
    ts(D, " rounds "); tu(D, g_rounds - s_rounds0); ts(D, " refused "); tu(D, g_rounds_refused - s_rref0);
    if (g_log_dropped) { ts(D, " | log text lost "); tu(D, g_log_dropped); }
    ts(D, "\n");
    if (g_pilot_at && now - g_pilot_at < 1500) {
        ts(D, "  pilot: at "); tvec(D, g_pilot.pos.x, g_pilot.pos.y, g_pilot.pos.z); ts(D, " to ("); tf(D, g_pilot_to[0]); ts(D, " "); tf(D, g_pilot_to[1]);
        ts(D, ") roofs "); tf(D, g_pilot_to[2]); ts(D, " left "); tf(D, g_pilot_out.dist); ts(D, "m speed "); tf(D, g_pilot_out.speed);
        ts(D, " climb "); tf(D, g_pilot.vel.z); ts(D, " pitch "); tf(D, g_pilot.pitch * 57.3f); ts(D, " roll "); tf(D, g_pilot.roll * 57.3f);
        if (g_pilot_out.arrived) ts(D, " ARRIVED");
        if (g_pilot_flags & 1) ts(D, " stop-there");
        if (g_pilot_flags & 2) ts(D, " BLOCKED");
        if (g_pilot_flags & 4) ts(D, " ON-STATION-IN-A-FIGHT (the brain's own pilot)");
        if (g_pilot_flags & 8) ts(D, " LANDING-APPROACH");
        ts(D, "\n");
    }
    for (i = 0; i < g_snap.n_dangers && i < HCB_MAX_DANGERS; i++) {
        static const char *const DG[] = {"?", "GRENADE", "FIRE-BOTTLE", "ROCKET", "explosion"};
        const hcb_danger *d = &g_snap.dangers[i];
        ts(D, "  danger: "); ts(D, NAME(DG, d->kind)); ts(D, " at "); tvec(D, d->at.x, d->at.y, d->at.z); ts(D, " keep clear "); tf(D, d->radius); ts(D, "m\n");
    }
    hc_scan(D, now - s_hc_at >= 30000 || !s_hc_at);
    if (now - s_hc_at >= 30000 || !s_hc_at) s_hc_at = now;
    session_ours(D);
    session_summary(now);
    session_contacts(D);
    if (now - s_scripts_at >= 5000 || !s_scripts_at) { scripts_list(D); s_scripts_at = now; }
    s_sec_at = now; s_looks = s_frames = s_ev_lines = s_ev_cut = s_shots_ours = s_shots_other = s_shots_at_us = s_calls_early = 0;
    s_think_us = s_think_max = s_gap_max = s_log_us = 0;
    for (i = 0; i < 8; i++) s_calls[i] = 0;
    s_own0 = g_own_shots; s_ref0 = g_own_refused; s_rounds0 = g_rounds; s_rref0 = g_rounds_refused; s_rays0 = g_rays; s_skip0 = g_rays_skipped;
}
static void session_look(u32 now, u64 cost) {
    int busy = g_snap.heli || g_snap.n_ours || g_out.alert >= HCB_ALERT_WARY;
    u64 t0 = now_us();
    g_dump.len = 0; g_dump.buf[0] = 0;
    s_looks++; s_think_us += cost; if (cost > s_think_max) s_think_max = cost;
    session_events(now);
    if (now < s_sec_at) s_sec_at = now;                                  /* (a new game: the clock starts again) */
    if (now - s_sec_at >= (busy ? 1000U : 10000U)) session_second(now);
    if (g_dump.len) lg(g_dump.buf);
    s_log_us += now_us() - t0;
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
    if (!g_ready || g_busy || !g_ticks) { s_calls_early++; if (cmd != CMD_STATUS && count >= 3) { vars[1] = 0; vars[2] = 0; } return; }
    g_busy = 1; g_where = 10 + (u32)(cmd & 7); s_calls[cmd & 7]++;
    if (cmd == CMD_GUNNER && count >= 9) cmd_gunner(vars);
    else if (cmd == CMD_SQUAD && count >= 3) cmd_squad(vars);
    else if (cmd == CMD_STATUS && count >= 5) cmd_status(vars, count);
    else if (cmd == CMD_POST && count >= 10) cmd_post(vars);
    else if (cmd == CMD_DETAIL && count >= 9) cmd_detail(vars);
    else if (cmd == CMD_PILOT && count >= 6) cmd_pilot(vars);
    else if (cmd == CMD_PLAN && count >= 10) cmd_plan(vars);
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
    log_end();
    flush_log();
}
/* "The game is crawling": twenty frames in a row each longer than a quarter of a second (a pause, a menu or a switch to
   another app does not count: the frames do not run then, and a gap over 5 s is not counted). One report is saved
   by itself the first time, with what the brain cost in those frames. */
static void watch_frames(u64 t, u64 brain_us) {
    u64 gap = g_frame_at_us ? t - g_frame_at_us : 0;
    if (gap > 250000 && gap < 5000000) g_slow_run++; else g_slow_run = 0;
    if (gap < 5000000 && gap > g_gap_max_us) g_gap_max_us = gap;
    if (gap < 5000000 && gap > s_gap_max) s_gap_max = gap;
    s_frames++;
    if (brain_us > g_frame_brain_us_max) g_frame_brain_us_max = brain_us;
    if (g_slow_run == 20) {
        g_crawls++;
        log_begin();
        lg("the game crawled: 20 frames in a row over 0.25 s (the last "); tu(&g_log, gap / 1000); lg(" ms); the brain took ");
        tu(&g_log, brain_us); lg(" us of it, rays this frame "); tu(&g_log, g_frame_ray_us); lg(" us\n");
        log_end(); flush_log();
        if (g_crawls == 1) save_report("the game crawled (20 frames in a row over 0.25 s)");
    }
}
/* 2.0: none of ours comes down faster than a man on a rope. (The second four used to drop from a helicopter that was flying away;
   the scripts now hold it - this is the net under them: a guard on foot who falls faster than 8 m/s is slowed to 6.) */
static void soft_fall(void) {
    u32 k;
    for (k = 0; k < HCB_MAX_OURS; k++) {
        u8 *e = (u8 *)g_our_ent[2 + k];
        float vz;
        if (!e || (RD(u8, e + 0x585) & 1) || is_dead(e)) continue;
        vz = RD(float, e + 0x70);
        if (vz == vz && vz < -0.16f) { RD(float, e + 0x70) = -0.12f; g_soft_falls++; }
    }
}
HIDDEN void brain_scripts(void) {
    u64 t = now_us();
    if (!g_main_tid) g_main_tid = syscall(178);        /* gettid: the game's thread, for the hang recorder */
    g_frame_ray_us = 0;
    if (g_ready && !g_busy) { g_busy = 1; g_where = 1; bridge(); think(); g_where = 0; g_busy = 0; watch_frames(t, now_us() - t); }
    g_frame_at_us = t;
    g_scripts_orig();
    if (g_ready && !g_busy) { g_busy = 1; g_where = 4; pilot_turn(); gunners_fire(); soft_fall(); ropes_keep(); g_where = 0; g_busy = 0; }
    if (g_ready && now_us() - g_flush_us > 3000000UL) flush_log();     /* (only if the writer thread has stopped) */
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
/* 0.4.1: the libraries of the game's process that are not Android's own (the game, its mods), for the log */
static int list_libs(struct dl_phdr_info *info, u64 size, void *data) {
    const char *n = info->dlpi_name, *f, *base;
    (void)size; (void)data;
    if (!n || !n[0] || !ends_with(n, ".so")) return 0;
    if ((n[0] == '/' && n[1] == 's' && n[2] == 'y') || (n[1] == 'a' && n[2] == 'p') || (n[1] == 'v' && n[2] == 'e')) return 0;   /* /system /apex /vendor */
    for (f = base = n; *f; f++) if (*f == '/') base = f + 1;
    lg(" "); lg(base);
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
    tune_apply(hcb_config(BRAIN)); g_cfg_now = hcb_config(BRAIN);
    if (g_tuned || g_tune_bad) { lg("tactical numbers from the settings file: "); tu(&g_log, g_tuned); lg(" changed, "); tu(&g_log, g_tune_bad); lg(" ignored (not a number or outside the limits)\n"); }
    save_config();
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
    log_begin(); lg("libraries in the game:"); dl_iterate_phdr(list_libs, 0); lg("\n"); log_end();
    fire_setup();
    more_setup();
    body_setup();
    mind_setup();
    places_load();
    map_load();
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
    flush_log();
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
    char path[64], st[256]; const char *q; long tid = g_main_tid; u32 i, v; int running = 0, held;
    struct sigact act, old;
    task_path(path, tid, "stat");
    if (read_small(path, st, sizeof st)) { for (q = st; *q && *q != ')'; q++) {} if (*q) running = q[2] == 'R'; }
    held = log_begin();
    lg("\n"); up_stamp(&g_log); lg("HANG: no new frame for "); tu(&g_log, secs); lg(" s and the game is not paused. The game's thread is ");
    lg(running ? "running (a loop that does not end)" : "asleep (waiting for something)"); lg("; inside the brain: ");
    tu(&g_log, g_where); lg(" (0 = outside, 1 = a look, 2 = a ray, 3 = markers, 11-13 = a script's question)\nHelicover:");
    for (i = 0; i < sizeof KEYS / sizeof KEYS[0]; i++) if (shared_get(HC_STATE + KEYS[i], &v)) { lg(" +"); tu(&g_log, KEYS[i]); lg("="); ti(&g_log, (int)v); }
    lg("\n(if you had switched to another app, this is not a hang - ignore it)\n");
    memset(&act, 0, sizeof act); act.flags = 4 | 0x10000000; act.handler = (void *)&brain_on_sample;   /* SA_SIGINFO | SA_RESTART */
    if (running && sigaction(27, &act, &old)) running = 0;
    for (i = 0; i < 6; i++) { one_look(tid, (int)i, running); if (i < 5) usleep(300000); }
    if (running) sigaction(27, &old, 0);
    if (held) log_end();
    flush_log();
    save_report("the game hung (see hcbrain_log.txt for where)");
}
/* ---------- the crash recorder (1.4.1): a crash of the game is written to the log before the game's own handler runs ----------
   Where (pc, lr, the fault address, the frames on the stack with their names), what the brain was doing (g_where) and
   what Helicover was doing; then a report is saved (once) and the previous handler takes over as if we were not there. */
static struct sigact g_crash_old[32];
static u32 g_crash_where;                 /* g_where at the crash, kept for the next start (written into the settings) */
static void crash_settings(u32 where);
HIDDEN void brain_on_crash(int sig, void *info, void *ucv) {
    static const u32 KEYS[] = {0, 1, 7, 20, 21, 27, 29, 440, 451, 452, 454, 455};
    const u8 *uc = (const u8 *)ucv;
    u64 pc = uc ? RD(u64, uc + 440) : 0, lr = uc ? RD(u64, uc + 424) : 0, sp = uc ? RD(u64, uc + 432) : 0, fp = uc ? RD(u64, uc + 416) : 0;
    u64 fault = info ? RD(u64, (const u8 *)info + 16) : 0, a, w, fr[2];
    u32 i, n, v; int held;
    if (__atomic_exchange_n(&g_crashing, 1, __ATOMIC_ACQ_REL)) goto pass;   /* a crash inside the recorder: let the game have it */
    held = log_begin();
    g_crash_where = g_where;
    lg("\n"); up_stamp(&g_log); if (G) stamp(&g_log, RD(u32, G + TIME_MS));
    lg("CRASH: signal "); tu(&g_log, (u64)sig);
    lg(sig == 11 ? " (bad memory access)" : sig == 7 ? " (bus error)" : sig == 4 ? " (illegal instruction)" : sig == 8 ? " (arithmetic)" : sig == 6 ? " (abort)" : "");
    lg("\n  pc "); addr_name(pc); lg("\n  lr "); addr_name(lr); lg("\n  fault address "); tx(&g_log, fault);
    lg("\n  inside the brain: "); tu(&g_log, g_where);
    lg(" (0 outside, 1 a look, 2 a ray, 3 markers, 4 the pilot's turn, 11-16 a script's question, 20 a gunner's shot, 21 the commander's voice, 22 the water level)\n");
    for (n = 0; fp && n < 16 && safe_read(fr, fp, 16); n++) { if (!fr[1]) break; lg("  called from "); addr_name(fr[1]); lg("\n"); if (fr[0] <= fp) break; fp = fr[0]; }
    for (a = sp, n = 0; sp && a < sp + 2048 && n < 10; a += 8) if (safe_read(&w, a, 8) && is_code(w)) { lg("  on the stack "); addr_name(w); lg("\n"); n++; }
    lg("  Helicover:");
    for (i = 0; i < sizeof KEYS / sizeof KEYS[0]; i++) if (shared_get(HC_STATE + KEYS[i], &v)) { lg(" +"); tu(&g_log, KEYS[i]); lg("="); ti(&g_log, (int)v); }
    lg("\n  brain looks "); tu(&g_log, g_ticks); lg("\n  CLEO scripts at the crash:\n");
    g_dump.len = 0; scripts_list(&g_dump); lg(g_dump.buf);
    lg("(the game ends here: its own crash handler takes over)\n");
    /* straight into the file, now (the writer thread may be the one that crashed, or stopped with the game) */
    if (g_log.len) { log_append(g_log.buf, g_log.len); g_log.len = 0; g_log.buf[0] = 0; }
    if (held) log_end();
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
/* 0.4.1: it also writes the log to its file twice a second, and notes when the frames stop (the game went to the
   background, or it is stuck) and start again, and the pause menu. */
static void *watchdog(void *arg) {
    u32 last = 0, still = 0, dumps = 0, fc, paused, was_paused = 0, stopped = 0;
    (void)arg;
    for (;;) {
        usleep(500000);
        flush_log();
        if (!__atomic_load_n(&g_ready, __ATOMIC_ACQUIRE) || !g_main_tid) continue;
        fc = RD(u32, G + FRAME_COUNTER);
        paused = RD(u8, G + USER_PAUSE) || RD(u8, G + CODE_PAUSE);
        if (paused != was_paused) { log_begin(); up_stamp(&g_log); lg(paused ? "the game is paused (menu)\n" : "the game goes on (pause over)\n"); log_end(); was_paused = paused; }
        if (fc != last || paused) {
            if (stopped) { log_begin(); up_stamp(&g_log); lg("frames again (after "); tu(&g_log, stopped / 2); lg(" s without)\n"); log_end(); }
            last = fc; still = 0; stopped = 0; continue;
        }
        stopped++;
        if (stopped == 2) { log_begin(); up_stamp(&g_log); lg("no new frame for 1 s: the game went to the background (or it is stuck)\n"); log_end(); }
        if (++still == 12 && dumps < 2) { dumps++; hang_dump(still / 2); }
    }
    return 0;
}

struct ModInfo { char guid[48]; char name[48]; char version[24]; char author[48]; u16 ver[4]; u8 reserved[336]; };
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.brain", "Helicover Brain", "1.1", "Helicover", {1, 1, 0, 0}, {0}};
static int g_done;
EXPORT struct ModInfo *__GetModInfo(void) { return &g_info; }
EXPORT void OnModPreLoad(void) {}
EXPORT void OnModLoad(void) {
    u64 th; int r;
    if (g_done) return;
    g_done = 1;
    g_page = (u64)getpagesize();
    if (g_page < 4096 || (g_page & (g_page - 1))) g_page = 4096;
    g_start_us = now_us();
    log_begin();
    lg("\n\n========== a new game: Helicover Brain " VERSION " ==========\n");
    lg("started "); wall_date(&g_log);
    lg(" (UTC). This one file holds the whole game: it is written twice a second until the game is closed, crashes or hangs;\n"
       "the games before this one are above (the file is renamed hcbrain_log_old.txt when it grows over 24 MB).\n");
    first_line_of(&g_log, "/proc/meminfo", "MemTotal");
    first_line_of(&g_log, "/proc/meminfo", "MemAvailable");
    first_line_of(&g_log, "/proc/cpuinfo", "Hardware");
    first_line_of(&g_log, "/sys/devices/system/cpu/present", "0");
    log_end();
    load_config();
    lg("settings: markers "); tu(&g_log, (u64)g_marks); lg(", fire off "); tu(&g_log, (u64)g_fire_off); lg(", last crash step "); tu(&g_log, g_last_crash); lg("\n");
    add_menu_items();
    r = try_install();
    if (r != -1 && (r == 0 || !g_cleo)) { if (pthread_create(&th, 0, waiter, (void *)(long)r)) lg("cannot start the waiting thread\n"); else lg("waiting (for the game or for CLEO)\n"); }
    if (r != -1) { if (pthread_create(&th, 0, path_thread, 0)) lg("cannot start the way-finding thread: the ways are found in the look\n"); else { g_path_thread = 1; lg("way-finding thread on\n"); } }
    if (r != -1) { if (pthread_create(&th, 0, watchdog, 0)) lg("cannot start the hang recorder\n"); else lg("hang recorder on\n"); }
    if (r != -1) { crash_recorder_on(); lg("crash recorder on\n"); if (g_last_crash == 20) { g_fire_off = 1; lg("the last game crashed in a gunner's shot: the game's weapon fire stays off from now on\n"); }
        if (g_last_crash == 23) { g_body_off = 1; g_body_ok = 0; lg("the last game crashed while the mod was giving a guard his task: from now on the scripts walk the guards\n"); }
        if (g_last_crash == 24) { g_map_off = 1; g_map_ok = 0; g_body_ok = 0; lg("the last game crashed in a ground question: the map and the mod's walking stay off from now on\n"); }
        if (g_last_crash == 25) { g_mind_off = 1; g_mind_ok = 0; lg("the last game crashed while the mod was keeping the game AI off a guard: that stays off from now on\n"); }
        if (g_last_crash == 26) { g_gun_off = 1; g_gun_ok = 0; lg("the last game crashed in the mod's gun task: the scripts fire the guards' weapons from now on\n"); }
        if (g_last_crash == 27) { g_rope_off = 1; g_rope_ok = 0; lg("the last game crashed while the mod held a rope: the ropes are the game's own from now on\n"); }
        if (g_last_crash) { if (g_last_crash == 99) lg("the last game crashed outside the brain"); else { lg("the last game crashed inside the brain at step "); tu(&g_log, g_last_crash); } lg(" (its CRASH block is above, at the end of that game)\n"); g_last_crash = 0; save_config(); } }
    ti(&g_log, r); lg(" = state at load\n");
    flush_log();
}
