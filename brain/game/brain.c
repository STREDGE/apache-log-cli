/*
 * Helicover Brain - AML mod for GTA San Andreas Android (arm64, the build described by gta_words.h).
 * Stage 1: the OBSERVER. It changes nothing in the game's behaviour. Ten times a second it reads the world around
 * CJ (people, vehicles, shots, damage), lets the core judge who is a threat, records everything in the black box and
 * draws small markers over the people it has an opinion about. The player sends the report file; the fight is then
 * replayed on a desk with brain/tools/replay.py.
 *
 * What is touched in the game, only if every instruction word in gta_words.h matches the game in memory:
 *   three GOT slots of libGTASA (CTheScripts::Process, CHud::Draw, CEventGunShot::CEventGunShot) are pointed at
 *   functions of this mod, which call the original. No code is patched, no executable memory is created.
 * If anything does not match, nothing is changed and the log says what differed.
 * Files (AML mods folder): hcbrain_log.txt, hcbrain_report.bin. Settings: configs/net.helicover.brain.ini.
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
struct timespec { long tv_sec, tv_nsec; };
extern int clock_gettime(int clock, struct timespec *t);
extern void *memcpy(void *d, const void *s, u64 n);
extern void *memset(void *d, int c, u64 n);

#define HIDDEN __attribute__((visibility("hidden")))
#define EXPORT __attribute__((visibility("default")))
#define VERSION "0.1 (stage 1: observer)"
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
#define HC_GROUND (HC_STATE + 71)           /* +0..4 ground team */
/* CLEO (offsets from the start of libSAcleo64.so; the unpacked library is at +0x88000) */
#define CLEO_IMAGE 0x88000UL
#define CLEO_VERSION (CLEO_IMAGE + 0x1bc30UL)
#define CLEO_SHARED (CLEO_IMAGE + 0x7d1f8UL)    /* std::vector<{u32 key, u32 value}>: begin, end, end of capacity */
#define CLEO_MIN_SIZE (CLEO_IMAGE + 0x27e000UL)
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
static int write_file(const char *name, const void *a, u64 an, const void *b, u64 bn, const void *c, u64 cn) {
    char path[640]; u32 n = 0; const char *p; int fd;
    for (p = g_dir; *p && n < sizeof(path) - 64; p++) path[n++] = *p;
    for (p = name; *p && n < sizeof(path) - 1; p++) path[n++] = *p;
    path[n] = 0;
    fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return 0;
    if (an) write(fd, a, an);
    if (bn) write(fd, b, bn);
    if (cn) write(fd, c, cn);
    close(fd);
    return 1;
}
static void set_dir(const char *d) { u32 i = 0; while (d[i] && i < sizeof(g_dir) - 1) { g_dir[i] = d[i]; i++; } g_dir[i] = 0; }
static void flush_log(void) {
    Dl_info di; u32 n = 0, cut = 0; const char *f; char own[512];
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
static int g_marks = 1;
static void load_config(void) {
    char b[256]; long n; int fd = open(CFG, O_RDONLY), i;
    if (fd < 0) return;
    n = read(fd, b, sizeof(b) - 1); close(fd);
    if (n <= 0) return;
    b[n] = 0;
    for (i = 0; b[i]; i++)
        if (b[i] == 'M' && b[i + 1] == 'a' && b[i + 2] == 'r' && b[i + 3] == 'k' && b[i + 4] == 's') {
            for (i += 5; b[i] == ' ' || b[i] == '\t' || b[i] == '='; i++) {}
            if (b[i] == '0' || b[i] == '1') g_marks = b[i] == '1';
            return;
        }
}
static void save_config(void) {
    const char *t = g_marks ? "[Preferences]\nMarks = 1\n" : "[Preferences]\nMarks = 0\n";
    int fd = open(CFG, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, t, slen(t)); close(fd);
}

/* ---------- the brain and its black box ---------- */
#define BRAIN_BYTES (64 * 1024)
#define BOX_BYTES (3 * 1024 * 1024)
static u8 g_brain[BRAIN_BYTES] __attribute__((aligned(16)));
static u8 g_box[BOX_BYTES];
static hcb_rec g_rec;
static hcb_snapshot g_snap;
static hcb_out g_out, g_shown;
static u32 g_ticks, g_last_think, g_dumps, g_peds_max, g_tick_us_max, g_events_lost;
static u64 g_tick_us_sum;
static int g_ready, g_dump_request, g_was_alive, g_busy;
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
    if (RD(u32, veh + 0x568) & 1) o->flags |= HCB_VF_EMERGENCY;
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
        s->ent = ent; s->o[0] = ox; s->o[1] = oy; s->o[2] = oz; s->t[0] = tx; s->t[1] = ty; s->t[2] = tz; s->time = RD(u32, G + TIME_MS);
        g_shot_head++;
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
static int sees(const float *a, const float *b) {
    float p[3], q[3];
    p[0] = a[0]; p[1] = a[1]; p[2] = a[2] + 0.6f; q[0] = b[0]; q[1] = b[1]; q[2] = b[2] + 0.6f;      /* chest to chest */
    return ((los_fn)(G + G_LOS_CLEAR))(p, q, 1, 1, 0, 1, 0, 0, 0) != 0;
}
static float dist2(const float *a, const float *b) { float x = a[0] - b[0], y = a[1] - b[1], z = a[2] - b[2]; return x * x + y * y + z * z; }

static int build_snapshot(hcb_snapshot *s, const hcb_out *prev) {
    struct pool pp, vp;
    const u8 *cj = player_ped(), *wanted, *e;
    const float *cjp;
    u32 cj_h, i, n, k, v, flag, los_left = 6;                    /* rays per look are rationed: 6 here + 12 answers below */
    float best[HCB_MAX_PEDS], d;
    u32 idx[HCB_MAX_PEDS];

    if (!cj || !get_pool(PED_POOL, &pp) || !get_pool(VEH_POOL, &vp)) return 0;
    cj_h = handle_of(&pp, cj, PED_STRIDE);
    if (!cj_h) return 0;
    memset(s, 0, sizeof *s);
    s->time = RD(u32, G + TIME_MS); s->frame = g_ticks;
    fill_ped(&s->player, cj, cj_h, &pp, &vp, cj);
    cjp = pos_of(cj);
    wanted = RD(const u8 *, G + PLAYERS + (u64)RD(u8, G + PLAYER_FOCUS) * PLAYER_INFO + 8);
    s->wanted = wanted ? (u8)RD(u32, wanted + 0x2c) : 0;
    flag = RD(u32, G + MISSION_FLAG);
    s->on_mission = flag && flag < SCRIPT_SPACE_SIZE - 4 && RD(u32, G + SCRIPT_SPACE + flag) == 1;
    s->cutscene = RD(u8, G + CUTSCENE) != 0;
    s->roe = HCB_ROE_DEFEND;
    if (shared_get(HC_FIRE, &v) && v <= 4) s->roe = (u8)v;

    /* ours: what the scripts have published (a handle that no longer names a live ped is dropped) */
    if (shared_get(HC_PUB + 1, &v) && obj_of(&vp, v, VEH_STRIDE)) s->heli = VID(v);
    for (k = 0; k < 10 && s->n_ours < HCB_MAX_OURS; k++) {
        u32 key = k < 5 ? HC_PUB + 2 + k : HC_GROUND + (k - 5);
        if (!shared_get(key, &v) || !obj_of(&pp, v, PED_STRIDE) || v == cj_h) continue;
        s->ours[s->n_ours] = v;
        s->our_role[s->n_ours] = (u8)(k == 0 ? HCB_ROLE_PILOT : k < 5 ? HCB_ROLE_GUNNER + (k - 1) : HCB_ROLE_SQUAD + (k - 5 < 4 ? k - 5 : 3));
        s->n_ours++;
    }

    /* the nearest people within 150 m (ours always) */
    n = 0;
    for (i = 0; i < pp.size; i++) {
        const u8 *ped;
        int ours = 0;
        if (pp.flags[i] & 0x80) continue;
        ped = pp.objs + (u64)i * PED_STRIDE;
        if (ped == cj) continue;
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
        if (los_left && !(o->flags & HCB_PF_DEAD) && hcb_weapon_class(o->weapon) >= HCB_WC_PISTOL && best[k] > 0 && best[k] < 70.0f * 70.0f) {
            o->flags2 |= HCB_PF2_LOS_KNOWN | (sees(pos_of(ped), cjp) ? HCB_PF2_LOS_CLEAR : 0);
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

    /* the lines of sight the core asked for on the previous look */
    for (i = 0; i < prev->n_queries && s->n_los < 12; i++) {           /* (the core asks again for what was not answered) */
        const u8 *a = obj_of(&pp, prev->queries[i].from, PED_STRIDE), *b = obj_of(&pp, prev->queries[i].to, PED_STRIDE);
        hcb_los *l = &s->los[s->n_los++];
        l->from = prev->queries[i].from; l->to = prev->queries[i].to;
        l->clear = (u8)(a && b && sees(pos_of(a), pos_of(b)));
    }
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
    g_note.len = 0;
    ts(&g_note, "Helicover Brain " VERSION "\nsaved: "); ts(&g_note, why);
    ts(&g_note, "\nticks "); tu(&g_note, g_ticks); ts(&g_note, ", think time avg "); tu(&g_note, g_ticks ? g_tick_us_sum / g_ticks : 0);
    ts(&g_note, " us, max "); tu(&g_note, g_tick_us_max); ts(&g_note, " us\nmost peds in a look "); tu(&g_note, g_peds_max);
    ts(&g_note, ", events lost "); tu(&g_note, g_events_lost); ts(&g_note, "\nscripts bridge: "); ts(&g_note, g_cleo ? "CLEO shared values" : "none (CLEO not recognised)");
    ts(&g_note, "\nscreen "); ti(&g_note, RD(int, G + RSGLOBAL + 8)); ts(&g_note, "x"); ti(&g_note, RD(int, G + RSGLOBAL + 12)); ts(&g_note, "\n");
    first_line_of(&g_note, "/proc/meminfo", "MemTotal");
    first_line_of(&g_note, "/proc/meminfo", "MemAvailable");
    first_line_of(&g_note, "/proc/cpuinfo", "Hardware");
    first_line_of(&g_note, "/sys/devices/system/cpu/present", "0");
    hcb_box_head_fill(&head, &g_rec, BRAIN, g_note.len);
    if (write_file("hcbrain_report.bin", &head, sizeof head, g_box + g_rec.start, g_rec.end - g_rec.start, g_note.buf, g_note.len)) g_dumps++;
}

/* ---------- the two per-frame entries ---------- */
typedef void (*void_fn)(void);
static void_fn g_scripts_orig, g_hud_orig;
static void think(void) {
    u32 now = RD(u32, G + TIME_MS);
    u64 t0;
    if (now - g_last_think < 100 && now >= g_last_think) return;        /* ten looks a second of game time */
    t0 = now_us();
    if (!build_snapshot(&g_snap, &g_out)) return;
    g_last_think = now;
    if (g_ticks % 50 == 0) hcb_rec_push_state(&g_rec, g_box, BRAIN);
    hcb_think(BRAIN, &g_snap, &g_out);
    hcb_rec_push(&g_rec, g_box, &g_snap, g_out.digest);
    memcpy(&g_shown, &g_out, sizeof g_shown);
    g_ticks++;
    t0 = now_us() - t0;
    g_tick_us_sum += t0;
    if (t0 > g_tick_us_max) g_tick_us_max = (u32)t0;
    /* a report on request, and by itself when CJ dies: those are the moments worth looking at */
    if (g_snap.player.health <= 0 && g_was_alive) save_report("CJ died");
    g_was_alive = g_snap.player.health > 0;
    if (__atomic_exchange_n(&g_dump_request, 0, __ATOMIC_ACQ_REL)) save_report("asked for in Mods Settings");
}
HIDDEN void brain_scripts(void) {
    if (g_ready && !g_busy) { g_busy = 1; think(); g_busy = 0; }
    g_scripts_orig();
}

typedef void (*poly_fn)(float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4, const u8 *rgba);
typedef int (*screen_fn)(const float *in, float *out, float *w, float *h, int far_clip, int near_clip);
static void square(float x, float y, float r, const u8 *c) { ((poly_fn)(G + G_DRAW_POLY))(x - r, y - r, x + r, y - r, x - r, y + r, x + r, y + r, c); }
static void draw(void) {
    static const u8 COL[5][4] = {{60, 200, 90, 220}, {150, 150, 150, 0}, {250, 220, 40, 230}, {255, 140, 0, 240}, {240, 40, 40, 255}};
    static const u8 ALLY[4] = {70, 150, 255, 220}, EDGE[4] = {0, 0, 0, 200}, BAR[5][4] = {{90, 90, 90, 150}, {250, 220, 40, 220}, {255, 140, 0, 230}, {240, 40, 40, 240}, {255, 255, 255, 255}};
    struct pool pp, vp;
    float W = (float)RD(int, G + RSGLOBAL + 8), H = (float)RD(int, G + RSGLOBAL + 12), in[3], out[3], w, h, r;
    u32 i;
    if (!g_marks || !g_ticks || RD(u8, G + USER_PAUSE) || W < 100 || H < 100) return;
    /* a small strip at the top of the screen: the alert level (and proof that the brain is running) */
    {
        const u8 *c = BAR[g_shown.alert <= 4 ? g_shown.alert : 4];
        float x1 = W * 0.47f, x2 = W * 0.53f, y2 = H * 0.008f + 3;
        ((poly_fn)(G + G_DRAW_POLY))(x1, 0, x2, 0, x1, y2, x2, y2, c);
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
        square(out[0], out[1], r + H * 0.0016f, EDGE);
        square(out[0], out[1], r, c);
    }
}
HIDDEN void brain_hud(void) {
    g_hud_orig();
    if (g_ready && !g_busy) { g_busy = 1; draw(); g_busy = 0; }
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
    if (!sa) { lg("SAUtils not found - no settings items (markers are on; a report is still saved when CJ dies)\n"); return; }
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
    lg(g_cleo ? "CLEO recognised: Helicover's people are read from its shared values\n" : "CLEO not recognised (or not started yet): the brain cannot tell who is ours\n");
    if (hcb_brain_size() > BRAIN_BYTES) { lg("internal: brain larger than its buffer\n"); return -1; }
    hcb_init(BRAIN, 1);
    hcb_rec_init(&g_rec, BOX_BYTES);
    /* the per-frame slot is what the brain cannot do without; without the other two it still watches and records */
    if (!got_swap(GOT_SCRIPTS, GOT_SCRIPTS_TARGET, (u64)&brain_scripts, &c)) { lg("could not change the scripts slot - nothing changed\n"); return -1; }
    g_scripts_orig = (void_fn)c; g_slots = 1;
    if (got_swap(GOT_GUNSHOT, GOT_GUNSHOT_TARGET, (u64)&brain_gunshot, &a)) { g_gunshot_orig = (gunshot_fn)a; g_slots++; }
    else { lg("the gunshot slot is taken or could not be changed: shots will not be seen (damage still is)\n"); }
    if (got_swap(GOT_HUD, GOT_HUD_TARGET, (u64)&brain_hud, &b)) { g_hud_orig = (void_fn)b; g_slots++; }
    else { lg("the HUD slot is taken or could not be changed: no markers on screen (the report still works)\n"); }
    __atomic_store_n(&g_ready, 1, __ATOMIC_RELEASE);
    lg("libGTASA.so base "); tx(&g_log, G); lg("\n66 instruction words match; GOT slots pointing at the brain: "); tu(&g_log, (u64)g_slots); lg(" of 3 (no code changed)\nthe brain is watching\n");
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
            if (!CLEO_VERSION_TEXT[k]) { __atomic_store_n(&g_cleo, g_cleo_base, __ATOMIC_RELEASE); lg("CLEO recognised later\n"); }
        }
    }
    flush_log();
    return 0;
}

struct ModInfo { char guid[48]; char name[48]; char version[24]; char author[48]; u16 ver[4]; u8 reserved[336]; };
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.brain", "Helicover Brain", "0.1", "Helicover", {0, 1, 0, 0}, {0}};
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
    ti(&g_log, r); lg(" = state at load\n");
    flush_log();
}
