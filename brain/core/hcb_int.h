/* Helicover Brain - core internals shared by the core's own source files. Not part of the interface. */
#ifndef HCB_INT_H
#define HCB_INT_H
#include "hcb.h"

#define API __attribute__((visibility("default")))
#define HID __attribute__((visibility("hidden")))
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;

/* ------------------------------------------------------------------ small maths */
static inline float f_abs(float a) { return a < 0 ? -a : a; }
static inline float f_min(float a, float b) { return a < b ? a : b; }
static inline float f_max(float a, float b) { return a > b ? a : b; }
static inline float f_clamp(float a, float lo, float hi) { return a < lo ? lo : a > hi ? hi : a; }
static inline float f_sqrt(float x) {
    union { float f; u32 i; } u;
    float y;
    if (x <= 0) return 0;
    u.f = x;
    u.i = 0x1fbd1df5u + (u.i >> 1);          /* first guess, then four Newton steps */
    y = u.f;
    y = 0.5f * (y + x / y); y = 0.5f * (y + x / y); y = 0.5f * (y + x / y); y = 0.5f * (y + x / y);
    return y;
}
static inline hcb_vec v_sub(hcb_vec a, hcb_vec b) { hcb_vec r; r.x = a.x - b.x; r.y = a.y - b.y; r.z = a.z - b.z; return r; }
static inline hcb_vec v_add(hcb_vec a, hcb_vec b) { hcb_vec r; r.x = a.x + b.x; r.y = a.y + b.y; r.z = a.z + b.z; return r; }
static inline hcb_vec v_mul(hcb_vec a, float k) { hcb_vec r; r.x = a.x * k; r.y = a.y * k; r.z = a.z * k; return r; }
static inline float v_dot(hcb_vec a, hcb_vec b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static inline float v_len(hcb_vec a) { return f_sqrt(v_dot(a, a)); }
static inline float v_dist(hcb_vec a, hcb_vec b) { return v_len(v_sub(a, b)); }
/* Distance from p to the segment a-b; *t = where along it (0..1) the nearest point lies. */
static inline float seg_dist(hcb_vec p, hcb_vec a, hcb_vec b, float *t) {
    hcb_vec ab = v_sub(b, a), ap = v_sub(p, a);
    float l2 = v_dot(ab, ab), k = l2 > 1e-6f ? f_clamp(v_dot(ap, ab) / l2, 0, 1) : 0;
    if (t) *t = k;
    return v_dist(p, v_add(a, v_mul(ab, k)));
}
static inline void zero(void *p, u32 n) { u8 *q = p; while (n--) *q++ = 0; }
static inline void copy(void *d, const void *s, u32 n) { u8 *a = d; const u8 *b = s; while (n--) *a++ = *b++; }

/* ------------------------------------------------------------------ the brain */
typedef struct track {
    hcb_ped last;
    u32 first_seen, last_seen, last_hostile, last_shot, cj_hit_him, cj_marked;
    u32 hold_until;         /* a THREAT verdict that rests on a pose is kept until then */
    float damage_cj, damage_ours, aim_ms, edps, dist;
    u16 shots_at_cj, shots_at_ours, shots_total;
    u8 used, seen, cls, why, best_weapon, friendly, aims_at_ours, aim_latch;
    u8 hold_why, reserved0, reserved1, reserved2;
} track;
typedef struct vtrack {
    hcb_veh last;
    u32 last_seen;
    u32 ram_until;          /* on a collision course lately: the verdict is kept until then */
    u32 hit_time;           /* when it last ran into CJ or one of ours */
    u32 air_fire;           /* a helicopter: when rounds from nowhere last hit CJ or ours with it overhead */
    u32 cj_marked;          /* when CJ last fired at it */
    u32 driver_was;         /* the last driver it had (policemen jump out of a car that is still rolling) */
    float edps, dist, ram_edps;
    u8 used, seen, cls, why;
} vtrack;
/* one of our shooters between ticks: whom he is on, since when, where he is in his burst */
typedef struct shooter {
    u32 id, target, since, fire_from, burst_until, pause_until;
    u32 last_fire;          /* the last tick he was ordered to fire */
    u32 aim;                /* the man his weapon is on (his target, or the suspect he covers); 0 = nobody */
    u32 next_round, noted, rrng;    /* a gunner between looks: when his next round is due, the last refusal noted, his own dice */
    u8 used, hold, role, ready;
} shooter;
/* what is known about lines of sight (answers of the adapter), and what has been asked */
#define HCB_LOS_CACHE 160
typedef struct losent {
    u32 from, to, time;
    u8 used, clear, reserved0, reserved1;
} losent;
/* the protective detail: what the cover questions have shown, and the detail's own memory */
#define HCB_MAX_COVERS 192
typedef struct cover {
    hcb_vec at, from;       /* a spot, and the threat it was tested against */
    u32 asked, answered;    /* when the question went out, when the answer came (0 = not yet) */
    u8 used, hidden, ground, reserved0;
} cover;
typedef struct detail {
    hcb_vec anchor;         /* the formation's "ahead": the way CJ travels (unit, flat) */
    hcb_vec anchor_try;     /* a new way he has started to go, and since when */
    u32 anchor_since;
    hcb_vec cj_cover;       /* where CJ should be: a spot hidden from the threat */
    hcb_vec threat;         /* the threat the detail fights now */
    u32 threat_id, contact_since, cover_said, evac_said, safe_said, lead, mover, clear_said;
    u16 say_seq;
    u8 cj_cover_ok, duty, last_say, say_dir;
} detail;
struct hcb_brain {
    hcb_cfg cfg;
    u32 time, ticks, rng, seed, alert_since, calm_since, kills;
    u8 alert, started, cj_in_heli, reserved1;   /* cj_in_heli: CJ sits in our helicopter (this tick) */
    track tr[HCB_MAX_TRACKS];
    vtrack vt[HCB_MAX_VTRACKS];
    shooter sh[HCB_MAX_OURS];
    losent los[HCB_LOS_CACHE];
    cover cv[HCB_MAX_COVERS];
    detail dt;
};


/* hcb_core.c */
HID track *hcb_find(hcb_brain *b, u32 id);
HID int hcb_is_ours(const hcb_snapshot *s, u32 id);
HID const hcb_ped *hcb_ped_of(const hcb_snapshot *s, u32 id);
HID u32 hcb_fnv(u32 h, u32 v);
HID u32 hcb_bits(float f);
HID u32 hcb_rand(hcb_brain *b);
HID int hcb_is_firearm(int w);
HID vtrack *hcb_vfind(hcb_brain *b, u32 id);
/* hcb_fire.c */
HID void hcb_fire_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out);
/* hcb_detail.c */
HID void hcb_detail_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out);
#endif
