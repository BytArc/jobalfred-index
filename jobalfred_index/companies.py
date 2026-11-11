"""Which well-known lists a company belongs to (field co), and the language inference that uses the company's head-office country.

Lists are versioned data: data/companies/curated.json (big tech, AI labs, Big 4, consultancies, edited by hand) and
data/companies/indices.json (stock-index constituents from Wikipedia with source and date, scripts/companies_refresh.py, refreshed monthly).
A row's company matches a member by normalised name, an alias, or the registrable domain of its own postings.

co: codes joined by commas ("sp500,bigtech"); "" when the company is on no list.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from . import industry, language
from .industry import norm

DATA = Path(__file__).resolve().parent.parent / "data" / "companies"
_lock = threading.Lock()
_idx: dict = {}


def lists() -> dict:
    out: dict[str, dict] = {}
    for fn in ("curated.json", "indices.json"):
        p = DATA / fn
        if p.exists():
            out.update(json.loads(p.read_text()).get("lists", {}))
    return out


def index() -> dict:
    """{'names': norm name -> [codes], 'hq': norm name -> country, 'domains': registrable domain -> [codes]}"""
    with _lock:
        if not _idx:
            names: dict[str, list] = {}
            hq: dict[str, str] = {}
            domains: dict[str, list] = {}
            for code, lst in lists().items():
                for m in lst["members"]:
                    for n in [m["name"]] + list(m.get("aliases") or []):
                        k = norm(n)
                        if len(k) >= 3:
                            if code not in names.setdefault(k, []):
                                names[k].append(code)
                            hq.setdefault(k, m.get("hq") or lst.get("hq") or "")
                    if m.get("domain"):
                        d = domains.setdefault(m["domain"].lower(), [])
                        if code not in d:
                            d.append(code)
            dp = DATA / "domains.json"          # domains the probe found for members (scripts/companies_probe.py)
            if dp.exists():
                for code, ms in json.loads(dp.read_text()).items():
                    for dom in ms.values():
                        d = domains.setdefault(dom.lower(), [])
                        if code not in d:
                            d.append(code)
            _idx.update(names=names, hq=hq, domains=domains)
        return _idx


def reset() -> None:
    with _lock:
        _idx.clear()


def membership(name: str, urls: list[str] | tuple = ()) -> tuple[list[str], str]:
    ix = index()
    k = norm(name)
    codes = list(ix["names"].get(k, []))
    hq = ix["hq"].get(k, "")
    if not codes:
        d = industry.own_domain(urls)
        if d and d in ix["domains"]:
            codes = list(ix["domains"][d])
    return codes, hq


CO, LR, LQ = 16, 17, 18        # positions after t c l cc r u p a smin smax cur lv ls in fn ft


def assign(rows: list[list], log=print) -> dict:
    """Fill co for every row, and lr/lq (inferred) where the description stated nothing. One lookup per company."""
    cache: dict[str, tuple[list[str], str]] = {}
    stated = inferred = unknown = listed = 0
    for r in rows:
        if len(r) <= LQ:
            r.extend([""] * (LQ + 1 - len(r)))
        k = r[1]
        if k not in cache:
            cache[k] = membership(k, [r[5]])
        codes, hq = cache[k]
        if codes:
            r[CO] = ",".join(codes)
            listed += 1
        if r[LQ] == "s" and r[LR]:
            stated += 1
        else:
            langs = language.national(hq) or language.national(r[3])
            if langs:
                r[LR], r[LQ] = ",".join(langs), "i"
                inferred += 1
            else:
                r[LR], r[LQ] = "", ""
                unknown += 1
    stats = {"rows_on_a_list": listed, "lang_stated": stated, "lang_inferred": inferred, "lang_unknown": unknown}
    log(f"companies: {stats}")
    return stats
