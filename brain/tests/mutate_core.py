"""Mutation check for the brain's core: break one rule at a time in a scratch copy and make sure test_core.py notices.
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
 (C, "if (!e->src || e->src == s->player.id || is_ours(s, e->src)) return;", "if (!e->src || e->src == s->player.id) return;", 'shot: our own fire is not counted'),
 (C, "else if (is_ours(s, e->dst)) { t = touch(b, e->src, s->time); t->damage_ours += e->value; t->last_hostile = e->time; }", "", 'damage to ours'),
 (C, "if (t->last_hostile && now - t->last_hostile < (u32)c->attacker_ms) {", "if (t->last_hostile) {", 'attacker for 20 s'),
 (C, "if (!(p->flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP)) && p->pedtype != 8) return 0;", "if (!(p->flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP))) return 0;", 'Grove are allies'),
 (C, "if (!(p->flags & (HCB_PF_RESPECTS | HCB_PF_IN_GROUP)) && p->pedtype != 8) return 0;", "if (!(p->flags & HCB_PF_RESPECTS) && p->pedtype != 8) return 0;", 'recruits are allies'),
 (C, "    if (p->flags & HCB_PF_HATES) return 0;\n    if (!(p->flags", "    if (!(p->flags", 'hatred overrides the uniform'),
 (C, "return !(t->damage_cj >= 20 && now", "return !(t->damage_cj >= 2000 && now", 'an ally who attacks CJ'),
 (C, "if (is_ours(s, p->id)) { t->friendly = 1;", "if (0) { t->friendly = 1;", 'ours are friends'),
 (C, "if (defensive && cls == HCB_CLS_THREAT", "if (0 && cls == HCB_CLS_THREAT", 'mission people are left alone'),
 (C, "keep = t->cls == HCB_CLS_ATTACKER ? (u32)c->attacker_ms :", "keep = t->cls == HCB_CLS_ATTACKER ? (u32)c->forget_ms :", 'an unseen attacker is remembered'),
 (C, "if (!t->seen) edps *= 0.25f;", "", 'out of sight is less dangerous'),
 (C, "if (p->flags & HCB_PF_DEAD) { t = find(b, p->id); if (t) t->used = 0; continue; }", "", 'the dead are dropped'),
 (C, "if (!t->seen && !ped_of(s, e->src)) t->last.pos = e->a;", "", 'an unseen shooter is placed at the muzzle'),
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
 (C, "if (need != len) return 0;", "", 'black box: damaged records are refused'),
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
    r = subprocess.run([sys.executable, str(ROOT / 'brain' / 'tests' / 'test_core.py')], capture_output=True, text=True, env=env)
    caught = r.returncode != 0
    missed += not caught
    print(('CAUGHT  ' if caught else 'MISSED  ') + name + ('' if caught else '  <<<<<<'), flush=True)
sys.exit(1 if missed else 0)
