/*
 * Helicover Brain core, 1.1: a firing place chosen by weights.
 *
 * Until 1.0 an outer man took the FIRST spot behind something that the ring search came across. Now every candidate near
 * his corner is valued and the best one is taken:
 *   candidates (at most 20): the corner itself, the places the game calls cover (its own cover points), the cells of the
 *     brain's map that have a wall on the threat's side, and three rings of points round the corner;
 *   thrown out before any valuing: too near to the threat (6 m), outside the distances allowed from CJ, in CJ's line of
 *     fire or on the line between CJ and the threat, within 1.2 m of a place another of ours holds, no ground under it,
 *     a ledge or a drop away from the man's own height, CJ known not to be seen from it (when that is asked for), and -
 *     for the two best - no way to it on the map;
 *   value (the weights are hcb_cfg's, set in the settings file):
 *     + place_w_fire    a crouching man is hidden from the main threat and a standing one fires over it
 *     + place_w_open    no cover, but a line of fire (a full wall gets next to nothing: safe and blind)
 *     + place_w_others  the share of the other threats it is hidden from
 *     + place_w_dist    15-35 m from the main threat is best, falling off to nothing at 0 and 50 m
 *     + place_w_near    near the man (nothing beyond 20 m)
 *     - place_w_crowd   another of ours within 3 m
 *     - place_w_path    the middle of the way there is known to lie open to the threat (legs over 6 m)
 * What is not known yet is asked (the cover questions of hcb_detail.c, a few a look) and counted as half an open place
 * meanwhile, so a man is never left without a place while the answers come in. The caller keeps a place until a new one
 * is place_better times better and place_keep_ms have passed.
 */
#include "hcb_int.h"

#define PL_MAX 48
static hcb_vec flat(hcb_vec v) { v.z = 0; return v; }
static float d2(hcb_vec a, hcb_vec b) { return v_len(flat(v_sub(a, b))); }

HID float hcb_place_score(hcb_brain *b, hcb_out *out, const place_in *in, hcb_vec at, u32 now, int ask, int *cover) {
    const hcb_cfg *c = &b->cfg;
    float sc = 0, dT = d2(at, in->threat), dcj = d2(at, in->cj), dman = d2(at, in->man), z, t;
    int hid = 0, hi = 0, gr = 1, k, known, room = out->n_probe_q < HCB_MAX_PROBES, on_road = 0;
    hcb_vec a2 = flat(at), cj2 = flat(in->cj), th2 = flat(in->threat);

    *cover = 0;
    if (dT < 6.0f || dT < in->threat_min) return -1.0f;
    if (in->q_cos > -0.99f && (in->q_dir.x != 0.0f || in->q_dir.y != 0.0f) && dcj > 1.0f) {   /* 1.6: his own quarter round CJ */
        hcb_vec rel = v_sub(a2, cj2);
        if ((rel.x * in->q_dir.x + rel.y * in->q_dir.y) / dcj < in->q_cos) return -1.0f;
    }
    for (k = 0; k < in->n_bad && k < 3; k++) if (d2(at, in->bad[k]) < 3.0f) return -1.0f;   /* 1.6: he could not get there */
    if (in->cj_max > 0.0f && (dcj > in->cj_max || dcj < in->cj_min)) return -1.0f;
    if (in->cj_fires) {                                                  /* nobody in front of CJ's weapon */
        hcb_vec rel = v_sub(a2, cj2);
        float along = rel.x * in->cj_dir.x + rel.y * in->cj_dir.y;
        if (along > 0.0f && along < 45.0f) {
            hcb_vec off = v_sub(rel, v_mul(flat(in->cj_dir), along));
            if (v_len(off) < 2.0f + along * 0.05f) return -1.0f;
        }
    }
    if (!in->stand_in && d2(in->cj, in->threat) > 3.0f && seg_dist(a2, cj2, th2, &t) < 1.5f) return -1.0f;   /* the line the fight runs along (1.5: none in peace) */
    /* 1.3 (the second 2.0 log: one order in five to a man with a target was "CJ in the line" - and in 71 % of them he was further
       from the man than CJ): no place from which the line to the threat passes CJ, or within a metre of a place another of ours holds */
    /* (1.5: the corridor the fire plan keeps round CJ - 2 m and 2 cm a metre out (hcb_fire.c, cj_line_m / line_per_m): from a place
       with CJ inside it a man may not fire at all. A place he holds goes when CJ is inside it; a new one needs 0.4 m more - no
       flapping between the two) */
    if (!in->stand_in) {
        float lt = d2(a2, th2), dl = seg_dist(cj2, a2, th2, &t);
        if (t > 0.02f && t < 0.98f && dl < (in->keep ? 0.0f : 0.4f) + c->cj_line_m + c->line_per_m * t * lt) return -1.0f;
    }
    for (k = 0; k < in->n_taken; k++) { hcb_vec tk = flat(in->taken[k]); if (d2(at, in->taken[k]) < 1.2f || (!in->keep && seg_dist(tk, a2, th2, &t) < 1.0f && t > 0.05f && t < 0.95f)) return -1.0f; }
    if (hcb_nav_ground(b, at, &z) && f_abs(z + 1.0f - in->man.z) > 2.5f && f_abs(z + 1.0f - at.z) > 2.5f) return -1.0f;   /* a roof, a pit */
    known = hcb_cv_raw(b, at, in->threat, now, &hid, &hi, &gr);
    if (!known) {
        if (ask && room) hcb_cv_ask(b, out, at, in->threat, now);
        if (in->strict) return -1.0f;
        sc += c->place_w_open * 0.5f;
    } else {
        if (!gr) return -1.0f;
        if (hid && !hi) { sc += c->place_w_fire; *cover = 1; }
        else if (!hid) sc += c->place_w_open;
        else { sc += 0.05f; *cover = 2; }                               /* (wholly behind a wall: safe, out of sight - and blind) */
    }
    /* 1.6 (the player: "not a soul in the open - heads and barrels over cover"): with the whole quarter to choose from, cover counts for
       more than everything else together; next best a place right beside a wall, a fence or a step; and never where cars drive */
    if (in->wide) {
        if (*cover == 1) {
            /* (with the weight as shipped, 0.4: one whole point for the middle of the thing - cover on both sides of him too - and about
               half of it for its end, where a step to the side, his or CJ's, brings him into sight) */
            hcb_vec tv = flat(v_sub(in->threat, at)), pv;
            float tl = v_len(tv);
            int sides = 0;
            /* (the cells next to his along the thing - whichever way it runs - have it between them and the threat too) */
            (void)tl;
            pv.x = 1; pv.y = 0; pv.z = 0; sides = hcb_nav_wall_side(b, v_add(at, pv), in->threat) + hcb_nav_wall_side(b, v_sub(at, pv), in->threat);
            pv.x = 0; pv.y = 1; sides += hcb_nav_wall_side(b, v_add(at, pv), in->threat) + hcb_nav_wall_side(b, v_sub(at, pv), in->threat);
            if (sides > 2) sides = 2;
            if (!hcb_nav_wall_side(b, at, in->threat)) sides = 0;        /* (not right at the thing - behind a car, or metres back in its shadow: the same as its end) */
            sc += c->place_w_fire * 2.5f * (sides == 2 ? 1.0f : sides == 1 ? 0.6f : 0.45f);
        }
        else if (*cover == 2) sc += c->place_w_fire * 0.6f;              /* (out of everybody's sight at least) */
        else if (hcb_nav_by_wall(b, at)) { sc += c->place_w_fire * 0.9f; *cover = 3; }
        for (k = 0; k < b->dt.road_n && k < 24; k++) {
            hcb_vec r0 = flat(v_sub(b->dt.road[k], v_mul(b->dt.road_d[k], 12.0f))), r1 = flat(v_add(b->dt.road[k], v_mul(b->dt.road_d[k], 12.0f)));
            if (seg_dist(a2, r0, r1, &t) < 3.2f) { on_road = 1; if (*cover == 3) *cover = 0; break; }   /* (the last resort: any place off the road is better) */
        }
    }
    if (in->n_other) {
        int h2, x2, g2, hidden = 0;
        for (k = 0; k < in->n_other; k++) {
            if (hcb_cv_raw(b, at, in->other[k], now, &h2, &x2, &g2)) hidden += h2 != 0;
            else if (ask && known && out->n_probe_q < HCB_MAX_PROBES - 2) hcb_cv_ask(b, out, at, in->other[k], now);
        }
        sc += c->place_w_others * (float)hidden / (float)in->n_other;
    }
    sc += c->place_w_dist * (dT < 15.0f ? dT / 15.0f : dT <= 35.0f ? 1.0f : dT < 50.0f ? (50.0f - dT) / 15.0f : 0.0f);
    sc += c->place_w_near * (dman < 20.0f ? 1.0f - dman / 20.0f : 0.0f);
    for (k = 0; k < in->n_taken; k++) if (d2(at, in->taken[k]) < 3.0f) { sc -= c->place_w_crowd; break; }
    if (dman > 6.0f) {                                                   /* the way there: is its middle open to the threat? */
        hcb_vec mid = v_mul(v_add(in->man, at), 0.5f);
        int h2, x2, g2;
        if (hcb_cv_raw(b, mid, in->threat, now, &h2, &x2, &g2)) { if (!h2) sc -= c->place_w_path; }
        else if (ask > 1 && out->n_probe_q < HCB_MAX_PROBES - 1) hcb_cv_ask(b, out, mid, in->threat, now);
    }
    if (in->need_cj) {                                                   /* CJ must be seen from it */
        hcb_vec eye = in->cj;
        int h2, x2, g2;
        eye.z += 0.4f;
        /* (1.6: seen by a man who stands up there - down behind a low thing he is out of CJ's sight, and that is wanted) */
        if (in->low_cj) { if (known && hi) return -1.0f; }
        else if (hcb_cv_raw(b, at, eye, now, &h2, &x2, &g2)) { if (in->wide ? x2 : h2) return -1.0f; if (in->wide && h2 && *cover != 1) sc += 0.2f; }
        else { if (ask && known && out->n_probe_q < HCB_MAX_PROBES - 1) hcb_cv_ask(b, out, at, eye, now); if (in->strict) return -1.0f; }
    }
    return on_road ? sc * 0.01f : sc;                                   /* (1.6: whatever it is worth otherwise) */
}

HID int hcb_place_pick(hcb_brain *b, hcb_out *out, const place_in *in, u32 now, hcb_vec *found, float *score, int *cover) {
    static const float C6[6] = {1.0f, 0.5f, -0.5f, -1.0f, -0.5f, 0.5f}, S6[6] = {0.0f, 0.866025f, 0.866025f, 0.0f, -0.866025f, -0.866025f};
    hcb_vec cand[PL_MAX], away = flat(v_sub(in->anchor, in->threat)), wl[10], tmp[AG_PATH];
    float sc[PL_MAX], l = v_len(away), reach = in->reach > 1.0f ? in->reach : 7.5f;
    int cv[PL_MAX], n = 0, i, k, r, tries, best;

    if (l < 0.01f) { away.x = 1; away.y = 0; away.z = 0; } else away = v_mul(away, 1.0f / l);
#define ADD(P) do { hcb_vec p_ = (P); int q_, dup_ = 0; float z_; p_.z = hcb_nav_ground(b, p_, &z_) && f_abs(z_ + 1.0f - in->anchor.z) < 2.5f ? z_ + 1.0f : in->anchor.z; \
        for (q_ = 0; q_ < n; q_++) if (d2(cand[q_], p_) < 0.8f) dup_ = 1; if (!dup_ && n < PL_MAX) cand[n++] = p_; } while (0)
    ADD(in->anchor);
    for (i = 0, k = 0; i < b->dt.n_hint && i < 12 && k < 4; i++) {       /* behind the things the game calls cover */
        hcb_vec at = v_add(b->dt.hint[i], v_mul(away, 1.6f));
        if (d2(at, in->anchor) > reach + 3.0f) continue;
        ADD(at); k++;
    }
    k = hcb_nav_walls(b, in->anchor, reach, in->threat, wl, in->wide ? 8 : 6);   /* behind the walls the map knows */
    for (i = 0; i < k; i++) ADD(wl[i]);
    if (in->wide) {
        /* 1.6: the whole quarter - the walls the map knows round three more points of it, and the far side of every standing vehicle */
        hcb_vec qd = in->q_dir, qs, c2;
        float rc = d2(in->anchor, in->cj);
        int w_;
        qs.x = -qd.y; qs.y = qd.x; qs.z = 0;
        for (w_ = 0; w_ < 5; w_++) {
            static const float AL[5] = {0.82f, 0.82f, 0.70f, 0.55f, 0.55f}, SI[5] = {0.55f, -0.55f, 0.0f, 0.85f, -0.85f};
            c2 = v_add(in->cj, v_add(v_mul(qd, rc * AL[w_]), v_mul(qs, rc * SI[w_])));
            c2.z = in->anchor.z;
            k = hcb_nav_walls(b, c2, 8.0f, in->threat, wl, 7);
            for (i = 0; i < k; i++) ADD(wl[i]);
        }
        for (i = 0; i < in->n_veh && i < 8; i++) {
            hcb_vec dv = flat(v_sub(in->veh[i], in->threat));
            float lv = v_len(dv);
            if (lv < 3.0f) continue;
            c2 = v_add(in->veh[i], v_mul(dv, 2.3f / lv)); c2.z = in->veh[i].z;
            ADD(c2);
        }
    }
    for (r = in->wide ? 2 : 1; r <= 3 && n < PL_MAX; r++)                /* rings round the corner (wide: two - the walls come first) */
        for (i = 0; i < 6 && n < PL_MAX; i++) {
            hcb_vec at = in->anchor;
            float rad = reach * (float)r / 3.0f;
            int j = (i + r) % 6;
            at.x += (away.x * C6[j] - away.y * S6[j]) * rad; at.y += (away.x * S6[j] + away.y * C6[j]) * rad;
            ADD(at);
        }
#undef ADD
    for (i = 0; i < n; i++) sc[i] = hcb_place_score(b, out, in, cand[i], now, 1, &cv[i]);
    for (tries = 0; tries < 3; tries++) {
        best = -1;
        for (i = 0; i < n; i++) if (sc[i] >= 0.0f && (best < 0 || sc[i] > sc[best])) best = i;
        if (best < 0) return 0;
        /* (the way there, for the best one or two: a place with no way to it on the map is no place) */
        if (tries < 2 && d2(cand[best], in->man) > 2.5f) {
            /* (1.1: asked outside the look. Until the answer is here the place is taken on trust by a man who has none, and
               left alone by a man who holds one) */
            u32 key = 0x80000000u | (((u32)(int)(in->man.x * 0.5f) * 7919u) ^ ((u32)(int)(in->man.y * 0.5f) * 104729u) ^ ((u32)(int)cand[best].x * 31u) ^ ((u32)(int)cand[best].y * 1009u));
            int r_ = hcb_path_ask(b, out, key, in->man, cand[best], tmp, AG_PATH, now);
            if (r_ == 0 || (r_ == -2 && in->held)) { sc[best] = -1.0f; continue; }   /* (1.6: `held`, not `strict` - a man with no place takes it on trust) */
        }
        hcb_place_score(b, out, in, cand[best], now, 2, &cv[best]);       /* (and the middle of that way is asked about) */
        *found = cand[best]; *score = sc[best]; *cover = cv[best];
        return 1;
    }
    return 0;
}

API float hcb_place_value(hcb_brain *b, hcb_vec anchor, hcb_vec man, hcb_vec cj, hcb_vec threat, const hcb_vec *others, int n_others,
                          const hcb_vec *taken, int n_taken, hcb_vec cj_dir, int cj_fires, hcb_vec at, uint32_t now) {
    static hcb_out none;
    place_in in;
    int k, cover;
    zero(&in, sizeof in); zero(&none, sizeof none);
    in.anchor = anchor; in.man = man; in.cj = cj; in.threat = threat; in.reach = 7.5f; in.cj_dir = cj_dir; in.cj_fires = (u8)((cj_fires & 1) != 0);
    in.keep = (u8)((cj_fires & 2) != 0);                               /* (1.5: bit 1 - the place is one he holds) */
    in.stand_in = (u8)((cj_fires & 4) != 0);                           /* (1.5: bit 2 - `threat` is the peace stand-in beyond his quarter) */
    in.wide = (u8)((cj_fires & 8) != 0);                               /* (1.6: bit 3 - valued the way an outer man's place is) */
    in.q_cos = -1.0f;
    for (k = 0; k < n_others && k < 2; k++) in.other[in.n_other++] = others[k];
    for (k = 0; k < n_taken && k < 8; k++) in.taken[in.n_taken++] = taken[k];
    return hcb_place_score(b, &none, &in, at, now, 0, &cover);
}
