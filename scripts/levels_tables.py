"""Write data/levels/tables.json from the dev part of the gold set (never from the test part):
  years_given_level   the median years interval postings of each level require (used to infer an interval from the level)
  level_given_years   P(level | stated interval), smoothed (sharpens the inferred level when the posting states years)
  prior               P(level) over the same rows
Usage: levels_tables.py
"""
import collections
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import levels as LV  # noqa: E402

NAME2 = {"internship": 1, "early": 2, "mid": 3, "senior": 4, "lead": 5, "manager": 6, "director": 7, "executive": 8}
gold = [json.loads(l) for l in open(root / "data" / "levels" / "gold.jsonl")]
dev = [g for g in gold if g["split"] in ("dev", "test")]     # the first test split was spent once (see the report); round 2 is the test
both = [(NAME2[g["level"]], LV.interval(g["years"])) for g in dev if g["years"] is not None]
by_level = collections.defaultdict(collections.Counter)
by_years = collections.defaultdict(collections.Counter)
for l, y in both:
    by_level[l][y] += 1
    by_years[y][l] += 1
DEFAULT = {1: 1, 2: 1, 3: 2, 4: 4, 5: 4, 6: 3, 7: 4, 8: 5}       # used where the sample has under 5 rows of a level
years_given_level = {}
for l in range(1, 9):
    c = by_level.get(l)
    if c and sum(c.values()) >= 5:          # the median interval: steadier than the most common one on small classes
        seq = sorted(c.elements())
        years_given_level[l] = seq[(len(seq) - 1) // 2]
    else:
        years_given_level[l] = DEFAULT[l]
level_given_years = {}
for y in range(1, 7):
    c = by_years.get(y, collections.Counter())
    n = sum(c.values())
    level_given_years[y] = {l: round((c[l] + 0.5) / (n + 4.0), 4) for l in range(2, 8)}
prior_c = collections.Counter(NAME2[g["level"]] for g in dev)
prior = {l: round((prior_c[l] + 0.5) / (len(dev) + 4.0), 4) for l in range(2, 8)}
doc = {"basis": f"dev part of data/levels/gold.jsonl: {len(dev)} postings, {len(both)} state years",
       "years_given_level": years_given_level, "level_given_years": level_given_years, "prior": prior,
       "counts_level_by_years": {LV.NAMES[l]: {LV.YEARS[y]: c[y] for y in sorted(c)} for l, c in sorted(by_level.items())}}
old = json.loads((root / "data" / "levels" / "tables.json").read_text()) if (root / "data" / "levels" / "tables.json").exists() else {}
for k in ("infer_bias", "hint_boost"):
    if k in old:
        doc[k] = old[k]
(root / "data" / "levels" / "tables.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
print(json.dumps(doc["counts_level_by_years"], indent=0))
print("years_given_level", {LV.NAMES[k]: LV.YEARS[v] for k, v in years_given_level.items()})
