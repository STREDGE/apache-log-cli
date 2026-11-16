/* Helicover Brain - fire: who of ours shoots at whom, and when nobody may.
 *
 * Every tick: (1) the contacts the player's fire rule allows; (2) for every shooter and every such contact the hard
 * rules - CJ, our own people and bystanders in or behind the line, vehicles that could blow up next to CJ, range,
 * the far side of the helicopter, what is known about the line of sight; (3) targets handed out so that the damage
 * CJ can expect falls fastest (two on the worst threat, the rest spread); (4) human timing - a reaction time before
 * the first round at a new target, bursts and pauses. Spare shooters cover suspects without firing.
 *
 * The hard rules are checked on every tick for the pair as it is NOW; an order to fire never outlives the tick. */
#include "hcb_int.h"

#define MAX_CAND 32
#define SOFT_LOS 100        /* internal: the line of sight is not known yet - he may take the man and bring his weapon round, not fire */

typedef struct cand {
    track *t;
    float value;        /* expected damage per second he does to CJ (a floor for those CJ points at) */
    u8 fire;            /* the fire rule allows shooting him; 0 = cover only */
    u8 taken;           /* shooters already on him */
    u8 free;            /* a man who is not firing at anybody could take him */
} cand;

static losent *los_find(hcb_brain *b, u32 from, u32 to) {
    int i;
    for (i = 0; i < HCB_LOS_CACHE; i++) if (b->los[i].used && b->los[i].from == from && b->los[i].to == to) return &b->los[i];
    return 0;
}
static void los_store(hcb_brain *b, u32 from, u32 to, int clear, u32 now) {
    losent *e = los_find(b, from, to);
    int i, old = 0;
    if (!e) {
        for (i = 0; i < HCB_LOS_CACHE; i++) {
            if (!b->los[i].used) { old = i; break; }
            if (b->los[i].time < b->los[old].time) old = i;
        }
        e = &b->los[old];
    }
    e->used = 1; e->from = from; e->to = to; e->clear = (u8)(clear != 0); e->time = now;
}
static void ask(hcb_out *out, u32 from, u32 to) {
    int i;
    for (i = 0; i < out->n_queries; i++) if (out->queries[i].from == from && out->queries[i].to == to) return;
    if (out->n_queries >= HCB_MAX_LOS) return;
    out->queries[out->n_queries].from = from; out->queries[out->n_queries].to = to; out->n_queries++;
}

/* Is the man at p in the way of a round from a to e, or behind the target within `behind` metres?
   Returns 0 no, 1 in the line, 2 behind the target. Somebody level with or behind the muzzle (the first `skip`
   metres of the line) is not in the line. */
static int in_line(hcb_vec a, hcb_vec e, hcb_vec p, float margin, float per_m, float behind, float behind_margin, float skip) {
    hcb_vec d = v_sub(e, a), ap = v_sub(p, a);
    float len = v_len(d), along, lat2, m;
    if (len < 0.01f) return 0;
    along = v_dot(ap, d) / len;
    if (along <= skip) return 0;
    lat2 = v_dot(ap, ap) - along * along;
    if (along <= len) { m = margin + per_m * along; return lat2 <= m * m ? 1 : 0; }
    if (along > len + behind) return 0;
    m = behind_margin + per_m * along;
    return lat2 <= m * m ? 2 : 0;
}

static shooter *shooter_of(hcb_brain *b, u32 id) {
    int i, free_i = -1;
    for (i = 0; i < HCB_MAX_OURS; i++) {
        if (b->sh[i].used && b->sh[i].id == id) return &b->sh[i];
        if (!b->sh[i].used && free_i < 0) free_i = i;
    }
    if (free_i < 0) return 0;
    zero(&b->sh[free_i], sizeof(shooter));
    b->sh[free_i].used = 1; b->sh[free_i].id = id;
    return &b->sh[free_i];
}
static float rnd_between(hcb_brain *b, float lo, float hi) {
    return hi > lo ? lo + (hi - lo) * (float)(hcb_rand(b) & 0xffff) / 65535.0f : lo;
}
#define veh_of hcb_vfind
/* A door gunner's rounds are made by the script along the checked line: they start muzzle_m out (clear of the
   helicopter and of the man beside him) and end round_past_m behind the aim point. Everybody else fires the game's
   own weapon, whose rounds fly on. */
static int is_gunner(int role) { return role >= HCB_ROLE_GUNNER && role < HCB_ROLE_GUNNER + 4; }

/* May this shooter fire at this contact right now? Returns HCB_HOLD_NONE or the reason. *aim_at / *aim are set. */
static int check(hcb_brain *b, const hcb_snapshot *s, const hcb_ped *me, int role, const track *t, hcb_out *out, u8 *aim_at, hcb_vec *aim) {
    const hcb_cfg *c = &b->cfg;
    hcb_vec from = me->pos, to = t->last.pos;
    float dist = v_dist(from, to), range = hcb_weapon_range(me->weapon) * 1.2f;
    vtrack *car = veh_of(b, t->last.vehicle), *heli = veh_of(b, s->heli);
    losent *l;
    int i, r, mine = 0, door = is_gunner(role), gunner = door && c->gunner_weapon < 0.5f;     /* gunner: his rounds are made by the script */
    float skip = gunner ? (heli && v_dist(from, heli->last.pos) < 6 ? c->muzzle_m : 0.8f) : door ? 0.8f : 0.3f;
    float cj_skip = door && b->cj_in_heli && heli && v_dist(from, heli->last.pos) < 6 ? c->cabin_skip_m : 0.3f;

    *aim_at = HCB_AIM_BODY; *aim = to;
    if (!hcb_is_firearm(me->weapon) || dist > range) return HCB_HOLD_RANGE;
    /* 0.8, proportionate force: a man on foot within 12 m of CJ (a brawler) with nothing in his hands, who has never held a firearm, is not shot while
       CJ is not in a bad way - a guard takes him down by hand (hcb_squad_state says so to the man nearest) */
    if (!t->last.vehicle && t->last.weapon == 0 && !hcb_is_firearm(t->best_weapon) && v_dist(t->last.pos, s->player.pos) < 12.0f && s->player.health >= 40.0f && !(t->last.flags & HCB_PF_SHOOTING) && s->roe != HCB_ROE_FOLLOW) return HCB_HOLD_FISTS;   /* (WHERE I SHOOT is CJ's own decision) */
    /* the sight of his own man is asked even while a rule holds the fire (CJ or a mate in the line): the answer is fresh
       the moment the line clears, and an old "clear" is never used for a man who may have hidden meanwhile */
    l = los_find(b, me->id, t->last.id);
    for (i = 0; i < HCB_MAX_OURS; i++)
        if (b->sh[i].used && b->sh[i].id == me->id) { mine = b->sh[i].target == t->last.id || b->sh[i].aim == t->last.id; break; }
    if (mine) ask(out, me->id, t->last.id);
    /* a door gunner does not fire across his own cabin */
    if (heli && door && me->vehicle == 0 && dist > 0.5f) {
        hcb_vec right, d = v_sub(to, from);
        float side = ((role - HCB_ROLE_GUNNER) & 1) ? -1.0f : 1.0f;
        right.x = heli->last.fwd.y; right.y = -heli->last.fwd.x; right.z = 0;
        if (v_dist(from, heli->last.pos) < 6 && side * (d.x * right.x + d.y * right.y) < -0.17f * f_sqrt(d.x * d.x + d.y * d.y)) return HCB_HOLD_NO_LOS;
    }
    /* CJ first, then everybody who is ours or an ally, then people who have nothing to do with it */
    /* (a gunner's round is checked again when it leaves, on the line it really takes: here only half the allowance for scatter) */
    r = in_line(from, to, s->player.pos, c->cj_line_m, gunner ? c->line_per_m * 0.5f : c->line_per_m, gunner ? c->round_past_m + c->cj_line_m : c->backstop_m, gunner ? c->cj_line_m : 1.0f, cj_skip);
    if (r) return r == 1 ? HCB_HOLD_CJ_IN_LINE : HCB_HOLD_CJ_BEHIND;
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        const track *o = &b->tr[i];
        if (!o->used || !o->seen || o == t || o->last.id == me->id) continue;
        if (o->friendly) {
            if (in_line(from, to, o->last.pos, c->friend_line_m, c->line_per_m * 0.75f, gunner ? c->round_past_m + c->friend_line_m : 25, gunner ? c->friend_line_m : 0.8f, skip)) return HCB_HOLD_FRIEND;
        } else if (o->cls <= HCB_CLS_NEUTRAL) {
            r = in_line(from, to, o->last.pos, c->bystander_line_m, 0, gunner ? c->round_past_m + c->bystander_line_m : 15, gunner ? c->bystander_line_m : 0.6f, skip);
            /* somebody standing behind a man who is about to kill CJ does not save that man */
            if (r == 1 || (r == 2 && t->edps < 40)) return HCB_HOLD_BYSTANDER;
        }
    }
    /* a man in a vehicle: never when the vehicle could blow up beside CJ or one of ours */
    if (car) {
        float near = v_dist(car->last.pos, s->player.pos);
        for (i = 0; i < HCB_MAX_TRACKS; i++) {
            const track *o = &b->tr[i];
            if (o->used && o->seen && o->friendly) near = f_min(near, v_dist(car->last.pos, o->last.pos));
        }
        if (near <= c->explode_m) {
            if (car->last.health < c->car_floor || (car->last.flags & HCB_VF_BURNING)) return HCB_HOLD_CAR_NEAR;
            *aim_at = car->why == HCB_WHY_RAMMING ? HCB_AIM_TYRE : HCB_AIM_DRIVER;
        } else *aim_at = HCB_AIM_DRIVER;
    }
    /* the line of sight is the adapter's to answer, and it is asked on every tick for every pair that passed the rules
       above: known and blocked = no; not known yet = he may take the man and bring his weapon round, not fire */
    if (!mine) ask(out, me->id, t->last.id);
    if (!l || s->time - l->time > 600) return SOFT_LOS;
    if (!l->clear) return HCB_HOLD_NO_LOS;
    return HCB_HOLD_NONE;
}

HID void hcb_fire_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out) {
    const hcb_cfg *c = &b->cfg;
    cand cs[MAX_CAND];
    const hcb_ped *me[HCB_MAX_OURS];
    u8 why[HCB_MAX_OURS][MAX_CAND], aim_at[HCB_MAX_OURS][MAX_CAND], done[HCB_MAX_OURS], busy[HCB_MAX_OURS];
    int choice[HCB_MAX_OURS];
    hcb_vec dummy;
    u32 now = s->time;
    int n_ours = s->n_ours < HCB_MAX_OURS ? s->n_ours : HCB_MAX_OURS, n = 0, i, j, k, round;

    for (i = 0; i < s->n_los && i < HCB_MAX_LOS; i++) los_store(b, s->los[i].from, s->los[i].to, s->los[i].clear, now);
    for (i = 0; i < HCB_LOS_CACHE; i++) if (b->los[i].used && now - b->los[i].time > 5000) b->los[i].used = 0;

    /* (1) who may be shot at, who may only be covered */
    for (i = 0; i < HCB_MAX_TRACKS && n < MAX_CAND; i++) {
        track *t = &b->tr[i];
        int fire = 0, armed_hostile;
        if (!t->used || !t->seen || t->friendly || (t->last.flags & HCB_PF_DEAD)) continue;
        armed_hostile = t->cls == HCB_CLS_WATCH && (t->why == HCB_WHY_ARMED_NEAR || t->why == HCB_WHY_ARMED_FACING);
        switch (s->roe) {
        case HCB_ROE_DEFEND: fire = t->cls >= HCB_CLS_THREAT; break;
        case HCB_ROE_ARMED: case HCB_ROE_LEGACY_ALL: fire = t->cls >= HCB_CLS_THREAT || armed_hostile; break;
        case HCB_ROE_FOLLOW: fire = t->cj_marked && now - t->cj_marked < (u32)c->follow_ms; break;
        default: fire = 0;
        }
        /* "evade": the police are never fired at, whatever they do */
        if (fire && s->police == HCB_POLICE_EVADE && t->last.pedtype == 6) fire = 0;
        /* "answer": a policeman is fired at only once he has attacked */
        if (fire && s->police == HCB_POLICE_ANSWER && t->last.pedtype == 6 && t->cls < HCB_CLS_ATTACKER && s->roe != HCB_ROE_FOLLOW) fire = 0;
        if (!fire && t->cls < HCB_CLS_WATCH) continue;
        /* kept sorted, most dangerous first and those that may be fired at before the rest: when the questions about
           lines of sight do not all fit into one tick, the ones that matter most are asked */
        {
            float value = t->edps > 1 ? t->edps : 1;
            for (j = n; j > 0 && (fire > cs[j - 1].fire || (fire == cs[j - 1].fire && value > cs[j - 1].value)); j--) cs[j] = cs[j - 1];
            cs[j].t = t; cs[j].fire = (u8)fire; cs[j].taken = 0; cs[j].value = value;
            n++;
        }
    }

    /* (2) the hard rules for every pair */
    out->n_orders = 0;
    b->cj_in_heli = (u8)(s->heli && s->player.vehicle == s->heli);
    for (i = 0; i < n_ours; i++) {
        int role = s->our_role[i];
        me[i] = hcb_ped_of(s, s->ours[i]);
        done[i] = 0; choice[i] = -1;
        if (!me[i] || (me[i]->flags & HCB_PF_DEAD) || role < HCB_ROLE_GUNNER) { me[i] = 0; done[i] = 1; }
    }
    for (j = 0; j < n; j++) for (i = 0; i < n_ours; i++) {
        if (!me[i]) continue;
        if (cs[j].fire && s->roe != HCB_ROE_HOLD) why[i][j] = (u8)check(b, s, me[i], s->our_role[i], cs[j].t, out, &aim_at[i][j], &dummy);
        else { why[i][j] = HCB_HOLD_ROE; aim_at[i][j] = HCB_AIM_BODY; }
    }

    /* (3) hand the targets out: always the pair that takes most danger off CJ; each further shooter on the same man
       counts for less, so fire spreads, but the worst threat still gets two */
    /* who is firing at a man he may still fire at */
    for (i = 0; i < n_ours; i++) {
        shooter *sh = me[i] ? shooter_of(b, me[i]->id) : 0;
        busy[i] = 0;
        if (sh && sh->target && (sh->hold == HCB_HOLD_NONE || sh->hold == HCB_HOLD_PAUSE || sh->hold == HCB_HOLD_REACTING))
            for (j = 0; j < n; j++) if (cs[j].t->last.id == sh->target && (why[i][j] == HCB_HOLD_NONE || why[i][j] == SOFT_LOS)) busy[i] = 1;
    }
    for (j = 0; j < n; j++) {                /* can a man with free hands take this one? */
        cs[j].free = 0;
        for (i = 0; i < n_ours; i++) if (!done[i] && !busy[i] && (why[i][j] == HCB_HOLD_NONE || why[i][j] == SOFT_LOS)) cs[j].free = 1;
    }
    for (round = 0; round < n_ours; round++) {
        float best = 0;
        int bi = -1, bj = -1;
        for (i = 0; i < n_ours; i++) {
            shooter *sh;
            if (done[i]) continue;
            sh = shooter_of(b, me[i]->id);
            for (j = 0; j < n; j++) {
                static const float share[4] = {1.0f, 0.55f, 0.3f, 0.15f};
                float v;
                if ((why[i][j] != HCB_HOLD_NONE && why[i][j] != SOFT_LOS) || cs[j].taken >= 3) continue;
                v = cs[j].value * share[cs[j].taken];
                if (why[i][j] == SOFT_LOS) v *= 0.9f;                         /* a man he is known to see comes first */
                if (sh && sh->target == cs[j].t->last.id) v *= 1.3f;         /* stay on your man */
                /* a man who is firing does not drop his target for another one that is looked after: somebody is on it already,
                   or a man with free hands can take it. An attacker nobody is on gets a rifle whatever it costs. */
                else if (busy[i] && (cs[j].free || cs[j].taken)) v *= 0.6f;
                v *= 1.0f / (1.0f + 0.01f * v_dist(me[i]->pos, cs[j].t->last.pos));  /* the nearer shooter, other things equal */
                /* 1.4.1: the men on the ground take who is close to CJ, the door gunners who is further off (the tablet's fight:
                   the gunners had them all and the guards next to CJ had nobody 64 % of the time) */
                {
                    float dcj = v_dist(cs[j].t->last.pos, s->player.pos);
                    int role = s->our_role[i];
                    if (role >= HCB_ROLE_SQUAD) v *= dcj < 20.0f ? 1.3f : 0.8f;
                    else if (role >= HCB_ROLE_GUNNER) v *= dcj > 15.0f ? 1.15f : 0.85f;
                }
                if (v > best) { best = v; bi = i; bj = j; }
            }
        }
        if (bi < 0) break;
        choice[bi] = bj; done[bi] = 1; cs[bj].taken++;
    }
    /* nobody we may fire at is left without a rifle while another man has more than he needs: a third rifle goes over to
       anybody, the second one to a man who is attacking */
    for (j = 0; j < n; j++) {
        int need, from = -1;
        if (!cs[j].fire || cs[j].taken) continue;
        need = cs[j].t->cls == HCB_CLS_ATTACKER ? 2 : 3;
        for (i = 0; i < n_ours; i++) {
            if (!me[i] || choice[i] < 0 || cs[choice[i]].taken < need || (why[i][j] != HCB_HOLD_NONE && why[i][j] != SOFT_LOS)) continue;
            if (from < 0 || cs[choice[i]].taken > cs[choice[from]].taken ||
                (cs[choice[i]].taken == cs[choice[from]].taken && v_dist(me[i]->pos, cs[j].t->last.pos) < v_dist(me[from]->pos, cs[j].t->last.pos))) from = i;
        }
        if (from >= 0) { cs[choice[from]].taken--; choice[from] = j; cs[j].taken++; }
    }

    /* (4) orders with human timing; whoever is left covers a suspect or reports why he cannot fire */
    for (i = 0; i < n_ours; i++) {
        hcb_order *o;
        shooter *sh;
        if (!me[i]) continue;
        sh = shooter_of(b, me[i]->id);
        o = &out->orders[out->n_orders++];
        zero(o, sizeof *o);
        o->who = me[i]->id;
        if (!sh) { o->hold = HCB_HOLD_NO_TARGET; continue; }
        sh->role = s->our_role[i]; sh->aim = 0; sh->ready = 0;
        if (choice[i] >= 0) {
            track *t = cs[choice[i]].t;
            if (sh->target != t->last.id) {
                /* a new man: the weapon has to come round. Quicker when already in a fight, quicker still when alert. */
                float react = rnd_between(b, c->react_min_ms, c->react_max_ms);
                if (sh->target && sh->fire_from <= now) react *= 0.6f;
                if (b->alert >= HCB_ALERT_COMBAT) react *= 0.7f;
                sh->target = t->last.id; sh->since = now; sh->fire_from = now + (u32)react;
                sh->burst_until = 0; sh->pause_until = 0;
            }
            o->target = t->last.id; o->aim = t->last.pos; o->aim_at = aim_at[i][choice[i]]; o->ready = 1;
            if (why[i][choice[i]] == SOFT_LOS) o->hold = HCB_HOLD_NO_LOS;           /* the answer is on its way; the reaction clock is running */
            else if (now < sh->fire_from) o->hold = HCB_HOLD_REACTING;
            /* a guard on foot fires the game's own weapon and the game makes his bursts: for him it is fire or cease fire */
            else if (!is_gunner(sh->role)) { o->fire = 1; o->hold = HCB_HOLD_NONE; sh->last_fire = now; }
            else if (now < sh->pause_until) o->hold = HCB_HOLD_PAUSE;
            else {
                if (!sh->burst_until) sh->burst_until = now + (u32)rnd_between(b, c->burst_min_ms, c->burst_max_ms);
                if (now < sh->burst_until) { o->fire = 1; o->hold = HCB_HOLD_NONE; sh->last_fire = now; }
                else {                                      /* the burst is over: a breath, then the next one */
                    sh->pause_until = now + (u32)rnd_between(b, c->pause_min_ms, c->pause_max_ms);
                    sh->burst_until = 0;
                    o->hold = HCB_HOLD_PAUSE;
                }
            }
            sh->hold = o->hold; sh->aim = o->target; sh->ready = o->ready;
            continue;
        }
        /* nothing to fire at: the most dangerous contact he could not take says why; a suspect gets a weapon pointed at him */
        {
            float best = -1;
            int bj = -1, cover = -1;
            for (j = 0; j < n; j++) {
                if (cs[j].fire && cs[j].value > best) { best = cs[j].value; bj = j; }
                if (!cs[j].fire && cs[j].t->cls >= HCB_CLS_WATCH && s->roe != HCB_ROE_HOLD && (cover < 0 || cs[j].value > cs[cover].value)) cover = j;
            }
            /* a man he had his weapon on and may not fire at just now (CJ in the line, a wall) is still his man: when the
               line clears he fires without a new reaction time */
            if (bj < 0 || sh->target != cs[bj].t->last.id) { sh->target = 0; sh->fire_from = 0; }
            sh->burst_until = 0; sh->pause_until = 0;
            if (bj >= 0) {
                o->hold = why[i][bj] == SOFT_LOS ? HCB_HOLD_NO_LOS : why[i][bj] == HCB_HOLD_NONE ? HCB_HOLD_ENOUGH : why[i][bj];
                o->target = cs[bj].t->last.id; o->aim = cs[bj].t->last.pos; o->ready = 1;
            }
            else if (cover >= 0) { o->hold = HCB_HOLD_COVERING; o->target = cs[cover].t->last.id; o->aim = cs[cover].t->last.pos; o->ready = 1; }
            else { o->hold = s->roe == HCB_ROE_HOLD && n ? HCB_HOLD_ROE : HCB_HOLD_NO_TARGET; o->ready = (u8)(b->alert >= HCB_ALERT_THREAT); }
            sh->hold = o->hold; sh->aim = o->target; sh->ready = o->ready;
        }
    }
    /* shooters who are no longer with us */
    for (k = 0; k < HCB_MAX_OURS; k++) {
        if (!b->sh[k].used) continue;
        for (i = 0; i < n_ours; i++) if (me[i] && me[i]->id == b->sh[k].id) break;
        if (i == n_ours) b->sh[k].used = 0;
    }
}

/* One round, now. The order must still stand (same man, firing, given on a recent tick), and the hard rules are run
   again on the positions of this frame: CJ, our own people, and - from what the last tick knew - allies, bystanders
   and the vehicle the man sits in. */
static int shot_check(const hcb_brain *cb, const hcb_shot *q, int as_guard);
API int hcb_shot_check(const hcb_brain *cb, const hcb_shot *q) { return shot_check(cb, q, 0); }
/* as_guard: the question comes from a man on foot who fires the game's own weapon - his rounds fly on, whatever his role says */
static int shot_check(const hcb_brain *cb, const hcb_shot *q, int as_guard) {
    hcb_brain *b = (hcb_brain *)cb;
    const hcb_cfg *c = &b->cfg;
    const shooter *sh = 0;
    const track *t;
    int i, r, gunner;
    float skip, past;
    for (i = 0; i < HCB_MAX_OURS; i++) if (b->sh[i].used && b->sh[i].id == q->who) sh = &b->sh[i];
    if (!sh || !q->target || sh->target != q->target || sh->hold != HCB_HOLD_NONE || q->time - b->time > 300) return HCB_HOLD_NO_TARGET;
    t = hcb_find(b, q->target);
    if (!t || t->friendly) return HCB_HOLD_NO_TARGET;
    gunner = is_gunner(sh->role) && !as_guard;
    skip = gunner ? f_max(0.3f, v_dist(q->from, q->muzzle)) : is_gunner(sh->role) ? 0.8f : 0.3f;
    past = gunner ? c->round_past_m : c->backstop_m;
    /* the line given is the line the round takes: for a gunner there is no scatter left to allow for */
    r = in_line(q->from, q->to, q->cj, c->cj_line_m, gunner ? 0 : c->line_per_m, gunner ? past + c->cj_line_m : past, gunner ? c->cj_line_m : 1.0f,
                is_gunner(sh->role) && b->cj_in_heli ? c->cabin_skip_m : 0.3f);
    if (r) return r == 1 ? HCB_HOLD_CJ_IN_LINE : HCB_HOLD_CJ_BEHIND;
    for (i = 0; i < (int)q->n_friends && i < HCB_MAX_OURS; i++)
        if (in_line(q->from, q->to, q->friends[i], c->friend_line_m, c->line_per_m * 0.75f, gunner ? past + c->friend_line_m : 25, gunner ? c->friend_line_m : 0.8f, skip)) return HCB_HOLD_FRIEND;
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        const track *o = &b->tr[i];
        if (!o->used || !o->seen || o == t || o->last.id == q->who) continue;
        if (o->friendly) {
            if (o->why == HCB_WHY_OURS) continue;       /* our own people came with the question, as they stand now */
            if (in_line(q->from, q->to, o->last.pos, c->friend_line_m + 0.5f, c->line_per_m * 0.75f, gunner ? past + c->friend_line_m : 25, gunner ? c->friend_line_m + 0.5f : 0.8f, skip)) return HCB_HOLD_FRIEND;
        } else if (o->cls <= HCB_CLS_NEUTRAL) {
            r = in_line(q->from, q->to, o->last.pos, c->bystander_line_m + 0.3f, 0, gunner ? past + c->bystander_line_m : 15, gunner ? c->bystander_line_m + 0.3f : 0.6f, skip);
            if (r == 1 || (r == 2 && t->edps < 40)) return HCB_HOLD_BYSTANDER;
        }
    }
    if (t->last.vehicle) {
        const vtrack *car = hcb_vfind(b, t->last.vehicle);
        if (car) {
            float near = v_dist(car->last.pos, q->cj);
            for (i = 0; i < (int)q->n_friends && i < HCB_MAX_OURS; i++) near = f_min(near, v_dist(car->last.pos, q->friends[i]));
            if (near <= c->explode_m && (car->last.health < c->car_floor || (car->last.flags & HCB_VF_BURNING))) return HCB_HOLD_CAR_NEAR;
        }
    }
    return HCB_HOLD_NONE;
}

static shooter *shooter_find(hcb_brain *b, u32 who) {
    int i;
    for (i = 0; i < HCB_MAX_OURS; i++) if (b->sh[i].used && b->sh[i].id == who) return &b->sh[i];
    return 0;
}
API int hcb_order_get(const hcb_brain *cb, u32 who, hcb_order *o) {
    const shooter *sh = shooter_find((hcb_brain *)cb, who);
    zero(o, sizeof *o);
    if (!sh) return 0;
    o->who = who; o->target = sh->aim; o->hold = sh->hold; o->ready = sh->ready;
    o->fire = (u8)(sh->hold == HCB_HOLD_NONE && sh->aim != 0 && sh->aim == sh->target);
    return 1;
}
static float dice(shooter *sh) {       /* -1..1, the gunner's own dice: the brain's are for its looks, so a replay does not need the rounds */
    u32 x = sh->rrng ? sh->rrng : (sh->id * 2654435761u) | 1u;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5; sh->rrng = x;
    return (float)(x & 0xffff) / 32767.5f - 1.0f;
}
API int hcb_gunner_round(hcb_brain *b, const hcb_shot *in, float heli_speed, int near_heli, hcb_round *r) {
    const hcb_cfg *c = &b->cfg;
    shooter *sh = shooter_find(b, in->who);
    hcb_shot q = *in;
    hcb_vec d;
    float len, out, spread;
    if (!sh || sh->hold != HCB_HOLD_NONE || !sh->target || sh->target != in->target) return 0;
    if (sh->next_round && (int)(in->time - sh->next_round) < 0 && sh->next_round - in->time < 2000) return 0;
    out = near_heli ? c->muzzle_m : 0.8f;
    d = v_sub(q.to, q.from); len = v_len(d);
    /* (written so that a position that is not a number, or one 500 m away, gives no round: the game hangs on such a line) */
    if (!(len >= out + 1.0f && len < 500.0f) || !(q.cj.x - q.cj.x == 0.0f && q.cj.y - q.cj.y == 0.0f && q.cj.z - q.cj.z == 0.0f)) { sh->next_round = in->time + 100; return 0; }
    if (!(heli_speed >= 0.0f && heli_speed < 150.0f)) heli_speed = 0.0f;
    spread = c->scatter_m + c->scatter_per_m * len + c->scatter_per_ms * (near_heli ? heli_speed : 0);
    q.to.x += dice(sh) * spread; q.to.y += dice(sh) * spread; q.to.z += dice(sh) * spread;
    d = v_sub(q.to, q.from); len = v_len(d);
    q.muzzle = v_add(q.from, v_mul(d, out / len));
    zero(r, sizeof *r);
    r->time = in->time; r->who = in->who; r->target = in->target; r->muzzle = q.muzzle; r->to = q.to;
    r->end = v_add(q.to, v_mul(d, c->round_past_m / len));
    r->verdict = (u8)hcb_shot_check(b, &q);
    if (r->verdict == HCB_HOLD_NONE) {
        float gap = c->round_min_ms + (c->round_max_ms - c->round_min_ms) * (dice(sh) * 0.5f + 0.5f);
        sh->next_round = in->time + (u32)gap; r->note = 1;
    } else {
        sh->next_round = in->time + 60;
        if (!sh->noted || in->time - sh->noted >= 250) { sh->noted = in->time; r->note = 1; }
    }
    return 1;
}
API void hcb_gunner_blocked(hcb_brain *b, u32 who, u32 time) {
    shooter *sh = shooter_find(b, who);
    if (sh) sh->next_round = time + 60;
}
API int hcb_squad_state(const hcb_brain *cb, const hcb_shot *q) {
    const shooter *sh = shooter_find((hcb_brain *)cb, q->who);
    if (!sh || !sh->aim) return 0;
    if (sh->hold == HCB_HOLD_COVERING) return sh->ready ? 1 : 0;
    if (sh->hold == HCB_HOLD_FISTS) return 5;                           /* 0.8: by hand */
    /* (the check below refuses by itself when his order is not "fire" or the man asked about is not his) */
    return shot_check(cb, q, 1) == HCB_HOLD_NONE ? 2 : 3;
}
