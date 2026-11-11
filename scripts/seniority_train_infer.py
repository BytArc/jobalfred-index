"""Train the level-inference model (levelinfer.py) on rows that state a level, and save it as data/seniority/infer-model.json.gz.

Usage: seniority_train_infer.py SHARD_DIR [--epochs 3] [--title-rows 400000] [--seed 7] [--use wbfacmt]
                                [--hand FILE[,FILE]] [--hand-weight 20] [--calibrate FILE] [--out PATH]
The published model (11 Nov 2026): --title-rows 150000 --hand data/seniority/infer-hand-r1.jsonl --calibrate data/seniority/infer-hand-r1.jsonl
Measured on a second, fresh hand-checked sample (infer-hand-r2.jsonl, never trained on): see README.
Plain Python (no scikit-learn): multinomial logistic regression, Adagrad, a little L2, deterministic for a given seed.

Training rows and weights. A level stated by the source's own tag (ls n) or read from the description (ls d) comes from rows whose title
has no level word, like the rows we infer for, so they weigh most. Rows whose title states the level (ls t) are many and teach the
vocabulary; their level words are removed and they carry the feature x:t, which the model sees only in training, so the way titles
that name a level lean to the extremes ("Senior", "Junior") does not shift the inferred levels. Only their junior, mid and senior rows
are used, and without the country and careers-system features: where titles name a level is a local habit, not a level. The company mix leaves the row's own
level out. 10% of the n and d rows are held out and the accuracy on them is printed (a hand-checked sample is the real measure).

The rows we infer for are not like the rows that state a level: most are frontline and everyday roles (cashier, nurse, technician)
whose postings never name one. So hand-labelled rows of exactly that kind (--hand, read from each posting's description) carry a
large weight, and the class priors are set so the predicted mix on them matches their hand-checked mix (--calibrate).
"""
import collections, gzip, json, math, random, sys, time
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import levelinfer as L
from jobalfred_index.industry import group_key

src = Path(sys.argv[1])
def opt(name, default, cast=int):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default
EPOCHS, TITLE_ROWS, SEED = opt("--epochs", 3), opt("--title-rows", 400000), opt("--seed", 7)
USE = opt("--use", "wbfacmt", str)             # feature groups, see levelinfer.features
HAND = [a for a in opt("--hand", "", str).split(",") if a]      # hand-labelled rows (jsonl with title, company, url, ats, cc, truth)
HAND_WEIGHT = opt("--hand-weight", 20.0, float)
CALIBRATE = opt("--calibrate", "", str)        # hand-labelled rows whose level mix the class priors are set to
OUT = Path(opt("--out", str(L.FILE), str))
WEIGHT = {"d": 2.0, "n": 1.0, "t": 0.5}
CLASSES = list(range(1, 8))

man = json.loads((src / "manifest.json").read_text())
rows = []
for s in man["shards"]:
    d = json.loads(gzip.decompress((src / s["file"]).read_bytes()))
    at = {k: i for i, k in enumerate(d["f"])}
    for r in d["rows"]:
        if r[at["lv"]] and r[at["ls"]] in ("n", "t", "d"):
            rows.append((r[at["t"]], r[at["fn"]], r[at["ft"]], r[at["a"]], r[at["cc"]], group_key(r[at["c"]], r[at["u"]]),
                         r[at["lv"]], r[at["ls"]]))
counts = collections.defaultdict(lambda: collections.Counter())
tcounts = collections.defaultdict(lambda: collections.Counter())
hcounts = collections.defaultdict(lambda: collections.Counter())
keys = {}
for t, fn, ft, a, cc, k, lv, ls in rows:
    counts[k][lv] += 1
    if t not in keys:
        keys[t] = L.title_keys(t)
    tk, hk = keys[t]
    tcounts[tk][lv] += 1
    hcounts[hk][lv] += 1
rnd = random.Random(SEED)
# a title that names intern, lead, manager or director names it nearly always, so a title with no level word is rarely one of those:
# from titles that state a level only junior, mid and senior teach the model
title_rows = [r for r in rows if r[7] == "t" and r[6] in (2, 3, 4)]
rnd.shuffle(title_rows)
nd = [r for r in rows if r[7] in ("n", "d")]
rnd.shuffle(nd)
hold = nd[: len(nd) // 10]
train = nd[len(nd) // 10:] + title_rows[:TITLE_ROWS]
print(f"{len(rows)} rows state a level; training on {len(train)} ({len(nd) - len(hold)} n/d, {min(TITLE_ROWS, len(title_rows))} t), holding out {len(hold)}")


def feats(r, train_row=True):
    t, fn, ft, a, cc, k, lv, ls = r
    tk, hk = keys[t]
    m = lv if ls in ("n", "t", "d") else 0          # a stated row's own level is left out of the mixes it is counted in
    f = L.features(t, fn, ft, a, cc, L.company_mix(counts[k], minus=m), L.company_mix(tcounts[tk], minus=m),
                   L.company_mix(hcounts[hk], minus=m), use=USE)
    if train_row and ls == "t":
        f["x:t"] = 1.0
        for k in [k for k in f if k.startswith(("cc:", "a:"))]:
            del f[k]                 # where titles name a level is a habit of the country and the careers system, not a level
    return f


def hand_rows(path):
    from jobalfred_index import function
    out = []
    for line in open(path):
        h = json.loads(line)
        fn, ft = h.get("fn") or "", h.get("ft") or ""
        if not fn:
            fn, ft = function.label(h["title"])
        out.append((h["title"], fn, ft, h.get("ats", ""), h.get("cc", ""), group_key(h.get("company", ""), h.get("url", "")), int(h["truth"]), "h"))
    return out


for path in HAND:
    for r in hand_rows(path):
        if r[0] not in keys:
            keys[r[0]] = L.title_keys(r[0])
        train.append(r)
WEIGHT["h"] = HAND_WEIGHT
X = [(feats(r), CLASSES.index(r[6]), WEIGHT[r[7]]) for r in train]
df = collections.Counter(k for f, _, _ in X for k in f)
keep = {k for k, n in df.items() if n >= 3}
X = [({k: v for k, v in f.items() if k in keep}, y, w) for f, y, w in X]
C = len(CLASSES)
W = {k: [0.0] * C for k in keep}
G = {k: [1e-6] * C for k in keep}
b, gb = [0.0] * C, [1e-6] * C
LR, L2 = 0.3, 1e-6
t0 = time.time()
for ep in range(EPOCHS):
    rnd.shuffle(X)
    loss = 0.0
    for f, y, w in X:
        z = list(b)
        for k, v in f.items():
            row = W[k]
            for i in range(C):
                z[i] += v * row[i]
        mx = max(z)
        e = [math.exp(a - mx) for a in z]
        s = sum(e)
        p = [x / s for x in e]
        loss -= w * math.log(max(p[y], 1e-12))
        g = [w * (p[i] - (1.0 if i == y else 0.0)) for i in range(C)]
        for i in range(C):
            gb[i] += g[i] * g[i]
            b[i] -= LR * g[i] / math.sqrt(gb[i])
        for k, v in f.items():
            row, acc = W[k], G[k]
            for i in range(C):
                gi = g[i] * v + L2 * row[i]
                acc[i] += gi * gi
                row[i] -= LR * gi / math.sqrt(acc[i])
    print(f"epoch {ep + 1}: loss {loss / len(X):.4f}, {int(time.time() - t0)}s")

model = {"classes": CLASSES, "use": USE, "b": [round(x, 5) for x in b],
         "w": {k: [round(x, 4) for x in v] for k, v in W.items() if max(abs(x) for x in v) >= 0.01},
         "trained": time.strftime("%Y-%m-%d"), "basis": f"{len(train)} rows that state a level, from the published shards built {man.get('built', '')}",
         "seed": SEED, "epochs": EPOCHS}
if CALIBRATE:
    # the rows we infer for are mostly frontline and everyday roles that rarely state a level, unlike the rows that do: set the class
    # priors so the predicted mix on a hand-labelled sample of them matches its hand-checked mix (a few multiplicative steps)
    cal = hand_rows(CALIBRATE)
    for r in cal:
        keys.setdefault(r[0], L.title_keys(r[0]))
    want = collections.Counter(r[6] for r in cal)
    for _ in range(25):
        got = collections.Counter(L.predict(feats(r, train_row=False), model)[0] for r in cal)
        for i, c in enumerate(CLASSES):
            model["b"][i] = round(model["b"][i] + 0.5 * math.log((want.get(c, 0) + 0.5) / (got.get(c, 0) + 0.5)), 5)
    got = collections.Counter(L.predict(feats(r, train_row=False), model)[0] for r in cal)
    print("calibrated on", CALIBRATE, "want", dict(sorted(want.items())), "got", dict(sorted(got.items())),
          f"exact on it {sum(L.predict(feats(r, train_row=False), model)[0] == r[6] for r in cal) / len(cal):.1%}")
    model["calibrated_on"] = Path(CALIBRATE).name
right = sum(L.predict(feats(r, train_row=False), model)[0] == r[6] for r in hold)
near = sum(abs(L.predict(feats(r, train_row=False), model)[0] - r[6]) <= 1 for r in hold)      # as inferred: never intern
print(f"held-out n/d rows: {right}/{len(hold)} = {right / max(1, len(hold)):.1%} exact, {near / max(1, len(hold)):.1%} within one level")
OUT.parent.mkdir(parents=True, exist_ok=True)
with gzip.open(OUT, "wt", encoding="utf-8") as fh:
    json.dump(model, fh, separators=(",", ":"))
print("saved", OUT, len(model["w"]), "features")
