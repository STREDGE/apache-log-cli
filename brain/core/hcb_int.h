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
    u8 ram_n, r0_, r1_, r2_;  /* 1.3: looks in a row on a collision course (two before it is "ramming") */
    u32 ram_said;           /* 1.3: when the commander last called this car */
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
#define HCB_MAX_COVERS 320
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
    u32 car_said;           /* 0.9: when "car - <dir>" was last said */
    hcb_vec cover_said_at;  /* 0.9: where CJ stood when "into cover" was last said (said again only if he has moved, or after 15 s) */
    u32 cj_shot_t;          /* when CJ last fired, and which way (unit, flat): nobody of ours stands in his line of fire */
    hcb_vec cj_shot_dir;
    hcb_vec threat_mem;     /* 1.4.1: where the last threat was, and when (the detail does not stand down between shots) */
    u32 threat_mem_t;
    hcb_vec lead_to;        /* where the commander leads CJ, since when, and the nearest CJ has come to it */
    u32 lead_since, lead_gave_up;
    float lead_best;
    u32 lead_prog_t;        /* 1.3: when CJ last came nearer to that cover (10 s without: the commander comes back to him) */
    u32 hold_said;          /* 1.3: when "fire is held" was last said */
    u32 gun_blind_since;    /* 1.3: since when every door gunner with a man to fire at has had no line to him */
    u8 lead_near, lead_wave, lead_r_[2];   /* 1.3: the commander is within 6 m of CJ / he stands and waves CJ on */
    hcb_vec heli_at;        /* the helicopter's spot for the gunners, the candidate being asked about */
    u32 heli_t;
    u8 heli_ok, heli_k, mode, leading, pose, pad_[3];
    u32 mode_since;
    struct { hcb_vec post; float best; u32 since; u8 alt, stuck, hold_ok, pad; hcb_vec hold; u32 hold_id, hold_bad; float hold_score; u32 hold_at; u8 hold_fight, hold_cv, n_bad, bad_i; hcb_vec bad[3]; u32 bad_t[3]; u32 hold_dl; u32 blind_since; } man[8];   /* each man's progress to his post; 0.6: an outer man's own post in a fight; 1.5: in peace too (hold_fight: which it was chosen for) */
    /* 1.5 (beta 6): the outer men's quarters round CJ - who has which (by id), and the axis they were dealt out on */
    u32 q_id[5];
    hcb_vec q_axis;
    u8 q_fight, q_r_[3];
    /* 1.6: where cars drive (seen driven at speed): no place of an outer man on the roadway */
    hcb_vec road[24], road_d[24];
    u8 road_n, road_i, lead_st, lead_calls;   /* lead_st: LEAD_* (the commander's hops to the cover); calls made to a CJ who did not come */
    hcb_vec lead_pt;        /* 1.6: the point of this hop */
    u32 lead_t;             /* 1.6: since when he has waited there / been on his way back */
    u32 low_said;           /* 1.6: when "CJ is hurt" was last said */
    u32 still_since;        /* 1.5: since when CJ has stood (0 = he walks): in peace the outer men walk beside him, and take places once he stands */
    u32 moved_at;           /* 1.5: when CJ last walked (over 1 m/s) */
    u16 say_seq;
    u8 cj_cover_ok, duty, last_say, say_dir;
    /* 0.4.2 (from the first whole-game log): the detail keeps its threat, its cover and its tongue */
    u32 threat_since;       /* when the threat the detail fights was taken */
    u32 cover_bad_since;    /* since when CJ's spot has been known exposed or too far with no better one (0 = it is good) */
    u32 said_at;            /* when the commander last said anything */
    u32 in_since;           /* since when CJ has been in his cover (0 = he is not) */
    u32 nocover_since;      /* since when there has been no cover for CJ in this fight (0 = there is one) */
    u32 heli_bad;           /* 0.5: since when the helicopter's spot has been known blind to the threat (0 = it sees) */
    /* 0.7 */
    u32 sniper_said, place_said;
    hcb_vec place[16];      /* where the detail was attacked before (kept between games by the adapter) */
    u16 place_n[16];
    u8 places, places_dirty, door_ok, n_hint;
    /* 0.8 */
    hcb_vec door;           /* where CJ last stood out of doors (inside a building the detail holds there) */
    hcb_vec hint[12];
    u32 grenade_said, water_said, ahead_said;
} detail;
/* ------------------------------------------------------------------ 1.0: the brain's own map, the men's actions, the squad */
#define NAV_N 48                 /* cells a side, one metre each: the ground round the focus (CJ, or the assault target) */
#define NAV_SEGS 48
typedef struct navcell {
    float z;                /* height of the ground */
    u32 asked;              /* when the question went out (state 3) */
    u32 blk_until;          /* the blocked ways out of this cell are forgotten then */
    u8 st;                  /* 0 not known, 1 ground, 2 nothing to stand on, 3 asked */
    u8 blk;                 /* bit d = the way out in direction d (0..7) is blocked (a man tried and did not get through) */
    u8 fix;                 /* what the level rays found: bit 0 = a wall to the next cell at +x, bit 1 = at +y */
    u8 r1;
} navcell;
typedef struct segent {
    hcb_vec a, b;
    u32 asked, answered;
    u8 used, clear, r0, r1;
} segent;
typedef struct nav {
    int ox, oy;             /* world x, y of the corner of cell (0, 0), whole metres */
    float fz;               /* the focus's ground height (the first question starts from it) */
    u32 known;              /* cells with an answer */
    u8 ok, r0, r1, r2;
    navcell c[NAV_N * NAV_N];
    segent sg[NAV_SEGS];
} nav;
/* 1.1: ways asked for and their answers (kept 2.5 s) */
#define NAV_PATHS 12
#define AG_PATH 10
typedef struct pathent {
    hcb_vec from, to;
    u32 key, asked, answered;
    int n;
    u8 used, r0, r1, r2;
    hcb_vec wp[AG_PATH];
} pathent;
typedef struct agent {
    u32 id;
    hcb_vec goal;           /* the place he is going to (the post as he took it) */
    hcb_vec via;            /* the point he walks to now */
    hcb_vec path[AG_PATH];
    hcb_vec last_pos, prog_pos;
    u32 goal_since, prog_since, plan_t, side_until, arrived_since, last_seen, failed_at;
    float prog_best;
    u8 used, phase, act, why, fails, n_path, i_path, moves;   /* moves: changes of action (for the log) */
    hcb_vec corner_at;      /* 1.1: the corner he has looked round last (he does not stop at it twice) */
    u32 corner_until;       /* ... he stands short of a corner until then */
    u32 door_since;         /* ... since when he has waited for a doorway to clear */
    u8 off_map, r_[3];      /* 1.1: the map does not reach where he stands (he is far from CJ / the target) */
    u32 pace_since;         /* 1.3: when his pace last changed (no change within 1.5 s - unless his place is now 3 m nearer or further) */
    float pace_d;           /* 1.3: ... and how far from his place he was then */
    u32 line_since;         /* 1.3: since when CJ or one of ours is in his line of fire while he stands */
    u32 step_until, step_at;    /* 1.3: a step out of the line: kept until then; when the last one began */
    hcb_vec step;           /* 1.3: ... the offset of that step */
    u8 aimwalk, pace_prev, aw_r_[2];   /* pace_prev (1.6): the pace he had before his last change of pace */   /* 1.6: he is on a short move with his weapon on the man (kept from 7 m until 10) */
    hcb_vec step_from;      /* 1.5: ... from where he stood when it began (not his place: a man a metre off it stepped a metre short) */
    float flank;            /* 1.3 (beta 5): one of the three at CJ's side steps to CJ's flank instead: +1 / -1 which side, 0 none */
} agent;
typedef struct squad {
    u8 umode, task, ow_ok, ow_ready, mover, gathered, pad0, pad1;
    u32 task_since, target, target_seen, bound_since, ow_since, ow_done_for, clear_since, lost_since;
    hcb_vec target_at, gather_at, ow_at, front;
    float target_dist;
    hcb_vec apost[8];       /* each man's place in the assault (kept between looks) */
    u32 apost_id[8], apost_t[8];
    u8 apost_ok[8];
    u32 regroup_until;      /* 1.3: CJ is hurt / far from the squad: everybody back to him until then */
    /* 1.3, the marksman's own plan (hcb_marksman_plan): what he is going for and how he gets up */
    u8 mk_state, mk_tries, mk_n_bad, mk_up;   /* MK_*; climbs tried at this place; bad places known; 1 = he is up (a roof, a step, high ground) */
    u32 mk_id, mk_since, mk_climb_t, mk_far_since, mk_prog_t, mk_pick_t;
    hcb_vec mk_at, mk_step, mk_prog_pos;      /* where he is going, the step on his way up (a car), where he last got on */
    float mk_best_d;                          /* 1.3: the nearest he has been to the wall he goes to (sliding along it is no progress) */
    u32 mk_down_until;                        /* 1.3: "to me" - no high place for him until then (he comes down with the others) */
    u32 mk_heli_done;                         /* 1.3 (beta 5): the helicopter's try to pick him up ended (a minute before the next) */
    hcb_vec mk_foot;                          /* 1.5: the foot of the wall below his roof, on his side (the map's ground) */
    u8 mk_foot_ok, mk_r_[3];
    u32 mk_ready_t;         /* 1.5: when the helicopter last hung over him for the pickup (ow_ready) */
    u32 mk_aboard_t;        /* 1.5: when he went up its rope (he vanished from the ground right after): he waits aboard for his roof */
    float mk_z0;            /* his feet when the climb began */
    hcb_vec mk_bad[8];      /* places he could not get up to (left alone for a minute; 1.5: eight, and a high cell with no way to it
                               takes its whole roof with it - mk_bad_r) */
    u32 mk_bad_t[8];
    float mk_bad_r[8];
} squad;
struct hcb_brain {
    hcb_cfg cfg;
    u32 time, ticks, rng, seed, alert_since, calm_since, kills;
    u8 alert, started, cj_in_heli, reserved1;   /* cj_in_heli: CJ sits in our helicopter (this tick) */
    u32 reload_who, reload_until, reload_last;   /* 1.1: who changes his magazine now (one man at a time), until when, when the last turn began */
    track tr[HCB_MAX_TRACKS];
    vtrack vt[HCB_MAX_VTRACKS];
    shooter sh[HCB_MAX_OURS];
    losent los[HCB_LOS_CACHE];
    cover cv[HCB_MAX_COVERS];
    detail dt;
    nav nv;
    pathent pa[NAV_PATHS];
    agent ag[8];
    squad sq;
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
/* hcb_nav.c */
HID void hcb_nav_update(hcb_brain *b, const hcb_snapshot *s, hcb_out *out, hcb_vec focus);
HID int hcb_nav_path(hcb_brain *b, hcb_vec from, hcb_vec to, hcb_vec *wp, int max, u32 now);   /* > 0 way points; 0 no way; -1 the map does not know */
HID int hcb_nav_line(hcb_brain *b, hcb_vec a, hcb_vec c, u32 now);
HID hcb_vec hcb_nav_centre(const hcb_brain *b, hcb_vec at);
HID int hcb_nav_seg(hcb_brain *b, hcb_out *out, hcb_vec a, hcb_vec c, u32 now);              /* 1 free, 0 blocked, -1 asked */
HID void hcb_nav_block(hcb_brain *b, hcb_vec at, hcb_vec toward, u32 now, u32 ttl);
HID int hcb_nav_by_wall(const hcb_brain *b, hcb_vec at);   /* 1.6: 1 = a wall, a step or a drop right next to this cell */
HID int hcb_nav_walls(const hcb_brain *b, hcb_vec c, float r, hcb_vec threat, hcb_vec *pts, int max);   /* cells behind a wall, seen from the threat */
/* hcb_places.c (1.1): a firing place chosen by weights */
typedef struct place_in {
    hcb_vec anchor;         /* where the man is wanted (his corner of the ring, his place in the fire team) */
    hcb_vec man;            /* where he is */
    hcb_vec cj;             /* CJ */
    hcb_vec threat;         /* the main threat */
    hcb_vec other[2];       /* other threats */
    hcb_vec taken[8];       /* places the others of ours hold */
    hcb_vec cj_dir;         /* the way CJ fires / faces (unit, flat) */
    float reach;            /* how far from the anchor a place may be */
    float cj_min, cj_max;   /* how near to CJ and how far from him it may be (0, 0 = does not matter) */
    float threat_min;       /* never nearer to the main threat than this (6 m at the least) */
    u8 n_other, n_taken, need_cj, cj_fires;   /* need_cj: CJ must be seen from it; cj_fires: nobody in CJ's line of fire */
    /* 1.6 (the log of 1.5: four places in five were in the open, with cover known in the man's own quarter three times in four) */
    hcb_vec q_dir;          /* wide: the middle of his quarter round CJ (unit, flat); a place lies within q_cos of it */
    float q_cos;
    hcb_vec veh[8];         /* wide: vehicles standing still near CJ - a spot behind each is a candidate */
    hcb_vec bad[3];         /* places he could not get to lately: nothing within 3 m of one */
    u8 wide, n_veh, n_bad, low_cj;   /* wide: candidates from the whole quarter, cover first; low_cj: `threat` is CJ's own eyes (peace) */
    u8 strict, keep, stand_in, pad;   /* stand_in (1.5): `threat` is no man but a point beyond the man's quarter (peace): no line-of-fight rules */   /* strict: 1 = only places everything is KNOWN about (the man holds a place already: no moving on a guess);
                               keep: 1.3 - the place he holds is valued (the line rules choose new places only: a shooter shifting about does not move him) */
} place_in;
HID float hcb_place_score(hcb_brain *b, hcb_out *out, const place_in *in, hcb_vec at, u32 now, int ask, int *cover);   /* < 0: not a place */
HID int hcb_place_pick(hcb_brain *b, hcb_out *out, const place_in *in, u32 now, hcb_vec *found, float *score, int *cover);
/* hcb_detail.c: the cover questions (shared with hcb_places.c) */
HID int hcb_cv_state(hcb_brain *b, hcb_vec at, hcb_vec from, u32 now, int low);     /* 1 cover, 0 none, -1 not known, -2 asked */
HID int hcb_cv_raw(hcb_brain *b, hcb_vec at, hcb_vec from, u32 now, int *hidden, int *hidden_hi, int *ground);   /* 1 known */
HID void hcb_cv_ask(hcb_brain *b, hcb_out *out, hcb_vec at, hcb_vec from, u32 now);
HID void hcb_path_forget(hcb_brain *b, u32 key);
HID void hcb_marksman_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out);   /* 1.3: the marksman: a roof, a step, high ground or a long look */
HID int hcb_path_ask(hcb_brain *b, hcb_out *out, u32 key, hcb_vec from, hcb_vec to, hcb_vec *wp, int max, u32 now);   /* 1.1: -2 asked (the answer comes with a later look); else as hcb_nav_path */
HID int hcb_nav_inside(const hcb_brain *b, hcb_vec at);                                    /* 1 = within the square the map covers now */
HID int hcb_nav_narrow(const hcb_brain *b, hcb_vec at);                                     /* 1 = a doorway: walls on both sides of the cell */
HID int hcb_nav_ground(const hcb_brain *b, hcb_vec at, float *z);                           /* 1 ground known there */
/* hcb_agent.c */
HID void hcb_agent_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out);
HID int hcb_agent_why(const hcb_brain *b, u32 id);   /* 1.5: why he did what he did at his last look (HCB_WHY2_*) */
/* hcb_squad.c */
HID void hcb_squad_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out);
HID int hcb_squad_roping(const hcb_snapshot *s, u32 id);
#endif
