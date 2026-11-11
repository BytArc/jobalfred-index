"""Carry-over: the roles of tenants a run did not reach in time are kept from the published index, for a few days.

A nightly run is time-boxed. Tenants it never tried (no fetch, no failure, no "gone" answer this run) would otherwise lose their roles,
and the published total would drop. For each such tenant whose roles were last read at most MAX_DAYS days ago, its rows in the
currently published shards are kept as they are (same posting date, every field as published); the tenant's own fetch date is not
moved, so after MAX_DAYS without a fetch its rows are dropped. Tenants that answered gone, failed this run, or were read this run are
never carried. A row is matched to its tenant among all known tenants by its URL (the careers system's host, board or site) or, failing
that, by the company name when only one tenant of that system carries it; rows that match no unreached tenant are not carried.
"""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from .adapters import SOURCES
from .discovery import classify
from .state import State, fetched_ts

MAX_DAYS = 3
# subdomain boards: the first label of the host is the tenant key
SUBDOMAIN = {"gupy.io": "gupy", "recruitee.com": "recruitee", "teamtailor.com": "teamtailor", "bamboohr.com": "bamboohr",
             "breezy.hr": "breezy", "applytojob.com": "jazzhr", "pinpointhq.com": "pinpoint", "jobs.personio.de": "personio",
             "jobs.personio.com": "personio", "icims.com": "icims", "eightfold.ai": "eightfold"}


class TenantIndex:
    """Which tenant a published row came from, among the tenants given."""

    def __init__(self, tenants):                      # (ats, key, data)
        out = {name: s.out for name, s in SOURCES.items()}
        self.keys: dict[str, dict[str, tuple[str, str]]] = {}        # row ats -> lower key -> (source ats, key)
        self.hosts: dict[str, dict[str, list[tuple[str, str, str]]]] = {}  # row ats -> host -> [(site lower, ats, key)]
        names: dict[str, dict[str, list[tuple[str, str]]]] = {}
        for ats, key, data in tenants:
            o = out.get(ats, ats)
            self.keys.setdefault(o, {})[key.lower()] = (ats, key)
            head, _, site = key.partition("|")
            host = data.get("host") or (f"{data['tenant']}.{data['wd']}.myworkdayjobs.com" if data.get("tenant") and data.get("wd") else "")
            if o in ("workday", "oracle", "jsonld", "icims", "pagelist", "careers-page") or host:
                h = (host or head).lower()
                self.hosts.setdefault(o, {}).setdefault(h, []).append(((site or data.get("site") or "").lower(), ats, key))
            if data.get("name"):
                names.setdefault(o, {}).setdefault(data["name"], []).append((ats, key))
        self.names = {o: {n: v[0] for n, v in d.items() if len(v) == 1} for o, d in names.items()}

    def of(self, ats: str, url: str, company: str) -> tuple[str, str] | None:
        sp = urlsplit(url or "")
        host = (sp.hostname or "").lower()
        segs = [x for x in sp.path.split("/") if x]
        keys = self.keys.get(ats, {})
        for a, key, _ in classify(url):
            hit = keys.get(key.lower())
            if hit:
                return hit
        for suffix, a in SUBDOMAIN.items():
            if a == ats and host.endswith("." + suffix):
                hit = keys.get(host.split(".")[0])
                if hit:
                    return hit
        cands = self.hosts.get(ats, {}).get(host)
        if cands:
            site = ""
            if ats == "workday" and segs:
                site = (segs[1] if len(segs) > 1 and "-" in segs[0] and len(segs[0]) == 5 else segs[0]).lower()
            elif ats == "oracle" and "sites" in segs:
                site = segs[segs.index("sites") + 1].lower() if len(segs) > segs.index("sites") + 1 else ""
            exact = [c for c in cands if c[0] and c[0] == site]
            pick = exact[0] if exact else (cands[0] if len(cands) == 1 else next((c for c in cands if not c[0]), None))
            if pick:
                return pick[1], pick[2]
        return self.names.get(ats, {}).get(company)


def published_rows(prev: Path):
    """(fields, row) for every row of the published shards in `prev` (manifest.json and its shard files)."""
    man = json.loads((prev / "manifest.json").read_text())
    for s in man["shards"]:
        p = prev / s["file"]
        if not p.exists():
            continue
        d = json.loads(gzip.decompress(p.read_bytes()))
        for r in d["rows"]:
            yield d["f"], r


def carry_over(state: State, prev: Path | str | None, run_started: float, fields: list[str], log=print,
               max_days: float = MAX_DAYS, now: float | None = None) -> tuple[list[list], dict]:
    """The published rows of the tenants this run did not reach, read at most `max_days` ago, laid out as `fields`."""
    now = now or time.time()
    stats = {"tenants": 0, "rows": 0, "unreached": 0, "too_old": 0, "max_days": max_days, "from": ""}
    prev = Path(prev) if prev else None
    if not prev or not (prev / "manifest.json").exists():
        log("carry-over: no published index to carry from")
        return [], stats
    man = json.loads((prev / "manifest.json").read_text())
    stats["from"] = man.get("built", "")
    fallback = fetched_ts(man.get("fetched") or man.get("built") or "")     # tenants with no fetch date of their own
    cutoff = now - max_days * 86400
    eligible = []
    for ats, key, data, ok in state.unreached(run_started):
        stats["unreached"] += 1
        when = ok or fallback
        if when and when >= cutoff:
            eligible.append((ats, key, data))
        else:
            stats["too_old"] += 1
    if not eligible:
        log(f"carry-over: {stats}")
        return [], stats
    ix = TenantIndex(state.all_tenants())          # every tenant, so a row of a tenant read this run is never taken for another
    eligible_keys = {(a, k) for a, k, _ in eligible}
    out: list[list] = []
    per: dict[tuple[str, str], int] = {}
    at_cache: dict[tuple, dict] = {}
    for f, r in published_rows(prev):
        at = at_cache.get(tuple(f))
        if at is None:
            at = at_cache[tuple(f)] = {k: i for i, k in enumerate(f)}
        t = ix.of(r[at["a"]], r[at["u"]], r[at["c"]])
        if t is None or t not in eligible_keys:
            continue
        out.append([r[at[k]] if k in at else "" for k in fields])
        per[t] = per.get(t, 0) + 1
    stats["tenants"], stats["rows"] = len(per), len(out)
    log(f"carry-over: {stats}")
    return out, stats
