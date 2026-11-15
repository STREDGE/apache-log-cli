"""Mutation check for the brain's core: break one rule at a time in a scratch copy and make sure the tests notice.
    python3 brain/tests/mutate_core.py [name ...]
A line 'MISSED ... <<<<<<' means a rule has no test that guards it."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get('HCB_MUT_ROOT') or Path(tempfile.gettempdir()) / 'hcb_mut')
C = 'core/hcb_core.c'
D = 'core/hcb_detail.c'
P = 'core/hcb_pilot.c'
M = [
 (C, "hostile && armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked", "hostile && armed && on_foot && (facing >= c->facing_cos || hunting) && !blocked", 'armed facing: close only'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked", "hostile && armed && on_foot && dist <= c->near_m && !blocked", 'armed facing: turned to CJ'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked", "hostile && armed && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked", 'armed facing: on foot'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked", "hostile && armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting)", 'armed facing: not behind a wall'),
 (C, "hostile && armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked", "armed && on_foot && dist <= c->near_m && (facing >= c->facing_cos || hunting) && !blocked", 'armed facing: hostile types only'),
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
 (C, "                t->used = 0;\n            }\n            continue;", "            }\n            continue;", 'the dead are dropped'),
 (C, "if (!t->seen && !hcb_ped_of(s, e->src)) t->last.pos = e->a;", "", 'an unseen shooter is placed at the muzzle'),
 (C, "if (tca > 0 && tca <= c->ram_time_s) {", "if (tca > 0) {", 'ramming: within 2 s'),
 (C, "if (tca > 0 && tca <= c->ram_time_s) {", "if (tca <= c->ram_time_s) {", 'ramming: approaching'),
 (C, "if (v_len(at) <= c->ram_miss_m && f_abs(rel.z) < 3) {", "if (f_abs(rel.z) < 3) {", 'ramming: on course'),
 (C, "if (!cj->vehicle && speed2 >= c->ram_speed * c->ram_speed && h->cls", "if (!cj->vehicle && h->cls", 'ramming: fast enough'),
 (C, "if (!cj->vehicle && speed2 >= c->ram_speed * c->ram_speed && h->cls", "if (speed2 >= c->ram_speed * c->ram_speed && h->cls", 'ramming: CJ on foot'),
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
 (F, "gunner ? c->line_per_m * 0.5f : c->line_per_m, gunner ? c->round_past_m", "0, gunner ? c->round_past_m", 'fire: the margin grows with range'),
 (F, "gunner ? c->round_past_m + c->cj_line_m : c->backstop_m", "0", 'fire: CJ behind the target'),
 (F, "gunner ? c->round_past_m + c->cj_line_m : c->backstop_m", "4000", 'fire: the backstop has an end'),
 (F, "gunner ? c->round_past_m + c->cj_line_m : c->backstop_m", "c->backstop_m", 'gunner: his round ends just past the aim point'),
 (F, "gunner ? c->cj_line_m : 1.0f, 0.3f);", "1.0f, 0.3f);", 'gunner: CJ just behind the target'),
 (F, "float skip = gunner ? (heli && v_dist(from, heli->last.pos) < 6 ? c->muzzle_m : 0.8f) : 0.3f;", "float skip = 0.3f;", 'gunner: past the man beside him'),
 (F, "(fire > cs[j - 1].fire || (fire == cs[j - 1].fire && value > cs[j - 1].value))", "0", 'questions: the dangerous first'),
 (F, "sh->target != q->target || ", "", 'round: the man of the standing order'),
 (F, "|| sh->hold != HCB_HOLD_NONE || q->time", "|| q->time", 'round: only while ordered to fire'),
 (F, " || q->time - b->time > 300) return", ") return", 'round: a stale order'),
 (F, "    if (r) return r == 1 ? HCB_HOLD_CJ_IN_LINE : HCB_HOLD_CJ_BEHIND;\n    for (i = 0; i < (int)q->n_friends", "    for (i = 0; i < (int)q->n_friends", 'round: CJ as he stands now'),
 (F, "gunner ? 0 : c->line_per_m, gunner ? past + c->cj_line_m : past", "c->line_per_m * 3, gunner ? past + c->cj_line_m : past", 'round: the line is exact'),
 (F, "gunner ? past + c->friend_line_m : 25, gunner ? c->friend_line_m : 0.8f, skip)) return HCB_HOLD_FRIEND;\n    for", "gunner ? past + c->friend_line_m : 25, gunner ? c->friend_line_m : 0.8f, 9000.0f)) return HCB_HOLD_FRIEND;\n    for", 'round: ours as they stand now'),
 (F, "skip = gunner ? f_max(0.3f, v_dist(q->from, q->muzzle)) : 0.3f;", "skip = 0.3f;", 'round: the man inside the muzzle distance'),
 (F, "c->bystander_line_m + 0.3f, 0,", "c->bystander_line_m - 0.3f, 0,", 'round: a passer-by, with a margin for his age'),
 (F, "if (near <= c->explode_m && (car->last.health < c->car_floor || (car->last.flags & HCB_VF_BURNING))) return HCB_HOLD_CAR_NEAR;", "", 'round: a damaged car beside CJ now'),
 (F, "for (i = 0; i < (int)q->n_friends && i < HCB_MAX_OURS; i++) near = f_min(near, v_dist(car->last.pos, q->friends[i]));", "", 'round: a damaged car beside ours now'),
 (F, "    if (along <= skip) return 0;\n", "", 'fire: behind the muzzle is not the line'),
 (F, "if (in_line(from, to, o->last.pos, c->friend_line_m, c->line_per_m * 0.75f, gunner ? c->round_past_m + c->friend_line_m : 25, gunner ? c->friend_line_m : 0.8f, skip)) return HCB_HOLD_FRIEND;", "", 'fire: one of ours in the line'),
 (F, "in_line(from, to, o->last.pos, c->friend_line_m, c->line_per_m * 0.75f, gunner ? c->round_past_m + c->friend_line_m : 25,", "in_line(from, to, o->last.pos, c->friend_line_m, c->line_per_m * 0.75f, 0,", 'fire: one of ours behind the target'),
 (F, "in_line(from, to, o->last.pos, c->friend_line_m,", "in_line(from, to, o->last.pos, c->friend_line_m * 3,", 'fire: beside the line is fine'),
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
 (F, "if (!l || s->time - l->time > 600) return SOFT_LOS;", "if (!l || s->time - l->time > 600) return HCB_HOLD_NONE;", 'fire: not before the line of sight is known'),
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
 (F, "if (now < sh->burst_until) { o->fire = 1; o->hold = HCB_HOLD_NONE; sh->last_fire = now; }", "if (1) { o->fire = 1; o->hold = HCB_HOLD_NONE; sh->last_fire = now; }", 'timing: bursts end'),
 (F, "sh->pause_until = now + (u32)rnd_between(b, c->pause_min_ms, c->pause_max_ms);", "sh->pause_until = now;", 'timing: a pause between bursts'),
 (F, "else if (!is_gunner(sh->role)) { o->fire = 1; o->hold = HCB_HOLD_NONE; sh->last_fire = now; }", "", 'timing: a guard on foot is not paced'),
 (F, "if (bj < 0 || sh->target != cs[bj].t->last.id) { sh->target = 0; sh->fire_from = 0; }", "if (1) { sh->target = 0; sh->fire_from = 0; }", 'timing: no second reaction after a blocked line'),
 (F, "else if (cover >= 0) { o->hold = HCB_HOLD_COVERING;", "else if (0) { o->hold = HCB_HOLD_COVERING;", 'covering a suspect'),
 (F, "|| role < HCB_ROLE_GUNNER) { me[i] = 0; done[i] = 1; }", ") { me[i] = 0; done[i] = 1; }", 'the pilot does not shoot'),
 (C, "if (cj->target && cj->target == p->id) t->cj_marked = now;", "", 'follow: the man CJ locks on'),
 (C, "if (t->used && t->seen && !t->friendly && fired_at(e->a, e->b, t->last.pos, 1.5f)) t->cj_marked = e->time;", "", 'follow: the man CJ\'s rounds pass'),
 (C, "t->cj_hit_him = e->time; t->cj_marked = e->time; }", "t->cj_hit_him = e->time; }", 'follow: the man CJ hits'),
 (C, "if (drv && !drv->friendly && drv->cls < HCB_CLS_THREAT) { drv->cls = HCB_CLS_THREAT; drv->why = HCB_WHY_RAMMING; drv->edps = v->edps; }", "if (0) { }", 'the driver of a ramming car is a threat'),
]
M += [
 (C, "(facing >= c->facing_cos || hunting)", "(facing >= c->facing_cos)", 'police with stars: whichever way he looks'),
 (C, "int hunting = p->pedtype == 6 && s->wanted > 0;", "int hunting = s->wanted > 0;", 'police with stars: policemen only'),
 (C, "t->hold_until = now + (u32)c->threat_hold_ms; t->hold_why = why;", "t->hold_until = now; t->hold_why = why;", 'a threat is held for 2 s'),
 (C, "t->hold_why && now < t->hold_until && t->seen", "t->hold_why && t->seen", 'the hold has an end'),
 (C, "hostile && armed && dist <= c->near_m * 1.25f", "hostile && dist <= c->near_m * 1.25f", 'the hold ends when the weapon is put away'),
 (C, "hostile && armed && dist <= c->near_m * 1.25f", "hostile && armed", 'the hold ends when he is far away'),
 (C, "v->ram_until = now + (u32)c->ram_hold_ms; v->ram_edps = v->edps;", "v->ram_until = 0; v->ram_edps = v->edps;", 'ramming is held through a swerve'),
 (C, "if (v->ram_until && now < v->ram_until && speed2", "if (v->ram_until && speed2", 'the ramming hold has an end'),
 (C, " && speed2 >= c->ram_speed * c->ram_speed * 0.25f) {", ") {", 'the ramming hold: braking releases'),
 (C, "float best_d = ram ? 9.0f : 150.0f;", "float best_d = ram ? 900.0f : 150.0f;", 'run down: only a car right there'),
 (C, "v_dot(v->last.vel, v->last.vel) < 9.0f", "v_dot(v->last.vel, v->last.vel) < 0.0f", 'run down: a parked car is not blamed'),
 (C, "            if (to_cj) t->damage_cj += e->value; else t->damage_ours += e->value;\n            t->last_hostile = e->time;", "", 'run down: the driver answers for it'),
 (C, "track *t = hcb_find(b, b->vt[best].driver_was);", "track *t = hcb_find(b, b->vt[best].last.driver);", 'run down: the man who jumped out'),
 (C, "        b->vt[best].hit_time = e->time;\n    } else", "    } else", 'run down: the car is remembered'),
 (C, "own2 >= 4.0f && dist <= 60", "dist <= 60", 'run down: only while the car moves'),
 (C, "} else b->vt[best].air_fire = e->time;", "}", 'fire from the air: the helicopter'),
 (C, "if (!v->used || !v->seen || v->last.id == s->heli || v->last.id == s->player.vehicle || hcb_is_ours(s, v->driver_was)) continue;", "if (!v->used || !v->seen) continue;", 'fire from the air: never our own helicopter'),
 (C, "if (!ram && !hcb_is_firearm(e->weapon) && e->weapon != 52) return;", "", 'fire from the air: gunfire only'),
 (C, "now - v->air_fire < 15000", "now - v->air_fire < 1500000", 'fire from the air: for 15 s'),
 (C, "s->on_mission && !s->mission_free &&", "s->on_mission &&", 'missions: as usual'),
 (C, "if (k < HCB_MAX_OURS && !t->friendly) b->kills++;", "b->kills++;", 'kills: only those ours were firing at'),
 (C, "if (k < HCB_MAX_OURS && !t->friendly) b->kills++;", "", 'kills are counted'),
 (C, "fired_at(e->a, e->b, v->last.pos, 2.5f))) v->cj_marked = e->time;", "fired_at(e->a, e->b, v->last.pos, 2.5f))) { }", 'follow: the car CJ fires at'),
 (C, "if (car && car->cj_marked > t->cj_marked) t->cj_marked = car->cj_marked;", "", 'follow: the men in that car'),
 (C, "if (round) copy(round, buf + at + 8, sizeof(hcb_round));", "", 'black box: rounds are given back'),
]
M += [
 (F, "o->fire = (u8)(sh->hold == HCB_HOLD_NONE && sh->aim != 0 && sh->aim == sh->target);", "o->fire = 1;", 'scripts: the order as it stands'),
 (F, "if (sh->next_round && (int)(in->time - sh->next_round) < 0 && sh->next_round - in->time < 2000) return 0;", "", 'rounds: not before the next one is due'),
 (F, "float gap = c->round_min_ms + (c->round_max_ms - c->round_min_ms) * (dice(sh) * 0.5f + 0.5f);", "float gap = 10;", 'rounds: 130 to 180 ms apart'),
 (F, "out = near_heli ? c->muzzle_m : 0.8f;", "out = 0.8f;", 'rounds: start outside the helicopter'),
 (F, "out = near_heli ? c->muzzle_m : 0.8f;", "out = c->muzzle_m;", 'rounds: 0.8 m when dismounted'),
 (F, "q.to.x += dice(sh) * spread; q.to.y += dice(sh) * spread; q.to.z += dice(sh) * spread;", "", 'rounds: nobody is a laser'),
 (F, "spread = c->scatter_m + c->scatter_per_m * len + c->scatter_per_ms * (near_heli ? heli_speed : 0);", "spread = c->scatter_m + c->scatter_per_m * len;", 'rounds: a fast helicopter scatters more'),
 (F, "spread = c->scatter_m + c->scatter_per_m * len + c->scatter_per_ms * (near_heli ? heli_speed : 0);", "spread = 3 * (c->scatter_m + c->scatter_per_m * len);", 'rounds: the scatter has a limit'),
 (F, "r->end = v_add(q.to, v_mul(d, c->round_past_m / len));", "r->end = v_add(q.to, v_mul(d, 30.0f / len));", 'rounds: end 0.6 m past the aim point'),
 (F, "r->verdict = (u8)hcb_shot_check(b, &q);", "r->verdict = 0;", 'rounds: the hard rules on the line of the round'),
 (F, "        sh->next_round = in->time + 60;\n        if (!sh->noted", "        sh->next_round = in->time;\n        if (!sh->noted", 'rounds: a refused round is asked for again 60 ms later'),
 (F, "if (!sh->noted || in->time - sh->noted >= 250) { sh->noted = in->time; r->note = 1; }", "r->note = 1;", 'rounds: refusals noted four times a second'),
 (F, "if (sh) sh->next_round = time + 60;", "", 'rounds: a blocked ray is tried again soon'),
 (F, "if (!sh || sh->hold != HCB_HOLD_NONE || !sh->target || sh->target != in->target) return 0;", "if (!sh) return 0;", 'rounds: only at the man he is ordered to fire at'),
 (F, "if (len < out + 1.0f) { sh->next_round = in->time + 100; return 0; }", "", 'rounds: not at a man at the muzzle'),
 (F, "if (sh->hold == HCB_HOLD_COVERING) return sh->ready ? 1 : 0;", "", 'guard: a suspect is only covered'),
 (F, "why[i][bj] == HCB_HOLD_NONE ? HCB_HOLD_ENOUGH : why[i][bj];", "why[i][bj];", 'the fourth rifle is told why he does not fire'),
 (F, "else if (busy[i] && (cs[j].free || cs[j].taken)) v *= 0.6f;", "", 'a firing man keeps his target when a new attacker turns up'),
 (F, "if (!(len >= out + 1.0f && len < 500.0f) || !(q.cj.x - q.cj.x == 0.0f && q.cj.y - q.cj.y == 0.0f && q.cj.z - q.cj.z == 0.0f))", "if (len < out + 1.0f)", 'a round never gets a point that is not a number'),
 (F, "if (!(heli_speed >= 0.0f && heli_speed < 150.0f)) heli_speed = 0.0f;", "", 'a nonsense helicopter speed is taken as 0'),
 (F, "if (from >= 0) { cs[choice[from]].taken--; choice[from] = j; cs[j].taken++; }", "", 'an attacker nobody is on gets a rifle from the crowd'),
 (F, "need = cs[j].t->cls == HCB_CLS_ATTACKER ? 2 : 3;", "need = 1;", 'a rifle is taken only from a man who has more than he needs'),
 (F, "else if (busy[i] && (cs[j].free || cs[j].taken)) v *= 0.6f;", "else if (busy[i] && cs[j].free) v *= 0.6f;", 'a firing man does not follow the free man to the new attacker'),
 (F, "else if (busy[i] && (cs[j].free || cs[j].taken)) v *= 0.6f;", "else if (busy[i] && cs[j].taken) v *= 0.6f;", 'the free man, not a firing one, takes the new attacker'),
 (F, "if (!done[i] && !busy[i] && (why[i][j] == HCB_HOLD_NONE || why[i][j] == SOFT_LOS)) cs[j].free = 1;", "if (!done[i] && !busy[i]) cs[j].free = 1;", 'free hands count only if he may fire at the man'),
 (F, "return shot_check(cb, q, 1) == HCB_HOLD_NONE ? 2 : 3;", "return 2;", 'guard: cease fire in the same frame'),
 (F, "gunner = is_gunner(sh->role) && !as_guard;", "gunner = is_gunner(sh->role);", 'guard: a man on foot is judged as one, whatever his role'),
 (F, "    if (mine) ask(out, me->id, t->last.id);\n", "\n", 'sight of his own man is asked while a rule holds the fire'),
 (D, "if (radii[i] > 0.01f && v_dot(d, u) > toward) continue;", "", 'detail: CJ is never sent towards the shooter'),
 (D, "return c->hidden && c->ground ? 1 : 0;", "return c->hidden ? 1 : 0;", 'detail: no cover without ground under it'),
 (D, "if (out->n_probe_q >= HCB_MAX_PROBES) return;", "if (out->n_probe_q >= HCB_MAX_PROBES) out->n_probe_q = 0;", 'detail: cover questions a look are limited'),
 (D, "if (now - c->answered > COVER_KEEP_MS) return -1;", "return -1;", 'detail: a fresh answer is not asked again'),
 (D, "else if (now - dt->anchor_since >= 1500) { dt->anchor = d;", "else { dt->anchor = d;", 'detail: the formation turns only after 1.5 s on a new course'),
 (D, "if (job == 1) at = v_add(cjp, v_mul(u, 1.3f));", "if (0) at = v_add(cjp, v_mul(u, 1.3f));", 'detail: a suspect - the bodyguard steps between him and CJ'),
 (D, "if (n_team == 2 && moving[0] && moving[1]) {", "if (0) {", 'detail: bounding overwatch'),
 (D, "cj_in = dt->cj_cover_ok && dist2d(cjp, dt->cj_cover) < 1.6f;", "cj_in = 0;", 'detail: CJ in cover - the bodyguard crouches beside him'),
 (D, "duty = b->alert >= HCB_ALERT_EVACUATE && threat ? HCB_DUTY_RING", "duty = 0 && threat ? HCB_DUTY_RING", 'detail: too hot - a tight ring'),
 (D, "(!dt->evac_said || now - dt->evac_said >= SAY_EVAC_MS)", "(1)", 'detail: "we pull out" not repeated for 20 s'),
 (D, "if (dt->lead && n) say = HCB_SAY_TAKE_OVER;", "", 'detail: the new commander says he has taken over'),
 (D, "if (dt->cj_shot_t && now - dt->cj_shot_t < 1200) {", "if (0) {", 'detail: nobody stands in front of CJ\'s gun'),
 (D, "if (dt->cj_cover_ok && !cj_in && (!dt->cover_said || now - dt->cover_said >= SAY_COVER_MS))", "if (dt->cj_cover_ok && !cj_in)", 'detail: "into cover" not said every look'),
 (D, "for (i = 0; i < n; i++) if (i != lead) { if (close < 0) close = i;", "for (i = 0; i < n; i++) if (1) { if (close < 0) close = i;", 'detail: the commander is not also the bodyguard'),
 (P, "    if (in->stop) vdes = f_min(vdes, f_max(f_sqrt(2.0f * BRAKE * f_max(0.0f, dist - 0.9f * TAU_V * f_sqrt(p->vel.x * p->vel.x + p->vel.y * p->vel.y))), f_min(2.0f, 0.5f * dist)));", "    if (in->stop) vdes = f_min(vdes, f_max(f_sqrt(2.0f * BRAKE * dist), f_min(2.0f, 0.5f * dist)));", 'pilot: braking starts early enough not to overshoot'),
 (P, "if (dist > 20.0f) vdes *= f_clamp(1.0f - f_abs(err) / 1.7f, 0.25f, 1.0f);", "", 'pilot: slower for a sharp turn'),
 (P, "if (a_len > a_max) a = v_mul(a, a_max / a_len);", "", 'pilot: at most 5 m/s2'),
 (P, "pitch_want = f_clamp(-f_atan(a_fwd / G_ACC)", "pitch_want = f_clamp(f_atan(a_fwd / G_ACC)", 'pilot: nose down to speed up'),
 (P, "roll_want = f_clamp(f_atan(a_side / G_ACC), -BANK_MAX, BANK_MAX);", "roll_want = f_clamp(-f_atan(a_side / G_ACC), -BANK_MAX, BANK_MAX);", 'pilot: banked into the turn'),
 (P, "out->right = v_sub(v_mul(r0, cr), v_mul(u1, sr));", "out->right = v_add(v_mul(r0, cr), v_mul(u1, sr));", 'pilot: the matrix rows match the bank'),
 (P, "    if (p->pos.z < ground + 10.0f || in->blocked) vdes = 0.0f;", "    if (in->blocked) vdes = 0.0f;", 'pilot: below the roofs, up first'),
 (P, "    if (in->blocked) { p->vel.x = p->vel.y = 0; a.x = a.y = 0; }\n", "\n", 'pilot: a refused step stops it at once'),
 (P, "    if (dt > 0.1f) dt = 0.1f;", "", 'pilot: a long frame is flown as a short one'),
 (P, "clear = hover + (CLEAR - hover) * f_clamp((dist - 60.0f) / 200.0f, 0.0f, 1.0f);", "clear = hover;", 'pilot: high while travelling, low only near the point'),
 (P, "    if (in->stop && p->pos.z - (ground + clear) > 3.0f) {", "    if (0) {", 'pilot: down in time after a tall roof'),
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
    for test in ('test_core.py', 'test_fire.py', 'test_detail.py', 'test_pilot.py'):
        r = subprocess.run([sys.executable, str(ROOT / 'brain' / 'tests' / test)], capture_output=True, text=True, env=env)
        if r.returncode:
            caught = True
            break
    missed += not caught
    print(('CAUGHT  ' if caught else 'MISSED  ') + name + ('' if caught else '  <<<<<<'), flush=True)
sys.exit(1 if missed else 0)
