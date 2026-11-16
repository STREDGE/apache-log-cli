/* Helicover Brain - core: memory of contacts, threat assessment, alert level, black box.
 * Plain C, no libc, no game code, no allocation. Only + - * / on floats (and -ffp-contract=off in the build), so a
 * recorded fight replays bit for bit on any machine. */
#include "hcb_int.h"

/* ------------------------------------------------------------------ weapons */
API int hcb_weapon_class(int w) {
    if (w <= 0) return HCB_WC_NONE;
    if (w <= 15) return HCB_WC_MELEE;
    if (w <= 18 || w == 39) return HCB_WC_THROWN;
    if (w <= 24) return HCB_WC_PISTOL;
    if (w <= 27) return HCB_WC_SHOTGUN;
    if (w == 28 || w == 29 || w == 32) return HCB_WC_SMG;
    if (w == 30 || w == 31) return HCB_WC_RIFLE;
    if (w == 33 || w == 34) return HCB_WC_SNIPER;
    if (w >= 35 && w <= 38) return HCB_WC_HEAVY;
    return HCB_WC_NONE;                       /* spray can, camera, parachute... */
}
API float hcb_weapon_dps(int w) {
    switch (hcb_weapon_class(w)) {
    case HCB_WC_MELEE: return w == 9 ? 60 : w == 4 || w == 8 ? 30 : 15;
    case HCB_WC_THROWN: return 80;
    case HCB_WC_PISTOL: return w == 24 ? 90 : 55;
    case HCB_WC_SHOTGUN: return 110;
    case HCB_WC_SMG: return 130;
    case HCB_WC_RIFLE: return 180;
    case HCB_WC_SNIPER: return 100;
    case HCB_WC_HEAVY: return w == 38 ? 900 : 400;
    }
    return 8;                                 /* fists */
}
API float hcb_weapon_range(int w) {
    switch (hcb_weapon_class(w)) {
    case HCB_WC_MELEE: return 2.2f;
    case HCB_WC_THROWN: return 30;
    case HCB_WC_PISTOL: return 35;
    case HCB_WC_SHOTGUN: return 25;
    case HCB_WC_SMG: return 40;
    case HCB_WC_RIFLE: return 80;
    case HCB_WC_SNIPER: return 200;
    case HCB_WC_HEAVY: return 90;
    }
    return 1.6f;
}
HID int hcb_is_firearm(int w) { int c = hcb_weapon_class(w); return c >= HCB_WC_PISTOL && c <= HCB_WC_HEAVY; }

API u32 hcb_brain_size(void) { return sizeof(struct hcb_brain); }
API u32 hcb_struct_size(int which) {
    switch (which) {
    case 0: return sizeof(hcb_ped);
    case 1: return sizeof(hcb_veh);
    case 2: return sizeof(hcb_event);
    case 3: return sizeof(hcb_snapshot);
    case 4: return sizeof(hcb_out);
    case 5: return sizeof(hcb_cfg);
    case 6: return sizeof(hcb_mark);
    case 7: return sizeof(hcb_track_info);
    case 8: return sizeof(hcb_rec);
    case 9: return sizeof(hcb_box_head);
    case 10: return sizeof(hcb_los);
    case 11: return sizeof(hcb_order);
    case 12: return sizeof(hcb_shot);
    case 13: return sizeof(hcb_round);
    case 14: return sizeof(hcb_pilot);
    case 15: return sizeof(hcb_pilot_in);
    case 16: return sizeof(hcb_pilot_out);
    }
    return 0;
}
API hcb_cfg *hcb_config(hcb_brain *b) { return &b->cfg; }
API int hcb_places_get(const hcb_brain *b, hcb_vec *at, u16 *count) {
    int i, n = b->dt.places > 16 ? 16 : b->dt.places;
    for (i = 0; i < n; i++) { at[i] = b->dt.place[i]; count[i] = b->dt.place_n[i]; }
    return n;
}
API void hcb_places_set(hcb_brain *b, const hcb_vec *at, const u16 *count, int n) {
    int i;
    if (n < 0) n = 0;
    if (n > 16) n = 16;
    for (i = 0; i < n; i++) { b->dt.place[i] = at[i]; b->dt.place_n[i] = count[i]; }
    b->dt.places = (u8)n; b->dt.places_dirty = 0;
}
API int hcb_places_changed(hcb_brain *b) { int d = b->dt.places_dirty; b->dt.places_dirty = 0; return d; }
API void hcb_init(hcb_brain *b, u32 seed) {
    zero(b, sizeof *b);
    b->seed = seed;
    b->rng = seed ? seed : 0x9e3779b9u;
    b->cfg.near_m = 40;
    b->cfg.watch_m = 60;
    b->cfg.facing_cos = 0.766f;              /* 40 degrees either side */
    b->cfg.aim_ms = 250;
    b->cfg.shot_pass_m = 3.0f;
    b->cfg.attacker_ms = 20000;
    b->cfg.forget_ms = 4000;
    b->cfg.ram_time_s = 1.5f;          /* (1.3: 2.0 and 2.5 m called 19 cars in 5.5 min that passed CJ by; none hit him) */
    b->cfg.ram_miss_m = 0.8f;
    b->cfg.ram_speed = 8.0f;
    b->cfg.burn_m = 14.0f;
    b->cfg.melee_m = 7.0f;
    b->cfg.calm_ms = 6000;
    b->cfg.evac_danger = 220;
    b->cfg.cj_line_m = 2.0f;
    b->cfg.line_per_m = 0.02f;
    b->cfg.friend_line_m = 1.25f;
    b->cfg.bystander_line_m = 0.8f;
    b->cfg.backstop_m = 40;
    b->cfg.explode_m = 18;
    b->cfg.car_floor = 700;
    b->cfg.react_min_ms = 150;
    b->cfg.react_max_ms = 350;
    b->cfg.burst_min_ms = 600;
    b->cfg.burst_max_ms = 1400;
    b->cfg.pause_min_ms = 200;
    b->cfg.pause_max_ms = 500;
    b->cfg.follow_ms = 3000;
    b->cfg.threat_hold_ms = 2000;
    b->cfg.ram_hold_ms = 1500;
    b->cfg.hit_hold_ms = 10000;
    b->cfg.muzzle_m = 5.5f;
    b->cfg.round_past_m = 0.6f;
    b->cfg.round_min_ms = 130;
    b->cfg.round_max_ms = 180;
    b->cfg.scatter_m = 0.06f;           /* 0.5: trained men - half the scatter of 0.4 (0.1 + 0.01 a metre) */
    b->cfg.scatter_per_m = 0.005f;
    b->cfg.scatter_per_ms = 0.02f;
    b->cfg.gunner_weapon = 1;
    b->cfg.cabin_skip_m = 1.5f;
    b->cfg.outer_peace_m = 21; b->cfg.outer_fight_m = 23; b->cfg.cj_low_hp = 40;
    b->cfg.gather_m = 32; b->cfg.rush_m = 8; b->cfg.assault_near_m = 9; b->cfg.fire_first_ms = 2000; b->cfg.search_ms = 6000;
    b->cfg.target_keep_ms = 20000; b->cfg.consolidate_ms = 8000; b->cfg.withdraw_down = 3;
    b->cfg.ow_min_h = 4; b->cfg.ow_max_h = 35; b->cfg.ow_min_d = 12; b->cfg.ow_max_d = 70; b->cfg.ow_try_ms = 40000;
    b->cfg.place_w_fire = 0.40f; b->cfg.place_w_open = 0.20f; b->cfg.place_w_others = 0.20f; b->cfg.place_w_dist = 0.20f;
    b->cfg.place_w_near = 0.15f; b->cfg.place_w_crowd = 0.20f; b->cfg.place_w_path = 0.12f; b->cfg.place_better = 1.2f; b->cfg.place_keep_ms = 4000;
    b->cfg.shooters_per_target = 3; b->cfg.movers_max = 3; b->cfg.reload_clip = 5; b->cfg.corner_ms = 800; b->cfg.door_ms = 1000;
}

HID track *hcb_find(hcb_brain *b, u32 id) {
    int i;
    if (!id) return 0;
    for (i = 0; i < HCB_MAX_TRACKS; i++) if (b->tr[i].used && b->tr[i].last.id == id) return &b->tr[i];
    return 0;
}
HID vtrack *hcb_vfind(hcb_brain *b, u32 id) {
    int i;
    if (!id) return 0;
    for (i = 0; i < HCB_MAX_VTRACKS; i++) if (b->vt[i].used && b->vt[i].last.id == id) return &b->vt[i];
    return 0;
}
/* A free slot, or the least valuable one: unseen before seen, harmless before dangerous, oldest first. */
static track *slot(hcb_brain *b) {
    int i, best = -1;
    u32 best_key = 0xffffffffu;
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        track *t = &b->tr[i];
        u32 key;
        if (!t->used) { best = i; break; }
        key = ((u32)t->seen << 30) | ((u32)(t->cls > HCB_CLS_NEUTRAL ? t->cls : 0) << 26) | ((t->last_seen >> 6) & 0x3ffffffu);
        if (key < best_key) { best_key = key; best = i; }
    }
    zero(&b->tr[best], sizeof(track));
    return &b->tr[best];
}
static track *touch(hcb_brain *b, u32 id, u32 now) {
    track *t = hcb_find(b, id);
    if (!t) { t = slot(b); t->used = 1; t->last.id = id; t->first_seen = now; t->last_seen = now; }
    return t;
}
HID int hcb_is_ours(const hcb_snapshot *s, u32 id) {
    int i;
    if (!id) return 0;
    for (i = 0; i < s->n_ours && i < HCB_MAX_OURS; i++) if (s->ours[i] == id) return 1;
    return id == s->heli;
}
HID const hcb_ped *hcb_ped_of(const hcb_snapshot *s, u32 id) {
    int i;
    if (id == s->player.id) return &s->player;
    for (i = 0; i < s->n_peds && i < HCB_MAX_PEDS; i++) if (s->peds[i].id == id) return &s->peds[i];
    return 0;
}
static int hostile_type(const hcb_snapshot *s, const hcb_ped *p) {
    if (p->flags & HCB_PF_HATES) return 1;
    if (p->pedtype == 6) return s->wanted > 0;
    return p->pedtype == 7 || (p->pedtype >= 9 && p->pedtype <= 13) || p->pedtype == 15 || p->pedtype == 16;
}
static int ally(const track *t, u32 now, const hcb_cfg *c) {
    const hcb_ped *p = &t->last;
    if (p->flags & HCB_PF_HATES) return 0;
    if (!(p->flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP)) && p->pedtype != 8) return 0;
    /* an ally who has put real damage into CJ lately is not one */
    return !(t->damage_cj >= 20 && now - t->last_hostile < (u32)c->attacker_ms);
}

/* A round from a to e: was it fired at the man standing at p? */
static int fired_at(hcb_vec a, hcb_vec e, hcb_vec p, float pass) {
    float t, d;
    hcb_vec dir = v_sub(e, a);
    float len = v_len(dir);
    if (len < 0.5f) return 0;
    /* the round carries on past the point the game reports (it may have stopped on a wall just short of him) */
    e = v_add(a, v_mul(dir, (len + 4.0f) / len));
    d = seg_dist(p, a, e, &t);
    return d <= pass && t > 0.02f;
}

/* 1.3: CJ's round marks a man for the squad only away from the muzzle (the second 2.0 log: a car that stood at CJ's side was
   "the man CJ fires at" for every round he fired past it - and the squad in ASSAULT fired at its driver) - unless the round ends at him */
static int cj_fired_at(hcb_vec a, hcb_vec e, hcb_vec p, float pass) {
    return fired_at(a, e, p, pass) && (v_dist(p, a) > 4.0f + pass || v_dist(p, e) < pass + 0.5f);
}

/* CJ or one of ours was hurt and the game does not say by whom. Run down: the nearest moving vehicle that is not ours
   did it, and its driver answers for it. Rounds from nowhere with a strange helicopter overhead: the helicopter. */
static void unknown_author(hcb_brain *b, const hcb_snapshot *s, const hcb_event *e) {
    const hcb_ped *victim = hcb_ped_of(s, e->dst);
    int to_cj = e->dst == s->player.id, i, best = -1, ram = e->weapon == 49 || e->weapon == 50;
    float best_d = ram ? 9.0f : 150.0f;
    if (!victim || (!to_cj && !hcb_is_ours(s, e->dst))) return;
    if (!ram && !hcb_is_firearm(e->weapon) && e->weapon != 52) return;
    for (i = 0; i < HCB_MAX_VTRACKS; i++) {
        const vtrack *v = &b->vt[i];
        float d;
        if (!v->used || !v->seen || v->last.id == s->heli || v->last.id == s->player.vehicle || hcb_is_ours(s, v->driver_was)) continue;
        if (ram ? (v->last.cls == HCB_VC_HELI || v->last.cls == HCB_VC_PLANE || v_dot(v->last.vel, v->last.vel) < 9.0f) : (v->last.cls != HCB_VC_HELI || !v->last.driver)) continue;
        d = v_dist(v->last.pos, victim->pos);
        if (d < best_d) { best_d = d; best = i; }
    }
    if (best < 0) return;
    if (ram) {
        /* the man at the wheel, or the one who has just jumped out of it, if he is still about */
        track *t = hcb_find(b, b->vt[best].driver_was);
        /* 1.3: a guard standing in the road and run down by the traffic is an accident, not an attack: only a car that was on a
           collision course, or a driver who is not a passer-by, answers for it */
        if (!b->vt[best].ram_n && !(b->vt[best].ram_until && e->time < b->vt[best].ram_until + 1000) && (!t || t->last.pedtype == 4 || t->last.pedtype == 5)) return;
        if (t) {
            if (to_cj) t->damage_cj += e->value; else t->damage_ours += e->value;
            t->last_hostile = e->time;
        }
        b->vt[best].hit_time = e->time;
    } else b->vt[best].air_fire = e->time;
}

static void on_event(hcb_brain *b, const hcb_snapshot *s, const hcb_event *e) {
    const hcb_cfg *c = &b->cfg;
    track *t;
    int i;
    if (e->type == HCB_EV_SHOT) {
        if (e->src && e->src == s->player.id) {      /* CJ's own fire points at people: the man he hit, or anybody his round passed close by */
            float dx = e->b.x - e->a.x, dy = e->b.y - e->a.y, l2 = dx * dx + dy * dy;
            if (l2 > 0.04f && l2 == l2) {
                float l = f_sqrt(l2);
                b->dt.cj_shot_t = e->time ? e->time : 1; b->dt.cj_shot_dir.x = dx / l; b->dt.cj_shot_dir.y = dy / l; b->dt.cj_shot_dir.z = 0;
            }
            if (e->dst && !hcb_is_ours(s, e->dst)) { t = hcb_find(b, e->dst); if (t) t->cj_marked = e->time; }
            for (i = 0; i < HCB_MAX_TRACKS; i++) {
                t = &b->tr[i];
                if (t->used && t->seen && !t->friendly && cj_fired_at(e->a, e->b, t->last.pos, 1.5f)) t->cj_marked = e->time;
            }
            /* ... and at vehicles: whoever sits in a car CJ is shooting at is CJ's target too */
            for (i = 0; i < HCB_MAX_VTRACKS; i++) {
                vtrack *v = &b->vt[i];
                if (v->used && v->seen && v->last.id != s->heli && (e->dst == v->last.id || cj_fired_at(e->a, e->b, v->last.pos, 2.5f))) v->cj_marked = e->time;
            }
            return;
        }
        if (!e->src || hcb_is_ours(s, e->src)) return;
        t = touch(b, e->src, s->time);
        if (!t->seen && !hcb_ped_of(s, e->src)) t->last.pos = e->a;     /* a shooter beyond the snapshot: at least where he is */
        t->shots_total++;
        t->last_shot = e->time;
        if (e->dst == s->player.id || fired_at(e->a, e->b, s->player.pos, c->shot_pass_m)) {
            t->shots_at_cj++; t->last_hostile = e->time; return;
        }
        if (hcb_is_ours(s, e->dst)) { t->shots_at_ours++; t->last_hostile = e->time; return; }
        for (i = 0; i < s->n_ours && i < HCB_MAX_OURS; i++) {
            const hcb_ped *o = hcb_ped_of(s, s->ours[i]);
            if (o && fired_at(e->a, e->b, o->pos, c->shot_pass_m)) { t->shots_at_ours++; t->last_hostile = e->time; return; }
        }
    } else if (e->type == HCB_EV_DAMAGE) {
        if (e->src == s->player.id) {                 /* CJ hit somebody: remembered, it is his business */
            if (e->dst && !hcb_is_ours(s, e->dst)) { t = touch(b, e->dst, s->time); t->cj_hit_him = e->time; t->cj_marked = e->time; }
            return;
        }
        if (hcb_is_ours(s, e->src)) return;
        if (!e->src) { unknown_author(b, s, e); return; }
        /* 1.3: run down by a passer-by's car that was not on a collision course: an accident */
        if ((e->weapon == 49 || e->weapon == 50) && (e->dst == s->player.id || hcb_is_ours(s, e->dst))) {
            const hcb_ped *p = hcb_ped_of(s, e->src);
            const vtrack *v = p ? hcb_vfind(b, p->vehicle) : 0;
            if (p && (p->pedtype == 4 || p->pedtype == 5) && (!v || (!v->ram_n && !(v->ram_until && e->time < v->ram_until + 1000)))) return;
        }
        if (e->dst == s->player.id) { t = touch(b, e->src, s->time); t->damage_cj += e->value; t->last_hostile = e->time; }
        else if (hcb_is_ours(s, e->dst)) { t = touch(b, e->src, s->time); t->damage_ours += e->value; t->last_hostile = e->time; }
        /* run down by a car whose driver the game named: the car is remembered as well */
        if ((e->weapon == 49 || e->weapon == 50) && (e->dst == s->player.id || hcb_is_ours(s, e->dst))) {
            const hcb_ped *p = hcb_ped_of(s, e->src);
            vtrack *v = p ? hcb_vfind(b, p->vehicle) : 0;
            if (v) v->hit_time = e->time;
        }
    }
}

static float hit_chance(float dist, float range) {
    float k;
    if (dist <= range * 0.3f) return 0.6f;
    if (dist >= range * 1.5f) return 0;
    k = (dist - range * 0.3f) / (range * 1.2f);
    return 0.6f - 0.55f * k;
}

static void judge(hcb_brain *b, const hcb_snapshot *s, track *t, float dt) {
    const hcb_cfg *c = &b->cfg;
    const hcb_ped *p = &t->last, *cj = &s->player;
    hcb_vec to_cj = v_sub(cj->pos, p->pos);
    float dist = v_len(to_cj), facing, closing, range = hcb_weapon_range(p->weapon);
    int armed = hcb_is_firearm(p->weapon), wclass = hcb_weapon_class(p->weapon), hostile = hostile_type(s, p);
    int on_foot = !p->vehicle, blocked = (p->flags2 & HCB_PF2_LOS_KNOWN) && !(p->flags2 & HCB_PF2_LOS_CLEAR);
    int aims_cj = p->target && p->target == cj->id, aims_ours = p->target && hcb_is_ours(s, p->target);
    int defensive = s->on_mission && !s->mission_free && (p->flags & HCB_PF_MISSION);
    int hunting = p->pedtype == 6 && s->wanted > 0;         /* a policeman with stars up is coming for CJ whichever way he looks */
    vtrack *car = hcb_vfind(b, p->vehicle);
    u32 now = s->time;
    u8 cls = HCB_CLS_NEUTRAL, why = HCB_WHY_NONE;
    float edps = 0;

    t->dist = dist;
    if (p->weapon > t->best_weapon && hcb_weapon_class(p->weapon) != HCB_WC_NONE) t->best_weapon = p->weapon;
    if (cj->target && cj->target == p->id) t->cj_marked = now;      /* CJ has him in his sights */
    if (car && car->cj_marked > t->cj_marked) t->cj_marked = car->cj_marked;
    facing = dist > 0.01f ? v_dot(p->fwd, to_cj) / dist : 1;
    closing = dist > 0.01f ? v_dot(p->vel, to_cj) / dist : 0;

    /* a weapon held on CJ or on one of ours: the clock runs while it is, and runs back twice as fast when it is not */
    if ((aims_cj || aims_ours) && (armed || (wclass <= HCB_WC_MELEE && dist < 4))) {
        t->aim_ms = f_min(t->aim_ms + dt, c->aim_ms + 350); t->aims_at_ours = aims_ours && !aims_cj;
    } else t->aim_ms = f_max(0, t->aim_ms - 2 * dt);
    /* latched: he becomes a threat after aim_ms on target and stays one until the clock has run all the way back */
    if (t->aim_ms >= c->aim_ms) t->aim_latch = 1;
    else if (t->aim_ms <= 0) t->aim_latch = 0;

    if (hcb_is_ours(s, p->id)) { t->friendly = 1; t->cls = HCB_CLS_FRIEND; t->why = HCB_WHY_OURS; t->edps = 0; return; }
    t->friendly = (u8)ally(t, now, c);
    if (t->friendly) { t->cls = HCB_CLS_FRIEND; t->why = HCB_WHY_ALLY; t->edps = 0; return; }

    if (t->last_hostile && now - t->last_hostile < (u32)c->attacker_ms) {
        cls = HCB_CLS_ATTACKER;
        why = t->damage_cj > 0 ? HCB_WHY_HURT_CJ : t->shots_at_cj ? HCB_WHY_SHOT_AT_CJ : t->damage_ours > 0 ? HCB_WHY_HURT_OURS : HCB_WHY_SHOT_AT_OURS;
    } else if (t->aim_latch) {
        cls = HCB_CLS_THREAT; why = t->aims_at_ours ? HCB_WHY_AIMS_AT_OURS : HCB_WHY_AIMS_AT_CJ;
    } else if (hostile && armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked) {
        cls = HCB_CLS_THREAT; why = HCB_WHY_ARMED_FACING;
    } else if ((hostile || aims_cj) && wclass <= HCB_WC_MELEE && on_foot && dist <= c->melee_m && closing > 2.0f
               && facing >= c->facing_cos && (wclass == HCB_WC_MELEE || aims_cj)) {
        cls = HCB_CLS_THREAT; why = HCB_WHY_MELEE_CLOSING;
    } else if (hostile && armed && dist <= c->watch_m) {
        cls = HCB_CLS_WATCH; why = HCB_WHY_ARMED_NEAR;
    } else if (hostile && on_foot && dist <= 15) {
        cls = HCB_CLS_WATCH; why = HCB_WHY_HOSTILE_NEAR;
    } else if (t->last_shot && now - t->last_shot < 5000 && dist <= 80) {
        cls = HCB_CLS_WATCH; why = HCB_WHY_SHOOTING_NEARBY;
    }
    /* A THREAT that rests on a pose (turned to CJ, running at him, nothing in between) does not blink with the pose:
       it is kept for threat_hold_ms while the man is still armed, hostile and about as near. */
    if (cls == HCB_CLS_THREAT && (why == HCB_WHY_ARMED_FACING || why == HCB_WHY_MELEE_CLOSING)) {
        t->hold_until = now + (u32)c->threat_hold_ms; t->hold_why = why;
    } else if (cls < HCB_CLS_THREAT && t->hold_why && now < t->hold_until && t->seen && on_foot
               && (t->hold_why == HCB_WHY_ARMED_FACING ? hostile && armed && dist <= c->near_m * 1.25f
                                                       : (hostile || aims_cj) && dist <= c->melee_m * 1.5f)) {
        cls = HCB_CLS_THREAT; why = t->hold_why;
    } else if (cls != HCB_CLS_THREAT || now >= t->hold_until) t->hold_why = 0;
    /* in a mission the people of the mission are left to the mission until they act against CJ */
    if (defensive && cls == HCB_CLS_THREAT && why != HCB_WHY_AIMS_AT_CJ && why != HCB_WHY_AIMS_AT_OURS) cls = HCB_CLS_WATCH;

    if (cls >= HCB_CLS_WATCH) {
        float k = cls == HCB_CLS_ATTACKER ? 1.0f : why == HCB_WHY_AIMS_AT_CJ ? 0.8f : cls == HCB_CLS_THREAT ? 0.4f : 0.1f;
        if (armed) edps = hcb_weapon_dps(p->weapon) * hit_chance(dist, range) * k;
        else if (why == HCB_WHY_MELEE_CLOSING || (cls == HCB_CLS_ATTACKER && dist < 4)) edps = hcb_weapon_dps(p->weapon) * (dist < 2.5f ? 1.0f : 0.3f) * k;
        if (blocked) edps *= 0.05f;
        if (!t->seen) edps *= 0.25f;         /* out of sight: he may come back, but he is not hitting CJ now */
    }
    t->cls = cls; t->why = why; t->edps = edps;
}

static void judge_vehicle(hcb_brain *b, const hcb_snapshot *s, vtrack *v) {
    const hcb_cfg *c = &b->cfg;
    const hcb_veh *h = &v->last;
    const hcb_ped *cj = &s->player;
    hcb_vec rel = v_sub(cj->pos, h->pos), rv = v_sub(h->vel, cj->vel);
    float speed2 = v_dot(rv, rv), dist = v_len(rel);
    track *drv = hcb_find(b, h->driver);
    u32 now = s->time;
    v->dist = dist; v->cls = HCB_CLS_NEUTRAL; v->why = HCB_WHY_NONE; v->edps = 0;
    if (h->id == s->heli || h->id == cj->vehicle || (drv && drv->friendly) || hcb_is_ours(s, h->driver)) { v->cls = HCB_CLS_FRIEND; v->why = HCB_WHY_OURS; return; }
    if ((h->flags & HCB_VF_BURNING) && !(h->flags & HCB_VF_WRECKED) && dist <= c->burn_m) {
        v->cls = HCB_CLS_THREAT; v->why = HCB_WHY_BURNING; v->edps = 60 * (1 - dist / (c->burn_m * 1.5f)); return;
    }
    /* collision course: closest approach of the car to CJ within the look-ahead time.
       1.3 (the first 2.0 log: 19 cars "on a collision course" in 5.5 min, none hit CJ - the game's drivers brake and swerve
       round a man; several were dead on for half a second and passed 5-7 m off): it has to be dead on (0.8 m) and close (1.5 s)
       on two looks running before it is a ram */
    if (!cj->vehicle && speed2 >= c->ram_speed * c->ram_speed && h->cls != HCB_VC_HELI && h->cls != HCB_VC_PLANE) {   /* (with or without a driver) */
        float tca = v_dot(rel, rv) / speed2;
        int on = 0;
        if (tca > 0 && tca <= c->ram_time_s) {
            hcb_vec at = v_sub(rel, v_mul(rv, tca));
            at.z = 0;
            on = v_len(at) <= c->ram_miss_m && f_abs(rel.z) < 3;
        }
        if (on) { if (v->ram_n < 255) v->ram_n++; } else v->ram_n = 0;
        if (on && v->ram_n >= 2) {
            v->cls = HCB_CLS_THREAT; v->why = HCB_WHY_RAMMING; v->edps = 70 * (1 - tca / (c->ram_time_s * 1.5f));
            v->ram_until = now + (u32)c->ram_hold_ms; v->ram_edps = v->edps;
            return;
        }
    } else v->ram_n = 0;
    if (!cj->vehicle && h->cls != HCB_VC_HELI && h->cls != HCB_VC_PLANE) {
        float own2 = v_dot(h->vel, h->vel);
        /* it was on a collision course a moment ago and is still coming fast: one swerve does not make it harmless */
        if (v->ram_until && now < v->ram_until && speed2 >= c->ram_speed * c->ram_speed * 0.25f && v_dot(rel, rv) > 0) {   /* (1.3: and still closing) */
            v->cls = HCB_CLS_THREAT; v->why = HCB_WHY_RAMMING; v->edps = v->ram_edps * 0.6f; return;
        }
        /* it has already run into CJ or one of ours and is still driving about */
        if (v->hit_time && now - v->hit_time < (u32)c->hit_hold_ms && own2 >= 4.0f && dist <= 60) {
            v->cls = HCB_CLS_THREAT; v->why = HCB_WHY_RAMMING; v->edps = 30; return;
        }
    }
    if (h->cls == HCB_VC_HELI && v->air_fire && now - v->air_fire < 15000 && dist <= 200) {
        v->cls = HCB_CLS_THREAT; v->why = HCB_WHY_AIR_FIRE; v->edps = 25; return;
    }
    if (drv && drv->cls >= HCB_CLS_WATCH) { v->cls = drv->cls; v->why = drv->why; }
}

HID u32 hcb_fnv(u32 h, u32 v) {
    int i;
    for (i = 0; i < 4; i++) { h ^= (v >> (8 * i)) & 0xff; h *= 16777619u; }
    return h;
}
HID u32 hcb_bits(float f) { union { float f; u32 i; } u; u.f = f; return u.i; }
HID u32 hcb_rand(hcb_brain *b) { u32 x = b->rng; x ^= x << 13; x ^= x >> 17; x ^= x << 5; b->rng = x; return x; }
/* marks ordered: most dangerous class first, then expected damage, then nearest */
static int before(const hcb_mark *a, const hcb_mark *b) {
    if (a->cls != b->cls) return a->cls > b->cls;
    if (a->edps != b->edps) return a->edps > b->edps;
    if (a->dist != b->dist) return a->dist < b->dist;
    return a->id < b->id;
}
static void add_mark(hcb_out *o, hcb_mark m) {
    int n = o->n_marks, i;
    if (n == HCB_MAX_MARKS) { if (!before(&m, &o->marks[n - 1])) return; n--; }
    for (i = n; i > 0 && before(&m, &o->marks[i - 1]); i--) o->marks[i] = o->marks[i - 1];
    o->marks[i] = m;
    o->n_marks = (u8)(n + 1);
}

API void hcb_think(hcb_brain *b, const hcb_snapshot *s, hcb_out *out) {
    const hcb_cfg *c = &b->cfg;
    u32 now = s->time, h = 2166136261u;
    float dt = b->started ? (float)(now - b->time) : 0, danger = 0;
    int i, want, n_ped = s->n_peds < HCB_MAX_PEDS ? s->n_peds : HCB_MAX_PEDS, n_veh = s->n_vehs < HCB_MAX_VEHS ? s->n_vehs : HCB_MAX_VEHS;
    int n_ev = s->n_events < HCB_MAX_EVENTS ? s->n_events : HCB_MAX_EVENTS, threats = 0, attackers = 0, watch = 0;

    if (dt < 0 || dt > 2000) dt = 0;          /* a loaded game or a long pause: no time has passed for the clocks */
    for (i = 0; i < HCB_MAX_TRACKS; i++) b->tr[i].seen = 0;
    for (i = 0; i < HCB_MAX_VTRACKS; i++) b->vt[i].seen = 0;

    for (i = 0; i < n_ped; i++) {
        const hcb_ped *p = &s->peds[i];
        track *t;
        if (!p->id || p->id == s->player.id) continue;
        if (p->flags & HCB_PF_DEAD) {
            t = hcb_find(b, p->id);
            if (t) {                                   /* he died while one of ours was firing at him: ours */
                int k;
                for (k = 0; k < HCB_MAX_OURS; k++) if (b->sh[k].used && b->sh[k].target == p->id && b->sh[k].last_fire && now - b->sh[k].last_fire <= 1500) break;
                if (k < HCB_MAX_OURS && !t->friendly) b->kills++;
                t->used = 0;
            }
            continue;
        }
        t = touch(b, p->id, now);
        t->last = *p; t->seen = 1; t->last_seen = now;
    }
    for (i = 0; i < n_veh; i++) {
        const hcb_veh *v = &s->vehs[i];
        int k, free_k = -1, old_k = 0;
        vtrack *t = 0;
        if (!v->id) continue;
        for (k = 0; k < HCB_MAX_VTRACKS; k++) {
            if (b->vt[k].used && b->vt[k].last.id == v->id) { t = &b->vt[k]; break; }
            if (!b->vt[k].used) { if (free_k < 0) free_k = k; }
            else if (b->vt[k].last_seen < b->vt[old_k].last_seen) old_k = k;
        }
        if (!t) { t = &b->vt[free_k >= 0 ? free_k : old_k]; zero(t, sizeof *t); t->used = 1; }
        t->last = *v; t->seen = 1; t->last_seen = now;
        if (v->driver) t->driver_was = v->driver;
    }
    for (i = 0; i < n_ev; i++) on_event(b, s, &s->events[i]);

    zero(out, sizeof *out);
    out->time = now;
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        track *t = &b->tr[i];
        u32 keep;
        if (!t->used) continue;
        judge(b, s, t, dt);
        /* how long an unseen contact is remembered depends on what he was */
        keep = t->cls == HCB_CLS_ATTACKER ? (u32)c->attacker_ms : t->cls >= HCB_CLS_WATCH ? (u32)(c->forget_ms * 3) : (u32)c->forget_ms;
        if (!t->seen && now - t->last_seen > keep) t->used = 0;
    }
    for (i = 0; i < HCB_MAX_VTRACKS; i++) {
        vtrack *v = &b->vt[i];
        hcb_mark m;
        track *drv;
        if (!v->used) continue;
        if (!v->seen) { if (now - v->last_seen > (u32)c->forget_ms) v->used = 0; continue; }
        judge_vehicle(b, s, v);
        if (v->why != HCB_WHY_RAMMING && v->why != HCB_WHY_BURNING && v->why != HCB_WHY_AIR_FIRE) continue;     /* occupants are marked as people */
        /* whoever drives a car at CJ is a threat for as long as he does - 1.3: once his car has hit CJ or one of ours; before that
           the car is called and dodged, the driver is not shot (the first 2.0 log: half the guards' fire went at drivers of cars
           passing by, and it earned the wanted level) */
        drv = v->why == HCB_WHY_RAMMING && v->hit_time && now - v->hit_time < (u32)c->hit_hold_ms ? hcb_find(b, v->last.driver) : 0;
        if (drv && !drv->friendly && drv->cls < HCB_CLS_THREAT) { drv->cls = HCB_CLS_THREAT; drv->why = HCB_WHY_RAMMING; drv->edps = v->edps; }
        else { threats++; danger += v->edps; }
        m.id = v->last.id; m.edps = v->edps; m.dist = v->dist; m.kind = HCB_KIND_VEH; m.cls = v->cls; m.why = v->why; m.seen = 1;
        add_mark(out, m);
    }
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        track *t = &b->tr[i];
        hcb_mark m;
        if (!t->used) continue;
        if (t->cls == HCB_CLS_ATTACKER) attackers++;
        if (t->cls >= HCB_CLS_THREAT) threats++;
        if (t->cls == HCB_CLS_WATCH) watch++;
        danger += t->edps;
        if (t->cls == HCB_CLS_NEUTRAL) continue;
        m.id = t->last.id; m.edps = t->edps; m.dist = t->dist; m.kind = HCB_KIND_PED; m.cls = t->cls; m.why = t->why; m.seen = t->seen;
        add_mark(out, m);
    }

    want = attackers ? HCB_ALERT_COMBAT : threats ? HCB_ALERT_THREAT : watch ? HCB_ALERT_WARY : HCB_ALERT_CALM;
    if (danger >= c->evac_danger || (attackers && s->player.health > 0 && s->player.health < 30)) want = HCB_ALERT_EVACUATE;
    if (s->cutscene) want = HCB_ALERT_CALM;
    if (want >= b->alert) {
        if (want > b->alert) { b->alert = (u8)want; b->alert_since = now; }
        b->calm_since = now;
    } else if (now - b->calm_since >= (u32)c->calm_ms) {      /* quiet long enough: one step down, not straight to calm */
        b->alert--; b->alert_since = now; b->calm_since = now;
    }

    out->alert = b->alert; out->danger = danger; out->kills = (u16)b->kills;
    out->n_threats = (u8)(threats > 255 ? 255 : threats); out->n_attackers = (u8)(attackers > 255 ? 255 : attackers);
    hcb_fire_plan(b, s, out);
    for (i = 0; i < out->n_orders; i++) {
        const hcb_order *o = &out->orders[i];
        h = hcb_fnv(h, o->who); h = hcb_fnv(h, o->target); h = hcb_fnv(h, ((u32)o->fire << 24) | ((u32)o->aim_at << 16) | ((u32)o->hold << 8) | o->ready);
    }
    for (i = 0; i < out->n_queries; i++) { h = hcb_fnv(h, out->queries[i].from); h = hcb_fnv(h, out->queries[i].to); }
    /* 1.0: the map first (it takes the answers and asks for more ground), then where everybody is to be (the detail in
       PROTECT, the squad over it in ASSAULT), then each man's own way there */
    hcb_nav_update(b, s, out, b->sq.umode == HCB_UMODE_ASSAULT && b->sq.target_seen && !s->recall ? b->sq.front : s->player.pos);
    hcb_detail_plan(b, s, out);
    hcb_squad_plan(b, s, out);
    hcb_marksman_plan(b, s, out);
    hcb_agent_plan(b, s, out);
    for (i = 0; i < out->n_posts; i++) {
        const hcb_post *p = &out->posts[i];
        h = hcb_fnv(h, p->who); h = hcb_fnv(h, hcb_bits(p->at.x)); h = hcb_fnv(h, hcb_bits(p->at.y));
        h = hcb_fnv(h, ((u32)p->move << 24) | ((u32)p->crouch << 16) | ((u32)p->duty << 8) | p->job);
        h = hcb_fnv(h, hcb_bits(p->via.x)); h = hcb_fnv(h, hcb_bits(p->via.y)); h = hcb_fnv(h, ((u32)p->act << 16) | ((u32)p->phase << 8) | p->why);
        h = hcb_fnv(h, hcb_bits(p->via2.x)); h = hcb_fnv(h, hcb_bits(p->via2.y)); h = hcb_fnv(h, ((u32)p->sign << 16) | ((u32)p->climb << 8) | p->face);
    }
    h = hcb_fnv(h, ((u32)out->task << 24) | ((u32)out->umode << 16) | ((u32)out->n_ground_q << 8) | out->n_seg_q); h = hcb_fnv(h, out->target); h = hcb_fnv(h, out->n_path_q);
    h = hcb_fnv(h, ((u32)out->ow_ok << 8) | out->ow_ready);
    for (i = 0; i < out->n_probe_q; i++) { h = hcb_fnv(h, hcb_bits(out->probe_q[i].at.x)); h = hcb_fnv(h, hcb_bits(out->probe_q[i].at.y)); }
    h = hcb_fnv(h, ((u32)out->say << 24) | ((u32)out->say_dir << 16) | out->say_seq); h = hcb_fnv(h, ((u32)out->cover_ok << 8) | out->duty);
    for (i = 0; i < out->n_marks; i++) {
        const hcb_mark *m = &out->marks[i];
        if (m->cls >= HCB_CLS_WATCH && !out->top) out->top = m->id;
        h = hcb_fnv(h, m->id); h = hcb_fnv(h, ((u32)m->kind << 24) | ((u32)m->cls << 16) | ((u32)m->why << 8) | m->seen); h = hcb_fnv(h, hcb_bits(m->edps));
    }
    h = hcb_fnv(h, out->alert); h = hcb_fnv(h, hcb_bits(danger)); h = hcb_fnv(h, out->kills);
    out->digest = h;
    b->time = now; b->ticks++; b->started = 1;
}

API int hcb_track(const hcb_brain *b, u32 id, hcb_track_info *o) {
    const track *t = hcb_find((hcb_brain *)b, id);
    if (!t) return 0;
    zero(o, sizeof *o);
    o->id = id; o->first_seen = t->first_seen; o->last_seen = t->last_seen; o->last_hostile = t->last_hostile;
    o->damage_cj = t->damage_cj; o->damage_ours = t->damage_ours; o->aim_ms = t->aim_ms;
    o->shots_at_cj = t->shots_at_cj; o->shots_at_ours = t->shots_at_ours; o->shots_total = t->shots_total;
    o->cls = t->cls; o->why = t->why; o->best_weapon = t->best_weapon; o->friendly = t->friendly; o->last_pos = t->last.pos;
    return 1;
}

/* ------------------------------------------------------------------ black box
 * A record: u32 length of the whole record, u32 kind, then
 *   snapshot: u32 digest, the head of the snapshot (everything before `ours`), then only the used entries of
 *             ours / our_role / peds / vehs / events;
 *   state:    the brain's memory, byte for byte. */
#define HEAD ((u32)__builtin_offsetof(hcb_snapshot, ours))
/* 0.8: what stands after the lines of sight (the game's cover points, the dangers) is recorded whole */
#define TAIL_AT ((u32)__builtin_offsetof(hcb_snapshot, n_hints))
#define TAIL ((u32)(sizeof(hcb_snapshot) - TAIL_AT))
static u32 put(u8 *buf, u32 at, const void *src, u32 n) { copy(buf + at, src, n); return at + n; }
static u32 rd32(const u8 *p) { return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24); }
API void hcb_rec_init(hcb_rec *r, u32 cap) { zero(r, sizeof *r); r->cap = cap; }
/* Room for `need` bytes at the end: forget the oldest records until half the buffer is free, then slide the rest
   to the front. Returns 0 when the record can never fit. */
static int make_room(hcb_rec *r, u8 *buf, u32 need) {
    u32 i;
    if (need > r->cap / 2) return 0;
    if (r->end + need <= r->cap) return 1;
    while (r->start < r->end && r->end - r->start > r->cap / 2) { r->start += rd32(buf + r->start); r->dropped++; r->records--; }
    for (i = 0; i < r->end - r->start; i++) buf[i] = buf[r->start + i];
    r->end -= r->start; r->start = 0;
    return 1;
}
static u32 snapshot_len(u32 no, u32 np, u32 nv, u32 ne, u32 nl) {
    return 12 + HEAD + no * 4 + ((no + 3) & ~3u) + np * sizeof(hcb_ped) + nv * sizeof(hcb_veh) + ne * sizeof(hcb_event) + nl * sizeof(hcb_los) + TAIL;
}
API void hcb_rec_push(hcb_rec *r, u8 *buf, const hcb_snapshot *s, u32 digest) {
    u32 no = s->n_ours < HCB_MAX_OURS ? s->n_ours : HCB_MAX_OURS, np = s->n_peds < HCB_MAX_PEDS ? s->n_peds : HCB_MAX_PEDS;
    u32 nv = s->n_vehs < HCB_MAX_VEHS ? s->n_vehs : HCB_MAX_VEHS, ne = s->n_events < HCB_MAX_EVENTS ? s->n_events : HCB_MAX_EVENTS;
    u32 nl = s->n_los < HCB_MAX_LOS ? s->n_los : HCB_MAX_LOS;
    u32 need = snapshot_len(no, np, nv, ne, nl), kind = HCB_REC_SNAPSHOT, at, head_at;
    u8 pad[4] = {0, 0, 0, 0};
    u16 n;
    if (!make_room(r, buf, need)) return;
    at = r->end;
    at = put(buf, at, &need, 4); at = put(buf, at, &kind, 4); at = put(buf, at, &digest, 4);
    head_at = at; at = put(buf, at, s, HEAD);
    /* the counts in the record are the ones really written (a snapshot may claim more than the arrays hold) */
    n = (u16)np; copy(buf + head_at + __builtin_offsetof(hcb_snapshot, n_peds), &n, 2);
    n = (u16)nv; copy(buf + head_at + __builtin_offsetof(hcb_snapshot, n_vehs), &n, 2);
    n = (u16)ne; copy(buf + head_at + __builtin_offsetof(hcb_snapshot, n_events), &n, 2);
    n = (u16)no; copy(buf + head_at + __builtin_offsetof(hcb_snapshot, n_ours), &n, 2);
    n = (u16)nl; copy(buf + head_at + __builtin_offsetof(hcb_snapshot, n_los), &n, 2);
    at = put(buf, at, s->ours, no * 4); at = put(buf, at, s->our_role, no); at = put(buf, at, pad, ((no + 3) & ~3u) - no);
    at = put(buf, at, s->peds, np * sizeof(hcb_ped)); at = put(buf, at, s->vehs, nv * sizeof(hcb_veh)); at = put(buf, at, s->events, ne * sizeof(hcb_event));
    at = put(buf, at, s->los, nl * sizeof(hcb_los));
    at = put(buf, at, (const u8 *)s + TAIL_AT, TAIL);
    r->end = at; r->records++;
}
API void hcb_rec_push_state(hcb_rec *r, u8 *buf, const hcb_brain *b) {
    u32 need = 8 + sizeof(struct hcb_brain), kind = HCB_REC_STATE, at;
    if (!make_room(r, buf, need)) return;
    at = r->end;
    at = put(buf, at, &need, 4); at = put(buf, at, &kind, 4); at = put(buf, at, b, sizeof(struct hcb_brain));
    r->end = at; r->records++;
}
API void hcb_rec_push_round(hcb_rec *r, u8 *buf, const hcb_round *round) {
    u32 need = 8 + sizeof(hcb_round), kind = HCB_REC_ROUND, at;
    if (!make_room(r, buf, need)) return;
    at = r->end;
    at = put(buf, at, &need, 4); at = put(buf, at, &kind, 4); at = put(buf, at, round, sizeof(hcb_round));
    r->end = at; r->records++;
}
API int hcb_rec_next(const u8 *buf, u32 end, u32 *offset, hcb_snapshot *s, u32 *digest, hcb_brain *state, hcb_round *round) {
    u32 at = *offset, len, kind, no, np, nv, ne, nl;
    if (at + 8 > end) return 0;
    len = rd32(buf + at); kind = rd32(buf + at + 4);
    if (len < 8 || len > end - at) return 0;
    if (kind == HCB_REC_STATE) {
        if (len != 8 + sizeof(struct hcb_brain)) { *offset = at + len; return HCB_REC_OTHER; }    /* (1.3: a state of another brain: skipped) */
        if (state) copy(state, buf + at + 8, sizeof(struct hcb_brain));
        *offset = at + len;
        return HCB_REC_STATE;
    }
    if (kind == HCB_REC_ROUND) {
        if (len != 8 + sizeof(hcb_round)) return 0;
        if (round) copy(round, buf + at + 8, sizeof(hcb_round));
        *offset = at + len;
        return HCB_REC_ROUND;
    }
    if (kind != HCB_REC_SNAPSHOT || len < 12 + HEAD) return 0;
    zero(s, sizeof *s);
    if (digest) *digest = rd32(buf + at + 8);
    copy(s, buf + at + 12, HEAD);
    no = s->n_ours; np = s->n_peds; nv = s->n_vehs; ne = s->n_events; nl = s->n_los;
    if (no > HCB_MAX_OURS || np > HCB_MAX_PEDS || nv > HCB_MAX_VEHS || ne > HCB_MAX_EVENTS || nl > HCB_MAX_LOS) return 0;
    if (snapshot_len(no, np, nv, ne, nl) != len) return 0;
    at += 12 + HEAD;
    copy(s->ours, buf + at, no * 4); at += no * 4;
    copy(s->our_role, buf + at, no); at += (no + 3) & ~3u;
    copy(s->peds, buf + at, np * sizeof(hcb_ped)); at += np * sizeof(hcb_ped);
    copy(s->vehs, buf + at, nv * sizeof(hcb_veh)); at += nv * sizeof(hcb_veh);
    copy(s->events, buf + at, ne * sizeof(hcb_event)); at += ne * sizeof(hcb_event);
    copy(s->los, buf + at, nl * sizeof(hcb_los)); at += nl * sizeof(hcb_los);
    copy((u8 *)s + TAIL_AT, buf + at, TAIL); at += TAIL;
    if (s->n_hints > HCB_MAX_HINTS) s->n_hints = HCB_MAX_HINTS;
    if (s->n_dangers > HCB_MAX_DANGERS) s->n_dangers = HCB_MAX_DANGERS;
    *offset = at;
    return HCB_REC_SNAPSHOT;
}
API void hcb_box_head_fill(hcb_box_head *h, const hcb_rec *r, const hcb_brain *b, u32 text_len) {
    static const char magic[8] = {'H', 'C', 'B', 'B', 'O', 'X', '1', 0};
    zero(h, sizeof *h);
    copy(h->magic, magic, 8);
    h->version = HCB_VERSION; h->brain_size = sizeof(struct hcb_brain); h->snapshot_size = sizeof(hcb_snapshot);
    h->ped_size = sizeof(hcb_ped); h->veh_size = sizeof(hcb_veh); h->event_size = sizeof(hcb_event);
    h->records = r->records; h->dropped = r->dropped; h->data_len = r->end - r->start; h->text_len = text_len; h->seed = b->seed;
}
