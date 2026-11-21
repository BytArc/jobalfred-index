"""Fit the few numbers of the inferred layer on the dev part of the gold set (never the test part) and save them in data/levels/tables.json:
  infer_bias   a multiplier per level on the model's probabilities (the model was trained on rows that state a level, which lean senior)
  hint_boost   how much a weaker title word or field ("Associate", "Manager, X", a Roman numeral) multiplies its level's probability
Usage: levels_fit.py --shards DIR
"""
import itertools
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "scripts"))
from jobalfred_index import levelinfer, levels as LV  # noqa: E402
import levels_eval as E  # noqa: E402

sd = sys.argv[sys.argv.index("--shards") + 1] if "--shards" in sys.argv else None
gold = [json.loads(l) for l in open(E.GOLD) if json.loads(l)["split"] in ("dev", "test")]
pages = {json.loads(l)["url"]: json.loads(l) for l in open(E.W / "pages.jsonl")}
mixes = E.Mixes(Path(sd) if sd else None)
model = levelinfer.load()
tb = json.loads(LV.TABLES.read_text())
lv_given_yx = {int(k): {int(a): b for a, b in v.items()} for k, v in tb["level_given_years"].items()}
prior = {int(k): v for k, v in tb["prior"].items()}

items = []
for cfg in ("nightly", "full"):
    for g in gold:
        pg = pages[g["url"]]
        desc = pg["text"] if (cfg == "full" or g["ats"] in E.DESC_NIGHTLY) else None
        lvl, yrs = E.natives(pg, g["ats"], cfg)
        sl, ss, yx, ys = LV.stated(g["title"], lvl, desc, yrs)
        if ss in LV.STATED:
            continue
        dist = dict(mixes.probs(g, model))
        items.append((dist, sl if ss == "w" else 0, yx if ys == "s" else 0, E.NAME2[g["level"]], g["w"]))


def predict(dist, hint, yx, bias, boost):
    p = {c: dist.get(c, 0.0) * bias.get(c, 1.0) for c in range(2, 8)}
    if yx and yx in lv_given_yx:
        p = {c: v * lv_given_yx[yx].get(c, 0.02) / max(prior.get(c, 0.15), 0.02) for c, v in p.items()}
    if hint:
        p[hint] = p.get(hint, 0.0) * boost + 1e-9 * boost
    return max(p, key=p.get)


TOTAL_W = sum(w for *_, w in items)
GOLD_MIX = {c: sum(w for d, h, y, t, w in items if t == c) / TOTAL_W for c in range(1, 9)}


def acc(bias, boost, report=False):
    """Population-weighted exact accuracy, minus how far the predicted level mix strays from the gold mix (total variation): a
    calibration that wins accuracy by calling most roles one level would flood that level's filter."""
    pm = {c: 0.0 for c in range(1, 9)}
    ok = 0.0
    for d, h, y, t, w in items:
        p = predict(d, h, y, bias, boost)
        pm[p] += w
        ok += w * (p == t)
    tv = 0.5 * sum(abs(pm[c] / TOTAL_W - GOLD_MIX[c]) for c in range(1, 9))
    if report:
        print("  accuracy", round(ok / TOTAL_W, 4), "mix distance", round(tv, 4), "mix", {LV.CODES[c]: round(v / TOTAL_W, 3) for c, v in pm.items() if v})
    return ok / TOTAL_W - tv


hinted = [(d, h, y, t) for d, h, y, t, w in items if h]
print(len(items), "inferred dev rows (both configs),", len(hinted), "with a weak hint")
print("hint alone right:", sum(h == t for d, h, y, t in hinted) / len(hinted))
print("model alone right on hinted rows:", sum(predict(d, 0, y, {}, 1) == t for d, h, y, t in hinted) / len(hinted))
print("gold mix", {LV.CODES[c]: round(v, 3) for c, v in GOLD_MIX.items() if v})
bias = {c: 1.0 for c in range(2, 8)}
boost = 1e6
best = acc(bias, boost)
print("start (hint wins, no bias):", round(best, 4))
acc(bias, boost, report=True)
grid = [0.4, 0.55, 0.7, 0.85, 1.0, 1.2, 1.5, 2.0, 2.5]
for _ in range(3):
    for c in range(2, 8):
        for v in grid:
            b2 = dict(bias)
            b2[c] = v
            a = acc(b2, boost)
            if a > best + 1e-9:
                best, bias = a, b2
    for v in (2, 5, 10, 30, 100, 1e6):
        a = acc(bias, v)
        if a > best + 1e-9:
            best, boost = a, v
print("fitted:", {LV.CODES[c]: v for c, v in bias.items()}, "hint_boost", boost, "objective", round(best, 4))
acc(bias, boost, report=True)
tb["infer_bias"] = {str(c): v for c, v in bias.items()}
tb["hint_boost"] = boost
LV.TABLES.write_text(json.dumps(tb, indent=1, ensure_ascii=False) + "\n")
