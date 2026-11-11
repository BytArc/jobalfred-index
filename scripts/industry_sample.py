"""Draw a fresh random sample of companies for the reader to label. Predictions are hidden when shown.

Usage: industry_sample.py draw ROUND N SEED MODE    MODE: uniform (every company equally likely) or rows (likelihood proportional to rows)
       industry_sample.py show ROUND                evidence only: name, rows, domain, homepage text, job-title words, hosts
"""
import json, pickle, random, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry as I

D = root / "data" / "industry"
comp = pickle.load(open(root / "work" / "ind" / "companies.pkl", "rb"))
hp = I.Homepages()


def seen():
    out = set()
    for f in [D / "labels.jsonl"] + list(D.glob("eval-r*.jsonl")):
        if f.exists():
            out |= {json.loads(l)["key"] for l in f.read_text().splitlines() if l.strip()}
    return out


def draw(rnd, n, seed, mode):
    random.seed(seed)
    done = seen()
    pool = [(k, c) for k, c in comp.items() if ("c:" + k if not k.startswith("~") else k) not in done and (not k.startswith("~") or c["rows"] >= 20)]
    if mode == "rows":
        pick = random.choices(pool, weights=[c["rows"] for _, c in pool], k=n * 3)
        seen_k, chosen = set(), []
        for k, c in pick:
            if k not in seen_k:
                seen_k.add(k)
                chosen.append((k, c))
            if len(chosen) == n:
                break
    else:
        chosen = random.sample(pool, n)
    from concurrent.futures import ThreadPoolExecutor
    from jobalfred_index.polite import Client
    live = I.Homepages(client=Client(), budget=10**9)          # the same fetch the nightly build does for a company it has not seen
    def fetch_one(kc):
        k, c = kc
        if not k.startswith("~"):
            live.ensure("c:" + k, c["name"], I.own_domain("https://" + h + "/" for h in c["hosts"]))
    with ThreadPoolExecutor(12) as ex:
        list(ex.map(fetch_one, chosen))
    live.save()
    hp.data = live.data
    out = []
    for k, c in chosen:
        key = "c:" + k if not k.startswith("~") else k
        entry = hp.get(key) if key.startswith("c:") else None
        dom = I.own_domain("https://" + h + "/" for h in c["hosts"])
        out.append({"key": key, "name": c["name"], "rows": c["rows"], "mode": mode, "domain": dom or (entry or {}).get("d", ""),
                    "home": I.home_text(entry)[:260], "words": [w for w, _ in c["words"].most_common(9)], "hosts": [h for h, _ in c["hosts"].most_common(2)],
                    "titles": c["titles"][:4]})
    json.dump(out, open(root / "work" / "ind" / f"round-{rnd}.json", "w"), ensure_ascii=False)
    print(len(out), "companies drawn")
    show(rnd)


def show(rnd):
    for i, o in enumerate(json.load(open(root / "work" / "ind" / f"round-{rnd}.json"))):
        extra = f" | {o['home'][:200]}" if o["home"] else ""
        print(f"[{i}] {o['name'][:38]} | rows={o['rows']} | {','.join(o['words'][:7])} | {o['domain'] or o['hosts'][0][:28]}{extra}")


if __name__ == "__main__":
    if sys.argv[1] == "draw":
        draw(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    else:
        show(sys.argv[2])
