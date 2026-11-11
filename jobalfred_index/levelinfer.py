"""A level for every role whose level nothing states (lv 0): inferred, marked ls "i".

A multinomial logistic regression over the title's own words (with every level word taken out, so "Senior Accountant" and
"Accountant" look the same), its word pairs, the job function and sub-role (fn, ft), the careers system, the country, and the
company's mix of stated levels in the same build. Trained offline by scripts/seniority_train_infer.py on the rows that do state a
level; the weights are versioned data (data/seniority/infer-model.json.gz). Inference is plain Python: no scikit-learn, no network,
no AI. Rows whose level is stated keep it; the inferred level is the most likely one, never left at 0.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import threading
from pathlib import Path

from . import seniority

FILE = Path(__file__).resolve().parent.parent / "data" / "seniority" / "infer-model.json.gz"
LV, LS, FN, FT = 11, 12, 14, 15           # field positions (checked against shards.FIELDS in the tests)
_lock = threading.Lock()
_model: dict = {}

# every word the title rules read as a level, removed before the words become features
_LEVEL_RX = [seniority.INTERN_RX, seniority.DIRECTOR_RX, seniority.HEAD_ROLE_RX, seniority.MANAGER_RX, seniority.LEAD_RX,
             seniority.SENIOR_RX, seniority.MID_RX, seniority.JUNIOR_RX, seniority.ROMAN_END, seniority.LEVEL_NUM_END]
_WORD = re.compile(r"[a-z][a-z0-9+#]*")
STOP = {"and", "or", "of", "the", "for", "in", "at", "to", "with", "de", "da", "do", "das", "dos", "del", "la", "le", "les", "el", "en",
        "et", "e", "y", "und", "der", "die", "das", "und", "m", "f", "d", "w", "x", "h", "all", "genders", "gender", "mwd", "fmd", "mfd",
        "ii", "iii", "iv", "vi"}


def stripped_words(title: str) -> list[str]:
    t = seniority.fold(title or "")
    for rx in _LEVEL_RX:
        t = rx.sub(" ", t)
    return [w for w in _WORD.findall(t) if w not in STOP and len(w) > 1][:12]


def title_keys(title: str) -> tuple[str, str]:
    """The title with its level words taken out, and its last word (the role noun): the keys the title mixes are counted under."""
    ws = stripped_words(title)
    return " ".join(ws), (ws[-1] if ws else "")


def features(title: str, fn: str = "", ft: str = "", ats: str = "", cc: str = "", mix: dict | None = None,
             tmix: dict | None = None, hmix: dict | None = None, use: str = "wbfacm") -> dict[str, float]:
    """use: w words, b word pairs, f function, a careers system, c country, m company mix (letters; the trained model says which)."""
    ws = stripped_words(title)
    f = {}
    if "w" in use:
        f.update({"w:" + w: 1.0 for w in ws})
        if not ws:
            f["w:<none>"] = 1.0
    if "b" in use:
        for a, b in zip(ws, ws[1:]):
            f["b:" + a + "_" + b] = 1.0
    if "f" in use:
        if fn:
            f["fn:" + fn] = 1.0
        if ft:
            f["ft:" + ft] = 1.0
    if "a" in use and ats:
        f["a:" + ats] = 1.0
    if "c" in use and cc:
        f["cc:" + cc] = 1.0
    if "m" in use:
        if mix:
            for k, v in mix.items():
                f["m:" + str(k)] = v
        else:
            f["m:none"] = 1.0
    # how often the same role, when a title does name its level, names each level: the level a title leaves unsaid is usually the one
    # it would not need to name ("Cashier" is rarely "Junior Cashier" but often "Head Cashier")
    if "t" in use:
        for name, mx in (("tm", tmix), ("hm", hmix)):
            if mx:
                for k, v in mx.items():
                    f[f"{name}:{k}"] = v
            else:
                f[name + ":none"] = 1.0
    return f


def company_mix(counts: dict[int, int], minus: int = 0) -> dict[int, float] | None:
    """Share of each stated level at the company (leaving one level out, for training rows); None below 3 stated roles."""
    c = dict(counts)
    if minus:
        c[minus] = c.get(minus, 0) - 1
    n = sum(v for v in c.values() if v > 0)
    if n < 3:
        return None
    return {k: v / n for k, v in c.items() if v > 0}


def load(path: Path | None = None) -> dict:
    with _lock:
        if path is not None or not _model:
            p = Path(path) if path else FILE
            if not p.exists():
                return {}
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                m = json.load(fh)
            if path is not None:
                return m
            _model.update(m)
        return _model


def reset() -> None:
    with _lock:
        _model.clear()


def predict(feats: dict[str, float], model: dict | None = None) -> tuple[int, float]:
    """(level 1-7, probability)."""
    m = model or load()
    if not m:
        return seniority.MID, 0.0
    z = list(m["b"])
    W = m["w"]
    for k, v in feats.items():
        row = W.get(k)
        if row:
            for i, wv in enumerate(row):
                z[i] += v * wv
    mx = max(z)
    e = [math.exp(a - mx) for a in z]
    s = sum(e)
    i = max(range(len(e)), key=e.__getitem__)
    return m["classes"][i], e[i] / s


def assign(rows: list[list], log=print, model: dict | None = None) -> dict:
    """Give every row with lv 0 the most likely level, ls "i". One prediction per distinct (title, fn, ft, ats, cc, company)."""
    from .industry import group_key
    m = model or load()
    use = m.get("use", "wbfacm") if m else ""
    counts: dict[str, dict[int, int]] = {}
    tcounts: dict[str, dict[int, int]] = {}
    hcounts: dict[str, dict[int, int]] = {}
    keys = []
    tkeys: dict[str, tuple[str, str]] = {}
    for r in rows:
        k = group_key(r[1], r[5])
        keys.append(k)
        if r[LV] and r[LS] in ("n", "t", "d"):
            for table, key in ((counts, k),) + (((tcounts, title_keys(r[0])[0]), (hcounts, title_keys(r[0])[1])) if "t" in use else ()):
                c = table.setdefault(key, {})
                c[r[LV]] = c.get(r[LV], 0) + 1
    cache: dict[tuple, int] = {}
    done = {i: 0 for i in range(1, 8)}
    for r, k in zip(rows, keys):
        if r[LV] and r[LS] != "i":
            continue
        ck = (r[0], r[FN], r[FT], r[7], r[3], k)
        if ck not in cache:
            tk, hk = tkeys.setdefault(r[0], title_keys(r[0])) if "t" in use else ("", "")
            cache[ck] = predict(features(r[0], r[FN], r[FT], r[7], r[3], company_mix(counts.get(k, {})),
                                         company_mix(tcounts.get(tk, {})), company_mix(hcounts.get(hk, {})), use=use or "wbfacm"), m)[0]
        r[LV], r[LS] = cache[ck], "i"
        done[r[LV]] += 1
    stats = {"inferred": sum(done.values()), "by_level": {seniority.NAMES[i]: n for i, n in done.items()}, "model": bool(m)}
    log(f"seniority inferred: {stats}")
    return stats
