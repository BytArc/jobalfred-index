"""Draw a fresh random sample of role titles for reader labelling.

Usage: function_sample.py draw ROUND N SEED SHARD_DIR   rows picked at random over all rows, never a title seen in an earlier round
       function_sample.py show ROUND                    titles only, no model output, so the reader labels blind
"""
import glob, gzip, json, random, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
D = root / "data" / "function"
W = root / "work" / "fn"


def seen():
    out = set()
    for f in glob.glob(str(D / "eval-r*.jsonl")):
        out |= {json.loads(l)["title"] for l in open(f)}
    return out


def draw(rnd, n, seed, shard_dir):
    rng = random.Random(seed)
    files = sorted(glob.glob(f"{shard_dir}/*.json.gz"))
    prior = seen()
    picks = []
    for f in files:
        doc = json.loads(gzip.decompress(Path(f).read_bytes()))
        if "rows" not in doc:
            continue
        for r in doc["rows"]:
            if rng.random() < 0.0008:
                picks.append(r[0])
    rng.shuffle(picks)
    out, titles = [], set()
    for t in picks:
        if t in prior or t in titles or len(t) < 3:
            continue
        titles.add(t)
        out.append(t)
        if len(out) == n:
            break
    W.mkdir(parents=True, exist_ok=True)
    (W / f"round-{rnd}.json").write_text(json.dumps(out, ensure_ascii=False))
    print(len(out), "titles drawn")


def show(rnd):
    for i, t in enumerate(json.load(open(W / f"round-{rnd}.json"))):
        print(f"[{i}] {t}")


if __name__ == "__main__":
    a = sys.argv
    draw(a[2], int(a[3]), int(a[4]), a[5]) if a[1] == "draw" else show(a[2])
