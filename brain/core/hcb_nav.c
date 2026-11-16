/* Helicover Brain 1.0 - the brain's own map of the ground and its own way-finding.
 *
 * Why (the 0.9 whole-game log): the guards were more than 8 m from their posts 65 % of the time and flagged STUCK 21 % of
 * it. The game walks a man in a straight line (the scripts' 05D3) or along its own path nodes, which exist on pavements only -
 * yards, slopes and roofs have none. So the brain keeps a small map of its own:
 *   - a grid of NAV_N x NAV_N one-metre cells round the focus (CJ, or the assault target), each with the height of the
 *     ground there; the core cannot see the world, so it ASKS the adapter (HCB_MAX_GROUND questions a look, each one ray
 *     straight down from just above the neighbouring ground) and fills the grid over a few seconds, nearest cells first;
 *   - a man can step from one cell to the next when both have ground and the step is no more than 0.75 m up or 1.5 m down;
 *   - thin things a ray down does not see (a fence, a wall between two cells of the same height) are found lazily: the
 *     first leg of every way is asked about with two level rays ("can a man walk straight from a to b", HCB_MAX_SEGS a
 *     look), and a man who does not get through reports the way out of his cell as blocked for 8 s;
 *   - A* over the grid (at most NAV_EXPAND cells), then the way is pulled straight where the grid allows.
 * Everything is deterministic: the same snapshots give the same map and the same ways. */
#include "hcb_int.h"

#define NAV_EXPAND 1700
#define NAV_OPEN 512
#define STEP_UP 0.75f
#define STEP_DOWN 1.5f
static const int DX[8] = {1, 1, 0, -1, -1, -1, 0, 1}, DY[8] = {0, 1, 1, 1, 0, -1, -1, -1};

static int f_floor_i(float x) { int i = (int)x; return (float)i > x ? i - 1 : i; }
static navcell *cell(nav *n, int i, int j) { return i >= 0 && j >= 0 && i < NAV_N && j < NAV_N ? &n->c[j * NAV_N + i] : 0; }
static int ci(const nav *n, float x) { return f_floor_i(x) - n->ox; }
static int cj_(const nav *n, float y) { return f_floor_i(y) - n->oy; }

static void recentre(nav *n, hcb_vec f) {
    int nox = f_floor_i(f.x) - NAV_N / 2, noy = f_floor_i(f.y) - NAV_N / 2, sx, sy, i, j;
    navcell tmp;
    if (!n->ok) { zero(n, sizeof *n); n->ox = nox; n->oy = noy; n->ok = 1; n->fz = f.z - 1.0f; return; }
    sx = nox - n->ox; sy = noy - n->oy;
    if (sx > -10 && sx < 10 && sy > -10 && sy < 10) return;         /* the focus is still within 10 m of the middle */
    if (sx >= NAV_N || sx <= -NAV_N || sy >= NAV_N || sy <= -NAV_N) { zero(n->c, sizeof n->c); n->known = 0; }
    else {
        /* move the cells that stay; walk in the direction that does not overwrite what is still to be read */
        for (j = 0; j < NAV_N; j++) {
            int jj = sy >= 0 ? j : NAV_N - 1 - j, sj = jj + sy;
            for (i = 0; i < NAV_N; i++) {
                int ii = sx >= 0 ? i : NAV_N - 1 - i, si = ii + sx;
                if (si >= 0 && si < NAV_N && sj >= 0 && sj < NAV_N) tmp = n->c[sj * NAV_N + si]; else zero(&tmp, sizeof tmp);
                n->c[jj * NAV_N + ii] = tmp;
            }
        }
        n->known = 0;
        for (i = 0; i < NAV_N * NAV_N; i++) if (n->c[i].st == 1 || n->c[i].st == 2) n->known++;
    }
    n->ox = nox; n->oy = noy;
}

/* 1.1: places behind something solid, seen from the threat: ground cells within r of c with a wall on the side the threat is on
   (nearest to c first). The map only knows what its level rays found - the cover questions decide whether it really hides a man. */
HID int hcb_nav_walls(const hcb_brain *b, hcb_vec c, float r, hcb_vec threat, hcb_vec *pts, int max) {
    const nav *n = &b->nv;
    int i, j, k, m, got = 0, ci0 = ci(n, c.x), cj0 = cj_(n, c.y), rr = (int)r + 1;
    float d[16];
    if (max > 16) max = 16;
    for (j = cj0 - rr; j <= cj0 + rr; j++) for (i = ci0 - rr; i <= ci0 + rr; i++) {
        const navcell *a = cell((nav *)n, i, j), *w;
        hcb_vec at;
        float dx, dy, dd;
        int wall = 0;
        if (!a || a->st != 1) continue;
        at.x = (float)(n->ox + i) + 0.5f; at.y = (float)(n->oy + j) + 0.5f; at.z = a->z + 1.0f;
        dx = threat.x - at.x; dy = threat.y - at.y;
        if (dx > 1.0f && (a->fix & 1)) wall = 1;
        if (dy > 1.0f && (a->fix & 2)) wall = 1;
        if (dx < -1.0f && (w = cell((nav *)n, i - 1, j)) && (w->fix & 1)) wall = 1;
        if (dy < -1.0f && (w = cell((nav *)n, i, j - 1)) && (w->fix & 2)) wall = 1;
        if (!wall) continue;
        dd = (at.x - c.x) * (at.x - c.x) + (at.y - c.y) * (at.y - c.y);
        if (dd > r * r) continue;
        for (k = 0; k < got && d[k] <= dd; k++) {}
        if (k >= max) continue;
        if (got < max) got++;
        for (m = got - 1; m > k; m--) { d[m] = d[m - 1]; pts[m] = pts[m - 1]; }
        d[k] = dd; pts[k] = at;
    }
    return got;
}
HID int hcb_nav_ground(const hcb_brain *b, hcb_vec at, float *z) {
    const nav *n = &b->nv;
    int i = ci(n, at.x), j = cj_(n, at.y);
    if (!n->ok || i < 0 || j < 0 || i >= NAV_N || j >= NAV_N || n->c[j * NAV_N + i].st != 1) return 0;
    if (z) *z = n->c[j * NAV_N + i].z;
    return 1;
}

HID void hcb_nav_update(hcb_brain *b, const hcb_snapshot *s, hcb_out *out, hcb_vec focus) {
    nav *n = &b->nv;
    u32 now = s->time;
    int k, r, i, j, fi, fj, ng = s->n_ground < HCB_MAX_GROUND ? s->n_ground : HCB_MAX_GROUND, ns = s->n_segs < HCB_MAX_SEGS ? s->n_segs : HCB_MAX_SEGS;

    out->n_ground_q = 0; out->n_seg_q = 0;
    if (!(focus.x - focus.x == 0.0f) || !(focus.y - focus.y == 0.0f) || !(focus.z - focus.z == 0.0f)) return;
    recentre(n, focus);
    n->fz = focus.z - 1.0f;
    /* the answers */
    for (k = 0; k < ng; k++) {
        const hcb_ground *g = &s->ground[k];
        navcell *c;
        if (!(g->x - g->x == 0.0f) || !(g->y - g->y == 0.0f)) continue;
        c = cell(n, ci(n, g->x), cj_(n, g->y));
        if (!c) continue;
        if (c->st != 1 && c->st != 2) n->known++;
        if (g->found && g->z - g->z == 0.0f) { c->st = 1; c->z = g->z; c->fix = g->wall & 3; } else { c->st = 2; c->fix = 0; }
    }
    for (k = 0; k < ns; k++) {
        const hcb_seg *q = &s->segs[k];
        for (i = 0; i < NAV_SEGS; i++) {
            segent *e = &n->sg[i];
            if (e->used && v_dist(e->a, q->a) < 0.05f && v_dist(e->b, q->b) < 0.05f) {
                e->clear = q->clear; e->answered = now ? now : 1;
                /* (a SHORT leg - a step or two - found blocked says where the thing stands: it goes on the map for 30 s. A long one only says
                   "not straight" - the way round is then looked for on the map, leg by leg) */
                if (!q->clear && v_dist(q->a, q->b) <= 1.8f) hcb_nav_block(b, q->a, q->b, now, 30000);
            }
        }
    }
    for (i = 0; i < NAV_SEGS; i++) if (n->sg[i].used && now - (n->sg[i].answered ? n->sg[i].answered : n->sg[i].asked) > 4000) n->sg[i].used = 0;
    /* (the map is only built while the mod walks somebody of the detail: every question costs the game a ray or three) */
    for (k = 0, r = 0; k < (int)s->n_ours && k < HCB_MAX_OURS; k++) if (s->our_role[k] >= HCB_ROLE_SQUAD && s->our_role[k] <= HCB_ROLE_SQUAD + 7) r = 1;
    if (!s->body || !r) return;
    /* the questions: the cells nearest the focus first, each asked from just above a neighbour that is known */
    fi = ci(n, focus.x); fj = cj_(n, focus.y);
    for (r = 0; r < NAV_N && out->n_ground_q < HCB_MAX_GROUND; r++) {
        for (j = fj - r; j <= fj + r && out->n_ground_q < HCB_MAX_GROUND; j++) {
            int edge = j == fj - r || j == fj + r, step = edge || r == 0 ? 1 : 2 * r;
            for (i = fi - r; i <= fi + r && out->n_ground_q < HCB_MAX_GROUND; i += step) {
                navcell *c = cell(n, i, j), *nb;
                hcb_ground *q;
                float zr = n->fz + 1.6f;
                int d, have = r == 0;
                if (!c || c->st == 1 || c->st == 2 || (c->st == 3 && now - c->asked < 1000)) continue;
                for (d = 0; d < 8 && !have; d++) if ((nb = cell(n, i + DX[d], j + DY[d])) && nb->st == 1) { zr = nb->z + 1.6f; have = 1; }
                if (!have) continue;                                    /* (the map grows outwards from what is known) */
                c->st = 3; c->asked = now ? now : 1;
                q = &out->ground_q[out->n_ground_q++];
                zero(q, sizeof *q);
                q->x = (float)(n->ox + i) + 0.5f; q->y = (float)(n->oy + j) + 0.5f; q->z = zr;
            }
        }
    }
}

/* is the straight step from cell (i, j) to its neighbour in direction d (0 +x, 2 +y, 4 -x, 6 -y) barred - by a wall the
   level rays found, or by a way a man tried and did not get through (remembered a while)? */
static int barred(nav *n, int i, int j, int d, u32 now) {
    navcell *a = cell(n, i, j), *c = cell(n, i + DX[d], j + DY[d]);
    if (!a || !c) return 1;
    if (a->blk_until > now && (a->blk & (1u << d))) return 1;
    if (c->blk_until > now && (c->blk & (1u << ((d + 4) & 7)))) return 1;
    switch (d) {
    case 0: return (a->fix & 1) != 0;
    case 2: return (a->fix & 2) != 0;
    case 4: return (c->fix & 1) != 0;
    default: return (c->fix & 2) != 0;
    }
}
/* may a man step from cell (i, j) in direction d? 1 yes, 0 no, 2 not known yet (taken as "perhaps") */
static int can_step(nav *n, int i, int j, int d, u32 now) {
    navcell *a = cell(n, i, j), *c = cell(n, i + DX[d], j + DY[d]);
    float dz;
    if (!a || !c) return 0;
    if (a->st == 2 || c->st == 2) return 0;
    if (!(d & 1)) { if (barred(n, i, j, d, now)) return 0; }
    else {
        /* a diagonal is two steps at once: free only if both ways round the corner are - a man is 0.7 m wide, he does not
           slip past the corner of a wall (and a fence between two rows bars every diagonal across it) */
        int dx = DX[d] > 0 ? 0 : 4, dy = DY[d] > 0 ? 2 : 6;
        navcell *p = cell(n, i + DX[d], j), *q = cell(n, i, j + DY[d]);
        int x_y = p && p->st != 2 && !barred(n, i, j, dx, now) && !barred(n, i + DX[d], j, dy, now);
        int y_x = q && q->st != 2 && !barred(n, i, j, dy, now) && !barred(n, i, j + DY[d], dx, now);
        if (a->blk_until > now && (a->blk & (1u << d))) return 0;
        if (c->blk_until > now && (c->blk & (1u << ((d + 4) & 7)))) return 0;
        if (!x_y || !y_x) return 0;                                  /* (no cutting a corner: BOTH ways round it must be free) */
        if ((p && p->st == 1 && a->st == 1 && p->z - a->z > STEP_UP) || (q && q->st == 1 && a->st == 1 && q->z - a->z > STEP_UP)) return 0;
    }
    if (a->st != 1 || c->st != 1) return 2;
    dz = c->z - a->z;
    if (dz > STEP_UP || dz < -STEP_DOWN) return 0;
    return 1;
}

HID void hcb_nav_block(hcb_brain *b, hcb_vec at, hcb_vec toward, u32 now, u32 ttl) {
    nav *n = &b->nv;
    hcb_vec d = v_sub(toward, at);
    float len, t;
    int pi, pj;
    if (!n->ok) return;
    d.z = 0; len = v_len(d);
    if (len < 0.01f) return;
    if (len > 1.6f) len = 1.6f;
    d = v_mul(d, 1.0f / v_len(d));
    pi = ci(n, at.x); pj = cj_(n, at.y);
    for (t = 0.25f; t <= len + 0.01f; t += 0.25f) {
        int i = ci(n, at.x + d.x * t), j = cj_(n, at.y + d.y * t), k;
        navcell *c;
        if (i == pi && j == pj) continue;
        c = cell(n, pi, pj);
        if (c) {
            for (k = 0; k < 8; k++) if (DX[k] == (i > pi) - (i < pi) && DY[k] == (j > pj) - (j < pj)) {
                if (c->blk_until <= now) c->blk = 0;
                c->blk |= (u8)(1u << k); if (c->blk_until < now + ttl) c->blk_until = now + ttl;
            }
            {                                                           /* and the same way back */
                navcell *o = cell(n, i, j);
                if (o) for (k = 0; k < 8; k++) if (DX[k] == (pi > i) - (pi < i) && DY[k] == (pj > j) - (pj < j)) {
                    if (o->blk_until <= now) o->blk = 0;
                    o->blk |= (u8)(1u << k); if (o->blk_until < now + ttl) o->blk_until = now + ttl;
                }
            }
        }
        pi = i; pj = j;
    }
}

HID int hcb_nav_seg(hcb_brain *b, hcb_out *out, hcb_vec a, hcb_vec c, u32 now) {
    nav *n = &b->nv;
    int i, old = -1;
    u32 best = 0xffffffffu;
    hcb_seg *q;
    for (i = 0; i < NAV_SEGS; i++) {
        segent *e = &n->sg[i];
        if (!e->used) { if (old < 0 || best) { old = i; best = 0; } continue; }
        if (v_dist(e->a, a) < 0.35f && v_dist(e->b, c) < 0.35f) {
            if (e->answered && now - e->answered <= 3000) {
                /* (an answer used again for a leg a little to one side: the block goes on the map for THIS leg too) */
                if (!e->clear && v_dist(a, c) <= 1.8f) hcb_nav_block(b, a, c, now, 30000);
                return e->clear ? 1 : 0;
            }
            if (!e->answered && now - e->asked < 600) return -1;
            old = i; best = 0; break;                                  /* stale: ask again in the same entry */
        }
        if (e->asked < best) { best = e->asked; old = i; }
    }
    if (out->n_seg_q >= HCB_MAX_SEGS || old < 0) return -1;
    n->sg[old].used = 1; n->sg[old].a = a; n->sg[old].b = c; n->sg[old].asked = now ? now : 1; n->sg[old].answered = 0; n->sg[old].clear = 0;
    q = &out->seg_q[out->n_seg_q++];
    zero(q, sizeof *q);
    q->a = a; q->b = c;
    return -1;
}

/* a straight walk over the grid from cell to cell: every step must be allowed */
static int line_ok(nav *n, float ax, float ay, float bx, float by, u32 now) {
    float dx = bx - ax, dy = by - ay, len = f_sqrt(dx * dx + dy * dy), t;
    int pi = ci(n, ax), pj = cj_(n, ay);
    if (len < 0.01f) return 1;
    for (t = 0.2f; t < len + 0.2f; t += 0.2f) {
        float u = t > len ? len : t;
        int i = ci(n, ax + dx * u / len), j = cj_(n, ay + dy * u / len), d, k = -1;
        if (i == pi && j == pj) continue;
        if (i - pi > 1 || pi - i > 1 || j - pj > 1 || pj - j > 1) return 0;
        for (d = 0; d < 8; d++) if (DX[d] == i - pi && DY[d] == j - pj) k = d;
        if (k < 0 || can_step(n, pi, pj, k, now) != 1) return 0;
        pi = i; pj = j;
    }
    return 1;
}

/* can a man walk in a straight line from a to c, as far as the map knows? */
HID int hcb_nav_line(hcb_brain *b, hcb_vec a, hcb_vec c, u32 now) { return b->nv.ok ? line_ok(&b->nv, a.x, a.y, c.x, c.y, now) : 0; }
/* the middle of the cell a man stands in (or of the nearest cell with ground when he is on an edge) */
HID hcb_vec hcb_nav_centre(const hcb_brain *b, hcb_vec at) {
    hcb_vec r = at;
    r.x = (float)f_floor_i(at.x) + 0.5f; r.y = (float)f_floor_i(at.y) + 0.5f;
    return r;
}

HID int hcb_nav_path(hcb_brain *b, hcb_vec from, hcb_vec to, hcb_vec *wp, int max, u32 now) {
    nav *n = &b->nv;
    static const float COST[2] = {1.0f, 1.41421f};
    float g[NAV_N * NAV_N];
    u16 par[NAV_N * NAV_N], open[NAV_OPEN], chain[NAV_N * 4];
    u8 stt[NAV_N * NAV_N];
    int si, sj, gi, gj, no = 0, expand = 0, i, cur, goal, start, nc = 0, nw = 0, a, off_cell = 0;
    navcell *c;

    if (!n->ok || max < 1) return -1;
    si = ci(n, from.x); sj = cj_(n, from.y); gi = ci(n, to.x); gj = cj_(n, to.y);
    c = cell(n, si, sj);
    if (c && c->st != 1) {
        /* he stands on the very edge of something (the cell under him is a wall's): the way starts from the nearest cell
           next to him that has ground */
        int d, bd = -1;
        float best = 1e9f;
        for (d = 0; d < 8; d++) {
            navcell *q = cell(n, si + DX[d], sj + DY[d]);
            float qx = (float)(n->ox + si + DX[d]) + 0.5f - from.x, qy = (float)(n->oy + sj + DY[d]) + 0.5f - from.y, dd = qx * qx + qy * qy;
            if (q && q->st == 1 && dd < best) { best = dd; bd = d; }
        }
        if (bd < 0) return -1;
        si += DX[bd]; sj += DY[bd]; c = cell(n, si, sj); off_cell = 1;
    }
    if (!c || c->st != 1) return -1;                                 /* the map does not know where he stands */
    if (gi < 0) gi = 0;
    if (gj < 0) gj = 0;
    if (gi >= NAV_N) gi = NAV_N - 1;
    if (gj >= NAV_N) gj = NAV_N - 1;
    c = cell(n, gi, gj);
    if (c->st == 2) {                                                /* nothing to stand on there: the nearest cell that has ground */
        int r, bi = -1, bj = -1, d2 = 1 << 30, x, y;
        for (r = 1; r <= 3 && bi < 0; r++)
            for (y = gj - r; y <= gj + r; y++) for (x = gi - r; x <= gi + r; x++) {
                navcell *q = cell(n, x, y);
                int dd = (x - gi) * (x - gi) + (y - gj) * (y - gj);
                if (q && q->st == 1 && dd < d2) { d2 = dd; bi = x; bj = y; }
            }
        if (bi < 0) return 0;
        gi = bi; gj = bj;
    }
    start = sj * NAV_N + si; goal = gj * NAV_N + gi;
    if (start == goal) { wp[0] = to; if (off_cell) { wp[0].x = (float)(n->ox + si) + 0.5f; wp[0].y = (float)(n->oy + sj) + 0.5f; } return 1; }
    zero(stt, sizeof stt);
    g[start] = 0; par[start] = (u16)start; stt[start] = 1; open[no++] = (u16)start;
    cur = -1;
    while (no > 0 && expand < NAV_EXPAND) {
        int bk = 0, x, y, d;
        float bf = 1e30f;
        for (i = 0; i < no; i++) {
            int q = open[i], qx = q % NAV_N - gi, qy = q / NAV_N - gj;
            float h, f;
            if (qx < 0) qx = -qx;
            if (qy < 0) qy = -qy;
            h = qx > qy ? (float)qx + 0.41421f * (float)qy : (float)qy + 0.41421f * (float)qx;
            f = g[q] + h;
            if (f < bf) { bf = f; bk = i; }
        }
        cur = open[bk]; open[bk] = open[--no]; stt[cur] = 2; expand++;
        if (cur == goal) break;
        x = cur % NAV_N; y = cur / NAV_N;
        for (d = 0; d < 8; d++) {
            int ok = can_step(n, x, y, d, now), q;
            float ng;
            if (!ok) continue;
            q = (y + DY[d]) * NAV_N + x + DX[d];
            if (stt[q] == 2) continue;
            ng = g[cur] + COST[d & 1] * (ok == 2 ? 2.5f : 1.0f);      /* (ground not known yet: perhaps, at a price) */
            if (n->c[q].st == 1 && n->c[cur].st == 1 && n->c[q].z - n->c[cur].z < -STEP_UP) ng += 3.0f;   /* a drop: allowed, not liked */
            if (stt[q] == 1) { if (ng < g[q]) { g[q] = ng; par[q] = (u16)cur; } continue; }
            if (no >= NAV_OPEN) continue;
            g[q] = ng; par[q] = (u16)cur; stt[q] = 1; open[no++] = (u16)q;
        }
        cur = -1;
    }
    if (cur != goal) return 0;
    for (a = goal; a != start && nc < (int)(sizeof chain / sizeof chain[0]); a = par[a]) chain[nc++] = (u16)a;
    if (a != start) return 0;
    /* pull it straight: from where he is, the furthest cell of the chain he can walk to in a line */
    {
        float px = from.x, py = from.y;
        int k = nc - 1;
        /* (he does not stand in the middle of his cell: when even the next cell of the chain is not a straight walk from where
           he is - a corner between them - he goes to the middle of his own cell first) */
        {
            float kx = (float)(n->ox + chain[k] % NAV_N) + 0.5f, ky = (float)(n->oy + chain[k] / NAV_N) + 0.5f;
            if ((off_cell || !line_ok(n, px, py, kx, ky, now)) && nw < max) {
                wp[nw].x = (float)(n->ox + si) + 0.5f; wp[nw].y = (float)(n->oy + sj) + 0.5f; wp[nw].z = n->c[start].z + 1.0f;
                px = wp[nw].x; py = wp[nw].y; nw++;
            }
        }
        while (k >= 0 && nw < max) {
            int far = k, m;
            for (m = 0; m < k; m++) {
                float mx = (float)(n->ox + chain[m] % NAV_N) + 0.5f, my = (float)(n->oy + chain[m] / NAV_N) + 0.5f;
                if (m == 0) { mx = to.x; my = to.y; if (ci(n, mx) != gi || cj_(n, my) != gj) { mx = (float)(n->ox + gi) + 0.5f; my = (float)(n->oy + gj) + 0.5f; } }
                if (line_ok(n, px, py, mx, my, now)) { far = m; break; }
            }
            wp[nw].x = (float)(n->ox + chain[far] % NAV_N) + 0.5f; wp[nw].y = (float)(n->oy + chain[far] / NAV_N) + 0.5f;
            wp[nw].z = (n->c[chain[far]].st == 1 ? n->c[chain[far]].z : from.z - 1.0f) + 1.0f;
            if (far == 0 && ci(n, to.x) == gi && cj_(n, to.y) == gj) { wp[nw].x = to.x; wp[nw].y = to.y; }
            px = wp[nw].x; py = wp[nw].y; nw++;
            k = far - 1;
        }
    }
    return nw;
}

API int hcb_nav_way(hcb_brain *b, hcb_vec from, hcb_vec to, hcb_vec *wp, int max, uint32_t now) { return hcb_nav_path(b, from, to, wp, max, now); }
API int hcb_nav_cell(const hcb_brain *b, float x, float y, float *z, int *blocked, uint32_t now) {
    const nav *n = &b->nv;
    int i = ci(n, x), j = cj_(n, y);
    const navcell *c;
    if (!n->ok || i < 0 || j < 0 || i >= NAV_N || j >= NAV_N) return 0;
    c = &n->c[j * NAV_N + i];
    if (z) *z = c->z;
    if (blocked) *blocked = c->blk_until > now ? c->blk : 0;
    return c->st == 3 ? 0 : c->st;
}
