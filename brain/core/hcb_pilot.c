/* Helicover Brain - the pilot (1.4).
 *
 * A helicopter flown by a person: the nose goes down to speed up and comes up to brake, it banks into a turn and slows
 * down for a sharp one, it keeps a safe height over the roofs ahead and comes down to hovering height only near the
 * point, and it stops there without overshooting. Nothing here is a game call: the adapter gives the real position,
 * the script measures the roofs ahead and moves the helicopter, the adapter turns it.
 *
 * Plain C, no libm: angles stay small (pitch, bank) or are handled as unit vectors (the heading). */
#include "hcb_int.h"

#define G_ACC       9.81f
#define CRUISE      68.0f      /* m/s top speed (about 245 km/h) */
#define ACCEL       5.0f       /* m/s^2 the helicopter can change its speed by, any direction (nose 25 degrees down) */
#define BRAKE       3.6f       /* m/s^2 planned for braking: it starts early and comes in gently */
#define TAU_V       1.4f       /* s: how fast the speed follows the wish */
#define CLEAR       35.0f      /* m over the highest roof ahead while travelling */
#define HOVER       25.0f      /* m over the ground where it stops */
#define CLIMB       12.0f      /* m/s up */
#define SINK        9.0f       /* m/s down */
#define SINK_FAST   14.0f      /* m/s down when far too high */
#define VACC        5.0f       /* m/s^2 vertical */
#define TURN_HOVER  0.9f       /* rad/s turn on the spot */
#define BANK_MAX    0.60f      /* rad (34 degrees) */
#define PITCH_MAX   0.36f      /* rad (21 degrees) */
#define TAU_ATT     0.35f      /* s: how fast the attitude follows */

static float f_atan(float x) {                  /* |error| < 0.005 rad */
    if (x > 1.0f) return 1.5707963f - x / (x * x + 0.28f);
    if (x < -1.0f) return -1.5707963f - x / (x * x + 0.28f);
    return x / (1.0f + 0.28f * x * x);
}
static float f_atan2(float y, float x) {
    if (x > 0) return f_atan(y / x);
    if (x < 0) return y >= 0 ? f_atan(y / x) + 3.1415927f : f_atan(y / x) - 3.1415927f;
    return y > 0 ? 1.5707963f : y < 0 ? -1.5707963f : 0.0f;
}
static float f_sin(float x) { float x2 = x * x; return x * (1.0f - x2 / 6.0f * (1.0f - x2 / 20.0f * (1.0f - x2 / 42.0f))); }   /* |x| <= 1 */
static float f_cos(float x) { float x2 = x * x; return 1.0f - x2 / 2.0f * (1.0f - x2 / 12.0f * (1.0f - x2 / 30.0f)); }
static int finite_f(float x) { return x == x && x < 1e7f && x > -1e7f; }
static int finite_v(hcb_vec v) { return finite_f(v.x) && finite_f(v.y) && finite_f(v.z); }
static hcb_vec flat_unit(hcb_vec v, hcb_vec fallback) {
    float l = f_sqrt(v.x * v.x + v.y * v.y);
    hcb_vec r;
    if (!(l > 1e-4f)) return fallback;
    r.x = v.x / l; r.y = v.y / l; r.z = 0;
    return r;
}

API void hcb_pilot_reset(hcb_pilot *p, hcb_vec pos, hcb_vec vel, hcb_vec fwd) {
    hcb_vec north = {0, 1, 0};
    zero(p, sizeof *p);
    p->pos = pos;
    p->vel = finite_v(vel) && v_len(vel) < 150.0f ? vel : (hcb_vec){0, 0, 0};
    p->head = flat_unit(finite_v(fwd) ? fwd : north, north);
    p->used = 1;
}

API void hcb_pilot_step(hcb_pilot *p, const hcb_pilot_in *in, hcb_pilot_out *out) {
    float dt = in->dt, cruise = in->cruise > 1.0f ? in->cruise : CRUISE, hover = in->hover > 1.0f ? in->hover : HOVER;
    hcb_vec d, dir, want, a, right, f0, r0, u0, f1, u1;
    float dist, vdes, err, deficit, climb, rate_max, rate_want, speed, cp, sp, cr, sr, z_want, vz_want, clear, k, a_len, a_fwd, a_side, pitch_want, roll_want, ground;

    zero(out, sizeof *out);
    if (!(dt > 0.0f && dt < 10.0f)) dt = 0.016f;
    if (dt > 0.1f) dt = 0.1f;                                 /* a long frame is flown as a short one: no jump */
    if (!finite_v(p->pos) || !finite_v(p->vel) || !finite_v(p->head) || !finite_f(p->pitch) || !finite_f(p->roll) || !finite_f(p->yaw_rate))
        hcb_pilot_reset(p, finite_v(p->pos) ? p->pos : (hcb_vec){0, 0, 0}, (hcb_vec){0, 0, 0}, p->head);
    ground = finite_f(in->ground) && in->ground > -200.0f && in->ground < 2000.0f ? in->ground : p->pos.z - CLEAR;

    /* where to: flat distance and direction */
    d = in->target; d.z = 0; d.x -= p->pos.x; d.y -= p->pos.y;
    if (!finite_v(d)) { d.x = d.y = 0; }
    dist = f_sqrt(d.x * d.x + d.y * d.y);
    dir = flat_unit(d, p->head);

    /* (0.9, fifth log: a landing approach reached the pad's last 4 m at 4.6-5.2 m/s: it brakes more gently, from further out) */
    /* the speed he wants: the top speed; braking in good time for the point (v^2 = 2 a d); slower for a sharp turn */
    err = f_atan2(p->head.x * dir.y - p->head.y * dir.x, p->head.x * dir.x + p->head.y * dir.y);   /* + = the point is to the left */
    vdes = cruise;
    /* (the speed follows the wish TAU_V late: the braking point is moved forward by the way he covers meanwhile) */
    if (in->stop) vdes = f_min(vdes, f_max(f_sqrt(2.0f * (in->land ? 1.1f : BRAKE) * f_max(0.0f, dist - 0.9f * TAU_V * f_sqrt(p->vel.x * p->vel.x + p->vel.y * p->vel.y))), f_min(2.0f, 0.5f * dist)));
    if (dist > 20.0f) vdes *= f_clamp(1.0f - f_abs(err) / 1.7f, 0.25f, 1.0f);
    clear = hover + (CLEAR - hover) * f_clamp((dist - 60.0f) / 200.0f, 0.0f, 1.0f);
    if (!in->stop) clear = CLEAR;
    /* 0.8, a landing approach: near the point he comes down to `hover` over the ground itself */
    if (in->land && dist < 25.0f) clear = hover;
    /* far too high for the point (after a tall roof): slow down enough to be down at hovering height when he gets there */
    if (in->stop && p->pos.z - (ground + clear) > 3.0f) {
        float excess = p->pos.z - (ground + clear), sink = f_min(excess > 40.0f ? SINK_FAST : SINK, 0.6f * excess);
        vdes = f_min(vdes, f_max(0.5f, 0.8f * dist * sink / excess));
    }
    /* below the roofs ahead (the script looks 250 m ahead) or a wall in the way: he brakes hard and climbs (fast, he
       zooms up on his speed), then goes on over them */
    if ((p->pos.z < ground + 10.0f && !(in->land && dist < 25.0f)) || in->blocked) vdes = 0.0f;

    /* the nose: towards the point while travelling; over the point it keeps its heading. The turn rate is what a bank
       of 34 degrees gives at this speed (on the spot: a pedal turn) */
    speed = f_sqrt(p->vel.x * p->vel.x + p->vel.y * p->vel.y);
    rate_max = speed < 8.0f ? TURN_HOVER : f_min(TURN_HOVER, G_ACC * 0.67f / speed + 0.08f);
    rate_want = dist > 12.0f ? f_clamp(1.6f * err, -rate_max, rate_max) : 0.0f;
    /* 0.6: on station he turns side-on to the threat (along the line given, whichever end is nearer) */
    if (dist <= 12.0f && speed < 8.0f && finite_v(in->face) && in->face.x * in->face.x + in->face.y * in->face.y > 0.25f) {
        hcb_vec fc = flat_unit(in->face, p->head);
        float e2;
        if (fc.x * p->head.x + fc.y * p->head.y < 0) { fc.x = -fc.x; fc.y = -fc.y; }
        e2 = f_atan2(p->head.x * fc.y - p->head.y * fc.x, p->head.x * fc.x + p->head.y * fc.y);
        rate_want = f_clamp(1.4f * e2, -TURN_HOVER, TURN_HOVER);
    }
    p->yaw_rate += (rate_want - p->yaw_rate) * f_min(1.0f, dt / 0.45f);
    {
        float t = p->yaw_rate * dt, c = f_cos(t), s = f_sin(t);
        hcb_vec h = p->head;
        p->head.x = h.x * c - h.y * s; p->head.y = h.x * s + h.y * c; p->head.z = 0;
        p->head = flat_unit(p->head, h);
    }

    /* the velocity he wants: along the nose when going fast (a helicopter flies nose first), straight at the point when
       slow (he edges sideways onto it) */
    k = f_clamp((vdes - 6.0f) / 12.0f, 0.0f, 1.0f);
    want = flat_unit(v_add(v_mul(p->head, k), v_mul(dir, 1.0f - k)), dir);
    want = v_mul(want, vdes);
    a.x = (want.x - p->vel.x) / TAU_V; a.y = (want.y - p->vel.y) / TAU_V; a.z = 0;
    a_len = f_sqrt(a.x * a.x + a.y * a.y);
    deficit = ground + clear - p->pos.z;
    {   /* (a hard flare when a tall roof comes up and he is far too low) */
        float a_max = deficit > 40.0f ? 8.0f : ACCEL;
        if (a_len > a_max) a = v_mul(a, a_max / a_len);
    }
    if (in->blocked) { p->vel.x = p->vel.y = 0; a.x = a.y = 0; }
    p->vel.x += a.x * dt; p->vel.y += a.y * dt;

    /* height: a safe height over the roofs ahead while travelling, coming down to hovering height near the point */
    z_want = ground + clear;
    /* (fast, he can zoom up: speed traded for height, up to 26 m/s at full speed) */
    climb = CLIMB + 0.35f * f_clamp(speed - 20.0f, 0.0f, 40.0f);
    vz_want = f_clamp((z_want - p->pos.z) * 0.6f, z_want - p->pos.z < -40.0f ? -SINK_FAST : -SINK, climb);
    if (in->blocked || (p->pos.z < ground + 10.0f && !(in->land && dist < 25.0f))) vz_want = climb;
    if (in->land && dist < 25.0f && vz_want < 0) {              /* down at 6 m/s, at 2.5 m/s below 12 m, and not before he is over the point */
        float hgt = p->pos.z - ground, lim = hgt < 12.0f ? 2.5f : 6.0f;
        if (dist > 6.0f) lim = hgt > 20.0f ? lim : 0.0f;
        if (vz_want < -lim) vz_want = -lim;
    }
    p->vel.z += f_clamp(vz_want - p->vel.z, -VACC * dt, (deficit > 40.0f ? 2.0f * VACC : VACC) * dt);

    p->pos = v_add(p->pos, v_mul(p->vel, dt));

    /* the attitude follows the acceleration: nose down to speed up, up to brake (with a little nose-down trim at speed),
       banked towards the side he turns or slides to */
    right.x = p->head.y; right.y = -p->head.x; right.z = 0;
    a_fwd = a.x * p->head.x + a.y * p->head.y;
    a_side = a.x * right.x + a.y * right.y;
    speed = f_sqrt(p->vel.x * p->vel.x + p->vel.y * p->vel.y);
    pitch_want = f_clamp(-f_atan(a_fwd / G_ACC) - 0.10f * f_min(1.0f, speed / cruise), -PITCH_MAX, PITCH_MAX);
    roll_want = f_clamp(f_atan(a_side / G_ACC), -BANK_MAX, BANK_MAX);
    p->pitch += (pitch_want - p->pitch) * f_min(1.0f, dt / TAU_ATT);
    p->roll += (roll_want - p->roll) * f_min(1.0f, dt / TAU_ATT);

    /* the rows of the game's matrix: heading, then pitch about the right axis, then bank about the nose */
    f0 = p->head; r0 = right; u0.x = 0; u0.y = 0; u0.z = 1;
    cp = f_cos(p->pitch); sp = f_sin(p->pitch); cr = f_cos(p->roll); sr = f_sin(p->roll);
    f1 = v_add(v_mul(f0, cp), v_mul(u0, sp));
    u1 = v_sub(v_mul(u0, cp), v_mul(f0, sp));
    out->fwd = f1;
    out->right = v_sub(v_mul(r0, cr), v_mul(u1, sr));
    out->up = v_add(v_mul(u1, cr), v_mul(r0, sr));
    out->pos = p->pos;
    d = in->target; d.x -= p->pos.x; d.y -= p->pos.y;
    out->dist = finite_f(d.x) && finite_f(d.y) ? f_sqrt(d.x * d.x + d.y * d.y) : 0.0f;
    out->speed = speed;
    out->arrived = (u8)(in->stop && out->dist < 2.5f && speed < 1.5f && f_abs(p->pos.z - (ground + hover)) < 4.0f);
}
