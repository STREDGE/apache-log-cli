/* Helicover Brain 1.0 - one man carrying out his order.
 *
 * The squad (hcb_detail.c in PROTECT, hcb_squad.c in ASSAULT) says WHERE each man is to be and why. This module is the man
 * himself: it turns "be there" into an action with a beginning and an end, and checks that it works.
 *   CHOSEN -> MOVING -> ARRIVED -> ACTING, or FAILED with a reason.
 *   - the way: straight when two level rays say nothing is between him and the place (asked of the adapter), else round by
 *     the brain's own map (hcb_nav.c); `via` is the point he walks to now;
 *   - the pace is chosen, not fixed: a walk beside CJ, a run to catch up or to a place in a fight, a sprint only for a rush
 *     under fire or out of danger (the 0.9 log: sprinting half the time);
 *   - "the order was given" is not "it is done": the distance to `via` must shrink. 1.5 s without progress -> that way out of
 *     his cell is marked blocked, he steps round it and another way is looked for; the fourth time the game's
 *     own path network is asked; the sixth time the squad is told the place cannot be reached and gives him another.
 * It keeps its decisions: a place is not changed for a move of under a metre, a way is kept 2.5 s. */
#include "hcb_int.h"

static hcb_vec flat(hcb_vec v) { v.z = 0; return v; }
static float d2(hcb_vec a, hcb_vec b) { return v_len(flat(v_sub(a, b))); }

static agent *agent_of(hcb_brain *b, u32 id, u32 now) {
    int i, old = 0;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) return &b->ag[i];
    for (i = 0; i < 8; i++) {
        if (!b->ag[i].used) { old = i; break; }
        if (b->ag[i].last_seen < b->ag[old].last_seen) old = i;
    }
    zero(&b->ag[old], sizeof b->ag[old]);
    b->ag[old].used = 1; b->ag[old].id = id; b->ag[old].goal_since = now; b->ag[old].prog_since = now; b->ag[old].prog_best = 1e9f;
    return &b->ag[old];
}

static agent *agent_find(hcb_brain *b, u32 id) {
    int i;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) return &b->ag[i];
    return 0;
}
static const hcb_order *order_of(const hcb_out *out, u32 who) {
    int i;
    for (i = 0; i < out->n_orders; i++) if (out->orders[i].who == who) return &out->orders[i];
    return 0;
}
/* 1.3: an attacker seen within 40 m of CJ: a real firefight (the movers' token and the step out of the line need one) */
static int firefight(const hcb_brain *b, const hcb_snapshot *s) {
    int i;
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        const track *t = &b->tr[i];
        if (t->used && t->seen && !t->friendly && t->cls == HCB_CLS_ATTACKER && d2(t->last.pos, s->player.pos) < 40.0f) return 1;
    }
    return 0;
}

HID int hcb_agent_fails(const hcb_brain *b, u32 id) {
    int i;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) return b->ag[i].fails;
    return 0;
}
/* has this man's action failed (six tries), and for at least three seconds (so that he has said so, and the squad does not hand out a new place every second)? */
HID int hcb_agent_failed(const hcb_brain *b, u32 id, u32 now) {
    int i;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) return b->ag[i].failed_at && now - b->ag[i].failed_at >= 1500;
    return 0;
}
/* 1.5: why this man did what he did at his last look (HCB_WHY2_*; 0 = not known) */
HID int hcb_agent_why(const hcb_brain *b, u32 id) {
    int i;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) return b->ag[i].why;
    return 0;
}
HID void hcb_agent_forgive(hcb_brain *b, u32 id) {
    int i;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) { b->ag[i].fails = 0; b->ag[i].n_path = 0; b->ag[i].failed_at = 0; }
}

static void set_act(agent *a, hcb_post *p, u8 act, u8 phase, u8 why) {
    if (a->act != act) { if (a->moves < 255) a->moves++; }
    a->act = act; a->phase = phase;
    if (why) a->why = why;
    p->act = act; p->phase = phase; p->why = a->why;
}

HID void hcb_agent_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out) {
    u32 now = s->time;
    float cj_speed = v_len(flat(s->player.vel));
    int i, plans = 0, moving = 0, movers = 0, hot = b->alert >= HCB_ALERT_THREAT, ff = firefight(b, s);

    if (!s->body) {                                                  /* the script body (the fallback) walks to `at` its own way */
        for (i = 0; i < out->n_posts; i++) { out->posts[i].via = out->posts[i].at; out->posts[i].via2 = out->posts[i].at; out->posts[i].face = 0; }
        out->n_moving = 0;
        return;
    }
    for (i = 0; i < 8; i++) if (b->ag[i].used && now - b->ag[i].last_seen > 3000 && b->ag[i].last_seen) b->ag[i].used = 0;
    /* 1.1 (the half-hour run: two bodyguards' places came out 0.8 m apart beside a wall and the men stood shoulder in shoulder):
       no two places nearer than 0.8 m - the later one of a pair is moved off along the line between them. 1.5 (the fifth 2.0 log:
       the brain itself put two of the three at CJ's side within a metre of each other in 58 looks, and they jostled): 1.1 m */
    for (i = 1; i < out->n_posts; i++) {
        int j;
        for (j = 0; j < i; j++) {
            hcb_vec dv_ = flat(v_sub(out->posts[i].at, out->posts[j].at));
            float l_ = v_len(dv_);
            if (l_ >= 1.1f) continue;
            if (l_ < 0.05f) { dv_.x = 1.0f; dv_.y = 0.0f; l_ = 1.0f; }
            out->posts[i].at.x = out->posts[j].at.x + dv_.x / l_ * 1.1f; out->posts[i].at.y = out->posts[j].at.y + dv_.y / l_ * 1.1f;
        }
    }
    for (i = 0; i < out->n_posts; i++) {
        hcb_post *p = &out->posts[i];
        const hcb_ped *me = hcb_ped_of(s, p->who);
        agent *a;
        float d, dv, ra;
        int urgent, inner, fight, force = 0, follow;
        hcb_vec feet, gfeet;

        p->via = p->at; p->via2 = p->at; p->face = 0;
        if (!me) continue;
        a = agent_of(b, p->who, now);
        a->last_seen = now ? now : 1;
        /* 1.3, out of the line (the first 2.0 log: one in five orders to a man with a target was "CJ in the line" and as many
           "one of ours in the line" - and he stood there): standing at his place with CJ or one of ours in his line of fire for
           0.7 s, he takes a step to the side - away from CJ - 2.5 m, once in 3 s, and keeps it 5 s (the outer men: the three with CJ
           shield him) */
        {
            const hcb_order *od = order_of(out, p->who);
            const hcb_ped *tp = od && od->target ? hcb_ped_of(s, od->target) : 0;
            int in3 = p->job == HCB_ROLE_LEAD || p->job == HCB_ROLE_CLOSE || p->job == HCB_ROLE_CLOSE2;
            /* (1.3, beta 5: the three with CJ step too - not 2.5 m away from him, but round him to his flank, 1.7 m beside him and half a
               metre towards the man: still at his side, and CJ is out of the line) */
            const hcb_ped *cjp_ = &s->player;
            /* (the three: only CJ himself in the line - one of the three in front of another is the shield, it stays) */
            int blocked = tp && !od->fire && (od->hold == HCB_HOLD_CJ_IN_LINE || (!in3 && (od->hold == HCB_HOLD_CJ_BEHIND || od->hold == HCB_HOLD_FRIEND)))
                && !(p->job == HCB_ROLE_LEAD && (b->dt.leading || p->sign))   /* (the commander leading CJ to cover goes on leading) */
                && d2(me->pos, p->at) < 2.5f && p->job != HCB_ROLE_MARKSMAN && !p->climb && !(p->crouch && in3);   /* (one of the three down in cover - CJ in cover with him - keeps it; 1.5: an outer man is down at every place now: he steps all the same) */
            if (blocked) { if (!a->line_since) a->line_since = now ? now : 1; } else a->line_since = 0;
            /* (1.5, the player: "all of them in cover, firing from there and sitting": an outer man down in cover in a fight keeps it - his place
               is chosen clear of CJ's line, and with one of ours in the way he holds his sector until his place is chosen again; out of a fight
               he steps when the line stays blocked 2.5 s - a man of ours crossing it does not get him up) */
            if (blocked && p->crouch && !in3 && (p->duty == HCB_DUTY_COVER || now - a->line_since < 2500)) blocked = 0;
            if (blocked && in3 && now - a->line_since >= 700 && !(a->step_until && now < a->step_until) && (!a->step_at || now - a->step_at >= 3000)) {
                hcb_vec rel = flat(v_sub(me->pos, cjp_->pos)), to = flat(v_sub(tp->pos, cjp_->pos));
                float l = v_len(to);
                if (l > 1.0f) {
                    /* (his own side of CJ; taken by another of the three already - the other side; both taken - a step further out) */
                    float sg = (to.x * rel.y - to.y * rel.x) >= 0.0f ? 1.0f : -1.0f, used[2] = {0, 0};
                    int k_;
                    for (k_ = 0; k_ < out->n_posts; k_++) {
                        const agent *o_ = k_ != i ? agent_find(b, out->posts[k_].who) : 0;
                        if (o_ && o_->step_until && now < o_->step_until && o_->flank != 0.0f) used[o_->flank > 0.0f ? 0 : 1] += 1.0f;
                    }
                    if (used[sg > 0.0f ? 0 : 1] > 0.0f) { if (used[sg > 0.0f ? 1 : 0] == 0.0f) sg = -sg; else sg *= 2.0f; }
                    a->flank = sg; a->step_until = now + 5000; a->step_at = now ? now : 1; a->why = HCB_WHY2_STEP_OUT;
                }
            } else if (blocked && !in3 && now - a->line_since >= 700 && !(a->step_until && now < a->step_until) && (!a->step_at || now - a->step_at >= 3000)) {
                hcb_vec to = flat(v_sub(tp->pos, me->pos)), side, away = flat(v_sub(me->pos, s->player.pos));
                float l = v_len(to), w = 2.5f;
                if (l > 0.5f) {
                    side.x = -to.y / l; side.y = to.x / l; side.z = 0;
                    if (side.x * away.x + side.y * away.y < 0) { side.x = -side.x; side.y = -side.y; }
                    a->step = v_mul(side, w); a->step_from = me->pos; a->step_until = now + 5000; a->step_at = now ? now : 1; a->why = HCB_WHY2_STEP_OUT; a->flank = 0;
                }
            }
            if (a->step_until && p->crouch && a->flank != 0.0f) a->step_until = 0;   /* (CJ has got into cover and he with him: no flank) */
            if (a->step_until && now < a->step_until && a->flank != 0.0f && tp && now + 1500 > a->step_until) a->step_until = now + 1500;   /* (kept while he has the man) */
            if (a->step_until && now < a->step_until && a->flank != 0.0f && p->job == HCB_ROLE_LEAD && (b->dt.leading || p->sign)) a->step_until = 0;
            if (a->step_until && now < a->step_until && a->flank != 0.0f && tp) {     /* (at CJ's flank: kept as CJ and the man move) */
                hcb_vec to = flat(v_sub(tp->pos, cjp_->pos)), side;
                float l = v_len(to);
                if (l > 1.0f) {
                    /* (his side first, 1.7 m out; a spot within a metre of another of ours - where he stands or is going - is
                       not taken: the other side, then 2.5 m out) */
                    static const float TRY[4][2] = {{1.0f, 1.7f}, {-1.0f, 1.7f}, {1.0f, 2.5f}, {-1.0f, 2.5f}};
                    float sg0 = a->flank > 0.0f ? 1.0f : -1.0f;
                    hcb_vec spot = cjp_->pos;
                    int tr, k2;
                    for (tr = 0; tr < 4; tr++) {
                        int free_ = 1;
                        float sg = sg0 * TRY[tr][0];
                        side.x = -to.y / l * sg; side.y = to.x / l * sg; side.z = 0;
                        spot = v_add(cjp_->pos, v_add(v_mul(side, TRY[tr][1]), v_mul(to, 0.5f / l))); spot.z = cjp_->pos.z;
                        for (k2 = 0; k2 < out->n_posts && free_; k2++) {
                            const hcb_ped *o2 = k2 != i ? hcb_ped_of(s, out->posts[k2].who) : 0;
                            if (!o2) continue;
                            if (d2(o2->pos, spot) < 1.0f || (k2 < i && d2(out->posts[k2].at, spot) < 1.0f)) free_ = 0;
                        }
                        if (free_) break;
                    }
                    if (tr == 4) { a->step_until = 0; a->flank = 0; goto flank_done; }   /* (no free spot by CJ: he stays where he is) */
                    p->at = spot;
                    p->via = p->at; p->via2 = p->at; p->crouch = 0; if (p->move == 0) p->move = 2;
                }
            } else if (a->step_until && now < a->step_until && a->flank == 0.0f) {
                /* (he was told to stay: the step is a move. 1.5: from where he stood, the height of his place - the outer men's places
                   are taken within 1.5 m now, and a step from the place itself left him in the line) */
                float z = p->at.z;
                p->at = v_add(a->step_from, a->step); p->at.z = z; p->via = p->at; p->via2 = p->at; if (p->move == 0) p->move = 2;
            }
            else { a->step_until = 0; a->flank = 0; }
        flank_done:;
        }
        if (hcb_squad_roping(s, p->who)) {                           /* on the rope: nothing until he stands */
            p->at = me->pos; p->via = me->pos; p->move = 0; p->crouch = 0;
            set_act(a, p, HCB_ACT_HOLD, HCB_PH_CHOSEN, HCB_WHY2_IN_AIR);
            a->goal = me->pos; a->n_path = 0; a->prog_since = now; a->prog_best = 1e9f;
            continue;
        }
        /* the place: taken when it has really changed */
        if (d2(a->goal, p->at) > 1.0f || a->phase == HCB_PH_CHOSEN) {
            if (d2(a->goal, p->at) > 3.0f) { a->n_path = 0; a->why = HCB_WHY2_NEW_POST; }       /* (the count of failures is kept: it is the man who does not get on, wherever he is sent) */
            a->goal = p->at; a->goal_since = now; a->arrived_since = 0;
        }
        inner = p->job == HCB_ROLE_LEAD || p->job == HCB_ROLE_CLOSE || p->job == HCB_ROLE_CLOSE2;
        fight = p->duty >= HCB_DUTY_SHIELD;
        urgent = p->act == HCB_ACT_SPRINT || p->duty == HCB_DUTY_SHIELD || p->duty == HCB_DUTY_RING || p->duty == HCB_DUTY_BOUND;
        ra = inner ? 0.9f : 1.3f;
        if (a->step_until && now < a->step_until) ra = 0.4f;           /* (a step out of the line is made all the way) */
        d = d2(me->pos, p->at);
        /* 1.3, a margin round "there" (a steady walk with CJ: his place moves along at CJ's pace, he walks at the same pace a step
           behind it - and was HOLD and WALK in turns, 40 times a minute, at the edge of "there"): on his way he goes on to well
           inside it */
        if (cj_speed > 0.5f && a->phase == HCB_PH_MOVING && a->act >= HCB_ACT_WALK && a->act <= HCB_ACT_SPRINT) { ra *= 0.5f; if (p->move == 0 && d > ra && d < 2.5f) p->move = 1; }
        /* (beta 5, the half-hour run: in a fight a man reached his place, took cover and was off again within a second or two - his
           place shifts a little with every look of the fight; a third of all changes went back and forth within 3 s. Arrived, he stays
           1.5 s for a shift of up to a metre beyond "there" - CJ standing, not in a pull-out) */
        else if (a->arrived_since && now - a->arrived_since < 1500 && p->move && p->move < 3 && d < ra + 1.0f && cj_speed < 0.8f && !(a->step_until && now < a->step_until)
                 && p->duty != HCB_DUTY_RING) p->move = 0;
        if (p->job == HCB_ROLE_MARKSMAN && f_abs(me->pos.z - p->at.z) > 2.0f) d += f_abs(me->pos.z - p->at.z);   /* (1.3: under his roof is not on it) */
        {   /* 1.1 (the half-hour run): "there" within a step of his place - unless another of ours stands within 0.6 m of him: then on to the place itself */
            int k_;
            for (k_ = 0; k_ < out->n_posts; k_++) {
                const hcb_ped *o = k_ != i ? hcb_ped_of(s, out->posts[k_].who) : 0;
                if (o && d2(o->pos, me->pos) < 0.6f) { ra = 0.3f; if (d > 0.3f && d < 2.5f && p->move == 0) p->move = 1; }   /* ("near enough" is not enough here) */
            }
        }
        /* (beta 5, the half-hour run: a bodyguard by a CJ on the move ran to his place, stopped, and ran again a second later - run,
           stop, run. With CJ on the move a man near his place does not stop: he walks on at CJ's pace) */
        follow = cj_speed > 0.8f && d < 2.5f && a->phase != HCB_PH_FAILED && !p->climb && !p->crouch;
        if (follow && p->move == 0) p->move = 1;
        if ((p->move == 0 || d < ra) && !follow) {                     /* there (or told to stay) */
            if (!a->arrived_since) a->arrived_since = now ? now : 1;
            a->n_path = 0; a->fails = 0; a->prog_since = now; a->prog_best = 1e9f; a->side_until = 0; a->prog_pos = me->pos;
            if (d < ra) p->move = 0;
            set_act(a, p, p->crouch ? HCB_ACT_COVER : p->job == HCB_ROLE_MARKSMAN || p->duty == HCB_DUTY_HOLD ? HCB_ACT_OVERWATCH : HCB_ACT_HOLD,
                    now - a->arrived_since >= 500 ? HCB_PH_ACTING : HCB_PH_ARRIVED, p->why == HCB_WHY2_WAIT_TURN ? HCB_WHY2_WAIT_TURN : HCB_WHY2_ARRIVED);
            continue;
        }
        a->arrived_since = 0;
        if (p->climb) {                                              /* 1.3: at the wall: the mod gives him the game's jump-and-climb */
            p->via = p->at; p->via2 = p->at; p->move = 2;
            a->prog_since = now; a->prog_pos = me->pos; a->n_path = 0;
            set_act(a, p, HCB_ACT_RUN, HCB_PH_MOVING, HCB_WHY2_CLIMB);
            moving++;
            continue;
        }
        /* FAILED (six tries): he stops trying the same thing - he stands and watches for 2.5 s (1.1: 8 s), then tries again from the
           beginning (the world may have changed: a car gone, a gate open). The squad may have given him another place by then. */
        if (a->fails >= 6) {
            if (!a->failed_at) a->failed_at = now ? now : 1;
            if (now - a->failed_at < 2500) {
                p->via = me->pos; p->move = 0; p->stuck = 1;
                set_act(a, p, HCB_ACT_HOLD, HCB_PH_FAILED, HCB_WHY2_NO_ROUTE);
                continue;
            }
            a->fails = 0; a->failed_at = 0; a->n_path = 0; a->prog_since = now; a->prog_best = 1e9f; a->prog_pos = me->pos;
        } else a->failed_at = 0;
        /* 1.1, the token: in a fight no more than movers_max of the outer men / the squad move at a time - the others hold
           and cover until one of them is in place. Never for the three with CJ, a man who is dodging (a grenade, a car), a
           shield or a pull-out, and never while CJ himself is moving (then everybody goes with him). */
        /* (1.3, the first 2.0 log: men waited "their turn" 13 % of the time - behind men who stood, and with no fight at all; the
           marksman 30 %. Now: only in a real firefight, never the marksman or a man far from his place, and only men who are
           really getting on hold a token) */
        if (!inner && fight && ff && p->job != HCB_ROLE_MARKSMAN && d <= 25.0f && p->act != HCB_ACT_SPRINT && p->duty != HCB_DUTY_SHIELD && p->duty != HCB_DUTY_RING && cj_speed < 1.0f
            && !s->recall && !(b->sq.umode == HCB_UMODE_ASSAULT && (b->sq.task == HCB_TASK_REGROUP || b->sq.task == HCB_TASK_WITHDRAW))   /* ("to me", falling back: everybody at once) */
            && movers >= (int)b->cfg.movers_max && !hcb_nav_narrow(b, me->pos)) {
            p->via = me->pos; p->move = 0;
            a->prog_since = now; a->prog_pos = me->pos; a->prog_best = 1e9f;
            set_act(a, p, HCB_ACT_HOLD, HCB_PH_CHOSEN, HCB_WHY2_WAIT_TURN);
            continue;
        }
        if (!inner && now - a->prog_since < 1500) movers++;
        moving++;
        /* the way */
        feet = me->pos; feet.z -= 0.6f; gfeet = p->at; gfeet.z = feet.z + (p->at.z - me->pos.z);
        /* (the step round is over and he has not moved at all: that counts at once, without another 1.5 s of waiting) */
        if (a->side_until && now >= a->side_until && d2(me->pos, a->last_pos) < 0.3f) force = 1;
        if (a->side_until && now < a->side_until) p->via = a->via;       /* stepping round something */
        else {
            int sg = d <= 14.0f ? hcb_nav_seg(b, out, feet, gfeet, now) : -1;      /* (1.3: far is "not known", not "blocked") */
            a->side_until = 0;
            if (d < 2.5f || sg == 1) { p->via = p->at; a->n_path = 0; a->why = HCB_WHY2_DIRECT; a->off_map = 0; }
            else {
                int need = !a->n_path || now - a->plan_t > 2500 || d2(a->path[a->n_path - 1], p->at) > 2.0f;
                if (need && plans < 2) {
                    /* 1.1: the way is found outside the look (hcb_path_ask): asked now, it is here with the next look or the one
                       after. Meanwhile he keeps the way he has; with none he waits where he is (never straight at a wall). */
                    hcb_vec np[AG_PATH];
                    int n = hcb_path_ask(b, out, p->who, me->pos, p->at, np, AG_PATH, now);
                    plans++;
                    if (n == -2) {
                        /* (no way of his own yet: he goes on to where he was going; only a man who has just been told the straight
                           way is shut stands and waits for the answer) */
                        /* (1.3, the first 2.0 log: "a way is being looked for" stood the man where he was and wound his clock back on every
                           look - 20 s in one place. Now he goes on where he was going, or straight at his place; the game itself walks
                           round houses, cars and things in his way) */
                        if (!a->n_path) p->via = a->phase == HCB_PH_MOVING && d2(a->via, me->pos) > 0.5f && d2(a->via, p->at) < d ? a->via : p->at;
                    } else {
                    a->plan_t = now;
                    if (n > 0) { int q_; for (q_ = 0; q_ < n; q_++) a->path[q_] = np[q_]; a->n_path = (u8)n; a->i_path = 0; a->why = HCB_WHY2_ROUTE; a->off_map = 0; }
                    else {
                        a->n_path = 0; a->why = n == 0 ? HCB_WHY2_NO_ROUTE : sg == 0 && d <= 14.0f ? HCB_WHY2_BLOCKED : HCB_WHY2_DIRECT;
                        a->off_map = (u8)(n == -1 && !hcb_nav_inside(b, me->pos));   /* (not a man on a roof or a ledge inside the map: he stays) */
                        /* (the map knows the ground and there is no way over it - a roof, a walled yard: that is three failures at
                           once, so the squad gives him another place within a few seconds instead of letting him run at a wall) */
                        /* 1.2 (the first log from the game): in a real yard the map said "no way" for three ways out of four, and
                           each such answer stood the man still for 8 s - 72 % of the time. The map may be wrong (a gate it takes
                           for a wall, a ledge a man steps down from). So "no way on the map" is not "stand": he goes straight
                           at his place, and if that does not get him on - by the game's own path network (move 4), like a man
                           off the map. Only the marksman on his roof stays where he is. */
                        if (n == 0) { p->stuck = 1; if (p->job != HCB_ROLE_MARKSMAN) a->off_map = 2; else a->fails = (u8)(a->fails + 3 > 250 ? 250 : a->fails + 3); }
                    }
                    }
                }
                if (a->n_path) {
                    /* on to the next point of the way when he is at this one - or near it with the next one in a straight walk
                       (not sooner: that would cut the corner the way goes round) */
                    while (a->i_path + 1 < a->n_path && (d2(me->pos, a->path[a->i_path]) < 0.6f || (d2(me->pos, a->path[a->i_path]) < 2.0f && hcb_nav_line(b, me->pos, a->path[a->i_path + 1], now)))) a->i_path++;
                    p->via = a->path[a->i_path];
                    p->via2 = a->i_path + 1 < a->n_path ? a->path[a->i_path + 1] : p->at;
                    if (a->i_path + 1 == a->n_path && d2(a->path[a->i_path], p->at) < 1.5f) { p->via = p->at; p->via2 = p->at; }
                    /* (1.3: a way that ends where he stands - found for a place that has moved on since - is no next point: straight on
                       to the place, and a new way is asked for) */
                    if (a->i_path + 1 >= a->n_path && d2(me->pos, p->via) < 0.6f) { p->via = p->at; p->via2 = p->at; a->n_path = 0; a->plan_t = 0; }
                    /* the map does not see thin things (a fence): the leg he is on is asked about too, and a blocked one is
                       marked on the map (hcb_nav_update does that with the answer) and planned round */
                    {
                        /* the next two steps of 1.5 m: a leg that short says exactly WHERE it is blocked */
                        hcb_vec dr = flat(v_sub(p->via, me->pos)), v1, v2;
                        float l = v_len(dr);
                        if (l > 0.8f) {
                            float s1 = l < 1.5f ? l : 1.5f, s2 = l < 3.0f ? l : 3.0f;
                            v1 = v_add(feet, v_mul(dr, s1 / l)); v2 = v_add(feet, v_mul(dr, s2 / l));
                            if (hcb_nav_seg(b, out, feet, v1, now) == 0 || (s2 > s1 + 0.5f && hcb_nav_seg(b, out, v1, v2, now) == 0)) {
                                /* (1.3: the way is kept and he keeps walking it - a new one is asked for; standing at the thing in his way
                                   made a man in the first 2.0 log stand for good) */
                                a->plan_t = 0; a->why = HCB_WHY2_BLOCKED;
                                hcb_path_forget(b, p->who);
                            }
                        }
                    }
                } else p->via = p->at;
            }
        }
        if (a->fails >= 6) {                                         /* (no way on the map: failed at once, without a step) */
            a->failed_at = now ? now : 1;
            p->via = me->pos; p->move = 0; p->stuck = 1;
            set_act(a, p, HCB_ACT_HOLD, HCB_PH_FAILED, HCB_WHY2_NO_ROUTE);
            moving--;
            continue;
        }
        /* 1.1, corners and doorways (only when there is somebody to be afraid of):
           - a blind corner: the way turns by 45 degrees or more at its next point and what lies beyond cannot be seen from here.
             He stops 2 m short of it for corner_ms with his weapon on the way he is about to go, then goes on (once a corner);
           - a doorway (a cell with walls on both sides): one man at a time. Another of ours within 2.5 m of the one ahead of
             him and himself in such a cell or moving: he waits, 3 s at most. Nobody stops inside a doorway. */
        if (hot && a->n_path && !(a->side_until && now < a->side_until) && !force) {
            hcb_vec cpt = a->path[a->i_path];
            int narrow_here = hcb_nav_narrow(b, me->pos);
            if (a->i_path + 1 < a->n_path && !narrow_here) {
                hcb_vec d1 = flat(v_sub(cpt, me->pos)), d2_ = flat(v_sub(a->path[a->i_path + 1], cpt));
                float l1 = v_len(d1), l2 = v_len(d2_);
                if (l1 > 0.2f && l2 > 0.5f && (d1.x * d2_.x + d1.y * d2_.y) / (l1 * l2) < 0.7071f && d2(cpt, a->corner_at) > 6.0f
                    && l1 < 2.2f && !hcb_nav_line(b, me->pos, a->path[a->i_path + 1], now)) {
                    if (!a->corner_until) a->corner_until = now + (u32)b->cfg.corner_ms;
                    if (now < a->corner_until) {
                        p->via = me->pos; p->move = 0; p->look = a->path[a->i_path + 1]; p->look.z += 0.8f;
                        a->prog_since = now; a->prog_pos = me->pos;
                        set_act(a, p, HCB_ACT_HOLD, HCB_PH_MOVING, HCB_WHY2_CORNER);
                        continue;
                    }
                    a->corner_at = cpt; a->corner_until = 0;
                }
            }
            if (!narrow_here && hcb_nav_narrow(b, cpt) && d2(me->pos, cpt) < 3.0f) {
                int k, busy = 0;
                for (k = 0; k < out->n_posts; k++) {
                    const hcb_ped *o = k != i ? hcb_ped_of(s, out->posts[k].who) : 0;
                    if (o && d2(o->pos, cpt) < 2.5f && d2(o->pos, cpt) < d2(me->pos, cpt) && (out->posts[k].phase == HCB_PH_MOVING || hcb_nav_narrow(b, o->pos))) busy = 1;
                }
                if (busy) {
                    if (!a->door_since) a->door_since = now ? now : 1;
                    if (now - a->door_since < 3000) {
                        p->via = me->pos; p->move = 0;
                        a->prog_since = now; a->prog_pos = me->pos;
                        set_act(a, p, HCB_ACT_HOLD, HCB_PH_MOVING, HCB_WHY2_DOORWAY);
                        continue;
                    }
                } else a->door_since = 0;
            } else a->door_since = 0;
        }
        /* does it work? */
        /* (progress is his own movement - half a metre in 1.5 s - not the distance to a place that may itself be moving
           with CJ: a man walking beside a strolling CJ is not "stuck") */
        dv = d2(me->pos, p->via);
        a->via = p->via;
        if (d2(me->pos, a->prog_pos) > 0.5f && !force) { a->prog_pos = me->pos; a->prog_since = now; a->prog_best = dv; }
        else if (now - a->prog_since > 1500 || force) {
            hcb_vec dir = flat(v_sub(p->via, me->pos));
            float l = v_len(dir);
            int k_, jam = 0;
            /* 1.1 (the half-hour run: three men met in a gap in a wall, each "made no progress", each marked the gap blocked on
               the map - and then nobody had a way through it): a man held up by ANOTHER OF OURS in front of him is in a jam,
               not at an obstacle. He waits a moment; nothing goes on the map and it does not count as a failure. And a doorway
               is never marked blocked by a man who merely did not get through it this time. */
            for (k_ = 0; k_ < out->n_posts && l > 0.1f; k_++) {
                const hcb_ped *o = k_ != i ? hcb_ped_of(s, out->posts[k_].who) : 0;
                hcb_vec rel;
                if (!o) continue;
                rel = flat(v_sub(o->pos, me->pos));
                /* (the man in front must be on the move himself - one who stands there is something to walk round - and nobody waits in a doorway) */
                {   /* (1.3: and really gets on - a man marked "moving" who stands is something to walk round) */
                    const agent *fa = agent_find(b, out->posts[k_].who);
                    if (v_len(rel) < 1.6f && (rel.x * dir.x + rel.y * dir.y) > 0.0f && out->posts[k_].phase == HCB_PH_MOVING && out->posts[k_].act != HCB_ACT_HOLD
                        && fa && now - fa->prog_since < 1500 && !hcb_nav_narrow(b, me->pos)) jam = 1;
                }
            }
            if (jam && !force) {
                a->prog_since = now - 900; a->prog_pos = me->pos; a->why = HCB_WHY2_WAIT_TURN;
                p->via = me->pos; p->move = 0;
                set_act(a, p, HCB_ACT_HOLD, HCB_PH_MOVING, HCB_WHY2_WAIT_TURN);
                continue;
            }
            if (a->fails < 250) a->fails++;
            a->why = HCB_WHY2_NO_PROGRESS; a->last_pos = me->pos;
            if (!hcb_nav_narrow(b, me->pos) && !hcb_nav_narrow(b, p->via)) hcb_nav_block(b, me->pos, p->via, now, 8000);
            a->n_path = 0; a->plan_t = 0; a->prog_best = 1e9f; a->prog_since = now;
            if (l > 0.1f) {                             /* a step round: left, then right, then left ... */
                hcb_vec side;
                float sgn = (a->fails & 1) ? 1.0f : -1.0f;
                side.x = -dir.y / l * sgn; side.y = dir.x / l * sgn; side.z = 0;
                a->via = v_add(me->pos, v_add(v_mul(side, 1.8f), v_mul(dir, 0.6f / l)));
                a->side_until = now + 900;
                p->via = a->via;
            }
        }
        if (a->fails >= 4) { p->stuck = 1; a->why = HCB_WHY2_NO_ROUTE; }
        else if (a->fails >= 1 && now - a->prog_since > 1500) p->stuck = 1;     /* (1.3: a man who stands where he should walk is stuck - and says so) */
        /* the pace */
        {
            u8 act;
            /* (1.3: the first 2.0 log changed a man's pace 19 times a minute - sprint, run, sprint: a band for the urgent pace too,
               and no change within 1.5 s; with no fight a sprint only when CJ himself sprints or the place is far) */
            int was_moving = a->phase == HCB_PH_MOVING && a->act >= HCB_ACT_WALK && a->act <= HCB_ACT_SPRINT;
            if (a->side_until && now < a->side_until) act = HCB_ACT_SIDESTEP;
            else if (follow) act = cj_speed > 4.5f ? HCB_ACT_RUN : cj_speed > 2.2f ? HCB_ACT_FASTWALK : HCB_ACT_WALK;   /* (at CJ's pace) */
            else if (urgent) act = d > (was_moving && a->act == HCB_ACT_SPRINT ? 3.0f : 5.5f) ? HCB_ACT_SPRINT : HCB_ACT_RUN;
            else if (fight) act = d > (was_moving && a->act >= HCB_ACT_RUN ? 2.0f : 3.5f) ? HCB_ACT_RUN : HCB_ACT_WALK;
            else if (cj_speed > 6.0f) act = d > 5.0f ? HCB_ACT_SPRINT : HCB_ACT_RUN;       /* (CJ sprints: nobody is left 30 m behind) */
            else if (cj_speed > 2.2f) act = d > 12.0f ? HCB_ACT_SPRINT : d > 2.5f ? HCB_ACT_RUN : HCB_ACT_FASTWALK;
            else if (inner) act = d > 4.0f ? HCB_ACT_RUN : d > 2.0f ? HCB_ACT_FASTWALK : HCB_ACT_WALK;   /* (a man of the three is never left behind) */
            else act = d > 35.0f ? HCB_ACT_SPRINT : d > 10.0f ? HCB_ACT_RUN : d > 5.0f ? HCB_ACT_FASTWALK : HCB_ACT_WALK;   /* (1.3: a sprint with no threat from 35 m, not 25 - the second 2.0 log: 12 %) */
            if (p->crouch && !fight && !urgent && !follow) act = HCB_ACT_WALK;   /* (1.5: down in peace - CJ creeps, or a man at his place - nobody runs) */
            /* (a pace once taken is kept while the distance is within a metre and a half of where it would change: no flicker) */
            if (was_moving && a->act != act && act >= HCB_ACT_WALK && act <= HCB_ACT_SPRINT) {
                static const float EDGE[4] = {5.0f, 10.0f, 2.5f, 35.0f};
                int k;
                if (!urgent && (act == a->act + 1 || act + 1 == a->act)) for (k = 0; k < 4; k++) if (f_abs(d - EDGE[k]) < 1.5f) act = a->act;   /* (only the pace next to it: a walk at 23 m is not "near the edge" of a sprint) */
                if (a->pace_since && now - a->pace_since < 1500 && f_abs(d - a->pace_d) < 3.0f && !(urgent && act > a->act)) act = a->act;   /* (danger: faster at once) */
            }
            if (act != a->act) { a->pace_since = now ? now : 1; a->pace_d = d; }
            p->move = act == HCB_ACT_SPRINT ? 3 : act == HCB_ACT_RUN || act == HCB_ACT_SIDESTEP ? 2 : 1;
            set_act(a, p, act, HCB_PH_MOVING, 0);
            /* 1.3, fire on the move (the player: "nobody ever fired on the move - backing away from me, firing"): a man on his way
               with an enemy he may fight within 35 m goes facing him - the mod makes it go-and-shoot at a walk or a run (backing
               away, sideways) and fires his weapon itself at a sprint. Weapon on the man while CJ or one of ours is in the line. */
            {
                const hcb_order *od = order_of(out, p->who);
                const hcb_ped *tp = od && od->target ? hcb_ped_of(s, od->target) : 0;
                if (tp && od->hold != HCB_HOLD_ROE && od->hold != HCB_HOLD_NO_TARGET && od->hold != HCB_HOLD_COVERING && od->hold != HCB_HOLD_FISTS
                    && b->alert >= HCB_ALERT_COMBAT && d2(tp->pos, me->pos) < 35.0f) p->face = 1;
            }
            /* 1.1: he stands where the brain's map does not reach (40 m from CJ and more) and has not got on by the straight way:
               the game's own path network takes him towards his place (move 4 - the script walks him by it, as before 2.0)
               until the map has him. That is not a failure of his. */
            if (a->off_map && a->fails >= 2) { p->move = 4; a->why = HCB_WHY2_NO_ROUTE; p->why = a->why; p->via = p->at; if (a->fails > 3 && a->off_map == 1) a->fails = 3; }
        }
    }
    out->n_moving = (u8)moving;
}
