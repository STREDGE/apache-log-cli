"""Replay a Helicover Brain report (the black box file the player sends) on this computer and say what the brain saw
and decided.

    python3 brain/tools/replay.py path/to/hcbrain_report.bin [--all]

The core is deterministic: from the first stored brain state in the file every decision is reproduced exactly and
checked against the digest recorded on the phone. Before that point the replay starts from an empty memory, so the
first seconds may differ - the tool says how many ticks matched.
"""
import ctypes, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tests'))
import hcb_py as h

CLS = {h.HCB_CLS_FRIEND: 'friend', h.HCB_CLS_NEUTRAL: 'neutral', h.HCB_CLS_WATCH: 'watch', h.HCB_CLS_THREAT: 'THREAT', h.HCB_CLS_ATTACKER: 'ATTACKER'}
ALERT = {0: 'calm', 1: 'wary', 2: 'threat', 3: 'COMBAT', 4: 'EVACUATE'}
WHY = {v: k[8:].lower().replace('_', ' ') for k, v in h.CONSTS.items() if k.startswith('HCB_WHY_')}
EVENT = {h.HCB_EV_SHOT: 'shot', h.HCB_EV_DAMAGE: 'damage', h.HCB_EV_EXPLOSION: 'explosion', h.HCB_EV_PROJECTILE: 'projectile'}


def replay(data):
    """Returns (head, text, ticks): ticks = [dict(snapshot, out (a copy), match (bool), exact (bool), rounds)];
    rounds = the rounds of ours asked for after that look and before the next (hcb_round)."""
    head, records, text = h.read_box(data)
    brain = h.Brain(seed=head.seed)
    ticks, exact = [], False
    for r in records:
        if r[0] == 'state':
            ctypes.memmove(brain.mem, r[1], len(r[1]))
            exact = True
            continue
        if r[0] == 'round':
            if ticks:
                ticks[-1]['rounds'].append(h.hcb_round.from_buffer_copy(bytes(r[1])))
            continue
        out = brain.think(r[1])
        copy = h.hcb_out.from_buffer_copy(bytes(out))
        ticks.append(dict(snapshot=r[1], out=copy, match=copy.digest == r[2], exact=exact, rounds=[]))
    return head, text, ticks


def summarize(data, everything=False):
    head, text, ticks = replay(data)
    lines = ['Helicover Brain report: %d records (%d dropped earlier), %d ticks' % (head.records, head.dropped, len(ticks))]
    if text.strip():
        lines += ['  ' + l for l in text.strip().splitlines()]
    if not ticks:
        return '\n'.join(lines + ['no snapshots in the file'])
    exact = [t for t in ticks if t['exact']]
    bad = [t for t in exact if not t['match']]
    lines.append('replay: %d of %d ticks start from a stored brain state; %s' % (
        len(exact), len(ticks), 'all of them reproduce the phone\'s decisions exactly' if exact and not bad else
        '%d DIFFER from the phone - the core here is not the one that wrote the file' % len(bad) if bad else 'none - the first seconds are approximate'))
    t0 = ticks[0]['snapshot'].time
    lines.append('time span: %.1f s, peds per snapshot %d..%d, events lost %d, peds lost %d' % (
        (ticks[-1]['snapshot'].time - t0) / 1000., min(t['snapshot'].n_peds for t in ticks), max(t['snapshot'].n_peds for t in ticks),
        sum(t['snapshot'].events_lost for t in ticks), max(t['snapshot'].peds_lost for t in ticks)))
    HOLD = {v: k[9:].lower().replace('_', ' ') for k, v in h.CONSTS.items() if k.startswith('HCB_HOLD_')}
    fired = sum(1 for t in ticks for r in t['rounds'] if r.verdict == h.HCB_HOLD_NONE and r.ray)
    refused = {}
    for t in ticks:
        for r in t['rounds']:
            if r.verdict != h.HCB_HOLD_NONE or not r.ray:
                why = HOLD.get(r.verdict, r.verdict) if r.verdict != h.HCB_HOLD_NONE else 'the ray was blocked'
                refused[why] = refused.get(why, 0) + 1
    lines.append('rounds of the door gunners: %d let go; refused (noted at most four times a second per gunner): %s' % (fired, ', '.join('%s %d' % kv for kv in sorted(refused.items())) or 'none'))
    last_alert, last_marks, last_orders = None, {}, {}
    for t in ticks:
        s, o = t['snapshot'], t['out']
        stamp = '%7.1fs' % ((s.time - t0) / 1000.)
        for e in s.events[:s.n_events]:
            if everything or e.dst == s.player.id or e.type != h.HCB_EV_SHOT:
                lines.append('%s   event %-10s src %#x dst %#x weapon %d value %.0f' % (stamp, EVENT.get(e.type, e.type), e.src, e.dst, e.weapon, e.value))
        if o.alert != last_alert:
            lines.append('%s alert %s (danger %.0f, CJ health %.0f, wanted %d%s)' % (stamp, ALERT.get(o.alert, o.alert), o.danger, s.player.health, s.wanted,
                                                                                    ', mission' if s.on_mission else ''))
            last_alert = o.alert
        marks = {m.id: (m.cls, m.why, m.seen) for m in o.marks[:o.n_marks] if m.cls != h.HCB_CLS_FRIEND or everything}
        for id, (cls, why, seen) in marks.items():
            if last_marks.get(id, (None,))[0] != cls or (everything and last_marks.get(id) != (cls, why, seen)):
                m = next(m for m in o.marks[:o.n_marks] if m.id == id)
                lines.append('%s   %s %#x -> %s (%s) at %.0f m, expected damage %.0f/s%s' % (
                    stamp, 'car' if m.kind else 'ped', id, CLS[cls], WHY.get(why, why), m.dist, m.edps, '' if seen else ', out of sight'))
        for id in last_marks:
            if id not in marks:
                lines.append('%s   %#x no longer of interest' % (stamp, id))
        last_marks = marks
        orders = {od.who: (od.target, od.fire, od.hold) for od in o.orders[:o.n_orders]}
        for who, (target, fire, hold) in orders.items():
            was = last_orders.get(who, (0, 0, 0))
            if target != was[0] or (everything and (fire, hold) != was[1:]):
                lines.append('%s   ours %#x -> %s' % (stamp, who, ('%#x, %s' % (target, 'FIRE' if fire else HOLD.get(hold, hold))) if target else 'no target'))
        last_orders = orders
        if everything:
            for r in t['rounds']:
                lines.append('%s     round %#x at %#x: %s' % (stamp, r.who, r.target, 'let go' if r.verdict == h.HCB_HOLD_NONE and r.ray else 'refused, ' + (HOLD.get(r.verdict, r.verdict) if r.verdict != h.HCB_HOLD_NONE else 'the ray was blocked')))
    return '\n'.join(lines)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        print(summarize(Path(sys.argv[1]).read_bytes(), '--all' in sys.argv))
    except ValueError as e:
        sys.exit('cannot use this file: %s' % e)
