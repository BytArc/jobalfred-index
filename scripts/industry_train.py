"""Fit the industry model from reader-labelled companies. Writes data/industry/model.json.

Usage: industry_train.py [--exclude eval-r3.jsonl ...]
Inputs, all versioned in the repo:
  data/industry/labels.jsonl      companies a reader labelled by looking at them (key, name, ind)
  data/industry/eval-r*.jsonl     fresh samples labelled the same way, folded into training once they have been measured
  data/industry/lexicon.json      hand-written keywords per industry, used as pseudo-observations
  data/industry/homepages.json.gz cached homepage text
  work/ind/companies.pkl          job-title words per company (rebuilt by scripts/industry_companies.py from the shards)
Retraining is a commit of model.json, not a code change.
"""
import collections, json, math, pickle, sys, time
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry as I

exclude = set()
a = sys.argv[1:]
while a:
    if a.pop(0) == "--exclude":
        while a and not a[0].startswith("--"):
            exclude.add(a.pop(0))
D = root / "data" / "industry"
tax = json.loads((D / "taxonomy.json").read_text())
classes = [c for c in tax if c not in (I.OTHER, I.NOT_STATED)]
lex = json.loads((D / "lexicon.json").read_text())
comp = pickle.load(open(root / "work" / "ind" / "companies.pkl", "rb"))
hp = I.Homepages()
labels = {}
for f in [D / "labels.jsonl"] + sorted(D.glob("eval-r*.jsonl")):
    if f.name in exclude or not f.exists():
        continue
    for line in f.read_text().splitlines():
        if line.strip():
            o = json.loads(line)
            labels[o["key"]] = o
ALPHA, SEED = 0.5, 2.5
g_counts = {g: collections.defaultdict(lambda: collections.defaultdict(float)) for g in "nthx"}
class_n = collections.Counter()
used = 0
for key, o in labels.items():
    c = o["ind"]
    if c == I.OTHER or c not in classes:
        class_n[c] += 1
        continue
    k = key[2:]
    info = comp.get(k)
    words = info["words"] if info else {}
    entry = hp.get(key)
    dom = I.own_domain("https://" + h + "/" for h in info["hosts"]) if info else ""
    feat = I.features(o["name"], words, I.home_text(entry), dom, I.row_meta(info["ats"], info["cc"]) if info else None)
    for g in "nthx":
        for f, v in feat[g].items():
            g_counts[g][f][c] += v
    class_n[c] += 1
    used += 1
# keywords: pseudo-observations in every group, and the substrings searched for in run-together names
subs = set()
for c, ws in lex.items():
    for w in ws:
        parts = [w] + (w.split("-") if "-" in w else [])
        for p in parts:
            p = I.fold(p)
            if len(p) < 3:
                continue
            for g in "nth":
                g_counts[g][p][c] += SEED
            if len(p) >= 5 and p.isalpha():
                subs.add(p)
model = {"version": time.strftime("%Y-%m-%d"), "alpha": ALPHA, "classes": classes, "labelled": used,
         "prior": {}, "groups": {}, "name_substrings": sorted(subs)}
tot_prior = sum(math.sqrt(class_n.get(c, 0) + 4) for c in classes)
for c in classes:
    model["prior"][c] = math.sqrt(class_n.get(c, 0) + 4) / tot_prior
for g in "nthx":
    tab = g_counts[g]
    tot = {c: 0.0 for c in classes}
    keep = {}
    for f, row in tab.items():
        s = sum(row.values())
        if s < 1.0:
            continue
        keep[f] = {c: round(v, 2) for c, v in row.items()}
        for c, v in row.items():
            tot[c] += v
    model["groups"][g] = {"total": {c: round(v, 2) for c, v in tot.items()}, "vocab": len(keep), "f": keep}
(D / "model.json").write_text(json.dumps(model, separators=(",", ":"), ensure_ascii=False))
print(f"trained on {used} labelled companies ({len(labels)} labels), {sum(len(model['groups'][g]['f']) for g in 'nthx')} features,",
      f"{(D / 'model.json').stat().st_size // 1024} KB")
