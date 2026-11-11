"""Decide, from labelled titles, which rules are reliable enough to publish.

For every rule: how often the function it gives was right (FN_MIN) and how often its sub-role was right (FT_MIN) over the labelled
titles it decided. A rule below FN_MIN publishes fn "0" (Not stated); one below FT_MIN publishes no sub-role. Rules with fewer than
MIN_SUPPORT labelled titles keep their default (published). The flags are written back into data/function/rules.json ("flags": rule
position -> letters, "f" = function not published, "t" = sub-role not published), so recalibrating is a data commit.

Usage: function_calibrate.py ROUND [ROUND ...]     rounds whose labels are used for the calibration
"""
import collections, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import function as F

FN_MIN, FT_MIN, MIN_SUPPORT = 0.90, 0.92, 3
D = root / "data" / "function"
doc = json.loads((D / "rules.json").read_text())
doc["flags"] = {}
F.reset_cache()
stats = collections.defaultdict(lambda: [0, 0, 0, 0])      # n, fn right, ft predicted, ft right
for r in sys.argv[1:]:
    for l in (D / f"eval-r{r}.jsonl").read_text().splitlines():
        c = json.loads(l)
        pos = F.rule_of(c["title"])
        if pos < 0:
            continue
        rule = doc["rules"][pos]
        st = stats[pos]
        st[0] += 1
        st[1] += rule["fn"] == c["fn"]
        if rule["ft"]:
            st[2] += 1
            st[3] += rule["fn"] == c["fn"] and rule["ft"] == c["ft"]
for pos, (n, fr, tp, tr) in sorted(stats.items()):
    flags = ""
    if n >= MIN_SUPPORT and fr / n < FN_MIN:
        flags += "f"
    if tp >= MIN_SUPPORT and tr / tp < FT_MIN:
        flags += "t"
    if flags:
        doc["flags"][str(pos)] = flags
        print(f"rule {pos} {doc['rules'][pos]['fn']}:{doc['rules'][pos]['ft']} n={n} fn {fr}/{n} ft {tr}/{tp} -> {flags}")
(D / "rules.json").write_text(json.dumps(doc, ensure_ascii=False, indent=0))
print(len(doc["flags"]), "rules flagged")
