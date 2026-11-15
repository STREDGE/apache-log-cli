/* Helicover Brain - core interface.
 *
 * The core is plain C with no libc and no game code: the game adapter fills an hcb_snapshot ten times a second,
 * the core thinks (hcb_think) and answers with an hcb_out. Because the core sees nothing but snapshots, a recorded
 * sequence of snapshots (the "black box") replays on a desk exactly as it ran in the game.
 *
 * This header is also read by brain/tests/hcb_py.py, which builds the ctypes mirror of every struct from it.
 * Keep to the plain layout it understands: fixed-width integers, float, nested structs, one-dimensional arrays
 * with a #define'd size, one field per line, no bit-fields, no implicit padding (every struct is a multiple of 4).
 */
#ifndef HCB_H
#define HCB_H
#include <stdint.h>

#define HCB_VERSION 1          /* layout of the structs below; a black box says which version wrote it */

#define HCB_MAX_PEDS 64        /* peds in one snapshot (nearest to CJ first) */
#define HCB_MAX_VEHS 40
#define HCB_MAX_EVENTS 48      /* events gathered between two snapshots */
#define HCB_MAX_OURS 16        /* pilot, gunners, squad */
#define HCB_MAX_MARKS 48       /* contacts reported back for the debug markers */
#define HCB_MAX_TRACKS 96      /* people the brain remembers at one time */
#define HCB_MAX_VTRACKS 48

/* ---- ped flags (hcb_ped.flags) */
#define HCB_PF_DEAD 1
#define HCB_PF_SHOOTING 2      /* fired at least once since the previous snapshot */
#define HCB_PF_AIMING 4        /* weapon raised / in a gun or fight task */
#define HCB_PF_DUCKING 8
#define HCB_PF_MISSION 16      /* created by a script (mission character), not an ambient ped */
#define HCB_PF_IN_GROUP 32     /* member of the player's group (recruited homie) */
#define HCB_PF_RESPECTS 64     /* the game's own relationship table: respects / likes the player */
#define HCB_PF_HATES 128       /* ... hates / dislikes the player */
/* ---- ped flags2 */
#define HCB_PF2_LOS_KNOWN 1    /* the adapter has checked the line of sight to CJ this snapshot */
#define HCB_PF2_LOS_CLEAR 2
#define HCB_PF2_ON_FIRE 4
#define HCB_PF2_DRIVER 8

/* ---- vehicle classes (hcb_veh.cls) and flags */
#define HCB_VC_CAR 0
#define HCB_VC_BIKE 1
#define HCB_VC_HELI 2
#define HCB_VC_PLANE 3
#define HCB_VC_BOAT 4
#define HCB_VC_OTHER 5
#define HCB_VF_BURNING 1
#define HCB_VF_WRECKED 2
#define HCB_VF_MISSION 4
#define HCB_VF_EMERGENCY 8     /* police / army / FBI vehicle */

/* ---- events */
#define HCB_EV_SHOT 1          /* src fired: a = muzzle, b = where the round went; dst = entity hit, if any */
#define HCB_EV_DAMAGE 2        /* src hurt dst by `value` with `weapon` */
#define HCB_EV_EXPLOSION 3     /* a = centre, value = radius, src = who caused it */
#define HCB_EV_PROJECTILE 4    /* src threw / launched `weapon`: a = position, b = velocity */

/* ---- roles of our own people (hcb_snapshot.our_role) */
#define HCB_ROLE_PILOT 1
#define HCB_ROLE_GUNNER 2      /* +0..3: right front, left front, right rear, left rear */
#define HCB_ROLE_SQUAD 6       /* +0..3 */

/* ---- what the brain thinks of a contact (hcb_mark.cls), least to most dangerous */
#define HCB_CLS_FRIEND 0
#define HCB_CLS_NEUTRAL 1
#define HCB_CLS_WATCH 2        /* worth an eye: armed hostile type, somebody closing in */
#define HCB_CLS_THREAT 3       /* about to hurt CJ: weapon on him, car on a collision course */
#define HCB_CLS_ATTACKER 4     /* has fired at or hurt CJ or one of ours */

/* ---- why (hcb_mark.why): the strongest piece of evidence */
#define HCB_WHY_NONE 0
#define HCB_WHY_OURS 1
#define HCB_WHY_ALLY 2
#define HCB_WHY_HURT_CJ 3
#define HCB_WHY_HURT_OURS 4
#define HCB_WHY_SHOT_AT_CJ 5
#define HCB_WHY_SHOT_AT_OURS 6
#define HCB_WHY_AIMS_AT_CJ 7
#define HCB_WHY_AIMS_AT_OURS 8
#define HCB_WHY_ARMED_FACING 9
#define HCB_WHY_ARMED_NEAR 10
#define HCB_WHY_HOSTILE_NEAR 11
#define HCB_WHY_RAMMING 12
#define HCB_WHY_BURNING 13
#define HCB_WHY_MELEE_CLOSING 14
#define HCB_WHY_SHOOTING_NEARBY 15

/* ---- alert levels (hcb_out.alert) */
#define HCB_ALERT_CALM 0
#define HCB_ALERT_WARY 1
#define HCB_ALERT_THREAT 2
#define HCB_ALERT_COMBAT 3
#define HCB_ALERT_EVACUATE 4

#define HCB_KIND_PED 0
#define HCB_KIND_VEH 1

typedef struct hcb_vec {
    float x;
    float y;
    float z;
} hcb_vec;

typedef struct hcb_ped {
    uint32_t id;        /* handle: stable while the ped exists, never 0 */
    uint32_t target;    /* whom he is aiming at or fighting; 0 = nobody */
    uint32_t vehicle;   /* vehicle he sits in; 0 = on foot */
    hcb_vec pos;        /* centre of the body, metres */
    hcb_vec vel;        /* metres per second */
    hcb_vec fwd;        /* unit vector he faces */
    float health;
    float armour;
    uint16_t model;
    uint8_t pedtype;    /* the game's ped type (6 police, 7-16 gangs, 8 Grove...) */
    uint8_t weapon;     /* weapon in his hands (game id; 0 = fists) */
    uint8_t flags;      /* HCB_PF_* */
    uint8_t flags2;     /* HCB_PF2_* */
    uint8_t seat;       /* 0 driver, 1.. passengers (when vehicle != 0) */
    uint8_t reserved;
} hcb_ped;

typedef struct hcb_veh {
    uint32_t id;
    uint32_t driver;    /* ped id; 0 = empty */
    hcb_vec pos;
    hcb_vec vel;
    hcb_vec fwd;
    float health;       /* 1000 new, burns below 250 */
    uint16_t model;
    uint8_t cls;        /* HCB_VC_* */
    uint8_t flags;      /* HCB_VF_* */
    uint8_t passengers;
    uint8_t max_passengers;
    uint8_t reserved0;
    uint8_t reserved1;
} hcb_veh;

typedef struct hcb_event {
    uint32_t time;      /* game time, ms */
    uint32_t src;
    uint32_t dst;
    hcb_vec a;
    hcb_vec b;
    float value;
    uint8_t type;       /* HCB_EV_* */
    uint8_t weapon;
    uint8_t reserved0;
    uint8_t reserved1;
} hcb_event;

typedef struct hcb_snapshot {
    uint32_t time;      /* game time, ms */
    uint32_t frame;
    hcb_ped player;     /* CJ */
    uint32_t heli;      /* our helicopter (vehicle id); 0 = not called */
    uint8_t wanted;     /* stars */
    uint8_t on_mission;
    uint8_t cutscene;
    uint8_t controls_off;
    uint8_t hour;
    uint8_t weather;
    uint8_t interior;
    uint8_t roe;        /* the player's fire mode setting */
    hcb_vec cam_pos;
    hcb_vec cam_fwd;
    uint16_t n_peds;
    uint16_t n_vehs;
    uint16_t n_events;
    uint16_t n_ours;
    uint16_t events_lost;   /* events that did not fit since the previous snapshot */
    uint16_t peds_lost;     /* peds in range that did not fit */
    uint32_t ours[HCB_MAX_OURS];
    uint8_t our_role[HCB_MAX_OURS];
    hcb_ped peds[HCB_MAX_PEDS];
    hcb_veh vehs[HCB_MAX_VEHS];
    hcb_event events[HCB_MAX_EVENTS];
} hcb_snapshot;

typedef struct hcb_mark {
    uint32_t id;
    float edps;         /* damage per second this contact can be expected to do to CJ right now */
    float dist;         /* metres from CJ */
    uint8_t kind;       /* HCB_KIND_* */
    uint8_t cls;        /* HCB_CLS_* */
    uint8_t why;        /* HCB_WHY_* */
    uint8_t seen;       /* 1 = in this snapshot, 0 = remembered (out of sight) */
} hcb_mark;

typedef struct hcb_out {
    uint32_t time;
    uint32_t digest;    /* checksum of everything decided this tick: a replay must reproduce it */
    float danger;       /* sum of edps over all contacts */
    uint32_t top;       /* the most dangerous contact, 0 = none */
    uint8_t alert;      /* HCB_ALERT_* */
    uint8_t n_marks;
    uint8_t n_threats;  /* contacts at THREAT or above */
    uint8_t n_attackers;
    hcb_mark marks[HCB_MAX_MARKS];
} hcb_out;

/* Tunable numbers. hcb_init fills in the defaults; tests and the tuning runs change them. */
typedef struct hcb_cfg {
    float near_m;           /* an armed hostile inside this range and turned to CJ is a THREAT */
    float watch_m;          /* hostile types are watched inside this range */
    float facing_cos;       /* "turned to CJ": cosine of the half angle */
    float aim_ms;           /* weapon held on CJ this long = THREAT whoever he is */
    float shot_pass_m;      /* a round passing this close to CJ or ours was fired at them */
    float attacker_ms;      /* how long somebody stays an ATTACKER after his last hostile act */
    float forget_ms;        /* an unseen contact is dropped after this long */
    float ram_time_s;       /* look this far ahead for cars on a collision course */
    float ram_miss_m;       /* ... passing this close */
    float ram_speed;        /* ... at this speed or more, m/s */
    float burn_m;           /* a burning vehicle inside this range is a hazard */
    float melee_m;          /* somebody with a blade or a bat running at CJ inside this range */
    float calm_ms;          /* quiet time before the alert level goes down one step */
    float evac_danger;      /* total expected damage per second at which the brain wants CJ out */
} hcb_cfg;

/* The brain itself is one opaque block of hcb_brain_size() bytes that the caller provides (no allocation). */
typedef struct hcb_brain hcb_brain;

uint32_t hcb_brain_size(void);
uint32_t hcb_struct_size(int which);   /* 0 ped, 1 veh, 2 event, 3 snapshot, 4 out, 5 cfg, 6 mark: layout check for bindings */
void hcb_init(hcb_brain *b, uint32_t seed);
hcb_cfg *hcb_config(hcb_brain *b);
void hcb_think(hcb_brain *b, const hcb_snapshot *s, hcb_out *out);

/* What the brain knows about one contact, for tests and the log. Returns 0 when it does not know the id. */
typedef struct hcb_track_info {
    uint32_t id;
    uint32_t first_seen;
    uint32_t last_seen;
    uint32_t last_hostile;  /* time of his last hostile act */
    float damage_cj;
    float damage_ours;
    float aim_ms;           /* how long he has held a weapon on CJ or ours */
    uint16_t shots_at_cj;
    uint16_t shots_at_ours;
    uint16_t shots_total;
    uint8_t cls;
    uint8_t why;
    uint8_t best_weapon;
    uint8_t friendly;
    uint8_t reserved0;
    uint8_t reserved1;
    hcb_vec last_pos;
} hcb_track_info;
int hcb_track(const hcb_brain *b, uint32_t id, hcb_track_info *info);

/* ---- black box: a ring of the latest snapshots in a caller-provided buffer */
typedef struct hcb_rec {
    uint32_t cap;
    uint32_t start;         /* offset of the oldest whole record */
    uint32_t end;           /* offset one past the newest record */
    uint32_t records;
    uint32_t dropped;       /* records thrown away to make room */
    uint32_t reserved;
} hcb_rec;
void hcb_rec_init(hcb_rec *r, uint32_t cap);
/* Append one snapshot (+ the digest of what was decided on it). buf is the caller's buffer of r->cap bytes. */
void hcb_rec_push(hcb_rec *r, uint8_t *buf, const hcb_snapshot *s, uint32_t digest);
/* Read the record at *offset (start with r->start, stop at r->end). Returns 1 and moves *offset on, 0 at the end
   or on damaged data. */
int hcb_rec_next(const uint8_t *buf, uint32_t end, uint32_t *offset, hcb_snapshot *s, uint32_t *digest);

/* Weapon knowledge shared with the adapter and the tests. */
#define HCB_WC_NONE 0
#define HCB_WC_MELEE 1
#define HCB_WC_PISTOL 2
#define HCB_WC_SHOTGUN 3
#define HCB_WC_SMG 4
#define HCB_WC_RIFLE 5
#define HCB_WC_SNIPER 6
#define HCB_WC_HEAVY 7
#define HCB_WC_THROWN 8
int hcb_weapon_class(int weapon);
float hcb_weapon_dps(int weapon);      /* damage per second when every round hits */
float hcb_weapon_range(int weapon);    /* effective range, metres */

#endif
