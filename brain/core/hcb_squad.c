/* Helicover Brain 1.0 - the squad: what the eight are doing together.
 *
 * The PLAYER chooses the mode (PROTECT / ASSAULT); the squad chooses the task inside it; a man's own reaction never changes
 * either. PROTECT is laid out by hcb_detail.c (three at CJ, four in cover that sees CJ and the attackers, the marksman up
 * high); this module adds what is common to both and all of ASSAULT.
 *
 * ASSAULT, one compromise of what the open sources describe (squad manuals: one element moves, one covers; the small
 * assault groups of 2022-25: pairs, gather first, then go; police teams: nobody runs into the open in a heap):
 *   the target   - the man CJ aims or fires at; else the most dangerous confirmed threat in sight; else the place where
 *                  the target was last SEEN, for 20 s. A man nobody sees is not known: his place is not read.
 *   APPROACH     - further than 45 m: a wedge towards the target, at a walk / run, 8 m apart.
 *   GATHER       - at 32 m from the target: six of eight in place, or 15 s, then on.
 *   BOUND        - the fire team (three, with the marksman) holds 30-40 m off on both sides and fires; the assault four
 *                  go in two pairs, one pair at a time, 8 m a rush, on a flank 35 degrees off the fire team's line (never
 *                  through it); a pair moves only when the other is down in place and the fire team has had 2 s.
 *   SEARCH       - the target out of sight 6 s: to where it was last seen, the same way.
 *   CONSOLIDATE  - there, nothing left: all-round watch for 8 s, 12 m to the side of the spot.
 *   REGROUP      - no target: back to CJ, the mode stays ASSAULT and waits for the next one.
 *   WITHDRAW     - three of ours down since the start: back to CJ.
 *   CJ badly hurt (under 40) or the brain's EVACUATE: the two bodyguards go back to him while that holds.
 * The marksman's high place: the adapter finds flat places well above CJ; the squad picks one that sees CJ, and the
 * helicopter takes him there by rope (a man cannot climb a real roof in this game: the climb reaches 3 m). */
#include "hcb_int.h"

HID int hcb_cover_near(hcb_brain *b, hcb_out *out, hcb_vec center, hcb_vec u, hcb_vec threat, u32 now, hcb_vec *found);   /* hcb_detail.c */

static hcb_vec flat(hcb_vec v) { v.z = 0; return v; }
static float d2(hcb_vec a, hcb_vec b) { return v_len(flat(v_sub(a, b))); }
static hcb_vec unit2(hcb_vec v, hcb_vec fb) { float l; v.z = 0; l = v_len(v); return l > 0.01f ? v_mul(v, 1.0f / l) : fb; }
static hcb_vec right_of(hcb_vec f) { hcb_vec r; r.x = f.y; r.y = -f.x; r.z = 0; return r; }

HID int hcb_squad_roping(const hcb_snapshot *s, u32 id) {
    int i, n = s->n_ours < HCB_MAX_OURS ? s->n_ours : HCB_MAX_OURS;
    for (i = 0; i < n; i++) if (s->ours[i] == id) return (s->our_state[i] & HCB_OS_ROPING) != 0;
    return 0;
}

static void set_task(squad *q, u8 task, u32 now) {
    if (q->task != task) { q->task = task; q->task_since = now ? now : 1; q->gathered = 0; q->bound_since = now; }
}

/* 1.1: a man's place in the assault is chosen by weights among what lies within `reach` of the spot the drill wants him at
   (hcb_places.c): low cover with a line of fire first, clear of the others' places, never on the line CJ - target */
static int place_near(hcb_brain *b, hcb_out *out, const squad *q, int slot, hcb_vec c0, hcb_vec man, hcb_vec cjp, hcb_vec T, float reach, u32 now, hcb_vec *found) {
    place_in in;
    float sc;
    int cv, k;
    zero(&in, sizeof in);
    in.anchor = c0; in.man = man; in.cj = cjp; in.threat = T; in.reach = reach; in.threat_min = b->cfg.assault_near_m;
    for (k = 0; k < 8 && in.n_taken < 8; k++) if (k != slot && q->apost_ok[k]) in.taken[in.n_taken++] = q->apost[k];
    if (!hcb_place_pick(b, out, &in, now, found, &sc, &cv)) return 0;
    found->z = c0.z;
    return 1;
}
/* the marksman's high place, and the helicopter that takes him there */
static void overwatch(hcb_brain *b, const hcb_snapshot *s, hcb_out *out, int n_ground, int have_marksman, int mk_roping) {
    squad *q = &b->sq;
    u32 now = s->time;
    int i, best = -1, n = s->n_high < HCB_MAX_HIGH ? s->n_high : HCB_MAX_HIGH;
    float bs = -1e9f;
    hcb_vec cjp = s->player.pos;

    out->ow_ok = 0; out->ow_ready = 0;
    /* he is on the rope over his roof: the helicopter stays where it hangs until he stands */
    if (have_marksman && mk_roping && q->ow_ok && s->heli) { out->heli_ok = 1; out->heli_at = q->ow_at; out->heli_at.z += 11.0f; return; }
    if (have_marksman || !s->heli || n_ground < 3 || s->interior || s->player.vehicle || b->alert >= HCB_ALERT_COMBAT) { q->ow_ok = 0; q->ow_since = 0; return; }
    /* (one try of 40 s for each commander's team: after that he comes down with the others) */
    if (q->ow_done_for == out->lead && out->lead) { q->ow_ok = 0; return; }
    for (i = 0; i < n; i++) {
        const hcb_high *h = &s->high[i];
        float d = d2(h->at, cjp), sc;
        if (!h->sees_cj || h->height < b->cfg.ow_min_h || h->height > b->cfg.ow_max_h || d < b->cfg.ow_min_d || d > b->cfg.ow_max_d) continue;
        sc = (h->height > 15.0f ? 15.0f : h->height) * 0.1f - f_abs(d - 30.0f) / 30.0f;
        if (q->ow_ok && d2(h->at, q->ow_at) < 3.0f) sc += 1.0f;        /* the one already chosen is kept */
        if (sc > bs) { bs = sc; best = i; }
    }
    if (best < 0) { if (q->ow_ok && now - q->ow_since > 3000) q->ow_ok = 0; if (!q->ow_ok) return; }
    else { if (!q->ow_ok) q->ow_since = now ? now : 1; q->ow_at = s->high[best].at; q->ow_ok = 1; }
    if (now - q->ow_since > (u32)b->cfg.ow_try_ms) { q->ow_ok = 0; q->ow_done_for = out->lead; return; }
    out->ow_ok = 1; out->ow_at = q->ow_at;
    out->heli_ok = 1; out->heli_at = q->ow_at; out->heli_at.z += 11.0f;
    {
        const vtrack *hv = hcb_vfind(b, s->heli);
        if (hv && d2(hv->last.pos, q->ow_at) < 4.0f && v_len(hv->last.vel) < 1.5f && f_abs(hv->last.pos.z - out->heli_at.z) < 5.0f) out->ow_ready = 1;
    }
}

HID void hcb_squad_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out) {
    squad *q = &b->sq;
    u32 now = s->time;
    const hcb_ped *cj = &s->player, *men[8];
    hcb_post *post[8];
    hcb_vec cjp = cj->pos, u, side, front, T;
    const track *tg = 0;
    int i, k, n = 0, have_marksman = 0, mk_roping = 0, n_ground = 0, danger_cj, seen = 0, n_ours = s->n_ours < HCB_MAX_OURS ? s->n_ours : HCB_MAX_OURS;
    float best = -1, D;

    q->umode = s->umode == HCB_UMODE_ASSAULT ? HCB_UMODE_ASSAULT : HCB_UMODE_PROTECT;
    out->umode = q->umode; out->target = 0; out->target_dist = 0; out->target_at = cjp;
    for (i = 0; i < n_ours; i++) {
        const hcb_ped *p;
        if (s->our_role[i] < HCB_ROLE_SQUAD || s->our_role[i] > HCB_ROLE_SQUAD + 7) continue;
        p = hcb_ped_of(s, s->ours[i]);
        if (!p || (p->flags & HCB_PF_DEAD)) continue;
        if (s->our_role[i] == HCB_ROLE_SQUAD + 7) { have_marksman = 1; mk_roping = (s->our_state[i] & HCB_OS_ROPING) != 0; }
        if (!(s->our_state[i] & HCB_OS_ROPING) && !p->vehicle) n_ground++;
    }
    overwatch(b, s, out, n_ground, have_marksman, mk_roping);
    for (i = 0; i < out->n_posts && n < 8; i++) {
        const hcb_ped *p = hcb_ped_of(s, out->posts[i].who);
        if (!p || hcb_squad_roping(s, out->posts[i].who)) continue;
        men[n] = p; post[n] = &out->posts[i]; n++;
    }
    /* PROTECT, or nobody to send: the task follows the detail's duty */
    if (q->umode == HCB_UMODE_PROTECT || !n || s->recall || cj->vehicle || (cj->flags & HCB_PF_DEAD) || s->interior || s->cutscene) {
        set_task(q, q->umode == HCB_UMODE_ASSAULT ? HCB_TASK_REGROUP : out->duty == HCB_DUTY_RING ? HCB_TASK_EXTRACT : out->duty >= HCB_DUTY_COVER ? HCB_TASK_SHIELD : HCB_TASK_ESCORT, now);
        q->target = 0; q->target_seen = 0;
        for (i = 0; i < 8; i++) q->apost_ok[i] = 0;
        out->task = q->task;
        return;
    }
    /* ---- ASSAULT: the target */
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        const track *t = &b->tr[i];
        float v;
        if (!t->used || t->friendly || (t->last.flags & HCB_PF_DEAD) || !t->seen) continue;
        if (t->cj_marked && now - t->cj_marked < 6000) v = 10000.0f + (float)(t->cj_marked & 0xffff) * 0.001f;   /* the man CJ points out */
        else if (t->cls >= HCB_CLS_THREAT) v = t->edps + (t->last.id == q->target ? 25.0f : 0.0f);           /* (the one in hand is kept) */
        else continue;
        if (v > best) { best = v; tg = t; }
    }
    if (tg) { q->target = tg->last.id; q->target_at = tg->last.pos; q->target_seen = now ? now : 1; q->lost_since = 0; seen = 1; }
    else if (q->target_seen && now - q->target_seen < (u32)b->cfg.target_keep_ms) { if (!q->lost_since) q->lost_since = now ? now : 1; }
    else { q->target = 0; q->target_seen = 0; }
    /* the man the squad was after is seen dead: that task is done at once (no 20 s of looking for him) - all-round watch if
       the squad is already close, else straight back */
    if (!tg && q->target) {
        const hcb_ped *dead = hcb_ped_of(s, q->target);
        if (dead && (dead->flags & HCB_PF_DEAD)) {
            q->target = 0; q->target_seen = 0;
            if (q->task >= HCB_TASK_GATHER && q->task <= HCB_TASK_SEARCH && q->target_dist < 30.0f) set_task(q, HCB_TASK_CONSOLIDATE, now);
        }
    }
    if (!q->target_seen) {
        if (q->task != HCB_TASK_REGROUP && q->task != HCB_TASK_CONSOLIDATE) set_task(q, HCB_TASK_REGROUP, now);
        if (q->task == HCB_TASK_CONSOLIDATE && now - q->task_since >= (u32)b->cfg.consolidate_ms) set_task(q, HCB_TASK_REGROUP, now);
        if (q->task == HCB_TASK_REGROUP) { for (i = 0; i < 8; i++) q->apost_ok[i] = 0; out->task = q->task; return; }
    }
    /* three of ours down since this task began: enough - back to CJ (the detail's own places stand) until the target is gone */
    if (q->task < HCB_TASK_APPROACH || q->task == HCB_TASK_REGROUP) q->pad0 = (u8)n;
    if (q->task == HCB_TASK_WITHDRAW || q->pad0 >= n + (int)b->cfg.withdraw_down) {
        set_task(q, HCB_TASK_WITHDRAW, now);
        for (i = 0; i < 8; i++) q->apost_ok[i] = 0;
        out->task = q->task; out->target = seen ? q->target : 0; out->target_at = q->target_at;
        return;
    }
    T = q->target_at;
    /* the squad's front: the middle of the men who are out (the bodyguards of a hurt CJ do not count) */
    danger_cj = cj->health < b->cfg.cj_low_hp || b->alert >= HCB_ALERT_EVACUATE;
    front.x = front.y = front.z = 0; k = 0;
    /* (1.3: the two bodyguards stay with CJ in ASSAULT and the marksman keeps his height: neither is in the front) */
    for (i = 0; i < n; i++) if (post[i]->job != HCB_ROLE_CLOSE && post[i]->job != HCB_ROLE_CLOSE2 && post[i]->job != HCB_ROLE_MARKSMAN) { front = v_add(front, men[i]->pos); k++; }
    if (!k) { out->task = q->task; return; }
    front = v_mul(front, 1.0f / (float)k);
    q->front = front;
    u = unit2(v_sub(T, front), unit2(cj->fwd, (hcb_vec){0, 1, 0})); side = right_of(u);
    D = d2(T, front);
    q->target_dist = D;
    out->target = seen ? q->target : 0; out->target_dist = D; out->target_at = T;
    /* 1.3 (the first 2.0 log: CJ died alone while the whole squad was 16-60 m off on the assault): CJ hurt, an evacuation, or
       CJ 60 m from the squad - everybody back to him, for 8 s at least */
    {   /* (CJ going away from the squad at a run: back to him from 35 m - the plan's "CJ has left the squad behind"; measured from the
           men who are out, not the commander, who comes back to CJ by himself) */
        hcb_vec out4 = {0, 0, 0}, away;
        float la, va;
        int k4 = 0;
        for (i = 0; i < n; i++) if (post[i]->job == HCB_ROLE_POINT || post[i]->job == HCB_ROLE_POINT2 || post[i]->job == HCB_ROLE_REAR || post[i]->job == HCB_ROLE_REAR2) { out4 = v_add(out4, men[i]->pos); k4++; }
        out4 = k4 ? v_mul(out4, 1.0f / (float)k4) : front;
        away = flat(v_sub(cjp, out4));
        la = v_len(away); va = la > 0.1f ? (cj->vel.x * away.x + cj->vel.y * away.y) / la : 0.0f;
        if (danger_cj || la > 60.0f || (la > 35.0f && va > 2.0f)) q->regroup_until = now + 8000;
    }
    if (q->regroup_until && now < q->regroup_until) {
        set_task(q, HCB_TASK_REGROUP, now);
        for (i = 0; i < 8; i++) q->apost_ok[i] = 0;
        out->task = q->task;
        return;
    }
    /* the task */
    if (q->task == HCB_TASK_ESCORT || q->task == HCB_TASK_SHIELD || q->task == HCB_TASK_EXTRACT || q->task == HCB_TASK_REGROUP)
        set_task(q, D > 45.0f ? HCB_TASK_APPROACH : D > 20.0f ? HCB_TASK_GATHER : HCB_TASK_BOUND, now);
    if (q->task == HCB_TASK_APPROACH && D <= 45.0f) set_task(q, HCB_TASK_GATHER, now);
    if (q->task == HCB_TASK_GATHER) {
        int there = 0;
        for (i = 0; i < n; i++) if (d2(men[i]->pos, post[i]->at) < 6.0f) there++;
        if ((q->gathered && there * 4 >= n * 3) || now - q->task_since >= 15000) set_task(q, HCB_TASK_BOUND, now);
        q->gathered = 1;                                               /* (counted from the second look: the posts are this task's) */
    }
    if ((q->task == HCB_TASK_BOUND || q->task == HCB_TASK_SEARCH) && !seen && q->lost_since && now - q->lost_since >= (u32)b->cfg.search_ms) set_task(q, HCB_TASK_SEARCH, now);
    if (q->task == HCB_TASK_SEARCH && seen) set_task(q, HCB_TASK_BOUND, now);
    if ((q->task == HCB_TASK_SEARCH || q->task == HCB_TASK_BOUND) && !seen && D < 10.0f) { set_task(q, HCB_TASK_CONSOLIDATE, now); q->target_seen = 0; q->target = 0; }
    if (q->task == HCB_TASK_CONSOLIDATE && seen) set_task(q, HCB_TASK_BOUND, now);
    out->task = q->task;

    /* ---- the places */
    {
        /* pairs: A1 = CLOSE + POINT, A2 = CLOSE2 + POINT2; fire team = REAR, REAR2, MARKSMAN; the leader behind the front pair */
        int moved_all = 1, fire_ok = 0;
        float lead_adv = 0;
        for (i = 0; i < out->n_orders; i++) if (out->orders[i].fire) fire_ok = 1;
        if (!seen) fire_ok = 1;                                        /* nobody to fire at: nothing to wait for */
        if (s->roe == HCB_ROE_HOLD) fire_ok = 1;                       /* (1.3: under HOLD FIRE nobody covers by fire: the pairs do not wait for it for ever) */
        if (fire_ok && !q->bound_since) q->bound_since = now ? now : 1;
        /* whose turn: the pair on the move has arrived (or 6 s have passed) -> the other pair */
        for (i = 0; i < n; i++) {
            int pair = post[i]->job == HCB_ROLE_POINT ? 0 : post[i]->job == HCB_ROLE_POINT2 ? 1 : -1;
            int m;
            if (pair != q->mover) continue;
            for (m = 0; m < 8; m++) if (q->apost_ok[m] && q->apost_id[m] == post[i]->who && d2(men[i]->pos, q->apost[m]) > 1.6f) moved_all = 0;
        }
        if (q->task == HCB_TASK_BOUND || q->task == HCB_TASK_SEARCH) {
            if ((moved_all && now - q->bound_since >= (u32)b->cfg.fire_first_ms) || now - q->bound_since >= 8000) { q->mover ^= 1; q->bound_since = now ? now : 1; for (i = 0; i < 8; i++) if (q->apost_ok[i] == 2) q->apost_ok[i] = 3; }
        }
        for (i = 0; i < n; i++) {
            hcb_post *p = post[i];
            hcb_vec at = men[i]->pos, want;
            int slot = -1, m, pair = -1, fire_team = 0, w = 0, is_lead = p->job == HCB_ROLE_LEAD, hold = 0;
            u8 duty = HCB_DUTY_BOUND, crouch = 0;
            /* 1.3: the two bodyguards never leave CJ (the detail's post stands); the commander goes with the squad only while CJ is
               within 25 m of it; the marksman's place is his own (hcb_marksman_plan) */
            if (p->job == HCB_ROLE_CLOSE || p->job == HCB_ROLE_CLOSE2 || p->job == HCB_ROLE_MARKSMAN) continue;
            if (is_lead && d2(cjp, front) > 25.0f) continue;
            for (m = 0; m < 8; m++) if (q->apost_id[m] == p->who) slot = m;
            if (slot < 0) { for (m = 0; m < 8; m++) if (!q->apost_ok[m]) { slot = m; break; } if (slot < 0) slot = i; q->apost_id[slot] = p->who; q->apost_ok[slot] = 0; }
            switch (p->job) {
            case HCB_ROLE_POINT: pair = 0; w = 0; break;     /* (1.3: the assault pair is POINT and POINT2, one a rush each in turn) */
            case HCB_ROLE_POINT2: pair = 1; w = 0; break;
            case HCB_ROLE_REAR: fire_team = 1; w = 0; break;
            case HCB_ROLE_REAR2: case HCB_ROLE_CLOSE3: fire_team = 1; w = 1; break;
            case HCB_ROLE_MARKSMAN: fire_team = 1; w = 2; break;
            default: break;
            }
            if (q->task == HCB_TASK_APPROACH) {
                /* a wedge that keeps 14 m ahead of its own middle: it walks until the target is 45 m off */
                static const float WX[8] = {0, -8, 8, -16, 16, -4, 4, 0}, WY[8] = {0, -4, -4, -8, -8, -12, -12, -16};
                int idx = is_lead ? 7 : pair == 0 ? w : pair == 1 ? 2 + w : 4 + w;
                want = v_add(front, v_add(v_mul(u, 14.0f + WY[idx]), v_mul(side, WX[idx])));
                duty = HCB_DUTY_CALM;
            } else if (q->task == HCB_TASK_GATHER) {
                static const float GX[8] = {-3, -7, 3, 7, -12, 12, 0, 0}, GY[8] = {0, 2, 0, 2, -4, -4, -12, -5};
                int idx = is_lead ? 7 : pair == 0 ? w : pair == 1 ? 2 + w : 4 + w;
                want = v_add(v_sub(T, v_mul(u, b->cfg.gather_m)), v_add(v_mul(u, GY[idx]), v_mul(side, GX[idx])));
                duty = HCB_DUTY_COVER; crouch = d2(men[i]->pos, want) < 1.5f;
            } else if (q->task == HCB_TASK_CONSOLIDATE) {
                /* all-round watch, 12 m to the side of the spot (never ON it) */
                static const float CC[8] = {1.0f, 0.7071f, 0.0f, -0.7071f, -1.0f, -0.7071f, 0.0f, 0.7071f}, CS[8] = {0.0f, 0.7071f, 1.0f, 0.7071f, 0.0f, -0.7071f, -1.0f, -0.7071f};
                hcb_vec c = v_add(T, v_mul(side, 12.0f));
                want.x = c.x + CC[i & 7] * 7.0f; want.y = c.y + CS[i & 7] * 7.0f; want.z = men[i]->pos.z;
                p->look.x = c.x + CC[i & 7] * 40.0f; p->look.y = c.y + CS[i & 7] * 40.0f; p->look.z = men[i]->pos.z + 0.8f;
                {   /* (nobody walks over the spot itself on his way there: round it, 6 m short of it on CJ's side) */
                    float t_;
                    hcb_vec m2 = flat(men[i]->pos), w2 = flat(want), t2 = flat(T);
                    if (seg_dist(t2, m2, w2, &t_) < 4.0f) { hcb_vec mid = v_sub(T, v_mul(u, 6.0f)); mid.z = men[i]->pos.z; if (d2(men[i]->pos, mid) > 1.5f) want = mid; }
                }
                duty = HCB_DUTY_HOLD; crouch = d2(men[i]->pos, want) < 1.5f;
            } else if (fire_team) {
                /* the base of fire: both sides of the line, the marksman behind; placed once, then kept */
                static const float FX[3] = {-11.0f, 11.0f, 3.0f}, FB[3] = {34.0f, 34.0f, 46.0f};
                float back = D < FB[w] ? (D > 14.0f ? D : 14.0f) : FB[w];
                if (q->apost_ok[slot] && d2(q->apost[slot], T) < 60.0f && d2(q->apost[slot], T) > 10.0f) want = q->apost[slot];
                else {
                    hcb_vec c0 = v_add(v_sub(T, v_mul(u, back)), v_mul(side, FX[w])), found;
                    c0.z = men[i]->pos.z;
                    want = place_near(b, out, q, slot, c0, men[i]->pos, cjp, T, 7.5f, now, &found) ? found : c0;
                    q->apost[slot] = want; q->apost_ok[slot] = 1; q->apost_t[slot] = now;
                }
                duty = d2(men[i]->pos, want) < 1.5f ? HCB_DUTY_COVER : HCB_DUTY_BOUND; crouch = d2(men[i]->pos, want) < 1.5f && p->job != HCB_ROLE_MARKSMAN;
            } else if (pair >= 0) {
                /* the assault pairs: on a flank 35 degrees off the line (pair 0 left, pair 1 right), 8 m a rush, never
                   nearer than 9 m; the pair whose turn it is not stays down */
                float sgn = pair == 0 ? -1.0f : 1.0f, co = 0.8192f, si = 0.5736f * sgn;
                hcb_vec ax;                                            /* from the target back along the flank line */
                float dd;
                ax.x = -(u.x * co - u.y * si); ax.y = -(u.x * si + u.y * co); ax.z = 0;
                if (pair != q->mover || !fire_ok) hold = 1;
                if (q->apost_ok[slot] == 2 || (hold && q->apost_ok[slot])) want = q->apost[slot];      /* this rush's place, or holding */
                else {
                    hcb_vec me = men[i]->pos, rel = flat(v_sub(me, T)), c0, found;
                    float along = rel.x * ax.x + rel.y * ax.y;         /* how far out on the flank line he is */
                    dd = along - b->cfg.rush_m;
                    if (dd < b->cfg.assault_near_m) dd = b->cfg.assault_near_m;
                    if (along <= b->cfg.assault_near_m + 0.5f && q->apost_ok[slot]) { want = q->apost[slot]; }
                    else {
                        c0 = v_add(T, v_add(v_mul(ax, dd), v_mul(right_of(ax), w ? 4.0f : -4.0f)));
                        c0.z = me.z;
                        /* (the first rush takes him from wherever he is on to the flank line: at most 14 m at a time) */
                        if (d2(c0, me) > 14.0f) { hcb_vec dr = unit2(v_sub(c0, me), u); c0 = v_add(me, v_mul(dr, 14.0f)); c0.z = me.z; }
                        want = place_near(b, out, q, slot, c0, me, cjp, T, 5.0f, now, &found) ? found : c0;
                        q->apost[slot] = want; q->apost_t[slot] = now;
                    }
                    q->apost_ok[slot] = hold ? 3 : 2;
                }
                if (hold && !q->apost_ok[slot]) { want = men[i]->pos; q->apost[slot] = want; q->apost_ok[slot] = 3; }
                duty = hold ? HCB_DUTY_HOLD : HCB_DUTY_BOUND;
                crouch = d2(men[i]->pos, want) < 1.5f;
                if (hold) p->why = HCB_WHY2_WAIT_TURN;
                if (d2(want, T) < lead_adv || lead_adv == 0) lead_adv = d2(want, T);
            } else {
                /* the leader: 7 m behind the pair that is furthest forward, on the line */
                float back = (lead_adv > 0 ? lead_adv : D) + 7.0f;
                if (back > D + 4.0f) back = D + 4.0f;
                if (back < 16.0f) back = 16.0f;
                want = v_sub(T, v_mul(u, back));
                duty = HCB_DUTY_COVER; crouch = d2(men[i]->pos, want) < 1.5f && seen;
            }
            want.z = men[i]->pos.z;
            at = want;
            p->at = at; p->duty = duty; p->crouch = crouch; p->stuck = 0;
            if (q->task != HCB_TASK_CONSOLIDATE) { p->look = T; p->look.z += 0.6f; }
            p->move = d2(men[i]->pos, at) < 0.9f ? 0 : (hold ? 0 : 2);
            if (hold && d2(men[i]->pos, at) >= 1.6f) p->move = 2;       /* (not yet at the place he is to hold) */
            p->act = duty == HCB_DUTY_BOUND && (q->task == HCB_TASK_BOUND || q->task == HCB_TASK_SEARCH) && pair >= 0 ? HCB_ACT_SPRINT : 0;
        }
    }
}

/* ---------- 1.3: the marksman (the player: "no roof near - let him improvise a place to watch from; a roof he cannot get up -
   let him see that himself and get up some real way; changing places - a real, quick way down") ----------
   In this order, the first that will do within 60 m of CJ:
     a roof the adapter has found (4-35 m over CJ's feet, CJ seen from it) that he can get up on foot: a wall up to 2.8 m over his
       feet is climbed (the game's own jump-and-climb, the one CJ uses), a higher one up to 4.6 m from the roof of a car standing
       within 7 m of it (two climbs);
     high ground: a cell of the brain's map 2 m and more over CJ's feet, 12-45 m off (stairs, a bank, a raised car park);
     the roof of a big vehicle standing within 35 m (bus, truck, van): climbed;
     a long look: a spot 28 m out on the side the threat is (or CJ is going), down on one knee, watching.
   He sees for himself that he cannot get up: three climbs or 20 s at one place and it is left alone for a minute.
   Once up he stays while CJ is within 60 m of him; CJ 10 s beyond that - he comes down the quickest way: off the edge nearest
   his next place (the mod slows a fall of ours), and on. */
#define MK_NONE 0
#define MK_ROOF 1           /* going for a roof he can climb */
#define MK_STEP 2           /* ... by way of a car beside it */
#define MK_HIGHGROUND 3
#define MK_VROOF 4          /* the roof of a big vehicle */
#define MK_LONG 5
#define MK_UP 6             /* he is up there: he stays */
static int big_vehicle(int model) {
    static const short M[] = {431, 437, 403, 514, 515, 456, 499, 498, 609, 414, 455, 578, 524, 443, 428, 427, 601, 528, 433, 573, 408, 440, 482, 413, 459, 588, 423};
    unsigned i;
    for (i = 0; i < sizeof M / sizeof M[0]; i++) if (M[i] == model) return 1;
    return 0;
}
static int mk_is_bad(const squad *q, hcb_vec at, u32 now) {
    int i;
    for (i = 0; i < 4 && i < q->mk_n_bad; i++) if (q->mk_bad_t[i] && now - q->mk_bad_t[i] < 60000 && d2(q->mk_bad[i], at) < 4.0f) return 1;
    return 0;
}
static void mk_mark_bad(squad *q, hcb_vec at, u32 now) {
    int i = q->mk_n_bad < 4 ? q->mk_n_bad++ : (int)(now / 1000 % 4);
    q->mk_bad[i] = at; q->mk_bad_t[i] = now ? now : 1;
}
HID void hcb_marksman_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out) {
    squad *q = &b->sq;
    u32 now = s->time;
    hcb_post *p = 0;
    const hcb_ped *me = 0, *cj = &s->player;
    hcb_vec cjp = cj->pos, look;
    float feet, here;
    int i;
    for (i = 0; i < out->n_posts; i++) if (out->posts[i].job == HCB_ROLE_MARKSMAN) { p = &out->posts[i]; me = hcb_ped_of(s, p->who); break; }
    if (s->recall) q->mk_down_until = now + 20000;             /* ("to me": down, and no new high place for 20 s) */
    if (!p || !me || !s->body || hcb_squad_roping(s, p->who) || me->vehicle || cj->vehicle || s->interior || s->recall || (cj->flags & HCB_PF_DEAD)
        || (q->mk_down_until && now < q->mk_down_until)) {
        q->mk_state = MK_NONE; q->mk_far_since = 0; q->mk_up = 0;
        return;
    }
    if (q->mk_id != p->who) { q->mk_id = p->who; q->mk_state = MK_NONE; q->mk_n_bad = 0; q->mk_up = 0; }
    feet = cjp.z - 1.0f; here = me->pos.z - 1.0f;
    look = p->look;
    if (b->dt.threat_mem_t && now - b->dt.threat_mem_t < 20000) { look = b->dt.threat_mem; look.z += 0.6f; }
    if (f_abs(me->pos.z - q->mk_prog_pos.z) > 0.8f) { q->mk_prog_pos = me->pos; q->mk_prog_t = now ? now : 1; q->mk_best_d = 1e9f; }   /* (up or down: progress) */
    /* up: he stays while CJ is within 60 m (10 s beyond it and he comes down) */
    if (here > feet + 2.0f && (q->mk_state == MK_UP || q->mk_state == MK_ROOF || q->mk_state == MK_STEP || q->mk_state == MK_VROOF || q->mk_state == MK_HIGHGROUND || q->mk_up || here > feet + 3.5f)) {
        if (d2(me->pos, cjp) > 60.0f) { if (!q->mk_far_since) q->mk_far_since = now ? now : 1; } else q->mk_far_since = 0;
        if (!q->mk_far_since || now - q->mk_far_since < 10000) {
            if (q->mk_state == MK_STEP && here < q->mk_at.z - 2.0f) goto plan;      /* (on the car on his way up: on to the roof) */
            q->mk_state = MK_UP; q->mk_up = 1;
            p->at = me->pos; p->via = me->pos; p->via2 = me->pos; p->move = 0; p->crouch = 0; p->duty = HCB_DUTY_HOLD; p->climb = 0;
            p->look = look;
            return;
        }
        q->mk_state = MK_NONE; q->mk_up = 0;                       /* down: the plan below gives him his next place; he walks off the edge */
    } else q->mk_up = 0;
    q->mk_far_since = 0;
plan:
    if (b->alert >= HCB_ALERT_EVACUATE || v_len(cj->vel) > 2.5f) { q->mk_state = MK_NONE; return; }   /* (an evacuation, or CJ on his way: he goes with the detail) */
    /* a plan is kept until it has worked, failed or is no good any more; a new one is looked for every 4 s */
    if (q->mk_state != MK_NONE && q->mk_state != MK_UP) {
        int stale = d2(q->mk_at, cjp) > 62.0f || now - q->mk_since > 30000;
        if (stale) { if (q->mk_state != MK_LONG && q->mk_state != MK_HIGHGROUND) mk_mark_bad(q, q->mk_at, now); q->mk_state = MK_NONE; }
    }
    if (q->mk_state == MK_NONE || (q->mk_state == MK_LONG && now - q->mk_pick_t > 4000)) {
        int best = -1, n = s->n_high < HCB_MAX_HIGH ? s->n_high : HCB_MAX_HIGH, j;
        float bd = 1e9f;
        hcb_vec step = me->pos;
        u8 how = MK_NONE;
        q->mk_pick_t = now ? now : 1;
        /* (1) a roof he can get up */
        for (i = 0; i < n; i++) {
            const hcb_high *h = &s->high[i];
            float up = h->at.z - 1.0f - here, dc = d2(h->at, cjp), dm = d2(h->at, me->pos);
            u8 k = MK_NONE;
            hcb_vec st = me->pos;
            if (!h->sees_cj || dc < 10.0f || dc > 60.0f || mk_is_bad(q, h->at, now)) continue;
            if (up <= 2.8f) k = MK_ROOF;
            else if (up <= 4.6f)
                for (j = 0; j < (int)s->n_vehs && j < HCB_MAX_VEHS; j++) {
                    const hcb_veh *v = &s->vehs[j];
                    if (v->cls != HCB_VC_CAR || v->driver || v_len(v->vel) > 0.5f || d2(v->pos, h->at) > 7.0f || h->at.z - 1.0f - (v->pos.z + 0.8f) > 2.8f) continue;
                    k = MK_STEP; st = v->pos; break;
                }
            if (k != MK_NONE && dm < bd) { bd = dm; best = i; how = k; step = st; }
        }
        if (best >= 0) { q->mk_at = s->high[best].at; q->mk_step = step; }
        /* (2) high ground on the map */
        if (best < 0 && b->nv.ok) {
            const nav *nv = &b->nv;
            float bh = 0;
            int x, y;
            for (y = 0; y < NAV_N; y += 2) for (x = 0; x < NAV_N; x += 2) {
                const navcell *c = &nv->c[y * NAV_N + x];
                hcb_vec at;
                float dc;
                if (c->st != 1 || c->z < feet + 2.0f || c->z > feet + 15.0f) continue;
                at.x = (float)(nv->ox + x) + 0.5f; at.y = (float)(nv->oy + y) + 0.5f; at.z = c->z + 1.0f;
                dc = d2(at, cjp);
                if (dc < 12.0f || dc > 45.0f || mk_is_bad(q, at, now)) continue;
                if (c->z - feet - dc * 0.02f > bh) { bh = c->z - feet - dc * 0.02f; q->mk_at = at; best = 1; }
            }
            if (best >= 0) how = MK_HIGHGROUND;
        }
        /* (3) the roof of a big vehicle */
        if (best < 0)
            for (j = 0; j < (int)s->n_vehs && j < HCB_MAX_VEHS; j++) {
                const hcb_veh *v = &s->vehs[j];
                float dc = d2(v->pos, cjp);
                if (v->cls != HCB_VC_CAR || !big_vehicle(v->model) || v->driver || v_len(v->vel) > 0.5f || dc > 35.0f || dc < 6.0f || mk_is_bad(q, v->pos, now)) continue;
                if (dc < bd) { bd = dc; q->mk_at = v->pos; q->mk_at.z += 2.6f; best = j; how = MK_VROOF; }
            }
        /* (4) a long look - in a fight (in peace his place on the far side of the detail is a look-out already) */
        if (best < 0 && b->alert >= HCB_ALERT_THREAT) {
            hcb_vec dir = look.x != 0.0f || look.y != 0.0f ? v_sub(look, cjp) : cj->fwd;
            float l;
            dir.z = 0; l = v_len(dir);
            if (l < 0.1f) { dir = cj->fwd; dir.z = 0; l = v_len(dir); if (l < 0.1f) { dir.x = 0; dir.y = 1; l = 1; } }
            q->mk_at = v_add(cjp, v_mul(dir, 28.0f / l)); q->mk_at.z = cjp.z;
            how = MK_LONG;
        }
        if (how != q->mk_state) { q->mk_state = how; q->mk_since = now ? now : 1; q->mk_tries = 0; q->mk_climb_t = 0; q->mk_z0 = here; q->mk_best_d = 1e9f; q->mk_prog_t = now ? now : 1; }
        if (how == MK_NONE) return;                                /* (nothing better: the squad's / the detail's place stands) */
    }
    /* the way there */
    p->look = look; p->climb = 0;
    if (q->mk_state == MK_LONG) {
        p->at = q->mk_at; p->duty = HCB_DUTY_HOLD; p->crouch = d2(me->pos, q->mk_at) < 1.5f; if (p->move == 0 && d2(me->pos, q->mk_at) > 1.3f) p->move = 2;
        return;
    }
    if (q->mk_state == MK_HIGHGROUND) {
        p->at = q->mk_at; p->duty = HCB_DUTY_HOLD; p->crouch = 0; if (p->move == 0 && d2(me->pos, q->mk_at) > 1.3f) p->move = 2;
        if (now - q->mk_since > 20000 && here < q->mk_at.z - 2.0f) { mk_mark_bad(q, q->mk_at, now); q->mk_state = MK_NONE; }
        return;
    }
    {   /* ROOF, STEP, VROOF: walk to the wall (or the car), then climb */
        hcb_vec wall = q->mk_state == MK_STEP && here < q->mk_step.z ? q->mk_step : q->mk_at;   /* (feet below the car's middle: not on it yet) */
        float dh = d2(me->pos, wall);
        int stalled;
        /* (no nearer to the wall by 0.3 m in a second: he is at it - walking along it, as the game's walk-round makes him, is no progress) */
        if (dh < q->mk_best_d - 0.3f) { q->mk_best_d = dh; q->mk_prog_t = now ? now : 1; }
        stalled = q->mk_prog_t && now - q->mk_prog_t > 1000;
        p->at = wall; p->duty = HCB_DUTY_BOUND; p->crouch = 0; if (p->move == 0) p->move = 2;
        if (q->mk_climb_t) {                                       /* climbing: up, or not */
            if (here > q->mk_z0 + 1.0f) { q->mk_climb_t = 0; q->mk_z0 = here; q->mk_tries = 0; }
            else if (now - q->mk_climb_t > 3500) {
                q->mk_climb_t = 0;
                if (++q->mk_tries >= 3) { mk_mark_bad(q, q->mk_at, now); q->mk_state = MK_NONE; return; }
            } else { p->climb = 1; return; }
        }
        /* at the wall: within 2.2 m of a car, or blocked within 9 m of the roof (the wall is between him and it) */
        if ((wall.x == q->mk_step.x && wall.y == q->mk_step.y && q->mk_state == MK_STEP && dh < 2.2f) || (q->mk_state == MK_VROOF && dh < 2.4f)
            || (dh < 9.0f && stalled)) {
            q->mk_climb_t = now ? now : 1; q->mk_z0 = here; p->climb = 1;
        }
        if (now - q->mk_since > 20000 && !q->mk_climb_t && here < q->mk_at.z - 2.0f) { mk_mark_bad(q, q->mk_at, now); q->mk_state = MK_NONE; }
    }
}
