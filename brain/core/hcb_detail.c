/* Helicover Brain - the protective detail on foot (stage 3).
 *
 * Four men round a principal, as a close-protection team works:
 *   - the COMMANDER (call sign Alpha) runs the detail: he picks where CJ is to go when shots come (a spot the threat cannot
 *     see, nearest first and never towards the threat), tells him so - the place is marked on the screen - and takes cover
 *     next to it himself; when he falls the next man takes over and says so;
 *   - the PERSONAL BODYGUARD stays at CJ's side: walking, a pace behind on his right; in a fight his body is between CJ and
 *     the threat, and when CJ is in cover he crouches beside him;
 *   - the FIRE TEAM (point and rear) walks ahead and behind in peace; in a fight it goes to cover on the threat's side, one
 *     man at a time (the other covers him from where he is: bounding overwatch), and fights from there crouched;
 *   - suspect: the bodyguard steps between him and CJ, everybody's weapon comes up;
 *   - too hot (the brain's EVACUATE): a tight ring round CJ and the call for the pickup.
 * The core cannot see walls: it asks the adapter (HCB_MAX_PROBES questions a tick, two rays each) whether a spot is hidden
 * from the threat and has ground under it, keeps the answers a few seconds, and decides from them.
 * Who fires at whom stays the fire plan's business (hcb_fire.c); this module says where each man is and how he holds.
 */
#include "hcb_int.h"

#define CJ_RINGS 4
static const float CJ_RADII[CJ_RINGS] = {2.5f, 4.0f, 6.0f, 8.0f};
/* twelve directions, the first one straight away from the threat, then alternately either side of it */
static const float DIR_C[12] = {1.0f, 0.866025f, 0.866025f, 0.5f, 0.5f, 0.0f, 0.0f, -0.5f, -0.5f, -0.866025f, -0.866025f, -1.0f};
static const float DIR_S[12] = {0.0f, 0.5f, -0.5f, 0.866025f, -0.866025f, 1.0f, -1.0f, 0.866025f, -0.866025f, 0.5f, -0.5f, 0.0f};
#define COVER_KEEP_MS 6000      /* an answer about a spot is good this long */
#define COVER_PENDING_MS 800    /* a question not answered after this is asked again */
#define SAY_COVER_MS 6000       /* "into cover" is repeated this often while CJ is not there */
#define SAY_EVAC_MS 20000

static hcb_vec flat(hcb_vec v) { v.z = 0; return v; }
static float dist2d(hcb_vec a, hcb_vec b) { return v_len(flat(v_sub(a, b))); }
static hcb_vec unit2(hcb_vec v, hcb_vec fallback) {
    float l;
    v.z = 0; l = v_len(v);
    return l > 0.01f ? v_mul(v, 1.0f / l) : fallback;
}
static hcb_vec right_of(hcb_vec f) { hcb_vec r; r.x = f.y; r.y = -f.x; r.z = 0; return r; }
static hcb_vec rot(hcb_vec d, int k) { hcb_vec r; r.x = d.x * DIR_C[k] - d.y * DIR_S[k]; r.y = d.x * DIR_S[k] + d.y * DIR_C[k]; r.z = 0; return r; }
static hcb_vec at_off(hcb_vec base, hcb_vec f, float ahead, hcb_vec r, float right) { return v_add(v_add(base, v_mul(f, ahead)), v_mul(r, right)); }
/* 0 ahead, 1 right, 2 behind, 3 left - seen from CJ, the way he faces */
static u8 rel_dir(const hcb_ped *cj, hcb_vec at) {
    hcb_vec f = unit2(cj->fwd, (hcb_vec){0, 1, 0}), d = unit2(v_sub(at, cj->pos), f);
    float a = v_dot(d, f), r = v_dot(d, right_of(f));
    if (a >= 0.7071f) return 0;
    if (a <= -0.7071f) return 2;
    return r > 0 ? 1 : 3;
}

/* ------------------------------------------------------------------ what is known about spots */
static cover *cv_find(hcb_brain *b, hcb_vec at, hcb_vec from, float slack) {
    int i;
    for (i = 0; i < HCB_MAX_COVERS; i++) {
        cover *c = &b->cv[i];
        if (c->used && dist2d(c->at, at) < 0.35f * slack && v_dist(c->from, from) < 3.5f * slack) return c;
    }
    return 0;
}
static cover *cv_slot(hcb_brain *b) {
    int i, old = 0;
    u32 best = 0xffffffffu;
    for (i = 0; i < HCB_MAX_COVERS; i++) {
        cover *c = &b->cv[i];
        u32 t = c->answered > c->asked ? c->answered : c->asked;
        if (!c->used) return c;
        if (t < best) { best = t; old = i; }
    }
    return &b->cv[old];
}
/* 1 good cover, 0 known to be no cover, -1 not known (ask), -2 asked, the answer is on its way */
static int cv_state(hcb_brain *b, hcb_vec at, hcb_vec from, u32 now) {
    cover *c = cv_find(b, at, from, 1.0f);
    if (!c) return -1;
    if (!c->answered || c->answered < c->asked) return now - c->asked < COVER_PENDING_MS ? -2 : -1;
    if (now - c->answered > COVER_KEEP_MS) return -1;
    return c->hidden && c->ground ? 1 : 0;
}
static void cv_ask(hcb_brain *b, hcb_out *out, hcb_vec at, hcb_vec from, u32 now) {
    cover *c;
    hcb_probe *q;
    if (out->n_probe_q >= HCB_MAX_PROBES) return;
    c = cv_find(b, at, from, 1.0f);
    if (!c) { c = cv_slot(b); zero(c, sizeof *c); c->used = 1; c->at = at; c->from = from; }
    c->asked = now;
    q = &out->probe_q[out->n_probe_q++];
    zero(q, sizeof *q);
    q->at = at; q->from = from;
}
static void cv_learn(hcb_brain *b, const hcb_snapshot *s) {
    int i, n = s->n_probes < HCB_MAX_PROBES ? s->n_probes : HCB_MAX_PROBES;
    for (i = 0; i < n; i++) {
        const hcb_probe *p = &s->probes[i];
        cover *c = cv_find(b, p->at, p->from, 0.2f);
        if (!c) { c = cv_slot(b); zero(c, sizeof *c); c->used = 1; c->at = p->at; c->from = p->from; c->asked = s->time; }
        c->hidden = p->hidden; c->ground = p->ground; c->answered = s->time;
    }
}
/* The nearest spot round `center` hidden from `threat`: rings outwards, each ring starting straight away from the threat.
   `toward` (0..1): spots further than this share of the radius towards the threat are not taken (CJ is not sent towards
   the man who shoots at him; a fire team may be). Unknown spots are asked about while there is room in this tick. */
static int find_cover(hcb_brain *b, hcb_out *out, hcb_vec center, hcb_vec u, hcb_vec threat, const float *radii, int nr, float toward, u32 now, hcb_vec *found) {
    int i, k;
    hcb_vec away = v_mul(u, -1.0f);
    for (i = 0; i < nr; i++) {
        for (k = 0; k < (radii[i] > 0.01f ? 12 : 1); k++) {
            hcb_vec d = rot(away, k), at = v_add(center, v_mul(d, radii[i]));
            int st;
            at.z = center.z;
            if (radii[i] > 0.01f && v_dot(d, u) > toward) continue;
            st = cv_state(b, at, threat, now);
            if (st == 1) { *found = at; return 1; }
            if (st == -1) cv_ask(b, out, at, threat, now);
        }
    }
    return 0;
}

/* how fast to get to a spot d metres away when CJ moves at cj_speed */
static u8 pace(float d, float cj_speed) {
    if (d < 0.9f) return 0;
    if (cj_speed > 5.5f || d > 12.0f) return 3;
    if (cj_speed > 2.2f || d > 5.0f) return 2;
    return 1;
}

/* the man of ours with this id, alive and on foot */
static const hcb_ped *member(const hcb_snapshot *s, u32 id) {
    const hcb_ped *p = hcb_ped_of(s, id);
    return p && !(p->flags & HCB_PF_DEAD) && !p->vehicle ? p : 0;
}

HID void hcb_detail_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out) {
    detail *dt = &b->dt;
    const hcb_ped *cj = &s->player, *men[4], *suspect = 0;
    const track *threat = 0;
    u32 now = s->time, ids[4];
    int i, n = 0, n_ours = s->n_ours < HCB_MAX_OURS ? s->n_ours : HCB_MAX_OURS, lead = -1, close = -1, team[2], n_team = 0;
    float cj_speed = v_len(flat(cj->vel)), best = -1, sbest = -1, leash = s->tactics ? 18.0f : 12.0f, line = s->tactics ? 9.0f : 5.0f;
    hcb_vec cjp = cj->pos, f, r, u, pr, T, look;
    u8 duty, say = HCB_SAY_NONE, say_dir = 0, cj_in = 0;

    out->n_posts = 0; out->n_probe_q = 0; out->say = HCB_SAY_NONE; out->cover_ok = 0; out->lead = 0;
    cv_learn(b, s);

    /* the detail: the guards on foot, by their number (guard 0 is the commander as long as he lives) */
    for (i = 0; i < n_ours && n < 4; i++) {
        int role = s->our_role[i];
        const hcb_ped *p;
        if (role < HCB_ROLE_SQUAD || role > HCB_ROLE_SQUAD + 3) continue;
        p = member(s, s->ours[i]);
        if (!p) continue;
        men[n] = p; ids[n] = s->ours[i]; n++;
    }
    for (i = 1; i < n; i++) {                              /* by their number: the order of the roles */
        int j = i;
        while (j > 0) {
            int ri = 0, rj = 0, k;
            for (k = 0; k < n_ours; k++) { if (s->ours[k] == ids[j]) ri = s->our_role[k]; if (s->ours[k] == ids[j - 1]) rj = s->our_role[k]; }
            if (ri >= rj) break;
            { const hcb_ped *tp = men[j]; u32 ti = ids[j]; men[j] = men[j - 1]; ids[j] = ids[j - 1]; men[j - 1] = tp; ids[j - 1] = ti; }
            j--;
        }
    }
    if (!n || cj->vehicle || (cj->flags & HCB_PF_DEAD) || s->cutscene) {      /* nobody on foot with CJ, or CJ in a vehicle */
        dt->cj_cover_ok = 0; dt->duty = HCB_DUTY_CALM; out->duty = HCB_DUTY_CALM;
        return;
    }

    /* the commander: the same man while he lives; else the first by number, and he says he has taken over */
    for (i = 0; i < n; i++) if (ids[i] == dt->lead) lead = i;
    if (lead < 0) {
        lead = 0;
        if (dt->lead && n) say = HCB_SAY_TAKE_OVER;
        dt->lead = ids[0];
    }
    for (i = 0; i < n; i++) if (i != lead) { if (close < 0) close = i; else if (n_team < 2) team[n_team++] = i; }
    if (n == 1) { close = lead; }                           /* one man left: he is the bodyguard, and in charge */
    out->lead = dt->lead;

    /* the way CJ goes: the formation turns when he has gone a new way (60 degrees or more off) for 1.5 s */
    if (v_len(dt->anchor) < 0.5f) dt->anchor = unit2(cj->fwd, (hcb_vec){0, 1, 0});
    if (cj_speed > 1.5f) {
        hcb_vec d = unit2(cj->vel, dt->anchor);
        if (v_dot(d, dt->anchor) < 0.5f) {
            if (v_len(dt->anchor_try) < 0.5f || v_dot(d, dt->anchor_try) < 0.85f) { dt->anchor_try = d; dt->anchor_since = now; }
            else if (now - dt->anchor_since >= 1500) { dt->anchor = d; dt->anchor_try = (hcb_vec){0, 0, 0}; }
        } else {
            dt->anchor = unit2(v_add(dt->anchor, v_mul(v_sub(d, dt->anchor), 0.2f)), dt->anchor);
            dt->anchor_try = (hcb_vec){0, 0, 0};
        }
    }
    f = dt->anchor; r = right_of(f);

    /* the threat the detail fights: the most dangerous man at THREAT or above; else a suspect to watch */
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        const track *t = &b->tr[i];
        if (!t->used || t->friendly || (t->last.flags & HCB_PF_DEAD)) continue;
        if (t->cls >= HCB_CLS_THREAT && t->edps > best) { best = t->edps; threat = t; }
        else if (t->cls == HCB_CLS_WATCH && t->seen && t->edps > sbest) { sbest = t->edps; suspect = &t->last; }
    }
    duty = b->alert >= HCB_ALERT_EVACUATE && threat ? HCB_DUTY_RING : threat ? HCB_DUTY_COVER : suspect ? HCB_DUTY_WATCH : HCB_DUTY_CALM;
    if (duty >= HCB_DUTY_COVER && dt->duty < HCB_DUTY_COVER) { dt->contact_since = now; dt->cover_said = 0; dt->safe_said = 0; dt->mover = 0; }
    if (duty < HCB_DUTY_COVER && dt->duty >= HCB_DUTY_COVER && (!dt->clear_said || now - dt->clear_said > 10000) && say == HCB_SAY_NONE) { say = HCB_SAY_CLEAR; dt->clear_said = now ? now : 1; }
    if (duty < HCB_DUTY_COVER) dt->cj_cover_ok = 0;
    dt->duty = duty; out->duty = duty;

    T = threat ? threat->last.pos : suspect ? suspect->pos : v_add(cjp, v_mul(f, 10));
    T.z += 0.6f;                                           /* the threat's chest: where a round of his comes from */
    u = unit2(v_sub(T, cjp), f); pr = right_of(u);
    look = T;

    if (duty >= HCB_DUTY_COVER) {
        /* CJ's spot: the one he has, while it still hides him from this threat and is near; else the nearest new one */
        int st = dt->cj_cover_ok ? cv_state(b, dt->cj_cover, T, now) : -1;
        if (!dt->cj_cover_ok || st == 0 || dist2d(dt->cj_cover, cjp) > 14.0f || v_dist(T, dt->threat) > 4.0f) {
            hcb_vec at;
            if (dt->cj_cover_ok && st == -1 && v_dist(T, dt->threat) <= 4.0f && dist2d(dt->cj_cover, cjp) <= 14.0f) cv_ask(b, out, dt->cj_cover, T, now);
            else if (find_cover(b, out, cjp, u, T, CJ_RADII, CJ_RINGS, 0.5f, now, &at)) {
                if (!dt->cj_cover_ok || dist2d(at, dt->cj_cover) > 3.0f) dt->cover_said = 0;
                dt->cj_cover = at; dt->cj_cover_ok = 1; dt->threat = T;
            } else if (st == 0 || dist2d(dt->cj_cover, cjp) > 14.0f || v_dist(T, dt->threat) > 4.0f) dt->cj_cover_ok = 0;
        }
        cj_in = dt->cj_cover_ok && dist2d(cjp, dt->cj_cover) < 1.6f;
        if (!cj_in) dt->safe_said = 0;
    }

#define POST(idx, AT, MOVE, CROUCH, DUTY, JOB, LOOK) do { \
        hcb_post *p_ = &out->posts[out->n_posts++]; zero(p_, sizeof *p_); \
        p_->who = ids[idx]; p_->at = (AT); p_->move = (u8)(MOVE); p_->crouch = (u8)(CROUCH); p_->duty = (u8)(DUTY); p_->job = (u8)(JOB); p_->look = (LOOK); \
    } while (0)

    if (duty == HCB_DUTY_CALM || duty == HCB_DUTY_WATCH) {
        static const float SLOT[4][2] = {{-2.6f, -1.6f}, {-1.3f, 1.1f}, {4.5f, -0.8f}, {-5.0f, 0.6f}};   /* ahead, right: lead, close, point, rear */
        hcb_vec sector[4];
        sector[0] = at_off(cjp, f, 2, r, -8); sector[1] = at_off(cjp, f, 0, r, 8); sector[2] = at_off(cjp, f, 12, r, 0); sector[3] = at_off(cjp, f, -12, r, 0);
        for (i = 0; i < 4; i++) sector[i].z += 0.8f;
        for (i = 0; i < n; i++) {
            int job = i == lead ? 0 : i == close ? 1 : (n_team > 0 && i == team[0]) ? 2 : 3;
            hcb_vec at = at_off(cjp, f, SLOT[job][0], r, SLOT[job][1]), lk = sector[job];
            if (duty == HCB_DUTY_WATCH) {
                if (job == 1) at = v_add(cjp, v_mul(u, 1.3f));          /* the bodyguard steps between the suspect and CJ */
                if (job != 3) lk = T;
            }
            if (n == 1) at = at_off(cjp, f, -1.3f, r, 1.1f);
            POST(i, at, pace(dist2d(at, men[i]->pos), cj_speed), 0, duty, job + 1, lk);
        }
    } else if (duty == HCB_DUTY_RING) {
        /* too hot: a tight ring, the bodyguard towards the threat, nobody further than two metres */
        for (i = 0; i < n; i++) {
            int job = i == lead ? 0 : i == close ? 1 : (n_team > 0 && i == team[0]) ? 2 : 3;
            hcb_vec base = cj_in ? dt->cj_cover : cjp, at;
            at = job == 1 ? v_add(base, v_mul(u, 1.3f)) : job == 0 ? v_add(base, v_mul(pr, -1.5f)) : job == 2 ? v_add(base, v_mul(pr, 1.5f)) : v_add(base, v_mul(u, -1.5f));
            POST(i, at, pace(dist2d(at, men[i]->pos), cj_speed > 2.2f ? cj_speed : 3.0f), 0, HCB_DUTY_RING, job + 1, look);
        }
        if ((!dt->evac_said || now - dt->evac_said >= SAY_EVAC_MS) && say == HCB_SAY_NONE) { say = HCB_SAY_EVAC; dt->evac_said = now ? now : 1; }
    } else {
        /* a fight */
        hcb_vec at;
        int moving[2] = {0, 0};
        hcb_vec spot[2];
        /* the bodyguard: between CJ and the threat; in cover, crouched beside him */
        if (cj_in) POST(close, v_add(dt->cj_cover, v_mul(pr, 0.8f)), pace(dist2d(v_add(dt->cj_cover, v_mul(pr, 0.8f)), men[close]->pos), 3), 1, HCB_DUTY_SHIELD, HCB_ROLE_CLOSE, look);
        else POST(close, v_add(cjp, v_mul(u, 1.3f)), pace(dist2d(v_add(cjp, v_mul(u, 1.3f)), men[close]->pos), cj_speed > 2.2f ? cj_speed : 3.0f), 0, HCB_DUTY_SHIELD, HCB_ROLE_CLOSE, look);
        /* the commander: in cover next to CJ's spot (or beside CJ while there is none) */
        if (lead != close) {
            if (dt->cj_cover_ok) {
                static const float NEAR[3] = {0.0f, 1.2f, 2.4f};
                hcb_vec c0 = v_add(dt->cj_cover, v_mul(pr, -1.6f));
                if (!find_cover(b, out, c0, u, T, NEAR, 3, 1.0f, now, &at)) at = c0;
                POST(lead, at, pace(dist2d(at, men[lead]->pos), 3), 1, HCB_DUTY_COVER, HCB_ROLE_LEAD, look);
            } else {
                at = v_add(v_add(cjp, v_mul(u, 0.6f)), v_mul(pr, -1.6f));
                POST(lead, at, pace(dist2d(at, men[lead]->pos), cj_speed > 2.2f ? cj_speed : 3.0f), 0, HCB_DUTY_SHIELD, HCB_ROLE_LEAD, look);
            }
        }
        /* the fire team: cover on the threat's side of CJ, left and right of the line; one moves while the other covers him */
        for (i = 0; i < n_team; i++) {
            static const float NEAR[3] = {0.0f, 1.5f, 3.0f};
            hcb_vec c0 = v_add(v_add(cjp, v_mul(u, line)), v_mul(pr, i == 0 ? -4.0f : 4.0f)), d;
            float far;
            if (!find_cover(b, out, c0, u, T, NEAR, 3, 1.0f, now, &spot[i])) spot[i] = c0;
            d = flat(v_sub(spot[i], cjp)); far = v_len(d);
            if (far > leash) spot[i] = v_add(cjp, v_mul(d, leash / far));
            spot[i].z = cjp.z;
            moving[i] = dist2d(spot[i], men[team[i]]->pos) > 2.0f;
        }
        if (n_team == 2 && moving[0] && moving[1]) {
            /* bounding overwatch: only one runs; the other holds where he is, crouched, and covers him */
            int m = dt->mover == ids[team[1]] ? 1 : 0;
            dt->mover = ids[team[m]];
            POST(team[m], spot[m], pace(dist2d(spot[m], men[team[m]]->pos), 3), 0, HCB_DUTY_BOUND, m == 0 ? HCB_ROLE_POINT : HCB_ROLE_REAR, look);
            POST(team[1 - m], men[team[1 - m]]->pos, 0, 1, HCB_DUTY_HOLD, m == 0 ? HCB_ROLE_REAR : HCB_ROLE_POINT, look);
        } else {
            for (i = 0; i < n_team; i++) {
                if (moving[i]) dt->mover = ids[team[i]];
                POST(team[i], spot[i], pace(dist2d(spot[i], men[team[i]]->pos), 3), moving[i] ? 0 : 1, moving[i] ? HCB_DUTY_BOUND : HCB_DUTY_COVER, i == 0 ? HCB_ROLE_POINT : HCB_ROLE_REAR, look);
            }
        }
        /* what the commander tells CJ */
        if (say == HCB_SAY_NONE) {
            if (dt->cj_cover_ok && !cj_in && (!dt->cover_said || now - dt->cover_said >= SAY_COVER_MS)) { say = HCB_SAY_TAKE_COVER; say_dir = rel_dir(cj, dt->cj_cover); dt->cover_said = now ? now : 1; }
            else if (cj_in && !dt->safe_said) { say = HCB_SAY_IN_COVER; dt->safe_said = 1; }
            else if (!dt->cj_cover_ok && now - dt->contact_since >= 1500 && (!dt->cover_said || now - dt->cover_said >= 8000)) {
                say = HCB_SAY_FOLLOW_ME; say_dir = rel_dir(cj, v_sub(cjp, v_mul(u, 5.0f))); dt->cover_said = now ? now : 1;
            }
        }
    }
#undef POST
    /* CJ is shooting (a round in the last 1.2 s): nobody stands in front of his gun - a post within 2 m of his line, up to
       40 m ahead, steps out sideways (the bodyguard only 1.2 m, he stays half in front of CJ) */
    if (dt->cj_shot_t && now - dt->cj_shot_t < 1200) {
        hcb_vec d = dt->cj_shot_dir, side;
        side.x = -d.y; side.y = d.x; side.z = 0;
        for (i = 0; i < out->n_posts; i++) {
            hcb_post *p = &out->posts[i];
            hcb_vec rel = flat(v_sub(p->at, cjp));
            float along = rel.x * d.x + rel.y * d.y, lat = rel.x * side.x + rel.y * side.y;
            float need = p->duty == HCB_DUTY_SHIELD ? 1.2f : 2.0f;
            if (p->move < 0 || along < 0.3f || along > 40.0f || f_abs(lat) >= need) continue;
            p->at = v_add(p->at, v_mul(side, (lat < 0 ? -need : need) - lat));
            if (p->move == 0) p->move = 2;
        }
    }
    out->cover_ok = (u8)(duty >= HCB_DUTY_COVER && dt->cj_cover_ok && !cj_in);
    out->cover_at = dt->cj_cover;
    if (say != HCB_SAY_NONE) { dt->say_seq++; dt->last_say = say; dt->say_dir = say_dir; }
    out->say = say; out->say_dir = dt->say_dir; out->say_seq = dt->say_seq;
}
