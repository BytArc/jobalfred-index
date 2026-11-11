"""The job function of a role (Sales, Engineering, ...) and its sub-role, read from the title.

No AI and no network. The rules are data (data/function/rules.json): an ordered list, each rule a function, an optional
sub-role code and the title phrases that trigger it. The first rule (lowest position) that matches anywhere in the title wins.
They start from the site's role families (site-jobalfred/src/search-worker.js FAMILIES) and were adjusted against titles
read and labelled by hand, each round measured on a fresh sample (scripts/function_sample.py, scripts/function_score.py,
labels in data/function/eval-r*.jsonl). Retraining is a commit to the data files, not a code change.

fn: function code, "oth" when the title names no office function (nurse, cook, driver ...).
ft: sub-role code, unique across functions, or "" when the function is clear but no sub-role is.
"""
from __future__ import annotations

import json
import re
import threading
import unicodedata
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "function"
OTHER = "oth"
NOT_STATED = "0"        # the title matched only a rule that is not reliable enough to publish (see scripts/function_calibrate.py)
_lock = threading.Lock()
_state: dict = {}
_cache: dict[str, tuple[str, str]] = {}


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower()) if not unicodedata.combining(c))


_PAY = re.compile(r"[$£€]\s*[\d.,]+k?(\s*[-to]+\s*[$£€]?[\d.,]+k?)?\s*(/|per)?\s*(hr|hour)?\b|\b\d[\d.,]*\s*/\s*(hr|hour)\b|/\s*hr\b")


def toks(s: str) -> list[str]:
    out = []
    for w in re.split(r"[^a-z0-9]+", _PAY.sub(" ", fold(s)).replace("&", " and ")):
        if not w:
            continue
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


def _load() -> dict:
    with _lock:
        if not _state:
            doc = json.loads((DATA / "rules.json").read_text())
            index: dict[str, list] = {}
            for pos, rule in enumerate(doc["rules"]):
                for ph in rule["any"]:
                    w = toks(ph)
                    if w:
                        index.setdefault(w[0], []).append((pos, w, rule["fn"], rule.get("ft", "")))
            _state.update(doc=doc, index=index)
        return _state


def reset_cache() -> None:
    with _lock:
        _state.clear()
        _cache.clear()


def maps() -> dict:
    """{"fn": {code: label}, "ft": {code: [fn code, label]}} for the manifest-side JSON."""
    doc = _load()["doc"]
    return {"fn": {**doc["functions"], NOT_STATED: "Not stated"}, "ft": doc["subroles"]}


def rule_of(title: str) -> int:
    """Position of the rule that decides this title, -1 when none matches (calibration only)."""
    index = _load()["index"]
    w = toks(title)
    best = -1
    for i, t in enumerate(w):
        for pos, ph, fn, ft in index.get(t, ()):
            if (best < 0 or pos < best) and w[i:i + len(ph)] == ph:
                best = pos
    return best


def label(title: str) -> list[str]:
    """[fn, ft] for one title. fn is "0" when the deciding rule is not reliable enough to publish; ft is "" when the sub-role is not."""
    hit = _cache.get(title)
    if hit is not None:
        return list(hit)
    index = _load()["index"]
    w = toks(title)
    best = None
    for i, t in enumerate(w):
        for pos, ph, fn, ft in index.get(t, ()):
            if best is not None and pos >= best[0]:
                continue
            if w[i:i + len(ph)] == ph:
                best = (pos, fn, ft)
    if best:
        flags = _load()["doc"].get("flags", {}).get(str(best[0]), "")
        res = (best[1], best[2]) if "f" not in flags else (NOT_STATED, "")
        if "t" in flags:
            res = (res[0], "")
    else:
        res = (OTHER, "")
    if len(_cache) < 400000:
        _cache[title] = res
    return list(res)
