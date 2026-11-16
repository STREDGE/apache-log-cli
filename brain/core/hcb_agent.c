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

HID int hcb_agent_fails(const hcb_brain *b, u32 id) {
    int i;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) return b->ag[i].fails;
    return 0;
}
/* has this man's action failed (six tries), and for at least three seconds (so that he has said so, and the squad does not hand out a new place every second)? */
HID int hcb_agent_failed(const hcb_brain *b, u32 id, u32 now) {
    int i;
    for (i = 0; i < 8; i++) if (b->ag[i].used && b->ag[i].id == id) return b->ag[i].failed_at && now - b->ag[i].failed_at >= 3000;
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
    int i, plans = 0, moving = 0, movers = 0, hot = b->alert >= HCB_ALERT_THREAT;

    if (!s->body) {                                                  /* the script body (the fallback) walks to `at` its own way */
        for (i = 0; i < out->n_posts; i++) out->posts[i].via = out->posts[i].at;
        out->n_moving = 0;
        return;
    }
    for (i = 0; i < 8; i++) if (b->ag[i].used && now - b->ag[i].last_seen > 3000 && b->ag[i].last_seen) b->ag[i].used = 0;
    for (i = 0; i < out->n_posts; i++) {
        hcb_post *p = &out->posts[i];
        const hcb_ped *me = hcb_ped_of(s, p->who);
        agent *a;
        float d, dv, ra;
        int urgent, inner, fight, force = 0;
        hcb_vec feet, gfeet;

        p->via = p->at;
        if (!me) continue;
        a = agent_of(b, p->who, now);
        a->last_seen = now ? now : 1;
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
        d = d2(me->pos, p->at);
        if (p->move == 0 || d < ra) {                                  /* there (or told to stay) */
            if (!a->arrived_since) a->arrived_since = now ? now : 1;
            a->n_path = 0; a->fails = 0; a->prog_since = now; a->prog_best = 1e9f; a->side_until = 0; a->prog_pos = me->pos;
            if (d < ra) p->move = 0;
            set_act(a, p, p->crouch ? HCB_ACT_COVER : p->job == HCB_ROLE_MARKSMAN || p->duty == HCB_DUTY_HOLD ? HCB_ACT_OVERWATCH : HCB_ACT_HOLD,
                    now - a->arrived_since >= 500 ? HCB_PH_ACTING : HCB_PH_ARRIVED, p->why == HCB_WHY2_WAIT_TURN ? HCB_WHY2_WAIT_TURN : HCB_WHY2_ARRIVED);
            continue;
        }
        a->arrived_since = 0;
        /* FAILED (six tries): he stops trying the same thing - he stands and watches for 8 s, then tries again from the
           beginning (the world may have changed: a car gone, a gate open). The squad may have given him another place by then. */
        if (a->fails >= 6) {
            if (!a->failed_at) a->failed_at = now ? now : 1;
            if (now - a->failed_at < 8000) {
                p->via = me->pos; p->move = 0; p->stuck = 1;
                set_act(a, p, HCB_ACT_HOLD, HCB_PH_FAILED, HCB_WHY2_NO_ROUTE);
                continue;
            }
            a->fails = 2; a->failed_at = 0; a->n_path = 0; a->prog_since = now; a->prog_best = 1e9f;
        } else a->failed_at = 0;
        /* 1.1, the token: in a fight no more than movers_max of the outer men / the squad move at a time - the others hold
           and cover until one of them is in place. Never for the three with CJ, a man who is dodging (a grenade, a car), a
           shield or a pull-out, and never while CJ himself is moving (then everybody goes with him). */
        if (!inner && fight && p->act != HCB_ACT_SPRINT && p->duty != HCB_DUTY_SHIELD && p->duty != HCB_DUTY_RING && cj_speed < 1.0f
            && movers >= (int)b->cfg.movers_max && !hcb_nav_narrow(b, me->pos)) {
            p->via = me->pos; p->move = 0;
            a->prog_since = now; a->prog_pos = me->pos; a->prog_best = 1e9f;
            set_act(a, p, HCB_ACT_HOLD, HCB_PH_CHOSEN, HCB_WHY2_WAIT_TURN);
            continue;
        }
        if (!inner) movers++;
        moving++;
        /* the way */
        feet = me->pos; feet.z -= 0.6f; gfeet = p->at; gfeet.z = feet.z + (p->at.z - me->pos.z);
        /* (the step round is over and he has not moved at all: that counts at once, without another 1.5 s of waiting) */
        if (a->side_until && now >= a->side_until && d2(me->pos, a->last_pos) < 0.3f) force = 1;
        if (a->side_until && now < a->side_until) p->via = a->via;       /* stepping round something */
        else {
            int sg = d <= 14.0f ? hcb_nav_seg(b, out, feet, gfeet, now) : 0;
            a->side_until = 0;
            if (d < 2.5f || sg == 1) { p->via = p->at; a->n_path = 0; a->why = HCB_WHY2_DIRECT; }
            else {
                int need = !a->n_path || now - a->plan_t > 2500 || d2(a->path[a->n_path - 1], p->at) > 2.0f;
                if (need && plans < 2) {
                    /* 1.1: the way is found outside the look (hcb_path_ask): asked now, it is here with the next look or the one
                       after. Meanwhile he keeps the way he has; with none he waits where he is (never straight at a wall). */
                    hcb_vec np[AG_PATH];
                    int n = hcb_path_ask(b, out, p->who, me->pos, p->at, np, AG_PATH, now);
                    plans++;
                    if (n == -2) {
                        if (!a->n_path) { p->via = sg == 0 ? me->pos : p->at; a->prog_since = now; a->prog_pos = me->pos; }
                    } else {
                    a->plan_t = now;
                    if (n > 0) { int q_; for (q_ = 0; q_ < n; q_++) a->path[q_] = np[q_]; a->n_path = (u8)n; a->i_path = 0; a->why = HCB_WHY2_ROUTE; }
                    else {
                        a->n_path = 0; a->why = n == 0 ? HCB_WHY2_NO_ROUTE : sg == 0 && d <= 14.0f ? HCB_WHY2_BLOCKED : HCB_WHY2_DIRECT;
                        /* (the map knows the ground and there is no way over it - a roof, a walled yard: that is three failures at
                           once, so the squad gives him another place within a few seconds instead of letting him run at a wall) */
                        if (n == 0) { p->stuck = 1; a->fails = (u8)(a->fails + 3 > 250 ? 250 : a->fails + 3); }
                    }
                    }
                }
                if (a->n_path) {
                    /* on to the next point of the way when he is at this one - or near it with the next one in a straight walk
                       (not sooner: that would cut the corner the way goes round) */
                    while (a->i_path + 1 < a->n_path && (d2(me->pos, a->path[a->i_path]) < 0.6f || (d2(me->pos, a->path[a->i_path]) < 2.0f && hcb_nav_line(b, me->pos, a->path[a->i_path + 1], now)))) a->i_path++;
                    p->via = a->path[a->i_path];
                    if (a->i_path + 1 == a->n_path && d2(a->path[a->i_path], p->at) < 1.5f) p->via = p->at;
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
                                hcb_vec mid = hcb_nav_centre(b, me->pos);
                                a->n_path = 0; a->plan_t = 0; a->why = HCB_WHY2_BLOCKED;
                                /* (not standing there: to the middle of his own cell, clear of the edge he is brushing) */
                                p->via = d2(mid, me->pos) > 0.25f ? mid : me->pos;
                            }
                        }
                    }
                } else if (!(need && d2(p->via, me->pos) < 0.01f)) p->via = p->at;
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
                        moving++;
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
                        moving++;
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
            if (a->fails < 250) a->fails++;
            a->why = HCB_WHY2_NO_PROGRESS; a->last_pos = me->pos;
            hcb_nav_block(b, me->pos, p->via, now, 8000);
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
        /* the pace */
        {
            u8 act;
            if (a->side_until && now < a->side_until) act = HCB_ACT_SIDESTEP;
            else if (urgent) act = d > 4.0f ? HCB_ACT_SPRINT : HCB_ACT_RUN;
            else if (fight) act = d > 3.0f ? HCB_ACT_RUN : HCB_ACT_WALK;
            else if (cj_speed > 4.0f) act = d > 5.0f ? HCB_ACT_SPRINT : HCB_ACT_RUN;       /* (CJ runs: nobody is left 30 m behind) */
            else if (cj_speed > 2.2f) act = d > 2.5f ? HCB_ACT_RUN : HCB_ACT_FASTWALK;
            else if (inner) act = d > 4.0f ? HCB_ACT_RUN : d > 2.0f ? HCB_ACT_FASTWALK : HCB_ACT_WALK;   /* (a man of the three is never left behind) */
            else act = d > 10.0f ? HCB_ACT_RUN : d > 5.0f ? HCB_ACT_FASTWALK : HCB_ACT_WALK;
            /* (a pace once taken is kept while the distance is within a metre and a half of where it would change: no flicker) */
            if (a->phase == HCB_PH_MOVING && a->act != act && a->act >= HCB_ACT_WALK && a->act <= HCB_ACT_SPRINT && act >= HCB_ACT_WALK && act <= HCB_ACT_SPRINT && !urgent) {
                static const float EDGE[3] = {5.0f, 10.0f, 2.5f};
                int k;
                for (k = 0; k < 3; k++) if (f_abs(d - EDGE[k]) < 1.5f) act = a->act;
            }
            p->move = act == HCB_ACT_SPRINT ? 3 : act == HCB_ACT_RUN || act == HCB_ACT_SIDESTEP ? 2 : 1;
            set_act(a, p, act, HCB_PH_MOVING, 0);
        }
    }
    out->n_moving = (u8)moving;
}
