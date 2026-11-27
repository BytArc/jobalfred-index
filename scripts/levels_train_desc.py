"""Train descmodel (level and years from the title and the description) and score the cascade on the gold sample.

    work/train-venv/bin/python scripts/levels_train_desc.py work/levels/corpus/corpus.jsonl.gz [--C 0.3] [--out data/levels/desc-model.json.gz]

Training rows come from scripts/levels_corpus.py (local only; descriptions are never committed). Distant supervision:
- level: postings whose careers-system field (n), title (t) or description (d) states the level; the title's level words and the
  title itself are taken out of the features (descmodel.features), so the model learns the other signs. n and d rows weigh 3,
  because their titles name no level, like the rows the model is for.
- years: postings whose description states the years; every years statement is taken out of the text.
Each posting with a description is also used once without it (weight 0.5), so the same model serves postings read title-only.

Scoring (scripts/levels_eval.py's cascade and gold set): the stated rules first, unchanged; then, for the level, the title model
(levelinfer) combined with the description model, P ~ P_title^(1-a) x P_desc^a; for the years, the description model combined
with the level, P ~ P_desc(years) x P(level | years)^b, where today the years come from the level alone. a and b are chosen on
the dev and test splits and the frozen sample test2 is reported once, as the 21 Nov study did.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.linear_model import LogisticRegression

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "scripts"))
from jobalfred_index import descmodel as D, function, levelinfer, levels as LV  # noqa: E402
import levels_eval as E  # noqa: E402

LEVELS = list(range(1, 9))
YEARS = list(range(1, 7))


def matrix(rows, label, weight, title_only=True):
    indptr, indices, y, w = [0], [], [], []
    for r in rows:
        variants = [(r["desc"] or None, 1.0)]
        if r["desc"] and title_only:
            variants.append((None, 0.5))
        for desc, k in variants:
            ids = D.features(r["title"], desc, r.get("fn") or "", r["ats"])
            indices.extend(ids)
            indptr.append(len(indices))
            y.append(label(r))
            w.append(weight(r) * k)
    X = csr_matrix((np.ones(len(indices), dtype=np.float32), np.array(indices, dtype=np.int32), np.array(indptr, dtype=np.int64)),
                   shape=(len(y), 1 << D.BITS))
    return X, np.array(y), np.array(w)


def fit(X, y, w, C, classes):
    clf = LogisticRegression(C=C, max_iter=300, tol=1e-4)
    clf.fit(X, y, sample_weight=w)
    order = [list(clf.classes_).index(c) if c in clf.classes_ else None for c in classes]
    used = np.asarray(X.getnnz(axis=0)).ravel() > 0
    coef = clf.coef_
    keep = np.where(used & (np.abs(coef).max(axis=0) >= 0.004))[0]
    wmap = {}
    for j in keep:
        wmap[int(j)] = [round(float(coef[o, j]), 4) if o is not None else -9.0 for o in order]
    b = [round(float(clf.intercept_[o]), 4) if o is not None else -9.0 for o in order]
    return {"classes": classes, "w": wmap, "b": b}


def combine(p_t, p_d, a, known=None):
    """P ~ P_title^(1-a) x P_desc^a. A level the description model never saw in training (no rows) keeps the title model's own
    probability, so the description model can neither push it up nor wipe it out."""
    d = dict(p_d)
    if known is not None:
        mass_t = sum(p for c, p in p_t if c in known) or 1e-9
        mass_d = sum(d.get(c, 0.0) for c in known) or 1e-9
        d = {c: (d.get(c, 0.0) / mass_d * mass_t if c in known else p) for c, p in p_t}
    s = {c: math.exp((1 - a) * math.log(max(p, 1e-9)) + a * math.log(max(d.get(c, 1e-9), 1e-9))) for c, p in p_t}
    z = sum(s.values()) or 1.0
    return [(c, v / z) for c, v in s.items()]


def run_cascade(g, pg, cfg, mixes, tmodel, dmodel, yx_table, lv_given_yx, a, b, title_years):
    desc = pg.get("text") if (cfg == "full" or g["ats"] in E.DESC_NIGHTLY) else None
    lvl, yrs = E.natives(pg, g["ats"], cfg)
    sl, ss, yx, ys = LV.stated(g["title"], lvl, desc, yrs)
    if ss == "w" and sl:
        ss = "i"
    fn = (mixes.row.get(g["url"]) or {}).get("fn") or function.label(g["title"])[0]
    pred = D.predict(g["title"], desc, fn, g["ats"], dmodel) if dmodel and (desc or title_years or a) else {}
    if not sl:
        dist = mixes.probs(g, tmodel)
        if pred and a and desc:
            known = {c for c, bb in zip(dmodel["level"]["classes"], dmodel["level"]["b"]) if bb > -8.9}
            dist = combine(dist, pred["level"], a, known)
        sl, _ = LV.infer_level(dist, yx if ys == "s" else 0, lv_given_yx)
        ss = "i"
    if not yx:
        if pred and (desc or title_years):
            best, top = 0, -1e9
            for y, p in pred["years"]:
                prior = (lv_given_yx.get(y) or {}).get(sl, 1e-3)
                sc = math.log(max(p, 1e-9)) + b * math.log(max(prior, 1e-9))
                if sc > top:
                    best, top = y, sc
            yx, ys = best, "m"
        else:
            yx, ys = yx_table.get(sl, 0), "i"
    return sl, ss, yx, ys


def score(gold, pages, cfg, mixes, tmodel, dmodel, tables, a, b, title_years=False):
    yx_table = {int(k): v for k, v in tables["years_given_level"].items()}
    lv_given_yx = {int(k): {int(x): y for x, y in v.items()} for k, v in tables["level_given_years"].items()}
    inf_n = inf_ok = inf_near = all_ok = 0
    yi_n = yi_ok = yi_near = 0
    for g in gold:
        pg = pages.get(g["url"]) or {"text": "", "native": {}}
        sl, ss, yx, ys = run_cascade(g, pg, cfg, mixes, tmodel, dmodel, yx_table, lv_given_yx, a, b, title_years)
        gl = E.NAME2[g["level"]]
        gy = LV.interval(g["years"]) if g["years"] is not None else 0
        all_ok += sl == gl
        if ss not in LV.STATED:
            inf_n += 1
            inf_ok += sl == gl
            inf_near += abs(sl - gl) <= 1
        if ys != "s" and gy:
            yi_n += 1
            yi_ok += yx == gy
            yi_near += abs(yx - gy) <= 1
    p = lambda k, n: round(100 * k / n, 1) if n else None  # noqa: E731
    return {"n": len(gold), "level_all": p(all_ok, len(gold)), "level_inferred": p(inf_ok, inf_n), "level_inferred_near": p(inf_near, inf_n),
            "inferred_rows": inf_n, "years_inferred": p(yi_ok, yi_n), "years_inferred_near": p(yi_near, yi_n), "years_rows": yi_n}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--C", type=float, default=0.3)
    ap.add_argument("--out", type=Path, default=root / "work" / "levels" / "desc-model.json.gz")
    ap.add_argument("--max-level", type=int, default=45000)
    ap.add_argument("--max-years", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=27)
    ap.add_argument("--score-only", action="store_true")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    if not a.score_only:
        rows = [json.loads(l) for l in gzip.open(a.corpus, "rt", encoding="utf-8")]
        seen, uniq = set(), []
        for r in rows:                                   # one copy of a posting, however many boards list it
            k = (r["title"], r["company"], (r["desc"] or "")[:200])
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        print(f"corpus {len(rows)} rows, {len(uniq)} distinct", flush=True)
        lvl_rows = [r for r in uniq if r["ss"] in LV.STATED and r["sl"]]
        yrs_rows = [r for r in uniq if r["ys"] == "s" and r["yx"]]
        rnd.shuffle(lvl_rows)
        rnd.shuffle(yrs_rows)
        lvl_rows, yrs_rows = lvl_rows[:a.max_level], yrs_rows[:a.max_years]
        print("level rows", len(lvl_rows), collections.Counter(r["sl"] for r in lvl_rows), collections.Counter(r["ss"] for r in lvl_rows), flush=True)
        print("years rows", len(yrs_rows), collections.Counter(r["yx"] for r in yrs_rows), flush=True)
        t0 = time.time()
        X, y, w = matrix(lvl_rows, lambda r: r["sl"], lambda r: 3.0 if r["ss"] in ("n", "d") else 1.0)
        level = fit(X, y, w, a.C, LEVELS)
        del X
        X, y, w = matrix(yrs_rows, lambda r: r["yx"], lambda r: 1.0, title_only=False)
        years = fit(X, y, w, a.C, YEARS)
        del X
        model = {"level": level, "years": years,
                 "meta": {"trained": time.strftime("%Y-%m-%d"), "bits": D.BITS, "C": a.C, "level_rows": len(lvl_rows),
                          "years_rows": len(yrs_rows), "level_features": len(level["w"]), "years_features": len(years["w"])}}
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(a.out, "wt", encoding="utf-8") as fh:
            json.dump({**model, "level": {**level, "w": {str(k): v for k, v in level["w"].items()}},
                       "years": {**years, "w": {str(k): v for k, v in years["w"].items()}}}, fh, separators=(",", ":"))
        print(f"trained in {time.time() - t0:.0f} s -> {a.out} ({a.out.stat().st_size // 1024} KB), {model['meta']}", flush=True)
    dmodel = D.load(a.out)
    gold = [json.loads(l) for l in open(E.GOLD)]
    pages = E.load_pages()
    mixes = E.Mixes(None)
    if (E.W / "mixes.pkl").exists():
        import pickle
        mixes.counts, mixes.tcounts, mixes.hcounts, mixes.row = pickle.load(open(E.W / "mixes.pkl", "rb"))
    tmodel = levelinfer.load()
    tables = json.loads((root / "data" / "levels" / "tables.json").read_text())
    tune = [g for g in gold if g["split"] in ("dev", "test")]
    frozen = [g for g in gold if g["split"] == "test2"]
    base = {cfg: score(tune, pages, cfg, mixes, tmodel, None, tables, 0, 0) for cfg in ("nightly", "full")}
    print("baseline dev+test", json.dumps(base), flush=True)
    best = None
    for aa in (0.0, 0.3, 0.5, 0.7):
        for bb in (0.0, 0.5, 1.0):
            r = score(tune, pages, "nightly", mixes, tmodel, dmodel, tables, aa, bb)
            key = (r["level_inferred"] or 0) + (r["years_inferred"] or 0)
            print(f"a={aa} b={bb} nightly dev+test {json.dumps(r)}", flush=True)
            if best is None or key > best[0]:
                best = (key, aa, bb)
    _, aa, bb = best
    print(f"chosen a={aa} b={bb}", flush=True)
    for cfg in ("nightly", "full"):
        old = score(frozen, pages, cfg, mixes, tmodel, None, tables, 0, 0)
        new = score(frozen, pages, cfg, mixes, tmodel, dmodel, tables, aa, bb)
        ty = score(frozen, pages, cfg, mixes, tmodel, dmodel, tables, aa, bb, title_years=True)
        print(f"test2 {cfg}: before {json.dumps(old)}", flush=True)
        print(f"test2 {cfg}: after  {json.dumps(new)}", flush=True)
        print(f"test2 {cfg}: after, years model on title-only rows too {json.dumps(ty)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
