"""A feed: the roles of some sources read on another machine, handed to the nightly build.

From 13 Nov 2026 Workday and Oracle refuse GitHub's servers (HTTP 422 and 429, robots.txt refused) yet answer other machines
normally, with the same honest user agent and the same pace and robots.txt rules. A server they answer runs

    python -m jobalfred_index feed --only workday,oracle

at night (scripts/feed_night.sh) and publishes the file as an asset of the release aws-feed (scripts/feed_upload.py). The nightly
build downloads the newest one and merges it before fetching (merge()). A fresh feed (built at most FRESH_HOURS ago) also means the
nightly does not fetch those sources itself. Each tenant keeps the time its roles were really read, so carry-over and its 14-day
window treat feed tenants like any other: a tenant the feed could not read is carried from the published index as before.

File: gzip JSON lines. The first line is the header {"v": 1, "built": ..., "sources": [...], "f": [fields], "stats": {...}}, then one
line per tenant, {"a": ats, "k": key, "d": data, "t": read at, "r": rows} or {"a": ats, "k": key, "gone": note}, and the last line
is {"end": true, "tenants": n}. A file without that last line is incomplete and is never used.
"""
from __future__ import annotations

import calendar
import gzip
import json
import os
import time
from pathlib import Path

from .state import State

FRESH_HOURS = 30.0      # a feed older than this is still merged, but the nightly also fetches its sources itself
NAME = "feed-{stamp}.jsonl.gz"


def export(state: State, out_dir: Path | str, sources: list[str], max_days: float, fields: list[str], log=print,
           now: float | None = None, stats: dict | None = None) -> tuple[Path, dict]:
    """Write every stored tenant of `sources` read at most `max_days` ago, plus the tenants that answered gone in this run."""
    now = now or time.time()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / NAME.format(stamp=time.strftime("%Y%m%d-%H%M%S", time.gmtime(now)))
    tmp = path.with_suffix(".part")
    cutoff = now - max_days * 86400
    marks = ",".join("?" * len(sources))
    counts = {"tenants": 0, "rows": 0, "gone": 0, "too_old": 0, "by_source": {}}
    head = {"v": 1, "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "sources": sorted(sources), "f": list(fields),
            "max_days": max_days, "stats": stats or {}}
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        fh.write(json.dumps(head, separators=(",", ":")) + "\n")
        with state.lock:
            cur = state.db.execute(
                f"SELECT t.ats,t.key,t.data,j.fetched,j.blob FROM jobs j JOIN tenants t ON t.ats=j.ats AND t.key=j.key "
                f"WHERE j.ats IN ({marks}) AND t.status!='dead'", sources)
            for ats, key, data, fetched, blob in cur:
                if fetched < cutoff:
                    counts["too_old"] += 1
                    continue
                rows = json.loads(gzip.decompress(blob))
                fh.write(json.dumps({"a": ats, "k": key, "d": json.loads(data or "{}"), "t": fetched, "r": rows},
                                    separators=(",", ":")) + "\n")
                counts["tenants"] += 1
                counts["rows"] += len(rows)
                s = counts["by_source"].setdefault(ats, {"tenants": 0, "rows": 0})
                s["tenants"] += 1
                s["rows"] += len(rows)
            gone = state.db.execute(f"SELECT ats,key,note FROM tenants WHERE ats IN ({marks}) AND last_gone_run=?",
                                    [*sources, state.run_id]).fetchall()
        for ats, key, note in gone:
            fh.write(json.dumps({"a": ats, "k": key, "gone": note or "gone"}, separators=(",", ":")) + "\n")
            counts["gone"] += 1
        fh.write(json.dumps({"end": True, "tenants": counts["tenants"]}) + "\n")
    os.replace(tmp, path)
    log(f"feed written: {path} {counts}")
    return path, counts


def _lines(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def complete(path: Path) -> dict | None:
    """The header of a feed file that is whole (gzip intact, last line present), else None."""
    try:
        head, last = None, None
        for d in _lines(path):
            if head is None:
                head = d
            last = d
        if head and head.get("v") == 1 and last and last.get("end"):
            return head
    except (OSError, EOFError, ValueError):
        pass
    return None


def newest(where: Path | str | None, log=print) -> tuple[Path, dict] | None:
    """The newest whole feed in a directory (or the file itself): (path, header)."""
    if not where:
        return None
    where = Path(where)
    files = [where] if where.is_file() else sorted(where.glob("feed-*.jsonl.gz"), reverse=True) if where.is_dir() else []
    for p in files:
        head = complete(p)
        if head:
            return p, head
        log(f"feed: {p.name} is incomplete, skipped")
    return None


def merge(state: State, where: Path | str | None, fields: list[str], log=print, max_days: float = 14,
          now: float | None = None, fresh_hours: float = FRESH_HOURS) -> tuple[set[str], dict]:
    """Store the feed's tenants as read when the feed read them. Returns the sources this run need not fetch (only when the feed
    is fresh) and the stats. Rows older than `max_days` are left out; tenants the feed saw gone are marked gone."""
    now = now or time.time()
    stats = {"file": "", "built": "", "age_hours": None, "fresh": False, "sources": [], "tenants": 0, "rows": 0, "gone": 0,
             "too_old": 0, "new_tenants": 0}
    found = newest(where, log)
    if not found:
        log("feed: none to merge")
        return set(), stats
    path, head = found
    built = calendar.timegm(time.strptime(head["built"], "%Y-%m-%dT%H:%M:%SZ"))
    stats.update(file=path.name, built=head["built"], age_hours=round((now - built) / 3600, 1), sources=head.get("sources", []))
    stats["fresh"] = now - built <= fresh_hours * 3600
    src_fields = head.get("f") or fields
    same = list(src_fields) == list(fields)
    at = {k: i for i, k in enumerate(src_fields)}
    cutoff = now - max_days * 86400
    lines = _lines(path)
    next(lines)
    for d in lines:
        if d.get("end"):
            break
        ats, key = d["a"], d["k"]
        if "gone" in d:
            if state.add_tenant(ats, key, {}, "feed"):
                stats["new_tenants"] += 1
            state.mark_gone(ats, key, f"feed: {d['gone']}"[:200])
            stats["gone"] += 1
            continue
        if d["t"] < cutoff:
            stats["too_old"] += 1
            continue
        if state.add_tenant(ats, key, d.get("d") or {}, "feed"):
            stats["new_tenants"] += 1
        rows = d["r"] if same else [[r[at[k]] if k in at and at[k] < len(r) else "" for k in fields] for r in d["r"]]
        state.save_read(ats, key, rows, d["t"], (d.get("d") or {}).get("name"))
        stats["tenants"] += 1
        stats["rows"] += len(rows)
    log(f"feed: {stats}")
    return (set(stats["sources"]) if stats["fresh"] else set()), stats
