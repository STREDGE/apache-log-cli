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

#define HCB_VERSION 3          /* layout of the structs below; a black box says which version wrote it */

#define HCB_MAX_PEDS 64        /* peds in one snapshot (nearest to CJ first) */
#define HCB_MAX_VEHS 40
#define HCB_MAX_EVENTS 48      /* events gathered between two snapshots */
#define HCB_MAX_OURS 16        /* pilot, gunners, squad */
#define HCB_MAX_MARKS 48       /* contacts reported back for the debug markers */
#define HCB_MAX_TRACKS 96      /* people the brain remembers at one time */
#define HCB_MAX_VTRACKS 48
#define HCB_MAX_LOS 96          /* line-of-sight questions per tick (answered by the adapter in the next snapshot) */

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
#define HCB_ROLE_NONE 0        /* ours, but not in the fight (a guard who was let go and walks away): a friend in every line of fire, no orders */
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
#define HCB_WHY_AIR_FIRE 16      /* a helicopter that is not ours while rounds from nowhere are hitting CJ or ours */

/* ---- alert levels (hcb_out.alert) */
#define HCB_ALERT_CALM 0
#define HCB_ALERT_WARY 1
#define HCB_ALERT_THREAT 2
#define HCB_ALERT_COMBAT 3
#define HCB_ALERT_EVACUATE 4

#define HCB_KIND_PED 0
#define HCB_KIND_VEH 1

/* ---- the player's fire rule (hcb_snapshot.roe; the numbers are the FIRE setting of the scripts) */
#define HCB_ROE_HOLD 0         /* nobody fires */
#define HCB_ROE_LEGACY_ALL 1   /* the old "fire at all": treated as ARMED - the brain does not shoot passers-by */
#define HCB_ROE_FOLLOW 2       /* only what CJ himself is shooting at */
#define HCB_ROE_DEFEND 3       /* threats and attackers (the default) */
#define HCB_ROE_ARMED 4        /* ... and every armed hostile in sight */
/* ---- police with a wanted level (hcb_snapshot.police) */
#define HCB_POLICE_ANSWER 0    /* fire back at policemen who are shooting */
#define HCB_POLICE_EVADE 1     /* never fire at the police: get CJ out instead */

/* ---- orders to our shooters (hcb_order) */
#define HCB_AIM_BODY 0
#define HCB_AIM_DRIVER 1       /* a man in a vehicle: at him, not at the engine */
#define HCB_AIM_TYRE 2         /* stop the vehicle without blowing it up */
#define HCB_HOLD_NONE 0        /* firing */
#define HCB_HOLD_NO_TARGET 1
#define HCB_HOLD_ROE 2
#define HCB_HOLD_CJ_IN_LINE 3
#define HCB_HOLD_CJ_BEHIND 4   /* CJ stands behind the target */
#define HCB_HOLD_FRIEND 5      /* one of ours or an ally in or behind the line */
#define HCB_HOLD_BYSTANDER 6
#define HCB_HOLD_CAR_NEAR 7    /* a damaged or burning vehicle close enough to hurt CJ or ours if it blows */
#define HCB_HOLD_NO_LOS 8      /* something in the way (or not yet known: the question has been asked) */
#define HCB_HOLD_RANGE 9
#define HCB_HOLD_REACTING 10   /* target taken, weapon coming up: a human reaction time */
#define HCB_HOLD_PAUSE 11      /* between two bursts */
#define HCB_HOLD_COVERING 12   /* weapon on a suspect, finger off the trigger */
#define HCB_HOLD_ENOUGH 13     /* a man to fire at, but three of ours are on him already: weapon on him, no fire */

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
    uint32_t id;        /* must never equal the id of a ped (the game adapter sets bit 31 on vehicle ids) */
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

typedef struct hcb_los {
    uint32_t from;      /* one of ours */
    uint32_t to;        /* a contact */
    uint8_t clear;      /* answer: 1 = nothing between them */
    uint8_t reserved0;
    uint8_t reserved1;
    uint8_t reserved2;
} hcb_los;

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
    uint8_t roe;        /* HCB_ROE_*: the player's fire rule */
    uint8_t police;     /* HCB_POLICE_* */
    uint8_t mission_free; /* 1 = the player wants mission characters treated like anybody else (default 0: defensive) */
    uint8_t reserved1;
    uint8_t reserved2;
    hcb_vec cam_pos;
    hcb_vec cam_fwd;
    uint16_t n_peds;
    uint16_t n_vehs;
    uint16_t n_events;
    uint16_t n_ours;
    uint16_t events_lost;   /* events that did not fit since the previous snapshot */
    uint16_t peds_lost;     /* peds in range that did not fit */
    uint16_t n_los;         /* answers to the questions of the previous hcb_out */
    uint16_t reserved3;
    uint32_t ours[HCB_MAX_OURS];
    uint8_t our_role[HCB_MAX_OURS];
    hcb_ped peds[HCB_MAX_PEDS];
    hcb_veh vehs[HCB_MAX_VEHS];
    hcb_event events[HCB_MAX_EVENTS];
    hcb_los los[HCB_MAX_LOS];
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

typedef struct hcb_order {
    uint32_t who;       /* one of ours */
    uint32_t target;    /* 0 = nobody */
    hcb_vec aim;        /* the point to aim at */
    uint8_t fire;       /* 1 = fire now */
    uint8_t aim_at;     /* HCB_AIM_* */
    uint8_t hold;       /* HCB_HOLD_*: why not firing */
    uint8_t ready;      /* 1 = weapon up */
} hcb_order;

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
    uint8_t n_orders;
    uint8_t n_queries;
    uint16_t kills;     /* contacts that died while our people were firing at them (running total, wraps) */
    hcb_order orders[HCB_MAX_OURS];
    hcb_los queries[HCB_MAX_LOS];
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
    /* fire discipline: the hard rules */
    float cj_line_m;        /* no round whose line passes this close to CJ ... */
    float line_per_m;       /* ... plus this much per metre of range (dispersion) */
    float friend_line_m;    /* the same for ours and allies */
    float bystander_line_m;
    float backstop_m;       /* how far behind the target CJ and friends are looked for */
    float explode_m;        /* a vehicle this close to CJ or ours must not be blown up */
    float car_floor;        /* ... so it is not fired at below this health */
    /* how a human shoots */
    float react_min_ms;
    float react_max_ms;
    float burst_min_ms;
    float burst_max_ms;
    float pause_min_ms;
    float pause_max_ms;
    float follow_ms;        /* FOLLOW: how long somebody CJ shot at stays a target */
    /* verdicts do not flicker */
    float threat_hold_ms;   /* a THREAT stays one this long after its reason was last true */
    float ram_hold_ms;      /* the same for a car on a collision course */
    float hit_hold_ms;      /* a car that has hit CJ or ours stays a threat this long while it keeps moving */
    /* rounds of the door gunners are created by the script along a line the brain has checked */
    float muzzle_m;         /* ... starting this far from the gunner (outside the helicopter) */
    float round_past_m;     /* ... and ending this far past the aim point */
    float round_min_ms;     /* time between two rounds of one gunner: at least this ... */
    float round_max_ms;     /* ... and at most this */
    float scatter_m;        /* scatter of a round on every axis: this much ... */
    float scatter_per_m;    /* ... plus this per metre of range ... */
    float scatter_per_ms;   /* ... plus this per m/s of the helicopter he fires from */
} hcb_cfg;

/* The brain itself is one opaque block of hcb_brain_size() bytes that the caller provides (no allocation). */
typedef struct hcb_brain hcb_brain;

uint32_t hcb_brain_size(void);
uint32_t hcb_struct_size(int which);   /* 0 ped, 1 veh, 2 event, 3 snapshot, 4 out, 5 cfg, 6 mark, 7 track_info, 8 rec, 9 box_head, 10 los, 11 order, 12 shot, 13 round */
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

/* One round, asked for at the moment it is to leave the barrel, with the positions of THIS frame (a snapshot may be
 * 100 ms old). The brain answers from the hard rules only: HCB_HOLD_NONE = let it go. The adapter still has to run
 * its own ray along muzzle -> to. */
typedef struct hcb_shot {
    uint32_t who;           /* one of ours */
    uint32_t target;        /* the contact of his current order */
    uint32_t time;          /* game time now, ms */
    uint32_t n_friends;
    hcb_vec from;           /* where the shooter is */
    hcb_vec muzzle;         /* where the round starts */
    hcb_vec to;             /* the point it is aimed at (a gunner's round ends round_past_m beyond it) */
    hcb_vec cj;             /* CJ now */
    hcb_vec friends[HCB_MAX_OURS];  /* our own people now (the shooter himself left out) */
} hcb_shot;
int hcb_shot_check(const hcb_brain *b, const hcb_shot *q);


/* ---- black box: a ring of the latest snapshots in a caller-provided buffer.
 * Besides the snapshots the adapter stores the brain's own memory every few seconds, so a replay can start from
 * the first such record in the file and reproduce every later decision exactly even though older records are gone. */
#define HCB_REC_SNAPSHOT 1
#define HCB_REC_STATE 2
#define HCB_REC_ROUND 3         /* one round of ours: asked for, and what the answer was */
typedef struct hcb_round {
    uint32_t time;
    uint32_t who;
    uint32_t target;
    hcb_vec muzzle;         /* where the round starts */
    hcb_vec to;             /* the point it is aimed at (scattered round the man) */
    hcb_vec end;            /* where it ends: round_past_m beyond `to` */
    uint8_t verdict;        /* HCB_HOLD_*: HCB_HOLD_NONE = the hard rules let it go */
    uint8_t ray;            /* 1 = the adapter's ray muzzle -> to was clear (set by the adapter) */
    uint8_t note;           /* 1 = worth a line in the black box (every round let go; refusals four times a second) */
    uint8_t reserved1;
} hcb_round;
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
/* Append the brain's memory as it is now (call it BEFORE hcb_think on the next snapshot). */
void hcb_rec_push_state(hcb_rec *r, uint8_t *buf, const hcb_brain *b);
/* Read the record at *offset (start with r->start, stop at r->end) and move *offset on. Returns 0 at the end or on
   damaged data, HCB_REC_SNAPSHOT (s and digest filled) or HCB_REC_STATE (state, a block of hcb_brain_size() bytes,
   filled when it is not NULL). */
int hcb_rec_next(const uint8_t *buf, uint32_t end, uint32_t *offset, hcb_snapshot *s, uint32_t *digest, hcb_brain *state, hcb_round *round);
void hcb_rec_push_round(hcb_rec *r, uint8_t *buf, const hcb_round *round);

/* The report file the player sends: this head, then the records [start, end) of the ring, then free text. */
typedef struct hcb_box_head {
    uint8_t magic[8];       /* "HCBBOX1" */
    uint32_t version;       /* HCB_VERSION */
    uint32_t brain_size;
    uint32_t snapshot_size;
    uint32_t ped_size;
    uint32_t veh_size;
    uint32_t event_size;
    uint32_t records;
    uint32_t dropped;
    uint32_t data_len;
    uint32_t text_len;
    uint32_t seed;
    uint32_t reserved;
} hcb_box_head;
void hcb_box_head_fill(hcb_box_head *h, const hcb_rec *r, const hcb_brain *b, uint32_t text_len);

/* ---- what the scripts ask for, frame by frame (the adapter adds the positions of this frame and the ray)
 * hcb_order_get: the standing order of one of ours as of the last look. Returns 0 when he has none.
 * hcb_gunner_round: a door gunner whose order is "fire". q->from = his chest, q->to = the man's chest NOW, q->muzzle is
 *   ignored. Returns 0 when no round is due yet; else fills *r - the line of this round (scattered: nobody is a
 *   laser) and the verdict of the hard rules for exactly that line - and sets the time of the next try. The adapter
 *   then runs its ray muzzle -> to; if the ray is blocked it says so with hcb_gunner_blocked.
 * hcb_squad_state: a guard on foot (he fires the game's own weapon). 0 nothing; 1 a suspect to keep a weapon on (not a
 *   man to leave his place for); 2 fire; 3 his man, but no fire now (CJ or one of ours in the line, a wall, enough
 *   rifles on him, the weapon still coming up). q->from = q->muzzle = where he stands, q->to = where the man stands. */
int hcb_order_get(const hcb_brain *b, uint32_t who, hcb_order *o);
int hcb_gunner_round(hcb_brain *b, const hcb_shot *q, float heli_speed, int near_heli, hcb_round *r);
void hcb_gunner_blocked(hcb_brain *b, uint32_t who, uint32_t time);
int hcb_squad_state(const hcb_brain *b, const hcb_shot *q);

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
