"""Turn a Helicover Brain report into a fight file that outlives the brain's version.

    python3 brain/tools/box2json.py report.bin brain/tests/data/name.json.gz [first_tick last_tick]

(1.3: a window of the report only - the looks first_tick..last_tick, counted from 0 - for a test that needs a few
hundred looks of a long report. A report of the version before is read for its inputs.)

A report can only be read by the core that wrote it (the structs are stored raw). A fight file stores the same
snapshots by FIELD NAME, so a later core with more fields can still be fed the recorded fight
(hcb_py.load_fight). Run this with the core the report was written by, i.e. before changing hcb.h.
"""
import ctypes, gzip, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tests'))
import hcb_py as h

COUNTS = dict(peds='n_peds', vehs='n_vehs', events='n_events', los='n_los', ours='n_ours', our_role='n_ours')


def num(v):
    return float('%.9g' % v) if isinstance(v, float) else v


def plain(obj, schema):
    """A ctypes struct as a flat list of values (nested structs flattened in place); the field names go to `schema` once."""
    name = type(obj).__name__
    row, names = [], []
    for field, ctype in obj._fields_:
        if field.startswith('reserved'):
            continue
        v = getattr(obj, field)
        if isinstance(v, ctypes.Structure):
            sub = plain(v, schema)
            row += sub
            names += ['%s.%s' % (field, n) for n in schema[type(v).__name__]]
        elif isinstance(v, ctypes.Array):
            continue                      # arrays are written by the caller, cut to their counts
        else:
            row.append(num(v))
            names.append(field)
    schema.setdefault(name, names)
    return row


def convert(data, first=0, last=None):
    head, records, text = h.read_box(data, inputs_only=True)
    schema, ticks = {}, []
    for k, r in enumerate([r for r in records if r[0] == 'snapshot']):
        if k < first or (last is not None and k > last):
            continue
        s = r[1]
        t = dict(head=plain(s, schema))
        for arr, count in COUNTS.items():
            items = list(getattr(s, arr))[:getattr(s, count)]
            t[arr] = [plain(i, schema) if isinstance(i, ctypes.Structure) else i for i in items]
        ticks.append(t)
    return dict(format='hcb-fight-1', core_version=h.HCB_VERSION, note=text, schema=schema, ticks=ticks)


if __name__ == '__main__':
    if len(sys.argv) not in (3, 5):
        sys.exit(__doc__)
    fight = convert(Path(sys.argv[1]).read_bytes(), *(int(a) for a in sys.argv[3:5]))
    raw = json.dumps(fight, separators=(',', ':')).encode()
    with gzip.GzipFile(sys.argv[2], 'wb', mtime=0) as f:
        f.write(raw)
    print('%d snapshots, %d bytes of json, %d bytes written' % (len(fight['ticks']), len(raw), Path(sys.argv[2]).stat().st_size))
