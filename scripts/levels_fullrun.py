"""Run the level and years build step over a pickled copy of a published index ((fields, rows) from the release shards) and print its
time and the tags it gives. Usage: levels_fullrun.py ROWS.pkl"""

import pickle, time, collections, sys, json
sys.path.insert(0, '.')
from jobalfred_index import levels as L, shards, levelinfer
F, rows = pickle.load(open(sys.argv[1], 'rb'))
ix = {k: i for i, k in enumerate(F)}
rows = [[r[ix[k]] if k in ix else "" for k in shards.FIELDS] for r in rows]
t0 = time.time()
for r in rows:
    shards.complete(r)
t1 = time.time()
st = L.assign(rows, log=lambda m: None)
t2 = time.time()
SS, SL, YX, YS = (shards.FIELDS.index(k) for k in ("ss", "sl", "yx", "ys"))
n = len(rows)
src = collections.Counter(r[SS] for r in rows)
out = {"rows": n, "complete_s": round(t1 - t0, 1), "assign_s": round(t2 - t1, 1),
       "level_source": {k: f"{v} ({100*v/n:.1f}%)" for k, v in src.most_common()},
       "levels": {L.NAMES[k]: v for k, v in sorted(collections.Counter(r[SL] for r in rows).items())},
       "years_source": dict(collections.Counter(r[YS] for r in rows)),
       "years": {L.YEARS[k]: v for k, v in sorted(collections.Counter(r[YX] for r in rows).items())}}
print(json.dumps(out, indent=1))
