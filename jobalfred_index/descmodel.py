"""Level and years from a posting's own words, for postings whose level or years nothing states.

Two multinomial logistic regressions over hashed features: the title's words and word pairs with every level word taken out
(levelinfer.stripped_words), the title's character 3-5 grams, the description's words and word pairs with the years statements
and the title itself taken out, the job function and the careers system. One gives the level (8 classes, levels.NAMES), the
other the years asked for (6 intervals, levels.YEARS). Trained offline by scripts/levels_train_desc.py on postings that do state
their level or years (distant supervision: the stating words are masked, so the model learns the other signs); the weights are
versioned data (data/levels/desc-model.json.gz). Inference is plain Python: no scikit-learn, no network, no AI service.

What it gives is a guess and is published as one: ss "m" (level) and ys "m" (years), never a stated code. levels.assign combines
the level guess with the title model's and keeps the years guess unless it is unsure.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import threading
import zlib
from pathlib import Path

from . import levelinfer, levels

FILE = Path(__file__).resolve().parent.parent / "data" / "levels" / "desc-model.json.gz"
BITS = 20
MASK = (1 << BITS) - 1
MAX_DESC_CHARS = 6000
MAX_DESC_TOKENS = 400
_TOK = re.compile(r"[a-z][a-z0-9+#]{1,24}")
_YEARS_ANY = levels._YEARS                       # every "N years", "N anos", "N Jahre"... the years rules read
STOP = levelinfer.STOP | {"you", "your", "our", "we", "will", "with", "are", "is", "be", "to", "a", "an", "as", "on", "by", "this",
                          "that", "it", "from", "que", "para", "com", "por", "con", "los", "las", "une", "des", "pour", "sur", "est",
                          "sie", "wir", "mit", "ihre", "fur", "von", "zu", "il", "lo", "per", "di", "che", "nel", "della"}
_lock = threading.Lock()
_model: dict = {}


def h(s: str) -> int:
    return zlib.crc32(s.encode("utf-8")) & MASK


def _desc_tokens(title: str, desc: str) -> list[str]:
    t = levels.fold_text(desc[:MAX_DESC_CHARS])
    t = _YEARS_ANY.sub(" ", t)                           # the years statements: the years model must learn the other signs
    ft = levels.fold_text(title or "").strip()
    if len(ft) >= 6:
        t = t.replace(ft, " ")                           # the title repeated in the text: its level words would leak in
    return [w for w in _TOK.findall(t) if w not in STOP][:MAX_DESC_TOKENS]


def features(title: str, desc: str | None, fn: str = "", ats: str = "") -> list[int]:
    """Hashed feature ids (unique). The same function trains and infers."""
    f = {"bias"}
    ws = levelinfer.stripped_words(title)
    for w in ws:
        f.add("t:" + w)
    for a, b in zip(ws, ws[1:]):
        f.add("tb:" + a + "_" + b)
    joined = " " + " ".join(ws) + " "
    for n in (3, 4, 5):
        for i in range(len(joined) - n + 1):
            g = joined[i:i + n]
            if g.strip():
                f.add("tc:" + g)
    if desc:
        toks = _desc_tokens(title, desc)
        for w in toks:
            f.add("d:" + w)
        for a, b in zip(toks, toks[1:]):
            f.add("db:" + a + "_" + b)
        f.add("has:desc")
    else:
        f.add("has:nodesc")
    if fn:
        f.add("f:" + fn)
    if ats:
        f.add("a:" + ats)
    return sorted({h(x) for x in f})


def load(path: Path | None = None) -> dict:
    """{"level": {"classes": [...], "w": {id: [weights]}, "prior": [...]}, "years": {...}, "meta": {...}}; {} when absent."""
    with _lock:
        if path is not None or not _model:
            p = Path(path) if path else FILE
            if not p.exists():
                return {}
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                m = json.load(fh)
            for part in ("level", "years"):
                if part in m:
                    m[part]["w"] = {int(k): v for k, v in m[part]["w"].items()}
            if path is not None:
                return m
            _model.update(m)
        return _model


def _dist(ids: list[int], part: dict) -> list[tuple[int, float]]:
    classes, w = part["classes"], part["w"]
    z = list(part.get("b") or [0.0] * len(classes))
    for i in ids:
        row = w.get(i)
        if row is not None:
            for k, v in enumerate(row):
                z[k] += v
    top = max(z)
    e = [math.exp(v - top) for v in z]
    s = sum(e)
    return [(c, e[k] / s) for k, c in enumerate(classes)]


def predict(title: str, desc: str | None, fn: str = "", ats: str = "", model: dict | None = None) -> dict:
    """{"level": [(level, p), ...], "years": [(interval, p), ...]} or {} without a model."""
    m = model if model is not None else load()
    if not m:
        return {}
    ids = features(title, desc, fn, ats)
    out = {}
    for part in ("level", "years"):
        if part in m:
            out[part] = _dist(ids, m[part])
    return out
