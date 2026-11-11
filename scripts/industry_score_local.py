"""Score the local industry model on reader-labelled companies it never saw: precision and coverage at each confidence cutoff.

Usage: industry_score_local.py MODEL.json.gz ROUND [ROUND ...]     (rounds as in data/industry/eval-r<ROUND>.jsonl, e.g. 4u 4r)
"""
import json, pickle, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry as I, localclf

model = localclf.load(Path(sys.argv[1]))
comp = pickle.load(open(root / "work" / "ind" / "companies.pkl", "rb"))
hp = I.Homepages()
cases = [json.loads(l) for r in sys.argv[2:] for l in open(root / "data" / "industry" / f"eval-r{r}.jsonl")]
P = []
for o in cases:
    k = o["key"][2:]
    c = comp.get(k)
    if not c:
        P.append((I.NOT_STATED, 0.0)); continue
    e = hp.get(o["key"]) if o["key"].startswith("c:") else None
    dom = I.own_domain(["https://" + h + "/" for h in c["hosts"]]) or (e or {}).get("d", "")
    P.append(localclf.classify(c["name"], dom, (e or {}).get("t", ""), (e or {}).get("m", ""), c["words"], c["ats"], c["cc"], model))
print(f"n={len(cases)} companies, {sum(c['rows'] for c in cases)} rows; unfiltered accuracy {sum(p[0] == c['ind'] for p, c in zip(P, cases)) / len(cases):.1%}")
for cut in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95):
    pub = [(p, c) for p, c in zip(P, cases) if p[0] != I.NOT_STATED and p[1] >= cut]
    if not pub:
        break
    pc = sum(p[0] == c["ind"] for p, c in pub) / len(pub)
    pr = sum(c["rows"] for p, c in pub if p[0] == c["ind"]) / sum(c["rows"] for p, c in pub)
    print(f"cutoff {cut}: published {len(pub)} companies ({len(pub) / len(cases):.0%}), {sum(c['rows'] for p, c in pub) / sum(c['rows'] for c in cases):.0%} of rows; precision per company {pc:.1%}, row-weighted {pr:.1%}")
