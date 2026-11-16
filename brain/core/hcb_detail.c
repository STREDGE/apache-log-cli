/* Helicover Brain - the protective detail on foot (stage 3).
 *
 * 1.4.1: up to eight men (the commander, two bodyguards, the advance pair Bravo, the counter-assault pair Charlie and a
 * marksman Delta); the commander walks CJ to cover himself; the detail remembers the threat between shots; it picks how to
 * fight (hold / pull out / assault); a man who does not get to his post is given another way round.
 * The first four, as a close-protection team works:
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

#define CJ_RINGS 5
static const float CJ_RADII[CJ_RINGS] = {0.0f, 2.5f, 4.0f, 6.0f, 8.0f};   /* 0: where CJ stands - already hidden, he stays */
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
static int cv_state(hcb_brain *b, hcb_vec at, hcb_vec from, u32 now, int low) {
    cover *c = cv_find(b, at, from, 1.0f);
    if (!c) return -1;
    if (!c->answered || c->answered < c->asked) return now - c->asked < COVER_PENDING_MS ? -2 : -1;
    if (now - c->answered > COVER_KEEP_MS) return -1;
    /* (1.0, `low`: a place to FIGHT from - a crouching man is hidden, a standing one sees over it; a full wall is no firing place) */
    return c->hidden && c->ground && (!low || !c->reserved0) ? 1 : 0;
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
        c->hidden = p->hidden; c->ground = p->ground; c->reserved0 = p->hidden_hi; c->answered = s->time;
    }
}
/* The nearest spot round `center` hidden from `threat`: rings outwards, each ring starting straight away from the threat.
   `toward` (0..1): spots further than this share of the radius towards the threat are not taken (CJ is not sent towards
   the man who shoots at him; a fire team may be). Unknown spots are asked about while there is room in this tick. */
static int find_cover(hcb_brain *b, hcb_out *out, hcb_vec center, hcb_vec u, hcb_vec threat, const float *radii, int nr, float toward, u32 now, hcb_vec *found, int low) {
    int i, k;
    hcb_vec away = v_mul(u, -1.0f);
    /* 0.8: first the places the game itself calls cover (its CCover points: walls, corners, cars) within reach of the
       centre - the spot 1.6 m behind such a thing, seen from the threat */
    if (nr > 0 && radii[nr - 1] > 0.01f)
        for (i = 0; i < b->dt.n_hint && i < 12; i++) {
            hcb_vec at = v_add(b->dt.hint[i], v_mul(away, 1.6f)), d;
            int st;
            if (dist2d(at, center) > radii[nr - 1] + 3.0f) continue;
            at.z = center.z;
            d = unit2(v_sub(at, center), away);
            if (dist2d(at, center) > 0.5f && v_dot(d, u) > toward) continue;
            st = cv_state(b, at, threat, now, low);
            if (st == 1) { *found = at; return 1; }
            if (st == -1) cv_ask(b, out, at, threat, now);
        }
    for (i = 0; i < nr; i++) {
        for (k = 0; k < (radii[i] > 0.01f ? 12 : 1); k++) {
            hcb_vec d = rot(away, k), at = v_add(center, v_mul(d, radii[i]));
            int st;
            at.z = center.z;
            if (radii[i] > 0.01f && v_dot(d, u) > toward) continue;
            st = cv_state(b, at, threat, now, low);
            if (st == 1) { *found = at; return 1; }
            if (st == -1) cv_ask(b, out, at, threat, now);
        }
    }
    return 0;
}
/* 1.0, for the squad: a firing place (low cover) within 7.5 m of a spot */
HID int hcb_cover_near(hcb_brain *b, hcb_out *out, hcb_vec center, hcb_vec u, hcb_vec threat, u32 now, hcb_vec *found) {
    static const float RR[4] = {0.0f, 2.5f, 5.0f, 7.5f};
    return find_cover(b, out, center, u, threat, RR, 4, 1.0f, now, found, 1);
}
HID int hcb_agent_fails(const hcb_brain *b, u32 id);
HID int hcb_agent_failed(const hcb_brain *b, u32 id, u32 now);
HID void hcb_agent_forgive(hcb_brain *b, u32 id);

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

/* is a spot hidden from `from` (1), seen from it (0), or not known (-1: asked if there is room)? (ground does not matter:
   used for the helicopter's spot in the air and for the marksman) */
static int cv_hidden(hcb_brain *b, hcb_out *out, hcb_vec at, hcb_vec from, u32 now) {
    cover *c = cv_find(b, at, from, 1.0f);
    if (c && c->answered && c->answered >= c->asked && now - c->answered <= COVER_KEEP_MS) return c->hidden ? 1 : 0;
    if (!c || now - c->asked >= COVER_PENDING_MS) cv_ask(b, out, at, from, now);
    return -1;
}
/* a post is checked for a straight walk from CJ (a wall or a fence between them: the post comes in towards CJ) */
static hcb_vec reachable(hcb_brain *b, hcb_out *out, hcb_vec cjp, hcb_vec at, u32 now, u8 *pulled) {
    hcb_vec from = cjp;
    from.z += 0.4f;
    /* (1.0: the answer is kept between looks - while it is being asked again, or there is no room to ask, the post stays
       where it was: it used to jump in and out every second and a half) */
    if (out->n_probe_q < HCB_MAX_PROBES / 2) {                           /* cover questions first */
        int h = cv_hidden(b, out, at, from, now);
        if (h == 1) *pulled = 1; else if (h == 0) *pulled = 0;
    }
    return *pulled ? v_add(cjp, v_mul(v_sub(at, cjp), 0.4f)) : at;
}

#define MAXD 8
/* the roles after the commander, in the order the men take them */
/* 0.6: eight are the commander, three bodyguards (CLOSE, CLOSE2, CLOSE3) and four outer men (POINT, POINT2, REAR, MARKSMAN);
   four are the commander, two bodyguards and one outer man */
/* 1.0 (the player: "a ring of three is enough, the rest take cover from which they see the attackers and CJ; the sniper goes up"):
   eight are the commander and TWO bodyguards at CJ, FOUR outer men (POINT, POINT2, REAR, REAR2) and the marksman */
static const u8 ORDER[MAXD - 1] = {HCB_ROLE_CLOSE, HCB_ROLE_POINT, HCB_ROLE_CLOSE2, HCB_ROLE_REAR, HCB_ROLE_REAR2, HCB_ROLE_POINT2, HCB_ROLE_MARKSMAN};
HID void hcb_detail_plan(hcb_brain *b, const hcb_snapshot *s, hcb_out *out) {
    detail *dt = &b->dt;
    const hcb_ped *cj = &s->player, *men[MAXD], *suspect = 0;
    const track *threat = 0;
    u32 now = s->time, ids[MAXD];
    int i, k, n = 0, n_ours = s->n_ours < HCB_MAX_OURS ? s->n_ours : HCB_MAX_OURS, lead = -1, close = -1, remembered = 0;
    u8 job[MAXD];
    float cj_speed = v_len(flat(cj->vel)), best = -1, sbest = -1, edps_sum = 0, heli_speed = 0;
    hcb_vec cjp = cj->pos, f, r, u, pr, T, look;
    u8 duty, mode, say = HCB_SAY_NONE, say_dir = 0, cj_in = 0;
    int indoor = 0;
    vtrack *heli = s->heli ? hcb_vfind(b, s->heli) : 0;

    out->n_posts = 0; out->n_probe_q = 0; out->say = HCB_SAY_NONE; out->cover_ok = 0; out->lead = 0;
    out->mode = dt->mode; out->leading = 0; out->heli_ok = 0;
    cv_learn(b, s);
    dt->n_hint = (u8)(s->n_hints < 12 ? s->n_hints : 12);
    for (i = 0; i < dt->n_hint; i++) dt->hint[i] = s->hints[i];
    /* 0.8, a building: inside one CJ is somewhere else altogether (the game's interiors are far away); the detail holds
       the place where he went in - everything below is laid out round that door until he is out again */
    if (!s->interior) { dt->door = cj->pos; dt->door_ok = 1; }
    else if (dt->door_ok) { cjp = dt->door; cj_speed = 0; indoor = 1; }

    /* the door gunners: seated on the skid while the helicopter travels or all is quiet, kneeling at the door when it
       hangs over a fight (the brain decides; there is no setting) */
    if (heli) heli_speed = v_len(heli->last.vel);
    if (!dt->pose) dt->pose = 2;
    if (b->alert >= HCB_ALERT_THREAT && heli_speed < 4.0f) dt->pose = 1;          /* (with a margin both ways: no flapping) */
    else if (b->alert < HCB_ALERT_THREAT || heli_speed > 8.0f) dt->pose = 2;
    out->gunner_pose = dt->pose;

    /* the detail: the guards on foot, by their number (guard 0 is the commander as long as he lives) */
    for (i = 0; i < n_ours && n < MAXD; i++) {
        int role = s->our_role[i];
        const hcb_ped *p;
        if (role < HCB_ROLE_SQUAD || role > HCB_ROLE_SQUAD + 7) continue;
        p = member(s, s->ours[i]);
        if (!p) continue;
        men[n] = p; ids[n] = s->ours[i]; n++;
    }
    for (i = 1; i < n; i++) {                              /* by their number: the order of the roles */
        int j = i;
        while (j > 0) {
            int ri = 0, rj = 0;
            for (k = 0; k < n_ours; k++) { if (s->ours[k] == ids[j]) ri = s->our_role[k]; if (s->ours[k] == ids[j - 1]) rj = s->our_role[k]; }
            if (ri >= rj) break;
            { const hcb_ped *tp = men[j]; u32 ti = ids[j]; men[j] = men[j - 1]; ids[j] = ids[j - 1]; men[j - 1] = tp; ids[j - 1] = ti; }
            j--;
        }
    }

    /* the threat the detail fights: the most dangerous man at THREAT or above; else a suspect to watch. The place of the
       last threat is remembered 12 s while the alert holds: between two bursts the detail does not stand down. */
    for (i = 0; i < HCB_MAX_TRACKS; i++) {
        const track *t = &b->tr[i];
        if (!t->used || t->friendly || (t->last.flags & HCB_PF_DEAD)) continue;
        if (t->cls >= HCB_CLS_THREAT) edps_sum += t->edps;
        if (t->cls >= HCB_CLS_THREAT && t->edps > best) { best = t->edps; threat = t; }
        else if (t->cls == HCB_CLS_WATCH && t->seen && t->edps > sbest) { sbest = t->edps; suspect = &t->last; }
    }
    /* the detail does not turn round for every new face: the man it fights stays its threat for 3 s at least, and after
       that until another is half again as dangerous (the posts were thrown from side to side every second) */
    if (threat) {
        const track *keep = dt->threat_id ? hcb_find(b, dt->threat_id) : 0;
        if (keep && keep != threat && keep->used && !keep->friendly && !(keep->last.flags & HCB_PF_DEAD) && keep->cls >= HCB_CLS_THREAT
            && (now - dt->threat_since < 3000 || best < keep->edps * 1.5f + 5.0f)) threat = keep;
        if (threat->last.id != dt->threat_id) { dt->threat_id = threat->last.id; dt->threat_since = now; }
    } else dt->threat_id = 0;
    if (indoor) { threat = 0; suspect = 0; dt->threat_id = 0; dt->threat_mem_t = 0; }   /* (what CJ meets inside is not at the door) */
    if (threat) { dt->threat_mem = threat->last.pos; dt->threat_mem_t = now ? now : 1; }
    else remembered = dt->threat_mem_t && now - dt->threat_mem_t < 12000 && b->alert >= HCB_ALERT_THREAT;

    /* the helicopter's spot for the gunners. 0.5 (from the second whole-game log: the spot jumped from side to side with
       every look and the helicopter never got there): 20 m from CJ and 16 m above him (or above the threat, if he is higher), abeam of the line CJ - threat
       first (the side the helicopter is on already), so its rounds do not pass over CJ; the spot is KEPT while CJ is
       9 - 34 m from it and the threat has not been out of its sight for 2 s; only then another is looked for */
    if (threat || remembered) {
        static const u8 ORD[12] = {5, 6, 3, 4, 7, 8, 1, 2, 9, 10, 0, 11};   /* in pairs: +90 -90, +60 -60, +120 -120 ... far side, over the threat */
        hcb_vec Tc = threat ? threat->last.pos : dt->threat_mem, uu = unit2(v_sub(Tc, cjp), (hcb_vec){0, 1, 0});
        const vtrack *hv = s->heli ? hcb_vfind(b, s->heli) : 0;
        int tries, flip = 0;
        Tc.z += 0.6f;
        if (hv) { hcb_vec side = rot(v_mul(uu, -1.0f), 5), rel = flat(v_sub(hv->last.pos, cjp)); flip = rel.x * side.x + rel.y * side.y < 0; }
        if (dt->heli_ok) {
            float d = dist2d(dt->heli_at, cjp);
            int h = cv_hidden(b, out, dt->heli_at, Tc, now);
            if (h == 0) dt->heli_bad = 0; else if (h == 1 && !dt->heli_bad) dt->heli_bad = now ? now : 1;
            if (d > 34.0f || d < 9.0f || (dt->heli_bad && now - dt->heli_bad > 2000)) { dt->heli_ok = 0; dt->heli_bad = 0; if (d <= 34.0f && d >= 9.0f) dt->heli_k = (u8)((dt->heli_k + 1) % 12); }
        }
        for (tries = 0; tries < 2 && !dt->heli_ok; tries++) {
            hcb_vec d = rot(v_mul(uu, -1.0f), ORD[(dt->heli_k % 12) ^ flip]), at = v_add(cjp, v_mul(d, 20.0f));
            int h;
            at.z = (Tc.z > cjp.z + 3.0f ? Tc.z : cjp.z) + 16.0f;       /* (a shooter on a roof: above him) */
            h = cv_hidden(b, out, at, Tc, now);
            if (h == 0) { dt->heli_at = at; dt->heli_ok = 1; dt->heli_t = now ? now : 1; dt->heli_bad = 0; break; }
            if (h == 1) { dt->heli_k = (u8)((dt->heli_k + 1) % 12); continue; }
            break;                                         /* asked: the answer comes with the next look */
        }
        if (dt->heli_ok) { out->heli_ok = 1; out->heli_at = dt->heli_at; }
    } else { dt->heli_ok = 0; dt->heli_k = 0; dt->heli_bad = 0; }

    /* 0.8, CJ in the water: the helicopter comes over him, 12 m up, for the rope */
    if (s->in_water && !indoor && s->heli) {
        out->heli_ok = 1; out->heli_at = cjp; out->heli_at.z = cjp.z + 12.0f;
    }
    /* 0.8, CJ drives: with no fight on, the helicopter scouts 50 m ahead of him along his way, and armed men ahead are
       called ("armed men ahead", once in 15 s) */
    if (cj->vehicle && cj->vehicle != s->heli && cj_speed > 8.0f && !(threat || remembered) && s->heli) {
        hcb_vec dir = unit2(cj->vel, (hcb_vec){0, 1, 0});
        out->heli_ok = 1; out->heli_at = v_add(cjp, v_mul(dir, 50.0f)); out->heli_at.z = cjp.z + 22.0f;
        if (!dt->ahead_said || now - dt->ahead_said >= 15000)
            for (i = 0; i < HCB_MAX_TRACKS; i++) {
                const track *t = &b->tr[i];
                hcb_vec rel;
                float along, lat;
                if (!t->used || t->friendly || !t->seen || (t->last.flags & HCB_PF_DEAD) || !hcb_is_firearm(t->last.weapon)) continue;
                if (t->cls < HCB_CLS_WATCH && !(t->last.pedtype >= 7 && t->last.pedtype <= 16)) continue;       /* (watched already, or an armed gang man further off) */
                rel = flat(v_sub(t->last.pos, cjp)); along = rel.x * dir.x + rel.y * dir.y; lat = rel.x * dir.y - rel.y * dir.x;
                if (along < 25.0f || along > 140.0f || f_abs(lat) > 25.0f) continue;
                dt->ahead_said = now ? now : 1; dt->say_seq++; dt->last_say = HCB_SAY_AHEAD; dt->say_dir = 0; dt->said_at = dt->ahead_said;
                out->say = HCB_SAY_AHEAD; out->say_dir = 0; out->say_seq = dt->say_seq;
                break;
            }
    }
    if (!n || cj->vehicle || (cj->flags & HCB_PF_DEAD) || s->cutscene) {      /* nobody on foot with CJ, or CJ in a vehicle */
        dt->cj_cover_ok = 0; dt->duty = HCB_DUTY_CALM; out->duty = HCB_DUTY_CALM; dt->leading = 0;
        return;
    }

    /* the commander: the same man while he lives; else the first by number, and he says he has taken over */
    for (i = 0; i < n; i++) if (ids[i] == dt->lead) lead = i;
    if (lead < 0) {
        lead = 0;
        if (dt->lead && n) say = HCB_SAY_TAKE_OVER;
        dt->lead = ids[0];
    }
    for (i = 0, k = 0; i < n; i++) {
        if (i == lead) { job[i] = HCB_ROLE_LEAD; continue; }
        job[i] = ORDER[k++];
        if (job[i] == HCB_ROLE_CLOSE) close = i;
    }
    if (n == 1) { close = lead; job[lead] = HCB_ROLE_CLOSE; }   /* one man left: he is the bodyguard, and in charge */
    (void)close;
    /* 0.6, rotation: an outer man who is badly hurt (under 100 of his 250) changes places with the fittest bodyguard - the
       wounded man comes in to CJ's side, a fresh one goes out to the post */
    for (i = 0; i < n; i++) {
        int fit = -1;
        if (!(job[i] == HCB_ROLE_POINT || job[i] == HCB_ROLE_POINT2 || job[i] == HCB_ROLE_REAR || job[i] == HCB_ROLE_REAR2) || men[i]->health >= 100.0f) continue;
        for (k = 0; k < n; k++)
            if ((job[k] == HCB_ROLE_CLOSE || job[k] == HCB_ROLE_CLOSE2) && men[k]->health >= 150.0f && (fit < 0 || men[k]->health > men[fit]->health)) fit = k;
        if (fit >= 0) { u8 t_ = job[i]; job[i] = job[fit]; job[fit] = t_; }
    }
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

    /* how to fight: too much for us -> pull out; few and weak, CJ safe in cover -> assault; else hold. A new choice
       stands at least 3 s (pulling out at once). The menu can force ASSAULT (1) or GUARD (2); AUTO (0) is the brain's. */
    {
        u8 want = HCB_MODE_HOLD;
        int was_in = dt->cj_cover_ok && dist2d(cjp, dt->cj_cover) < 1.6f;
        /* (one rifle at 30 m is about 100 of expected damage a second at CJ in the open: in cover he is safe from it) */
        if (b->alert >= HCB_ALERT_EVACUATE || (cj->health < 35 && out->n_threats >= 2) || s->wanted >= 5 || edps_sum > 320.0f || out->n_threats >= 6 || (n < 3 && out->n_threats >= 3)) want = HCB_MODE_PULLOUT;
        (void)was_in;                                      /* (0.6: no ASSAULT and no menu - the outer four hold forward posts in every fight) */
        if (!(threat || remembered)) want = HCB_MODE_HOLD;
        if (want != dt->mode && (want == HCB_MODE_PULLOUT || now - dt->mode_since >= 3000)) { dt->mode = want; dt->mode_since = now ? now : 1; }
        mode = dt->mode; out->mode = mode;
    }

    duty = (threat || remembered) ? (mode == HCB_MODE_PULLOUT ? HCB_DUTY_RING : HCB_DUTY_COVER) : suspect ? HCB_DUTY_WATCH : HCB_DUTY_CALM;
    if (duty >= HCB_DUTY_COVER && dt->duty < HCB_DUTY_COVER) {
        int best_i = -1, w;
        dt->contact_since = now; dt->cover_said = 0; dt->safe_said = 0; dt->mover = 0;
        /* 0.7: the place is remembered (one entry for 60 m round it; when the list is full the least attacked goes) */
        for (i = 0; i < dt->places && i < 16; i++) if (dist2d(dt->place[i], cjp) < 60.0f) best_i = i;
        if (best_i >= 0) { if (dt->place_n[best_i] < 60000) dt->place_n[best_i]++; }
        else {
            if (dt->places < 16) w = dt->places++;
            else { w = 0; for (i = 1; i < 16; i++) if (dt->place_n[i] < dt->place_n[w]) w = i; }
            dt->place[w] = cjp; dt->place_n[w] = 1;
        }
        dt->places_dirty = 1; dt->place_said = now ? now : 1;
    }
    /* ... and coming back to such a place in peace the commander says so, once in two minutes */
    if (duty < HCB_DUTY_COVER && n && !cj->vehicle && !indoor && say == HCB_SAY_NONE && (!dt->place_said || now - dt->place_said > 120000))
        for (i = 0; i < dt->places && i < 16; i++)
            if (dist2d(dt->place[i], cjp) < 45.0f) { say = HCB_SAY_BEEN_HERE; dt->place_said = now ? now : 1; break; }
    if (duty < HCB_DUTY_COVER && dt->duty >= HCB_DUTY_COVER && (!dt->clear_said || now - dt->clear_said > 10000) && say == HCB_SAY_NONE) { say = HCB_SAY_CLEAR; dt->clear_said = now ? now : 1; }
    if (duty < HCB_DUTY_COVER) { dt->cj_cover_ok = 0; dt->leading = 0; dt->in_since = 0; dt->nocover_since = 0; dt->cover_bad_since = 0; }
    dt->duty = duty; out->duty = duty;

    T = threat ? threat->last.pos : remembered ? dt->threat_mem : suspect ? suspect->pos : v_add(cjp, v_mul(f, 10));
    T.z += 0.6f;                                           /* the threat's chest: where a round of his comes from */
    u = unit2(v_sub(T, cjp), f); pr = right_of(u);
    look = T;

    if (duty >= HCB_DUTY_COVER) {
        /* CJ's spot: the one he has, while it still hides him from this threat and is near; else the nearest new one */
        /* (0.4.2: a threat that moves - a car - does not throw the spot away: it is asked about again and kept meanwhile;
           a spot known exposed or left far behind is kept one more second while a better one is looked for) */
        int st = dt->cj_cover_ok ? cv_state(b, dt->cj_cover, T, now, 0) : -1;
        int near_ = dt->cj_cover_ok && dist2d(dt->cj_cover, cjp) <= 14.0f;
        if (near_ && st == 1) dt->cover_bad_since = 0;
        else if (near_ && st == -1) cv_ask(b, out, dt->cj_cover, T, now);
        else {
            hcb_vec at;
            if (find_cover(b, out, cjp, u, T, CJ_RADII, CJ_RINGS, 0.5f, now, &at, 0)) {
                if (!dt->cj_cover_ok || dist2d(at, dt->cj_cover) > 3.0f) { dt->leading = 0; dt->lead_gave_up = 0; }
                dt->cj_cover = at; dt->cj_cover_ok = 1; dt->threat = T; dt->cover_bad_since = 0;
            } else if (dt->cj_cover_ok) {
                if (!dt->cover_bad_since) dt->cover_bad_since = now ? now : 1;
                if (now - dt->cover_bad_since > 1000) { dt->cj_cover_ok = 0; dt->cover_bad_since = 0; }
            }
        }
        /* in his cover: inside 1.6 m, and then until he is 2.4 m away */
        cj_in = dt->cj_cover_ok && dist2d(cjp, dt->cj_cover) < (dt->in_since ? 2.4f : 1.6f);
        if (cj_in) { if (!dt->in_since) dt->in_since = now ? now : 1; } else dt->in_since = 0;
        if (dt->cj_cover_ok) dt->nocover_since = 0; else if (!dt->nocover_since) dt->nocover_since = now ? now : 1;
    }

#define POST(idx, AT, MOVE, CROUCH, DUTY, LOOK) do { \
        hcb_post *p_ = &out->posts[out->n_posts++]; zero(p_, sizeof *p_); \
        p_->who = ids[idx]; p_->at = (AT); p_->move = (u8)(MOVE); p_->crouch = (u8)(CROUCH); p_->duty = (u8)(DUTY); p_->job = job[idx]; p_->look = (LOOK); \
    } while (0)

    /* ---- 0.6: the detail as the player asked for it after three whole-game logs ("a heap round me is in my way"):
         the commander is always at CJ's side; three bodyguards cover CJ with their bodies; the other four are OUT -
         walking, 8-12 m off at the four corners; in a fight each on a post of his own behind something solid in his
         sector, 10-18 m from CJ, from where he sees CJ's ground. A post once taken is kept (no running about with every
         look) until it is exposed, CJ has moved away from it, or CJ cannot be seen from it. ---- */
    {
        /* each outer man's corner: metres ahead (towards the threat in a fight, the way CJ goes in peace) and to the right */
        static const float CORNER[5][2] = {{0.62f, -0.78f}, {0.62f, 0.78f}, {-0.55f, -0.84f}, {-0.55f, 0.84f}, {-0.92f, 0.38f}};
        /* (1.0: further out - a real detail's outer ring stands well clear of the inner one) */
        static const float RAD_PEACE[5] = {15.0f, 15.0f, 14.0f, 14.0f, 18.0f}, RAD_FIGHT[5] = {18.0f, 18.0f, 16.0f, 16.0f, 22.0f};
        static const float RING_R[4] = {0.0f, 2.5f, 5.0f, 7.5f};
        int fight = duty >= HCB_DUTY_COVER, ring = duty == HCB_DUTY_RING, n_out = 0, turn;
        hcb_vec ahead = fight || duty == HCB_DUTY_WATCH ? u : f, side = right_of(ahead), away = cjp, lead_d = v_mul(ahead, -1.0f);
        float cs = cj_speed > 2.2f ? cj_speed : 3.0f;
        if (ring) {
            static const float FAR[3] = {8.0f, 12.0f, 16.0f};
            if (!find_cover(b, out, cjp, u, T, FAR, 3, -0.3f, now, &away, 0)) away = v_sub(cjp, v_mul(u, 15.0f));
            lead_d = unit2(v_sub(away, cjp), v_mul(u, -1.0f));
            if ((!dt->evac_said || now - dt->evac_said >= SAY_EVAC_MS) && say == HCB_SAY_NONE) { say = HCB_SAY_EVAC; dt->evac_said = now ? now : 1; }
        } else if (fight && dt->cj_cover_ok && !cj_in) lead_d = unit2(v_sub(dt->cj_cover, cjp), v_mul(u, -1.0f));
        for (i = 0; i < n; i++) if (job[i] == HCB_ROLE_POINT || job[i] == HCB_ROLE_POINT2 || job[i] == HCB_ROLE_REAR || job[i] == HCB_ROLE_REAR2 || job[i] == HCB_ROLE_MARKSMAN) n_out++;
        turn = n_out ? (int)(b->ticks % (u32)n_out) : 0;            /* one outer man looks for a post in a look: the questions are few */
        for (i = 0, k = 0; i < n; i++) {
            hcb_vec at = cjp, lk = look;
            int crouch = 0, mv, d_ = duty;
            if (job[i] == HCB_ROLE_LEAD) {
                /* the commander: at CJ's side, a step towards the cover (or the way out) - CJ goes where he goes */
                if (fight && (ring || (dt->cj_cover_ok && !cj_in))) {
                    at = v_add(cjp, v_mul(lead_d, 1.6f));
                    dt->leading = 1; dt->lead_to = ring ? away : dt->cj_cover; out->leading = 1;
                    d_ = ring ? HCB_DUTY_RING : HCB_DUTY_SHIELD;
                } else if (fight && cj_in) { at = v_add(v_sub(dt->cj_cover, v_mul(u, 0.9f)), v_mul(pr, -0.9f)); crouch = 1; d_ = HCB_DUTY_COVER; dt->leading = 0; }
                else if (fight) { at = v_add(v_sub(cjp, v_mul(u, 0.5f)), v_mul(pr, -1.3f)); d_ = HCB_DUTY_SHIELD; dt->leading = 0; }
                else { at = at_off(cjp, f, -0.8f, r, 1.2f); lk = duty == HCB_DUTY_WATCH ? T : at_off(cjp, f, 10, r, 6); dt->leading = 0; }   /* (1.0: at CJ's right shoulder, a step behind) */
                mv = pace(dist2d(at, men[i]->pos), fight ? cs : cj_speed);
            } else if (job[i] == HCB_ROLE_CLOSE || job[i] == HCB_ROLE_CLOSE2) {
                /* the bodyguards: their bodies between CJ and the threat; in peace a pace behind him, never in his way */
                int w = job[i] == HCB_ROLE_CLOSE ? 0 : 1;
                if (fight && cj_in && !ring) {
                    at = w == 0 ? v_add(dt->cj_cover, v_mul(pr, 1.0f)) : v_add(dt->cj_cover, v_mul(pr, -1.0f));
                    crouch = 1;
                } else if (fight) at = w == 0 ? v_add(cjp, v_mul(u, 1.4f)) : v_add(v_add(cjp, v_mul(u, 0.7f)), v_mul(pr, w == 1 ? 1.5f : -1.5f));
                else if (duty == HCB_DUTY_WATCH && w == 0) at = v_add(cjp, v_mul(u, 1.5f));
                /* (1.0: one ahead on the left, clear of CJ's way; one behind on the left who watches the rear - with the commander at
                   the right shoulder that is 360 degrees in three sectors) */
                else at = w == 0 ? at_off(cjp, f, 3.5f, r, -1.8f) : at_off(cjp, f, -2.2f, r, -1.6f);
                if (!fight && duty != HCB_DUTY_WATCH) lk = w == 0 ? at_off(cjp, f, 14, r, -8) : at_off(cjp, f, -14, r, -3);
                if (n == 1 && !fight) at = at_off(cjp, f, -1.3f, r, 1.1f);
                d_ = fight ? (ring ? HCB_DUTY_RING : HCB_DUTY_SHIELD) : duty;
                mv = pace(dist2d(at, men[i]->pos), fight ? cs : cj_speed);
            } else {
                /* the outer four */
                int c = job[i] == HCB_ROLE_POINT ? 0 : job[i] == HCB_ROLE_POINT2 ? 1 : job[i] == HCB_ROLE_REAR ? 2 : job[i] == HCB_ROLE_REAR2 ? 3 : 4;
                int up = job[i] == HCB_ROLE_MARKSMAN && men[i]->pos.z > cjp.z + 3.0f && dist2d(men[i]->pos, cjp) < 130.0f;   /* 1.0: the marksman on his roof */
                float R = ring ? 8.0f + 1.3f * (float)(c > 3 ? 3 : c) : fight ? RAD_FIGHT[c] : RAD_PEACE[c] * (cj_speed > 3.5f ? 0.8f : 1.0f);
                hcb_vec off0 = v_add(v_mul(ahead, CORNER[c][0] * R), v_mul(side, CORNER[c][1] * R)), c0;
                /* (1.0: a man whose place could not be reached is given the next one round CJ - 30 degrees on, then the other way) */
                if (s->body && i < MAXD && !fight && hcb_agent_failed(b, ids[i], now)) { hcb_agent_forgive(b, ids[i]); if (dt->man[i].alt < 250) dt->man[i].alt++; }
                if (s->body && i < MAXD && dt->man[i].alt) off0 = rot(off0, dt->man[i].alt % 12);
                c0 = v_add(cjp, off0);
                c0.z = cjp.z;
                if (up) {
                    /* he stays where the helicopter put him and watches: the threat, or CJ's ground and the way ahead */
                    at = men[i]->pos; mv = 0; crouch = 0; d_ = HCB_DUTY_HOLD;
                    if (!fight) lk = duty == HCB_DUTY_WATCH ? T : at_off(cjp, f, 25, r, 0);
                    if (i < MAXD) dt->man[i].hold_ok = 0;
                } else
                if (fight && !ring && i < MAXD) {
                    int st, hk;
                    if (dt->man[i].hold_id != ids[i]) { dt->man[i].hold_id = ids[i]; dt->man[i].hold_ok = 0; dt->man[i].hold_bad = 0; if (s->body) dt->man[i].alt = 0; }
                    hk = dt->man[i].hold_ok;
                    if (hcb_agent_failed(b, ids[i], now)) {
                        hk = 0; dt->man[i].hold_ok = 0; hcb_agent_forgive(b, ids[i]);
                        if (dt->man[i].alt < 250) dt->man[i].alt++;
                        c0 = v_add(cjp, rot(v_add(v_mul(ahead, CORNER[c][0] * R), v_mul(side, CORNER[c][1] * R)), dt->man[i].alt % 12)); c0.z = cjp.z;
                    }   /* 1.0: he cannot get there - another place */
                    if (hk) {                                           /* keep it while it is good */
                        float dc = dist2d(dt->man[i].hold, cjp);
                        st = cv_state(b, dt->man[i].hold, T, now, 1);
                        if (st == -1 && k == turn) cv_ask(b, out, dt->man[i].hold, T, now);
                        if (st == 0 && !dt->man[i].hold_bad) dt->man[i].hold_bad = now ? now : 1;
                        if (st == 1) dt->man[i].hold_bad = 0;
                        if (dc > 30.0f || dc < 4.0f || (hk == 1 && dt->man[i].hold_bad && now - dt->man[i].hold_bad > 1500)) hk = 0;
                        else if (k == turn && st == 1 && hk == 1) {    /* CJ's ground must be seen from it */
                            hcb_vec eye = cjp;
                            eye.z += 0.4f;
                            if (cv_hidden(b, out, dt->man[i].hold, eye, now) == 1) hk = 0;
                        }
                        dt->man[i].hold_ok = (u8)hk;
                    }
                    /* (0.7, from the fourth log: without a post behind cover a man ran after his corner, which moves with every
                       look - two men in three were always on the move. Now: nothing solid found yet -> he takes the corner
                       as it is NOW as an open post and keeps it like any other (hold_ok 2), and goes on looking for
                       something solid near it) */
                    if (hk != 1 && k == turn) {
                        hcb_vec found, base = hk == 2 ? dt->man[i].hold : c0;
                        if (find_cover(b, out, base, u, T, RING_R, 4, 1.0f, now, &found, 1)) {
                            hcb_vec eye = cjp;
                            eye.z += 0.4f;
                            found.z = cjp.z;
                            if (cv_hidden(b, out, found, eye, now) != 1) { dt->man[i].hold = found; dt->man[i].hold_ok = 1; dt->man[i].hold_bad = 0; hk = 1; }
                        }
                    }
                    if (!hk) { dt->man[i].hold = c0; dt->man[i].hold_ok = 2; dt->man[i].hold_bad = 0; hk = 2; }
                    at = hk ? dt->man[i].hold : c0;
                    crouch = dist2d(at, men[i]->pos) < 1.5f;
                    d_ = crouch ? HCB_DUTY_COVER : HCB_DUTY_BOUND;
                    mv = pace(dist2d(at, men[i]->pos), 3);
                } else {
                    if (i < MAXD) dt->man[i].hold_ok = 0;
                    at = c0;
                    if (!fight) {
                        lk = v_add(cjp, v_add(v_mul(ahead, CORNER[c][0] * 30.0f), v_mul(side, CORNER[c][1] * 30.0f)));     /* outwards: his sector */
                        if (duty == HCB_DUTY_WATCH && c < 2) lk = T;
                        if (cj_speed < 2.0f && i < MAXD) at = reachable(b, out, cjp, at, now, &dt->man[i].pad);
                    }
                    mv = pace(dist2d(at, men[i]->pos), fight ? cs : cj_speed);
                    if (ring) d_ = HCB_DUTY_RING;
                }
                k++;
            }
            if (!fight) lk.z += 0.8f;
            POST(i, at, mv, crouch, d_, lk);
        }
        if (fight && !ring) {
            /* nobody of the outer men stands where CJ would be in his line of fire: such a post steps 2.5 m aside */
            for (i = 0; i < out->n_posts; i++) {
                hcb_post *p = &out->posts[i];
                float tt, dd;
                if (p->duty == HCB_DUTY_SHIELD || p->job == HCB_ROLE_LEAD) continue;
                dd = seg_dist(cjp, p->at, T, &tt);
                if (dd < 1.5f && tt > 0.05f && tt < 0.95f) {
                    hcb_vec sd = right_of(unit2(v_sub(T, p->at), u)), rel = flat(v_sub(cjp, p->at));
                    float sg = rel.x * sd.x + rel.y * sd.y > 0 ? -1.0f : 1.0f;
                    p->at = v_add(p->at, v_mul(sd, 2.5f * sg));
                    if (p->move == 0) p->move = 2;
                }
            }
            /* what the commander tells CJ: 2.5 s between any two things said; "follow me" every 6 s at most whatever the
               spot; "in cover" when CJ has stayed there 1 s; "stay with me" after 2 s without any cover */
            if (say == HCB_SAY_NONE && (!dt->said_at || now - dt->said_at >= 2500)) {
                /* 0.7: a man far off (45 m+) who has fired at CJ or hit him: "sniper - <dir>!", once in 20 s */
                if (threat && dist2d(threat->last.pos, cjp) > 45.0f && (threat->shots_at_cj || threat->damage_cj > 0) && (!dt->sniper_said || now - dt->sniper_said >= 20000)) {
                    say = HCB_SAY_SNIPER; say_dir = rel_dir(cj, threat->last.pos); dt->sniper_said = now ? now : 1;
                } else
                if (dt->cj_cover_ok && !cj_in && (!dt->cover_said || (now - dt->cover_said >= SAY_COVER_MS && (dist2d(cjp, dt->cover_said_at) >= 3.0f || now - dt->cover_said >= 15000)))) { say = HCB_SAY_TAKE_COVER; say_dir = rel_dir(cj, dt->cj_cover); dt->cover_said = now ? now : 1; dt->cover_said_at = cjp; }
                else if (cj_in && now - dt->in_since >= 1000 && (!dt->safe_said || now - dt->safe_said >= 15000)) { say = HCB_SAY_IN_COVER; dt->safe_said = now ? now : 1; }
                else if (!dt->cj_cover_ok && now - dt->contact_since >= 1500 && dt->nocover_since && now - dt->nocover_since >= 2000 && (!dt->cover_said || now - dt->cover_said >= 8000)) {
                    say = HCB_SAY_FOLLOW_ME; say_dir = rel_dir(cj, v_sub(cjp, v_mul(u, 5.0f))); dt->cover_said = now ? now : 1;
                }
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
            if (along < 0.3f || along > 40.0f || f_abs(lat) >= need) continue;
            p->at = v_add(p->at, v_mul(side, (lat < 0 ? -need : need) - lat));
            if (p->move == 0) p->move = 2;
        }
    }
    /* 0.8, CJ in the water: nobody follows him in - each man stays where he stands (on the bank), eyes on CJ; the commander
       says the helicopter is coming over (the rope is the player's to take: CLIMB ABOARD BY ROPE) */
    if (s->in_water && !indoor) {
        for (i = 0; i < out->n_posts; i++) {
            hcb_post *p = &out->posts[i];
            int m;
            for (m = 0; m < n && ids[m] != p->who; m++) {}
            if (m == n) continue;
            p->at = men[m]->pos; p->move = 0; p->look = cjp;
        }
        if (say == HCB_SAY_NONE && (!dt->water_said || now - dt->water_said >= 30000)) { say = HCB_SAY_WATER; dt->water_said = now ? now : 1; }
    }
    /* 0.8, a grenade, a rocket, a fire bottle: every man within its radius sprints straight out of it (and no post is
       left inside); "grenade - <dir>!" when it is within 15 m of CJ, once in 3 s */
    for (k = 0; k < (int)s->n_dangers && k < HCB_MAX_DANGERS; k++) {
        const hcb_danger *g = &s->dangers[k];
        float R = g->radius > 1.0f && g->radius < 40.0f ? g->radius : 10.0f;
        /* 0.9 (fifth log: two guards took 183 and 152 from blasts 8 m from them; the old rule let blasts go as "gone off already"):
           a blast still in the game's table is avoided like a grenade. Its radius is not trusted (the same blast read 35 m,
           then 62 m a second later): 6 to 14 m is the keep-clear, whatever the table says */
        if (g->kind == HCB_DG_BLAST) R = R < 6.0f ? 6.0f : R > 14.0f ? 14.0f : R;
        for (i = 0; i < out->n_posts; i++) {
            hcb_post *p = &out->posts[i];
            int m;
            for (m = 0; m < n && ids[m] != p->who; m++) {}
            if (m == n) continue;
            if (dist2d(men[m]->pos, g->at) < R || dist2d(p->at, g->at) < R) {
                hcb_vec o = unit2(v_sub(men[m]->pos, g->at), unit2(v_sub(cjp, g->at), (hcb_vec){0, 1, 0}));
                p->at.x = g->at.x + o.x * (R + 3.0f); p->at.y = g->at.y + o.y * (R + 3.0f); p->at.z = men[m]->pos.z;
                p->move = 3; p->crouch = 0; p->act = HCB_ACT_SPRINT;
            }
        }
        if (dist2d(g->at, cjp) < 15.0f && !indoor && (!dt->grenade_said || now - dt->grenade_said >= 3000)) {
            say = HCB_SAY_GRENADE; say_dir = rel_dir(cj, g->at); dt->grenade_said = now ? now : 1;      /* (over anything else he was saying) */
        }
    }
    /* 0.9, a car on a collision course (fifth log: four rams took 40 of CJ's 125 health; the brain saw each car 0.7 to 2.3 s
       before it hit and said nothing): when it is on its way to CJ and will be there within 3 s the commander calls it, with
       the side it comes from, once in 2.5 s (over anything but a grenade) */
    if (n && !cj->vehicle && !indoor && (!dt->car_said || now - dt->car_said >= 2500))
        for (i = 0; i < HCB_MAX_VTRACKS; i++) {
            const vtrack *vt = &b->vt[i];
            hcb_vec rel;
            float d, closing;
            if (!vt->used || !vt->seen || vt->why != HCB_WHY_RAMMING || vt->cls < HCB_CLS_THREAT || vt->last.id == s->heli) continue;
            rel = flat(v_sub(cjp, vt->last.pos)); d = v_len(rel);
            if (d < 1.0f || d > 45.0f) continue;
            closing = (vt->last.vel.x * rel.x + vt->last.vel.y * rel.y) / d;
            if (closing < 4.0f || d / closing > 3.0f) continue;
            if (say != HCB_SAY_GRENADE) { say = HCB_SAY_CAR; say_dir = rel_dir(cj, vt->last.pos); dt->car_said = now ? now : 1; }
            break;
        }
    /* 0.7, stealth: CJ crouches and creeps while all is quiet - so does the detail (down, at a walk, no running about) */
    if (duty < HCB_DUTY_COVER && (cj->flags & HCB_PF_DUCKING) && cj_speed < 2.5f)
        for (i = 0; i < out->n_posts; i++) { out->posts[i].crouch = 1; if (out->posts[i].move > 1) out->posts[i].move = 1; }
    /* 0.7: nobody is posted within 12 m of a burning vehicle (it blows up): such a post is moved straight out to 13 m */
    for (k = 0; k < (int)s->n_vehs && k < HCB_MAX_VEHS; k++) {
        const hcb_veh *c = &s->vehs[k];
        if (!(c->flags & HCB_VF_BURNING) || (c->flags & HCB_VF_WRECKED) || c->id == s->heli) continue;
        for (i = 0; i < out->n_posts; i++) {
            hcb_post *p = &out->posts[i];
            float d = dist2d(p->at, c->pos);
            if (d < 12.0f) {
                hcb_vec o = unit2(v_sub(p->at, c->pos), unit2(v_sub(cjp, c->pos), (hcb_vec){0, 1, 0}));
                p->at.x = c->pos.x + o.x * 13.0f; p->at.y = c->pos.y + o.y * 13.0f;
                if (p->move < 2) p->move = 2;
                p->crouch = 0;
            }
        }
    }
    /* out of the way of a car (0.4.2; 0.5: sooner, wider, and nobody runs across in front of one - in the second game the
       men were hit while sprinting to posts on the other side of the road). A vehicle doing over 6 m/s:
         - it will pass within 3 m of a man in the next 2.5 s: he sprints straight out of its path, 4.5 m clear;
         - his way to his post crosses its path in that time: he waits where he is until it has passed. */
    for (i = 0; i < out->n_posts; i++) {
        hcb_post *p = &out->posts[i];
        int m, v;
        for (m = 0; m < n && ids[m] != p->who; m++) {}
        if (m == n) continue;
        for (v = 0; v < (int)s->n_vehs && v < HCB_MAX_VEHS; v++) {
            const hcb_veh *c = &s->vehs[v];
            hcb_vec vel = flat(c->vel), rel, rp, dir, side;
            float sp = v_len(vel), along, lat, along_p, lat_p, reach;
            if (c->id == s->heli || sp < 6.0f || (c->flags & HCB_VF_WRECKED) || (c->driver && hcb_is_ours(s, c->driver)) || c->driver == cj->id) continue;
            if (c->cls == HCB_VC_HELI || c->cls == HCB_VC_PLANE || c->cls == HCB_VC_BOAT) continue;
            dir = v_mul(vel, 1.0f / sp); side = right_of(dir); reach = sp * 2.5f + 4.0f;
            rel = flat(v_sub(men[m]->pos, c->pos)); rp = flat(v_sub(p->at, c->pos));
            along = rel.x * dir.x + rel.y * dir.y; lat = rel.x * side.x + rel.y * side.y;
            along_p = rp.x * dir.x + rp.y * dir.y; lat_p = rp.x * side.x + rp.y * side.y;
            if (along > -4.0f && along < reach && f_abs(lat) < 3.0f) {
                p->at = v_add(men[m]->pos, v_mul(side, lat < 0 ? -4.5f - lat : 4.5f - lat));
                p->at.z = men[m]->pos.z;
                p->move = 3; p->crouch = 0; p->act = HCB_ACT_SPRINT;
                break;
            }
            if (f_abs(lat) < 14.0f && ((along > -4.0f && along < reach) || (along_p > -4.0f && along_p < reach)) && (f_abs(lat_p) < 3.0f || (lat_p < 0) != (lat < 0))) {
                p->at = men[m]->pos; p->move = 0;
                break;
            }
        }
    }
    /* a man who does not get nearer to his post (a fence, a car, a wall): 1.5 s without progress -> the post is turned 30
       degrees round CJ the other way, then further; from the third try on he goes by the path network (move 4) */
    for (i = 0; i < out->n_posts && !s->body; i++) {              /* (1.0: with the mod's own body hcb_agent.c does this with the map) */
        hcb_post *p = &out->posts[i];
        int m;
        float d;
        for (m = 0; m < n && ids[m] != p->who; m++) {}
        if (m == n || m >= MAXD) continue;
        if (dist2d(dt->man[m].post, p->at) > 3.0f) { dt->man[m].post = p->at; dt->man[m].best = 1e9f; dt->man[m].since = now; dt->man[m].alt = 0; }
        d = dist2d(men[m]->pos, p->at);
        if (p->move == 0 || d < 1.5f) { dt->man[m].best = d; dt->man[m].since = now; dt->man[m].alt = 0; continue; }
        if (d < dt->man[m].best - 0.4f) { dt->man[m].best = d; dt->man[m].since = now; }
        else if (now - dt->man[m].since > 1500 && dt->man[m].alt < 250) { dt->man[m].alt++; dt->man[m].since = now; dt->man[m].best = 1e9f; }
        if (dt->man[m].alt) {
            int a_ = dt->man[m].alt;                                     /* 30, -30, 60, -60 ... degrees (the table's order) */
            hcb_vec rel = v_sub(p->at, cjp), q = rot(rel, a_ % 12);
            if (p->job != HCB_ROLE_CLOSE && p->job != HCB_ROLE_CLOSE2 && v_len(flat(rel)) > 1.0f) { q.z = rel.z; p->at = v_add(cjp, q); }
            p->stuck = 1;
            /* 0.9 (fifth log: two men stood 57 s, 37 and 58 m from their posts): the path network from the second try, and at once
               for a man far from his post */
            if (a_ >= 3 || d > 20.0f) p->move = 4;
        }
    }
    out->cover_ok = (u8)(duty >= HCB_DUTY_COVER && dt->cj_cover_ok && !cj_in);
    out->cover_at = dt->cj_cover;
    if (say != HCB_SAY_NONE) { dt->say_seq++; dt->last_say = say; dt->say_dir = say_dir; dt->said_at = now ? now : 1; }
    out->say = say; out->say_dir = dt->say_dir; out->say_seq = dt->say_seq;
}
