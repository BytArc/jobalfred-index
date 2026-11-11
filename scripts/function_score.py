"""Score the function model on reader-labelled titles.

Usage: function_score.py record ROUND JSON      JSON maps index -> "fn" or "fn:ft" ("oth" for none)
       function_score.py score ROUND [ROUND ...]
"""
import collections, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import function as F

D = root / "data" / "function"
W = root / "work" / "fn"


def record(rnd, truth):
    titles = json.load(open(W / f"round-{rnd}.json"))
    rows = []
    for i, t in enumerate(titles):
        fn, _, ft = truth[str(i)].partition(":")
        rows.append({"title": t, "fn": fn, "ft": ft})
    (D / f"eval-r{rnd}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(len(rows), "saved")


def score(rounds):
    cases = [json.loads(l) for r in rounds for l in (D / f"eval-r{r}.jsonl").read_text().splitlines()]
    pred = [F.label(c["title"]) for c in cases]
    n = len(cases)
    ok = sum(p[0] == c["fn"] for p, c in zip(pred, cases))
    real = [(p, c) for p, c in zip(pred, cases) if c["fn"] != "oth"]
    other = [(p, c) for p, c in zip(pred, cases) if c["fn"] == "oth"]
    print(f"titles={n} function correct={ok} ({ok / n:.1%})")
    print(f"  office-function titles: {sum(p[0] == c['fn'] for p, c in real)}/{len(real)} ({sum(p[0] == c['fn'] for p, c in real) / max(1, len(real)):.1%})")
    print(f"  Other titles (kept apart): {sum(p[0] == 'oth' for p, c in other)}/{len(other)} ({sum(p[0] == 'oth' for p, c in other) / max(1, len(other)):.1%})")
    sub = [(p, c) for p, c in real if c["ft"]]
    print(f"  sub-role among labelled: {sum(p[1] == c['ft'] for p, c in sub)}/{len(sub)} ({sum(p[1] == c['ft'] for p, c in sub) / max(1, len(sub)):.1%})")
    per = collections.defaultdict(lambda: [0, 0, 0])
    for p, c in zip(pred, cases):
        per[c["fn"]][1] += 1
        per[c["fn"]][0] += p[0] == c["fn"]
        per[p[0]][2] += 1
    print("  per true function (right/total, predicted):", {k: f"{v[0]}/{v[1]} ({v[2]})" for k, v in sorted(per.items(), key=lambda kv: -kv[1][1])})
    conf = collections.Counter((c["fn"], p[0]) for p, c in zip(pred, cases) if p[0] != c["fn"])
    print("  main confusions (truth->pred):", dict(conf.most_common(12)))
    for p, c in zip(pred, cases):
        if p[0] != c["fn"] or (c["ft"] and p[1] != c["ft"]):
            print(f"   ERR {c['title'][:60]:60} truth={c['fn']}:{c['ft']} pred={p[0]}:{p[1]}")


if __name__ == "__main__":
    a = sys.argv
    record(a[2], json.loads(a[3])) if a[1] == "record" else score(a[2:])
