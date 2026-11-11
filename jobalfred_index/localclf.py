"""The free local industry model: TF-IDF of a company's name, domain, homepage text and job titles, into a linear (logistic
regression) classifier. Trained offline by scripts/industry_train_local.py on hand labels and on the labels a language model gave once
(data/industry/ai-labels.json.gz); the weights are versioned data (data/industry/local-model.json.gz). Inference here is plain Python:
no scikit-learn, no network, no key, so the nightly run needs nothing.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import threading
from pathlib import Path

from . import industry

FILE = industry.DATA / "local-model.json.gz"
_lock = threading.Lock()
_model: dict = {}
MIN_CONFIDENCE = 0.70           # local model: below this the industry is Not stated (first measured on 240 unseen hand-labelled companies; re-set after the bulk retrain)


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


def featurize(name: str, domain: str, home_title: str, home_meta: str, title_words: dict, ats: dict | None = None, cc: dict | None = None) -> dict[str, float]:
    """Raw term counts per feature; the model applies sublinear tf and idf."""
    f: dict[str, float] = {}

    def add(k, v=1.0):
        f[k] = f.get(k, 0.0) + v
    for w in industry.words(name):
        add("n:" + w)
    flat = re.sub(r"[^a-z0-9]", "", industry.fold(name))
    for i in range(0, max(0, len(flat) - 3)):
        add("c:" + flat[i:i + 4], 0.5)
    if domain:
        for w in re.split(r"[.\-]", industry.fold(domain)):
            if len(w) >= 3:
                add("d:" + w)
        add("tld:" + domain.rsplit(".", 1)[-1])
    for w in industry.words(home_title or ""):
        add("h:" + w, 2.0)
    for w in industry.words(home_meta or ""):
        add("h:" + w)
    for w, n in (title_words or {}).items():
        add("t:" + w, float(n))
    tot = sum(ats.values()) if ats else 0
    for k, v in (ats or {}).items():
        if k and tot:
            add("a:" + k, v / tot)
    tot = sum(cc.values()) if cc else 0
    for k, v in (cc or {}).items():
        if k and tot:
            add("cc:" + k, v / tot)
    return f


def predict_proba(feats: dict[str, float], model: dict | None = None) -> dict[str, float]:
    m = model or load()
    if not m:
        return {}
    vocab, idf, W = m["idf"], m["idf"], m["w"]
    x = {}
    for k, tf in feats.items():
        if k in idf and tf > 0:
            x[k] = (1.0 + math.log(tf)) * idf[k]
    norm = math.sqrt(sum(v * v for v in x.values())) or 1.0
    classes = m["classes"]
    z = list(m["b"])
    for k, v in x.items():
        row = W.get(k)
        if row:
            v /= norm
            for ci, wv in row:
                z[ci] += v * wv
    mx = max(z)
    e = [math.exp(a - mx) for a in z]
    s = sum(e)
    return {c: e[i] / s for i, c in enumerate(classes)}


def classify(name: str, domain: str, home_title: str, home_meta: str, title_words: dict, ats=None, cc=None, model: dict | None = None) -> tuple[str, float]:
    """(industry code, probability); Not stated when there is no model or nothing to go on."""
    p = predict_proba(featurize(name, domain, home_title, home_meta, title_words, ats, cc), model)
    if not p:
        return industry.NOT_STATED, 0.0
    best = max(p, key=p.get)
    return best, p[best]
