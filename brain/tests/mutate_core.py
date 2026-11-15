"""Mutation check for the brain's core: break one rule at a time in a scratch copy and make sure the tests notice.
    python3 brain/tests/mutate_core.py [name ...]
A line 'MISSED ... <<<<<<' means a rule has no test that guards it."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get('HCB_MUT_ROOT') or Path(tempfile.gettempdir()) / 'hcb_mut')
C = 'core/hcb_core.c'
M = [
 (C, "hostile && armed && on_foot && dist <= c->near_m && facing >= c->facing_cos && !blocked", "hostile && armed && on_foot && facing >= c->facing_cos && !blocked", 'armed facing: close only'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && facing >= c->facing_cos && !blocked", "hostile && armed && on_foot && dist <= c->near_m && !blocked", 'armed facing: turned to CJ'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && facing >= c->facing_cos && !blocked", "hostile && armed && dist <= c->near_m && facing >= c->facing_cos && !blocked", 'armed facing: on foot'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && facing >= c->facing_cos && !blocked", "hostile && armed && on_foot && dist <= c->near_m && facing >= c->facing_cos", 'armed facing: not behind a wall'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && facing >= c->facing_cos && !blocked", "armed && on_foot && dist <= c->near_m && facing >= c->facing_cos && !blocked", 'armed facing: hostile types only'),
 (C, "if (p->pedtype == 6) return s->wanted > 0;", "if (p->pedtype == 6) return 1;", 'police only when wanted'),
 (C, "if (t->aim_ms >= c->aim_ms) t->aim_latch = 1;", "if (t->aim_ms > 0) t->aim_latch = 1;", 'aim: a quarter of a second'),
 (C, "t->aim_ms = f_max(0, t->aim_ms - 2 * dt);", "t->aim_ms = f_max(0, t->aim_ms - 200 * dt);", 'aim: the clock runs back'),
 (C, "(armed || (wclass <= HCB_WC_MELEE && dist < 4))", "(1)", 'aim: an unarmed stare is nothing'),
 (C, "return d <= pass && t > 0.02f;", "return d <= pass * 3 && t > 0.02f;", 'shot: within 3 m'),
 (C, "return d <= pass && t > 0.02f;", "return d <= pass;", 'shot: the muzzle is not the line'),
 (C, "e = v_add(a, v_mul(dir, (len + 4.0f) / len));", "", 'shot: the round carries on'),
 (C, "if (!e->src || hcb_is_ours(s, e->src)) return;\n        t = touch(b, e->src, s->time);", "if (!e->src) return;\n        t = touch(b, e->src, s->time);", 'shot: our own fire is not counted'),
 (C, "else if (hcb_is_ours(s, e->dst)) { t = touch(b, e->src, s->time); t->damage_ours += e->value; t->last_hostile = e->time; }", "", 'damage to ours'),
 (C, "if (t->last_hostile && now - t->last_hostile < (u32)c->attacker_ms) {", "if (t->last_hostile) {", 'attacker for 20 s'),
 (C, "if (!(p->flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP)) && p->pedtype != 8) return 0;", "if (!(p->flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP))) return 0;", 'Grove are allies'),
 (C, "if (!(p->flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP)) && p->pedtype != 8) return 0;", "if (!(p->flags & HCB_PF_RESPECTS) && p->pedtype != 8) return 0;", 'recruits are allies'),
 (C, "    if (p->flags & HCB_PF_HATES) return 0;\n    if (!(p->flags", "    if (!(p->flags", 'hatred overrides the uniform'),
 (C, "return !(t->damage_cj >= 20 && now", "return !(t->damage_cj >= 2000 && now", 'an ally who attacks CJ'),
 (C, "if (hcb_is_ours(s, p->id)) { t->friendly = 1;", "if (0) { t->friendly = 1;", 'ours are friends'),
 (C, "if (defensive && cls == HCB_CLS_THREAT", "if (0 && cls == HCB_CLS_THREAT", 'mission people are left alone'),
 (C, "keep = t->cls == HCB_CLS_ATTACKER ? (u32)c->attacker_ms :", "keep = t->cls == HCB_CLS_ATTACKER ? (u32)c->forget_ms :", 'an unseen attacker is remembered'),
 (C, "if (!t->seen) edps *= 0.25f;", "", 'out of sight is less dangerous'),
 (C, "if (p->flags & HCB_PF_DEAD) { t = hcb_find(b, p->id); if (t) t->used = 0; continue; }", "", 'the dead are dropped'),
 (C, "if (!t->seen && !hcb_ped_of(s, e->src)) t->last.pos = e->a;", "", 'an unseen shooter is placed at the muzzle'),
 (C, "if (tca > 0 && tca <= c->ram_time_s) {", "if (tca > 0) {", 'ramming: within 2 s'),
 (C, "if (tca > 0 && tca <= c->ram_time_s) {", "if (tca <= c->ram_time_s) {", 'ramming: approaching'),
 (C, "if (v_len(at) <= c->ram_miss_m && f_abs(rel.z) < 3) {", "if (f_abs(rel.z) < 3) {", 'ramming: on course'),
 (C, "h->driver && !cj->vehicle && speed2 >= c->ram_speed * c->ram_speed", "h->driver && !cj->vehicle", 'ramming: fast enough'),
 (C, "h->driver && !cj->vehicle && speed2 >= c->ram_speed * c->ram_speed", "h->driver && speed2 >= c->ram_speed * c->ram_speed", 'ramming: CJ on foot'),
 (C, "(h->flags & HCB_VF_BURNING) && !(h->flags & HCB_VF_WRECKED) && dist <= c->burn_m", "(h->flags & HCB_VF_BURNING) && dist <= c->burn_m", 'burning: not a wreck'),
 (C, "(h->flags & HCB_VF_BURNING) && !(h->flags & HCB_VF_WRECKED) && dist <= c->burn_m", "(h->flags & HCB_VF_BURNING) && !(h->flags & HCB_VF_WRECKED)", 'burning: near CJ'),
 (C, "b->alert--; b->alert_since = now;", "b->alert = 0; b->alert_since = now;", 'alert: one step down'),
 (C, "} else if (now - b->calm_since >= (u32)c->calm_ms) {", "} else if (1) {", 'alert: six quiet seconds'),
 (C, "if (danger >= c->evac_danger || (attackers", "if ((attackers", 'evacuate: too much fire'),
 (C, "s->player.health > 0 && s->player.health < 30)) want", "s->player.health > 0 && s->player.health < 0)) want", 'evacuate: CJ badly hurt'),
 (C, "if (s->cutscene) want = HCB_ALERT_CALM;", "", 'cutscene'),
 (C, "if (a->cls != b->cls) return a->cls > b->cls;", "if (a->cls != b->cls) return a->cls < b->cls;", 'ranking: class first'),
 (C, "if (a->edps != b->edps) return a->edps > b->edps;", "if (a->edps != b->edps) return a->edps < b->edps;", 'ranking: expected damage'),
 (C, "key = ((u32)t->seen << 30) | ((u32)(t->cls > HCB_CLS_NEUTRAL ? t->cls : 0) << 26) | ((t->last_seen >> 6) & 0x3ffffffu);", "key = (t->last_seen >> 6) & 0x3ffffffu;", 'memory: the dangerous are kept'),
 (C, "float k = cls == HCB_CLS_ATTACKER ? 1.0f : why == HCB_WHY_AIMS_AT_CJ ? 0.8f : cls == HCB_CLS_THREAT ? 0.4f : 0.1f;", "float k = 1.0f;", 'expected damage: by what he is doing'),
 (C, "if (dist <= range * 0.3f) return 0.6f;", "return 0.6f;", 'expected damage: by distance'),
 (C, "while (r->start < r->end && r->end - r->start > r->cap / 2) { r->start += rd32(buf + r->start); r->dropped++; r->records--; }", "r->start = r->end; r->dropped += r->records; r->records = 0;", 'black box: only the oldest half goes'),
 (C, "if (snapshot_len(no, np, nv, ne, nl) != len) return 0;", "", 'black box: damaged records are refused'),
 (C, "if (state) copy(state, buf + at + 8, sizeof(struct hcb_brain));", "", 'black box: the stored memory is given back'),
 (C, "at = put(buf, at, &need, 4); at = put(buf, at, &kind, 4); at = put(buf, at, b, sizeof(struct hcb_brain));", "at = put(buf, at, &need, 4); at = put(buf, at, &kind, 4); at += sizeof(struct hcb_brain);", 'black box: the memory is stored'),
 (C, "h->seed = b->seed;", "", 'report: the seed travels with it'),
]
F = 'core/hcb_fire.c'
M += [
 (F, "    if (r) return r == 1 ? HCB_HOLD_CJ_IN_LINE : HCB_HOLD_CJ_BEHIND;", "", 'fire: CJ in the line'),
 (F, "r = in_line(from, to, s->player.pos, c->cj_line_m, c->line_per_m, c->backstop_m, 1.0f);", "r = in_line(from, to, s->player.pos, c->cj_line_m, 0, c->backstop_m, 1.0f);", 'fire: the margin grows with range'),
 (F, "r = in_line(from, to, s->player.pos, c->cj_line_m, c->line_per_m, c->backstop_m, 1.0f);", "r = in_line(from, to, s->player.pos, c->cj_line_m, c->line_per_m, 0, 1.0f);", 'fire: CJ behind the target'),
 (F, "r = in_line(from, to, s->player.pos, c->cj_line_m, c->line_per_m, c->backstop_m, 1.0f);", "r = in_line(from, to, s->player.pos, c->cj_line_m, c->line_per_m, 4000, 1.0f);", 'fire: the backstop has an end'),
 (F, "    if (along <= 0.3f) return 0;\n", "", 'fire: behind the muzzle is not the line'),
 (F, "if (in_line(from, to, o->last.pos, c->friend_line_m, c->line_per_m * 0.75f, 25, 0.8f)) return HCB_HOLD_FRIEND;", "", 'fire: one of ours in the line'),
 (F, "c->friend_line_m, c->line_per_m * 0.75f, 25, 0.8f)", "c->friend_line_m, c->line_per_m * 0.75f, 0, 0.8f)", 'fire: one of ours behind the target'),
 (F, "c->friend_line_m, c->line_per_m * 0.75f, 25, 0.8f)", "c->friend_line_m * 3, c->line_per_m * 0.75f, 25, 0.8f)", 'fire: beside the line is fine'),
 (F, "if (r == 1 || (r == 2 && t->edps < 40)) return HCB_HOLD_BYSTANDER;", "if (r == 2 && t->edps < 40) return HCB_HOLD_BYSTANDER;", 'fire: a passer-by in front'),
 (F, "if (r == 1 || (r == 2 && t->edps < 40)) return HCB_HOLD_BYSTANDER;", "if (r == 1) return HCB_HOLD_BYSTANDER;", 'fire: a passer-by behind a man who has not fired'),
 (F, "if (r == 1 || (r == 2 && t->edps < 40)) return HCB_HOLD_BYSTANDER;", "if (r) return HCB_HOLD_BYSTANDER;", 'fire: a passer-by behind an attacker'),
 (F, "if (car->last.health < c->car_floor || (car->last.flags & HCB_VF_BURNING)) return HCB_HOLD_CAR_NEAR;", "if (car->last.flags & HCB_VF_BURNING) return HCB_HOLD_CAR_NEAR;", 'fire: a damaged car beside CJ'),
 (F, "if (car->last.health < c->car_floor || (car->last.flags & HCB_VF_BURNING)) return HCB_HOLD_CAR_NEAR;", "if (car->last.health < c->car_floor) return HCB_HOLD_CAR_NEAR;", 'fire: a burning car beside CJ'),
 (F, "        if (near <= c->explode_m) {", "        if (1) {", 'fire: a car far away may be stopped'),
 (F, "*aim_at = car->why == HCB_WHY_RAMMING ? HCB_AIM_TYRE : HCB_AIM_DRIVER;", "*aim_at = HCB_AIM_DRIVER;", 'fire: tyres of a ramming car'),
 (F, "} else *aim_at = HCB_AIM_DRIVER;", "}", 'fire: at the man in the car'),
 (F, "< -0.17f * f_sqrt(d.x * d.x + d.y * d.y)) return HCB_HOLD_NO_LOS;", "< -100.0f * f_sqrt(d.x * d.x + d.y * d.y)) return HCB_HOLD_NO_LOS;", 'fire: not across the cabin'),
 (F, "if (!hcb_is_firearm(me->weapon) || dist > range) return HCB_HOLD_RANGE;", "if (!hcb_is_firearm(me->weapon)) return HCB_HOLD_RANGE;", 'fire: range'),
 (F, "    if (!l->clear) return HCB_HOLD_NO_LOS;", "", 'fire: not through a wall'),
 (F, "if (!l || s->time - l->time > 1000) return SOFT_LOS;", "if (!l || s->time - l->time > 1000) return HCB_HOLD_NONE;", 'fire: not before the line of sight is known'),
 (F, "if (!l || s->time - l->time > 300) ask(out, me->id, t->last.id);", "if (!l) ask(out, me->id, t->last.id);", 'fire: the line of sight is asked again'),
 (F, "case HCB_ROE_DEFEND: fire = t->cls >= HCB_CLS_THREAT; break;", "case HCB_ROE_DEFEND: fire = t->cls >= HCB_CLS_WATCH; break;", 'fire rule: DEFEND'),
 (F, "fire = t->cls >= HCB_CLS_THREAT || armed_hostile; break;", "fire = t->cls >= HCB_CLS_THREAT; break;", 'fire rule: ARMED'),
 (F, "case HCB_ROE_FOLLOW: fire = t->cj_marked && now - t->cj_marked < (u32)c->follow_ms; break;", "case HCB_ROE_FOLLOW: fire = t->cls >= HCB_CLS_THREAT; break;", 'fire rule: FOLLOW'),
 (F, "fire = t->cj_marked && now - t->cj_marked < (u32)c->follow_ms; break;", "fire = t->cj_marked != 0; break;", 'fire rule: FOLLOW for 3 s'),
 (F, "if (fire && s->police == HCB_POLICE_EVADE && t->last.pedtype == 6) fire = 0;", "", 'police: evade'),
 (F, "if (fire && s->police == HCB_POLICE_ANSWER && t->last.pedtype == 6 && t->cls < HCB_CLS_ATTACKER && s->roe != HCB_ROE_FOLLOW) fire = 0;", "", 'police: answer only'),
 (F, "|| cs[j].taken >= 3) continue;", "|| cs[j].taken >= 9) continue;", 'sharing: three at most'),
 (F, "static const float share[4] = {1.0f, 0.55f, 0.3f, 0.15f};", "static const float share[4] = {1.0f, 1.0f, 1.0f, 1.0f};", 'sharing: fire spreads'),
 (F, "sh->target = t->last.id; sh->since = now; sh->fire_from = now + (u32)react;", "sh->target = t->last.id; sh->since = now; sh->fire_from = now;", 'timing: a reaction time'),
 (F, "if (sh->target && sh->fire_from <= now) react *= 0.6f;", "", 'timing: quicker when already fighting'),
 (F, "if (now < sh->burst_until) { o->fire = 1; o->hold = HCB_HOLD_NONE; }", "if (1) { o->fire = 1; o->hold = HCB_HOLD_NONE; }", 'timing: bursts end'),
 (F, "sh->pause_until = now + (u32)rnd_between(b, c->pause_min_ms, c->pause_max_ms);", "sh->pause_until = now;", 'timing: a pause between bursts'),
 (F, "else if (cover >= 0) { o->hold = HCB_HOLD_COVERING;", "else if (0) { o->hold = HCB_HOLD_COVERING;", 'covering a suspect'),
 (F, "|| role < HCB_ROLE_GUNNER) { me[i] = 0; done[i] = 1; continue; }", ") { me[i] = 0; done[i] = 1; continue; }", 'the pilot does not shoot'),
 (C, "if (cj->target && cj->target == p->id) t->cj_marked = now;", "", 'follow: the man CJ locks on'),
 (C, "if (t->used && t->seen && !t->friendly && fired_at(e->a, e->b, t->last.pos, 1.5f)) t->cj_marked = e->time;", "", 'follow: the man CJ\'s rounds pass'),
 (C, "t->cj_hit_him = e->time; t->cj_marked = e->time; }", "t->cj_hit_him = e->time; }", 'follow: the man CJ hits'),
 (C, "if (drv && !drv->friendly && drv->cls < HCB_CLS_THREAT) { drv->cls = HCB_CLS_THREAT; drv->why = HCB_WHY_RAMMING; drv->edps = v->edps; }", "if (0) { }", 'the driver of a ramming car is a threat'),
]
only = sys.argv[1:]
missed = 0
for fname, old, new, name in M:
    if only and name not in only:
        continue
    if ROOT.exists():
        shutil.rmtree(ROOT)
    shutil.copytree(SRC, ROOT / 'brain', ignore=shutil.ignore_patterns('__pycache__'))
    p = ROOT / 'brain' / fname
    t = p.read_text()
    if old not in t:
        print('GONE    ' + name + '  (the code this mutant broke no longer exists)', flush=True)
        missed += 1
        continue
    p.write_text(t.replace(old, new))
    env = dict(os.environ, HCB_OUT=str(ROOT / 'out'))
    caught = False
    for test in ('test_core.py', 'test_fire.py'):
        r = subprocess.run([sys.executable, str(ROOT / 'brain' / 'tests' / test)], capture_output=True, text=True, env=env)
        if r.returncode:
            caught = True
            break
    missed += not caught
    print(('CAUGHT  ' if caught else 'MISSED  ') + name + ('' if caught else '  <<<<<<'), flush=True)
sys.exit(1 if missed else 0)
