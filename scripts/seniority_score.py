"""Record the true level a reader decided for each sampled role, and score the rules against it.

Usage:
  seniority_score.py record ROUND '{"3":4,"7":2,...}'   truths for the listed indices; every other row of the round is 0 (not stated)
  seniority_score.py score ROUND [ROUND ...]            score the rules on those rounds (fresh text is read from work/sen/)
Labelled cases (no page text) are saved in data/seniority/labels-rROUND.jsonl.
"""
import collections, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import seniority as S

LANG = {"PT": "pt", "BR": "pt", "ES": "es", "FR": "fr", "DE": "de", "IT": "it", "NL": "nl"}


def record(rnd, truths):
    rows = json.load(open(root / "work" / "sen" / f"round-{rnd}.json"))
    out = []
    for i, o in enumerate(rows):
        out.append({"i": i, "title": o["title"], "company": o["company"], "ats": o["ats"], "cc": o["cc"], "url": o["url"],
                    "truth": int(truths.get(str(i), 0)), "round": rnd})
    (root / "data" / "seniority" / f"labels-r{rnd}.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n")
    print(len(out), "cases saved")


def predict(o, with_desc):
    return S.label(o["title"], None, o["text"] if with_desc else None)[0]


def score(rounds, with_desc=True, quiet=False):
    cases = []
    for r in rounds:
        texts = json.load(open(root / "work" / "sen" / f"round-{r}.json"))
        lab = [json.loads(l) for l in (root / "data" / "seniority" / f"labels-r{r}.jsonl").read_text().splitlines()]
        for l in lab:
            l["text"] = texts[l["i"]]["text"]
            cases.append(l)
    n = len(cases)
    pred = [predict(c, with_desc) for c in cases]
    given = [(c, p) for c, p in zip(cases, pred) if p]
    right = sum(1 for c, p in given if p == c["truth"])
    unstated = [(c, p) for c, p in zip(cases, pred) if not p]
    missed = sum(1 for c, p in unstated if c["truth"])
    determinable = sum(1 for c in cases if c["truth"])
    print(f"cases={n}  with_desc={with_desc}  labelled={len(given)} ({len(given)/n:.0%})  correct among labelled={right}/{len(given)} = {right/max(1,len(given)):.1%}")
    print(f"not stated={len(unstated)} ({len(unstated)/n:.0%}); of those the reader found a level in {missed} ({missed/max(1,len(unstated)):.0%}); "
          f"recall of determinable={(determinable-missed)/max(1,determinable):.0%}")
    if quiet: return right / max(1, len(given))
    by_lang = collections.defaultdict(lambda: [0, 0])
    by_lvl = collections.defaultdict(lambda: [0, 0])
    for c, p in given:
        by_lang[LANG.get(c["cc"], "en")][1] += 1
        by_lang[LANG.get(c["cc"], "en")][0] += p == c["truth"]
        by_lvl[S.NAMES[p]][1] += 1
        by_lvl[S.NAMES[p]][0] += p == c["truth"]
    print("per language:", {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_lang.items())})
    print("per predicted level:", {k: f"{v[0]}/{v[1]}" for k, v in by_lvl.items()})
    conf = collections.Counter((S.NAMES[c['truth']], S.NAMES[p]) for c, p in given if p != c["truth"])
    print("errors (truth -> predicted):", dict(conf.most_common(12)))
    for c, p in given:
        if p != c["truth"]:
            print(f"  ERR [{c['i']}] {c['ats'][:4]} {c['cc']} {c['title'][:60]} | pred={S.NAMES[p]} truth={S.NAMES[c['truth']]}")
    for c, p in unstated:
        if c["truth"]:
            print(f"  MISS [{c['i']}] {c['title'][:60]} | truth={S.NAMES[c['truth']]}")
    return right / max(1, len(given))


if __name__ == "__main__":
    if sys.argv[1] == "record":
        record(sys.argv[2], json.loads(sys.argv[3]))
    else:
        score([a for a in sys.argv[2:] if not a.startswith("--")], with_desc="--title-only" not in sys.argv)
