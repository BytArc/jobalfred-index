"""Score the industry model on reader-labelled companies.

Usage: industry_score.py record ROUND '{"0":"hlt",...}'   save truths (unlisted indices must be listed too: every company is labelled)
       industry_score.py score ROUND [ROUND ...]         accuracy, per industry, main confusions; both unweighted and weighted by rows
"""
import collections, json, pickle, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry as I

D = root / "data" / "industry"
comp = pickle.load(open(root / "work" / "ind" / "companies.pkl", "rb"))
hp = I.Homepages()
I.USE_OVERRIDES = False      # measure the model itself, not the labels it was given


def predict(o):
    k = o["key"][2:] if o["key"].startswith("c:") else o["key"]
    c = comp.get(k)
    entry = hp.get(o["key"]) if o["key"].startswith("c:") else None
    dom = I.own_domain("https://" + h + "/" for h in c["hosts"]) if c else ""
    return I.classify(o["name"], c["words"] if c else {}, I.home_text(entry), dom or (entry or {}).get("d", ""), I.row_meta(c["ats"], c["cc"]) if c else None)


def record(rnd, truths):
    rows = json.load(open(root / "work" / "ind" / f"round-{rnd}.json"))
    out = [{"key": o["key"], "name": o["name"], "ind": truths[str(i)], "rows": o["rows"], "mode": o["mode"], "set": f"eval-r{rnd}"} for i, o in enumerate(rows)]
    (D / f"eval-r{rnd}.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n")
    print(len(out), "saved")


def score(rounds):
    cases = []
    for r in rounds:
        for l in (D / f"eval-r{r}.jsonl").read_text().splitlines():
            cases.append(json.loads(l))
    ok = [(c, predict(c)[0]) for c in cases]
    n = len(ok)
    right = sum(1 for c, p in ok if p == c["ind"])
    w = sum(c["rows"] for c, _ in ok)
    wr = sum(c["rows"] for c, p in ok if p == c["ind"])
    print(f"companies={n} correct={right} ({right / n:.1%}) | weighted by rows {wr / w:.1%}")
    for mode in ("uniform", "rows"):
        sub = [(c, p) for c, p in ok if c["mode"] == mode]
        if sub:
            print(f"  {mode}: n={len(sub)} unweighted {sum(1 for c, p in sub if p == c['ind']) / len(sub):.1%}  row-weighted {sum(c['rows'] for c, p in sub if p == c['ind']) / sum(c['rows'] for c, _ in sub):.1%}")
    real = [(c, p) for c, p in ok if c["ind"] != I.OTHER]
    print(f"  real-industry companies only: {sum(1 for c, p in real if p == c['ind'])}/{len(real)}; predicted other: {sum(1 for c, p in ok if p == I.OTHER)}")
    per = collections.defaultdict(lambda: [0, 0, 0])
    for c, p in ok:
        per[c["ind"]][1] += 1
        per[c["ind"]][0] += p == c["ind"]
        per[p][2] += 1
    print("  per true industry (right/total, predicted count):", {k: f"{v[0]}/{v[1]} ({v[2]})" for k, v in sorted(per.items(), key=lambda kv: -kv[1][1])})
    conf = collections.Counter((c["ind"], p) for c, p in ok if p != c["ind"])
    print("  main confusions (truth->pred):", dict(conf.most_common(14)))
    for c, p in ok:
        if p != c["ind"]:
            print(f"   ERR {c['name'][:36]:36} rows={c['rows']:5} truth={c['ind']} pred={p}")


if __name__ == "__main__":
    if sys.argv[1] == "record":
        record(sys.argv[2], json.loads(sys.argv[3]))
    else:
        score(sys.argv[2:])
