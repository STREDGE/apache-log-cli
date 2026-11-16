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

#define HCB_VERSION 7          /* layout of the structs below; a black box says which version wrote it */

#define HCB_MAX_PEDS 64        /* peds in one snapshot (nearest to CJ first) */
#define HCB_MAX_VEHS 40
#define HCB_MAX_EVENTS 48      /* events gathered between two snapshots */
#define HCB_MAX_OURS 24        /* pilot, gunners, squad (8 on the ground), guards let go */
#define HCB_MAX_MARKS 48       /* contacts reported back for the debug markers */
#define HCB_MAX_TRACKS 96      /* people the brain remembers at one time */
#define HCB_MAX_VTRACKS 48
#define HCB_MAX_PROBES 16        /* cover questions per tick (a point, and where the threat is: is the point hidden from it, is there ground?) */
#define HCB_MAX_LOS 96          /* line-of-sight questions per tick (answered by the adapter in the next snapshot) */
#define HCB_MAX_HINTS 12        /* 0.8: the game's own cover points near CJ */
#define HCB_MAX_DANGERS 8       /* 0.8: live grenades, rockets, fires and fresh explosions near CJ */
#define HCB_MAX_GROUND 32       /* 1.0: ground questions per tick (the brain's own map of the ground round CJ): one ray down and four level
                                   rays each */
#define HCB_MAX_SEGS 16         /* 1.0: "can a man walk straight from a to b" questions per tick */
#define HCB_MAX_HIGH 8          /* 1.0: high places near CJ (roofs) the adapter has found for the marksman */

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
#define HCB_ROLE_SQUAD 6       /* +0..7: the detail on the ground, by number (0 is the commander while he lives) */

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
#define HCB_HOLD_FISTS 14      /* 0.8, proportionate force: an unarmed man on foot is not shot - a guard near him takes him down by hand */

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

/* A cover question and its answer: is the point `at` (on the ground, a man crouching there) hidden from `from` (the threat's
   chest), and is there ground under it? Asked by the core in hcb_out, answered by the adapter (two rays) in the next snapshot. */
typedef struct hcb_probe {
    hcb_vec at;
    hcb_vec from;
    uint8_t hidden;     /* the ray from `from` to a crouching chest at `at` is blocked */
    uint8_t ground;     /* there is something to stand on just below `at` */
    uint8_t hidden_hi;  /* 1.0: the ray to a STANDING man's head at `at` is blocked too (0 = he can fire over it standing up) */
    uint8_t reserved1;
} hcb_probe;

/* What one guard on foot is to do (the protective detail, stage 3): where to be, how fast to get there, standing or
   crouched (in cover he fights crouched: the game's own duck-and-fire), where to look, and what he is doing. Whom to fire
   at and whether is still the fire order. */
#define HCB_DUTY_CALM 0         /* walking with CJ in the formation, watching his sector */
#define HCB_DUTY_WATCH 1        /* a suspect: weapon up, between him and CJ */
#define HCB_DUTY_SHIELD 2       /* personal bodyguard: his body between CJ and the threat */
#define HCB_DUTY_COVER 3        /* fighting from cover */
#define HCB_DUTY_BOUND 4        /* moving to the next cover while his mate covers him */
#define HCB_DUTY_HOLD 5         /* holding his place, covering a mate who moves */
#define HCB_DUTY_RING 6         /* evacuation: a tight ring round CJ */
#define HCB_ROLE_LEAD 1         /* the commander (call sign Alpha) */
#define HCB_ROLE_CLOSE 2        /* the personal bodyguard, at CJ's side */
#define HCB_ROLE_POINT 3        /* the fire team: ahead / towards the threat */
#define HCB_ROLE_REAR 4         /* the fire team: the rear / the other flank (call sign Charlie: the counter-assault pair) */
#define HCB_ROLE_CLOSE2 5       /* the second bodyguard, on CJ's other side */
#define HCB_ROLE_POINT2 6       /* the advance pair (Bravo), second man: a flank on the move */
#define HCB_ROLE_REAR2 7        /* the counter-assault pair (Charlie), second man: the other flank */
#define HCB_ROLE_MARKSMAN 8     /* Delta: a rifle on a spot that sees far (high ground, the far side) */
#define HCB_ROLE_CLOSE3 9       /* 0.6: the third bodyguard (eight men: the commander, three bodyguards, four outer men) */
/* how the detail fights (hcb_out.mode): the brain picks it from the fight itself, the menu only forces one */
#define HCB_MODE_HOLD 0         /* CJ into cover, fight from cover, the pair bounds */
#define HCB_MODE_PULLOUT 1      /* too much for us: a ring round CJ, the commander leads him away, call the pickup */
#define HCB_MODE_ASSAULT 2      /* few and weak: CJ in cover, the pair pushes and flanks */
typedef struct hcb_post {
    uint32_t who;
    hcb_vec at;         /* where to be */
    hcb_vec look;       /* where to look / point the weapon when there is nobody to fire at */
    uint8_t move;       /* 0 stay where you are, 1 walk, 2 run, 3 sprint */
    uint8_t crouch;     /* 1 = crouched there */
    uint8_t duty;       /* HCB_DUTY_* */
    uint8_t job;        /* HCB_ROLE_LEAD .. HCB_ROLE_MARKSMAN */
    uint8_t stuck;      /* 1 = he has not got nearer to his post for a while: this is another way round (the script goes by the
                           path network when it is set) */
    uint8_t act;        /* 1.0: HCB_ACT_*: what he is doing now */
    uint8_t phase;      /* 1.0: HCB_PH_*: where that action stands */
    uint8_t why;        /* 1.0: HCB_WHY2_*: the reason of his last decision / failure */
    hcb_vec via;        /* 1.0: the next point on his way there (= at when the way is straight); the mod walks him to it */
} hcb_post;
/* 1.0: what a man does (hcb_post.act) and how far he has got (hcb_post.phase) */
#define HCB_ACT_HOLD 0          /* stay where he is */
#define HCB_ACT_WALK 1
#define HCB_ACT_FASTWALK 2
#define HCB_ACT_RUN 3
#define HCB_ACT_SPRINT 4        /* a rush from cover to cover, or closing on CJ under fire */
#define HCB_ACT_COVER 5         /* in his place, down behind something */
#define HCB_ACT_OVERWATCH 6     /* in his place, standing / kneeling, watching his sector */
#define HCB_ACT_SIDESTEP 7      /* getting round something that blocks him */
#define HCB_PH_CHOSEN 0
#define HCB_PH_MOVING 1
#define HCB_PH_ARRIVED 2
#define HCB_PH_ACTING 3
#define HCB_PH_FAILED 4
#define HCB_WHY2_NONE 0
#define HCB_WHY2_NEW_POST 1     /* the squad gave him another place */
#define HCB_WHY2_DIRECT 2       /* the straight way is free */
#define HCB_WHY2_ROUTE 3        /* going round by the brain's own map */
#define HCB_WHY2_BLOCKED 4      /* the straight way is blocked: a way round is being looked for */
#define HCB_WHY2_NO_PROGRESS 5  /* he did not get nearer: another way */
#define HCB_WHY2_NO_ROUTE 6     /* no way found: the game's path network, then another place */
#define HCB_WHY2_ARRIVED 7
#define HCB_WHY2_WAIT_TURN 8    /* his pair covers: he waits for his turn to move */
#define HCB_WHY2_IN_AIR 9       /* on the rope: no orders until he stands */
/* 1.0: the mode the PLAYER has chosen (hcb_snapshot.umode) and what the squad is doing about it (hcb_out.task) */
#define HCB_UMODE_PROTECT 0
#define HCB_UMODE_ASSAULT 1
#define HCB_TASK_ESCORT 0       /* protect: walking with CJ */
#define HCB_TASK_SHIELD 1       /* protect: a fight - three at CJ, four in cover, the marksman above */
#define HCB_TASK_EXTRACT 2      /* protect: too hot, getting CJ out */
#define HCB_TASK_APPROACH 3     /* assault: on the way to the target, nothing seen yet */
#define HCB_TASK_GATHER 4       /* assault: collecting at the last cover before the target */
#define HCB_TASK_BOUND 5        /* assault: fire and movement, one pair at a time */
#define HCB_TASK_SEARCH 6       /* assault: the target is out of sight - to where it was last seen */
#define HCB_TASK_CONSOLIDATE 7  /* assault: the place is taken - all-round watch */
#define HCB_TASK_REGROUP 8      /* assault: nothing left to do - back to CJ (the mode stays ASSAULT) */
#define HCB_TASK_WITHDRAW 9     /* assault: too many of ours down or no way - back by bounds */
/* per man of ours (hcb_snapshot.our_state) */
#define HCB_OS_ROPING 1         /* on a rope or falling: no post, no orders */
#define HCB_OS_NATIVE 2         /* the mod itself walks this man (not the script) */

/* What the commander says (hcb_out.say), with a direction from CJ's point of view (hcb_out.say_dir: 0 ahead, 1 right,
   2 behind, 3 left) */
#define HCB_SAY_NONE 0
#define HCB_SAY_TAKE_COVER 1    /* "CJ, into cover - <dir>!" (the place is marked on the screen) */
#define HCB_SAY_IN_COVER 2      /* "CJ is in cover, we hold" */
#define HCB_SAY_FOLLOW_ME 3     /* "CJ, stay with me, we move" (no cover near: the detail moves with him, the bodyguard covers) */
#define HCB_SAY_EVAC 4          /* "Too hot - we pull out, call the pickup" */
#define HCB_SAY_TAKE_OVER 5     /* "the commander is down - I have command" */
#define HCB_SAY_CLEAR 6         /* "clear - regroup on CJ" */
#define HCB_SAY_SNIPER 7        /* 0.7: "sniper - <dir>!" (a man far off who has hit or fired at CJ) */
#define HCB_SAY_BEEN_HERE 8     /* 0.7: "we were attacked here before - eyes open" (the brain remembers the places) */
#define HCB_SAY_GRENADE 9       /* 0.8: "grenade - <dir>!" */
#define HCB_SAY_WATER 10        /* 0.8: "CJ is in the water - the helicopter is over you, take the rope" */
#define HCB_SAY_AHEAD 11        /* 0.8: "armed men ahead" (CJ drives, the helicopter scouts the way) */
#define HCB_SAY_CAR 12          /* 0.9: "car - <dir>!": a car on a collision course with CJ reaches him within 3 s */
/* dangers (hcb_danger.kind) */
#define HCB_DG_GRENADE 1        /* a thrown grenade / satchel / tear gas on its way or lying */
#define HCB_DG_FIRE 2           /* a molotov */
#define HCB_DG_ROCKET 3
#define HCB_DG_BLAST 4          /* an explosion that has just gone off */

typedef struct hcb_los {
    uint32_t from;      /* one of ours */
    uint32_t to;        /* a contact */
    uint8_t clear;      /* answer: 1 = nothing between them */
    uint8_t reserved0;
    uint8_t reserved1;
    uint8_t reserved2;
} hcb_los;

typedef struct hcb_danger {
    hcb_vec at;
    float radius;       /* metres to keep clear */
    uint8_t kind;       /* HCB_DG_* */
    uint8_t pad[3];
} hcb_danger;
/* 1.0: the brain's own map. A ground question: what is the height of the ground at (x, y) looking down from z? */
typedef struct hcb_ground {
    float x;
    float y;
    float z;            /* question: look down from here; answer: the ground's height */
    uint8_t found;      /* answer: 1 = there is ground */
    uint8_t wall;       /* answer: bit 0 = something solid between this cell's middle and the next one to +x (a man cannot walk
                           straight across), bit 1 = the same to +y - two level rays each, at knee and chest height */
    uint8_t pad[2];
} hcb_ground;
/* can a man walk straight from a to b (nothing solid between them at knee and chest height)? */
typedef struct hcb_seg {
    hcb_vec a;
    hcb_vec b;
    uint8_t clear;      /* answer */
    uint8_t pad[3];
} hcb_seg;
/* a high place near CJ where a man could stand (found by the adapter: flat, well above CJ's ground) */
typedef struct hcb_high {
    hcb_vec at;
    float height;       /* metres above CJ's feet */
    uint8_t sees_cj;    /* 1 = CJ can be seen from it */
    uint8_t pad[3];
} hcb_high;
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
    uint8_t tactics;    /* the squad's tactics on the menu: 0 AUTO (the brain chooses), 1 ASSAULT (push towards the threat), 2 GUARD (stay close) */
    uint8_t in_water;   /* 0.8: CJ is swimming */
    hcb_vec cam_pos;
    hcb_vec cam_fwd;
    uint16_t n_peds;
    uint16_t n_vehs;
    uint16_t n_events;
    uint16_t n_ours;
    uint16_t events_lost;   /* events that did not fit since the previous snapshot */
    uint16_t peds_lost;     /* peds in range that did not fit */
    uint16_t n_los;         /* answers to the questions of the previous hcb_out */
    uint16_t n_probes;      /* answers to the cover questions of the previous hcb_out */
    hcb_probe probes[HCB_MAX_PROBES];
    uint32_t ours[HCB_MAX_OURS];
    uint8_t our_role[HCB_MAX_OURS];
    hcb_ped peds[HCB_MAX_PEDS];
    hcb_veh vehs[HCB_MAX_VEHS];
    hcb_event events[HCB_MAX_EVENTS];
    hcb_los los[HCB_MAX_LOS];
    /* 0.8 */
    uint16_t n_hints;
    uint16_t n_dangers;
    hcb_vec hints[HCB_MAX_HINTS];       /* the game's own cover points (CCover) near CJ: where something solid stands */
    hcb_danger dangers[HCB_MAX_DANGERS];
    /* 1.0 */
    uint8_t umode;      /* HCB_UMODE_*: the player's choice on the menu */
    uint8_t recall;     /* 1 = "to me": the assault task is dropped, everybody back to CJ */
    uint8_t n_ground;   /* answers to ground_q of the previous hcb_out */
    uint8_t n_segs;     /* answers to seg_q */
    uint8_t n_high;
    uint8_t body;       /* 1 = the mod walks the guards itself (posts are followed by `via`) */
    uint8_t reserved2;
    uint8_t reserved3;
    uint8_t our_state[HCB_MAX_OURS];    /* HCB_OS_* per entry of ours */
    hcb_ground ground[HCB_MAX_GROUND];
    hcb_seg segs[HCB_MAX_SEGS];
    hcb_high high[HCB_MAX_HIGH];
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
    /* the protective detail (stage 3) */
    uint8_t n_posts;
    uint8_t n_probe_q;
    uint8_t say;        /* HCB_SAY_*: what the commander says this tick (also repeated in say_last until the next) */
    uint8_t say_dir;
    uint16_t say_seq;   /* goes up by one with every new thing said */
    uint8_t cover_ok;   /* 1 = cover_at is where CJ should go (mark it on the screen) */
    uint8_t duty;       /* the detail's state: HCB_DUTY_CALM / WATCH / COVER (a fight) / RING (evacuation) */
    hcb_vec cover_at;
    uint32_t lead;      /* the commander now */
    uint8_t mode;       /* HCB_MODE_*: how the detail fights now */
    uint8_t leading;    /* 1 = the commander walks ahead of CJ to cover_at (or away from the threat when pulling out) */
    uint8_t gunner_pose; /* how the door gunners should hold: 0 standing, 1 kneeling at the door, 2 seated on the skid */
    uint8_t heli_ok;    /* 1 = heli_at is where the helicopter should hang: the gunners see the threat from there */
    hcb_vec heli_at;
    hcb_post posts[HCB_MAX_OURS];
    hcb_probe probe_q[HCB_MAX_PROBES];
    /* 1.0 */
    uint8_t n_ground_q;
    uint8_t n_seg_q;
    uint8_t umode;      /* the player's mode as the brain has taken it */
    uint8_t task;       /* HCB_TASK_*: what the squad is doing */
    uint8_t ow_ok;      /* 1 = ow_at is the high place the marksman should be put on (the helicopter takes him there) */
    uint8_t ow_ready;   /* 1 = the helicopter hangs over ow_at, steady: the rope can go down */
    uint8_t n_moving;   /* how many of the detail are on the move this tick */
    uint8_t reserved4;
    uint32_t target;    /* assault: the man the squad goes for (0 = a place, or nothing) */
    float target_dist;  /* assault: metres from the squad's front to the target */
    hcb_vec target_at;  /* assault: where the squad is going */
    hcb_vec ow_at;
    hcb_ground ground_q[HCB_MAX_GROUND];
    hcb_seg seg_q[HCB_MAX_SEGS];
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
    float gunner_weapon;    /* 1 = the door gunners fire their own weapon (1.4: a round of the game, judged like a guard's on foot,
                               bursts paced by the brain); 0 = the rounds are made by the script along a checked line (1.3) */
    float cabin_skip_m;     /* a door gunner's own cabin: CJ inside the same helicopter, this close to the gunner's end of the
                               line, is behind the cabin wall (firing across the cabin is refused anyway) */
    /* 1.1: the detail's and the squad's numbers (every one of them can be set in the settings file) */
    float outer_peace_m;    /* PROTECT: how far out the four outer men stand in peace ... */
    float outer_fight_m;    /* ... and in a fight */
    float cj_low_hp;        /* CJ under this health: armed men near him are targets at once, the bodyguards come back to him */
    float gather_m;         /* ASSAULT: the squad gathers this far short of the target */
    float rush_m;           /* ... a rush of an assault pair is this long */
    float assault_near_m;   /* ... and nobody goes nearer to the target than this */
    float fire_first_ms;    /* ... the fire team fires this long before a pair moves */
    float search_ms;        /* ... a target unseen this long is searched for */
    float target_keep_ms;   /* ... and dropped after this long */
    float consolidate_ms;   /* ... all-round watch for this long after the target is down */
    float withdraw_down;    /* ... this many of ours down since the task began: fall back */
    float ow_min_h;         /* the marksman's roof: at least this high above CJ's feet ... */
    float ow_max_h;
    float ow_min_d;         /* ... and at least this far from him */
    float ow_max_d;
    float ow_try_ms;        /* ... one try of this long for each commander */
    /* 1.1: how a firing place is valued (hcb_places.c) */
    float place_w_fire;     /* hidden when crouching, a line of fire on the main threat when standing */
    float place_w_open;     /* a line of fire with no cover at all */
    float place_w_others;   /* hidden from the other threats */
    float place_w_dist;     /* a good range to the main threat */
    float place_w_near;     /* near the man who is to take it */
    float place_w_crowd;    /* taken off: another of ours within 3 m */
    float place_w_path;     /* taken off: the way there lies open to the threat */
    float place_better;     /* a new place must be this many times better than the one he holds ... */
    float place_keep_ms;    /* ... and he keeps a place at least this long */
    /* 1.1: tokens */
    float shooters_per_target;  /* how many of the detail fire at one man at a time */
    float movers_max;       /* how many of the outer men / the squad are on the move at a time */
    float reload_clip;      /* a man with this many rounds or fewer in his magazine reloads - one at a time */
    float corner_ms;        /* a man stops this long before a blind corner and looks round it */
    float door_ms;          /* nobody stands in a doorway longer than this */
} hcb_cfg;

/* The brain itself is one opaque block of hcb_brain_size() bytes that the caller provides (no allocation). */
typedef struct hcb_brain hcb_brain;

uint32_t hcb_brain_size(void);
uint32_t hcb_struct_size(int which);   /* 0 ped, 1 veh, 2 event, 3 snapshot, 4 out, 5 cfg, 6 mark, 7 track_info, 8 rec, 9 box_head, 10 los, 11 order, 12 shot, 13 round */
void hcb_init(hcb_brain *b, uint32_t seed);
hcb_cfg *hcb_config(hcb_brain *b);
/* 0.7: the places where the detail was attacked (the adapter keeps them in a file between games). */
#define HCB_MAX_PLACES 16
int hcb_places_get(const hcb_brain *b, hcb_vec *at, uint16_t *count);   /* fills up to HCB_MAX_PLACES; returns how many */
void hcb_places_set(hcb_brain *b, const hcb_vec *at, const uint16_t *count, int n);
int hcb_places_changed(hcb_brain *b);   /* 1 once after the list has changed (the adapter saves it then) */
void hcb_think(hcb_brain *b, const hcb_snapshot *s, hcb_out *out);
/* 1.0, for tests and the log: the brain's map. hcb_nav_way: the way it would take from `from` to `to` now (> 0 way points,
   0 no way, -1 the map does not know where `from` is). hcb_nav_cell: what it knows of the ground at (x, y): 0 nothing yet,
   1 ground (*z its height), 2 nothing to stand on; *blocked = the ways out of the cell that are marked blocked (bit per
   direction, 0 = +x, counter-clockwise). */
int hcb_nav_way(hcb_brain *b, hcb_vec from, hcb_vec to, hcb_vec *wp, int max, uint32_t now);
int hcb_nav_cell(const hcb_brain *b, float x, float y, float *z, int *blocked, uint32_t now);

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

/* ------------------------------------------------------------------ the pilot (1.4)
 * hcb_pilot_step flies the helicopter to a point the way a person would: it speeds up with the nose down, banks into
 * turns (and slows down for a sharp one), keeps its height over the roofs ahead, brakes in good time with the nose up
 * and stops over the point. One step per frame. The adapter puts the helicopter's real position into `pos` before each
 * step (whatever moved it meanwhile), the script moves it to out->pos and the adapter turns it to out->right/fwd/up. */
typedef struct hcb_pilot {
    hcb_vec pos;                /* metres */
    hcb_vec vel;                /* metres a second */
    hcb_vec head;               /* where the nose points: a flat unit vector */
    float pitch;                /* radians, nose up + */
    float roll;                 /* radians, right side down + */
    float yaw_rate;             /* radians a second, + = turning left (counter-clockwise from above) */
    uint32_t used;              /* the adapter's: a pilot in use */
    uint32_t last;              /* the adapter's: the game time of the last step */
} hcb_pilot;
typedef struct hcb_pilot_in {
    hcb_vec target;             /* where to go (its height is the pilot's to choose) */
    float ground;               /* the highest ground or roof under the helicopter and ahead of it (the script measures it) */
    float dt;                   /* seconds since the last step */
    float cruise;               /* top speed, m/s (0 = 68) */
    float hover;                /* height over the ground to stop at (0 = 25 m) */
    uint8_t stop;               /* 1 = stop over the target; 0 = fly on through it */
    uint8_t blocked;            /* the last step was refused (something solid in the way): stop and climb */
    uint8_t land;               /* 0.8: come down over the point to `hover` metres over the ground (a landing approach: gently near the ground) */
    uint8_t pad;
    hcb_vec face;               /* 0.6, on station in a fight: the line the fuselage is to lie along (flat; zero = as it is) -
                                   side-on to the threat, so a door looks at him; turned to when slow and near the point */
} hcb_pilot_in;
typedef struct hcb_pilot_out {
    hcb_vec pos;                /* where the helicopter is to be now */
    hcb_vec right;              /* how it is to be turned: the rows of the game's matrix */
    hcb_vec fwd;
    hcb_vec up;
    float dist;                 /* metres left (flat) */
    float speed;                /* metres a second (flat) */
    uint8_t arrived;            /* stopped over the target */
    uint8_t pad[3];
} hcb_pilot_out;
void hcb_pilot_reset(hcb_pilot *p, hcb_vec pos, hcb_vec vel, hcb_vec fwd);
void hcb_pilot_step(hcb_pilot *p, const hcb_pilot_in *in, hcb_pilot_out *out);

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
