"""Candidate tenants from company names we already know.

Open feeds and the boards we already read give thousands of real company names. For ATSs where
every company has its own subdomain (Recruitee, Breezy, Teamtailor, BambooHR, Pinpoint, Personio, Gupy)
we turn each name into a slug and let the normal fetch decide: a 404 prunes the candidate at once,
so nothing but real boards is kept. Pacing is per ATS family, see polite.FAMILIES.
"""
from __future__ import annotations

import collections
import re
import unicodedata

from .adapters import FEED_NAMES

SUFFIX = re.compile(r"\b(inc|incorporated|ltd|limited|llc|gmbh|corp|corporation|co|sa|ag|bv|plc|pty|sarl|srl|sas|oy|ab|as|"
                    r"the|group|holding|holdings|company|technologies|technology|labs|solutions|international)\b\.?", re.I)
FAMILIES = ["recruitee", "breezy", "teamtailor", "bamboohr", "gupy", "pinpoint", "personio"]
SHARED = ["greenhouse", "lever", "ashby", "workable"]   # one shared host each, so the pace limit applies and the cap is small


def slugs(name: str) -> list[str]:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9 &-]", " ", s).replace("&", " and ")
    base = re.sub(r"\s+", " ", s).strip()
    core = re.sub(r"\s+", " ", SUFFIX.sub(" ", base)).strip() or base
    out = []
    for cand in (core.replace(" ", ""), core.replace(" ", "-"), base.replace(" ", "")):
        cand = cand.strip("-")
        if 3 <= len(cand) <= 40 and cand not in out:
            out.append(cand)
    return out


def candidate_names(state) -> collections.Counter:
    names: collections.Counter = collections.Counter()
    for ats, _key, rows in state.iter_rows():
        for r in rows:
            if r[1]:
                names[r[1]] += 1
    return names


def run_probe(state, per_family: int, log, per_shared: int = 2500) -> dict:
    names = candidate_names(state)
    ordered = [n for n, _ in names.most_common()]
    seen, cands = set(), []
    for n in ordered:
        for s in slugs(n)[:2]:
            if s not in seen:
                seen.add(s)
                cands.append(s)
    log(f"probe: {len(ordered)} company names -> {len(cands)} slugs")
    added: dict[str, int] = {}
    for fam in FAMILIES + SHARED:
        k = 0
        cap = per_shared if fam in SHARED else per_family
        for s in cands:
            if k >= cap:
                break
            data = {"tld": "de"} if fam == "personio" else {}
            if state.add_tenant(fam, s, data, "probe"):
                added[fam] = added.get(fam, 0) + 1
                k += 1
    log(f"probe: candidates added {added}")
    return added
