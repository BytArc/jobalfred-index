"""Turn stored rows into the shard files and manifest the extension reads."""
from __future__ import annotations

import collections
import gzip
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from . import seniority
from .adapters import FEED_NAMES

FIELDS = ["t", "c", "l", "cc", "r", "u", "p", "a", "smin", "smax", "cur", "lv", "ls"]
# lv: seniority level 0 not stated, 1 intern, 2 junior, 3 mid, 4 senior, 5 lead/staff/principal, 6 manager, 7 director and above.
# ls: where it came from: "n" the source's own tag, "t" the title, "d" the description, "" not stated. Readers map fields by name.
LV, LS = FIELDS.index("lv"), FIELDS.index("ls")
MAX_GZ = 8 * 1024 * 1024
TARGET_GZ = 6 * 1024 * 1024
_SUFFIX = re.compile(r"\b(inc|incorporated|ltd|limited|llc|gmbh|corp|corporation|co|sa|ag|bv|plc|pty|sarl|srl|sas|oy|ab|as)\b\.?")


def norm(s: str) -> str:
    s = _SUFFIX.sub(" ", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", "", s)


_ORACLE = re.compile(r"^(https?://[^/]+)/hcmUI/CandidateExperience/[a-z-]+/sites/[^/]+/job/(\d+)", re.I)
_WORKDAY = re.compile(r"^(https?://[^/]+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Za-z]{2}/)?[^/]+/(job/.+)$", re.I)


def canon_url(u: str) -> str:
    """Key used only to spot the same posting twice. The stored URL is never changed.
    Oracle and Workday show one posting under several career sites of the same employer."""
    m = _ORACLE.match(u)
    if m:
        return (m.group(1) + "/oracle-job/" + m.group(2)).lower()
    m = _WORKDAY.match(u)
    if m:
        return (m.group(1) + "/" + m.group(2)).lower()
    u = u.split("#", 1)[0]
    u = re.sub(r"[?&](utm_[a-z]+|gh_src|lever-source|source|ref)=[^&]*", "", u)
    u = re.sub(r"^https?://", "", u).rstrip("/?&").lower()
    return u


def dedupe(rows_iter):
    """rows_iter yields rows (lists in FIELDS order). Employer rows beat feed rows. Returns (kept, dropped counts)."""
    by_url: dict[str, int] = {}
    kept: list[list] = []
    dropped = {"same_url": 0, "feed_duplicate": 0}
    for r in rows_iter:
        k = canon_url(r[5])
        i = by_url.get(k)
        if i is None:
            by_url[k] = len(kept)
            kept.append(r)
            continue
        dropped["same_url"] += 1
        if r[7] in FEED_NAMES and kept[i][7] not in FEED_NAMES:
            continue
        if kept[i][7] in FEED_NAMES and r[7] not in FEED_NAMES:
            kept[i] = r
    employer_keys = set()
    for r in kept:
        if r[7] not in FEED_NAMES:
            employer_keys.add((norm(r[1]), norm(r[0])))
    out, seen_feed = [], set()
    for r in kept:
        if r[7] in FEED_NAMES:
            key = (norm(r[1]), norm(r[0]))
            if key in employer_keys:
                dropped["feed_duplicate"] += 1
                continue
            fk = key + (norm(r[2]),)
            if fk in seen_feed:
                dropped["feed_duplicate"] += 1
                continue
            seen_feed.add(fk)
        out.append(r)
    return out, dropped


TENANT_ATS = {"workday", "greenhouse", "lever", "ashby", "oracle", "workable", "recruitee", "bamboohr", "breezy",
              "teamtailor", "gupy", "jazzhr", "rippling", "comeet", "pinpoint", "personio", "smartrecruiters"}


def fill_country(rows: list[list]) -> int:
    """A row with no readable country gets its employer's country when that employer's located rows
    agree: at least 8 of them and at least 95% in one country. Counted and reported, never silent."""
    seen: dict[tuple, dict[str, int]] = {}
    for r in rows:
        if r[3] and r[7] in TENANT_ATS:
            d = seen.setdefault((r[7], norm(r[1])), {})
            d[r[3]] = d.get(r[3], 0) + 1
    pick = {}
    for k, d in seen.items():
        total = sum(d.values())
        cc, n = max(d.items(), key=lambda kv: kv[1])
        if total >= 8 and n / total >= 0.95:
            pick[k] = cc
    filled = 0
    for r in rows:
        if not r[3] and r[7] in TENANT_ATS:
            cc = pick.get((r[7], norm(r[1])))
            if cc:
                r[3] = cc
                filled += 1
    return filled


def fix_us_collisions(rows: list[list]) -> int:
    """A city that exists in several countries (Lisbon CT, Paris TX, Dublin OH) is in the US when the location carries a
    US state code, state name or ZIP code. Moves only rows that were put elsewhere."""
    from . import geo
    moved = 0
    for r in rows:
        if r[3] and r[3] != "US" and r[2] and geo.has_us_state(r[2]) and geo.country_of(r[2]) == "US":
            r[3] = "US"
            moved += 1
    return moved


def shard_id(r: list) -> tuple[str, str]:
    if r[4] == 2:
        return "REMOTE", ""
    cc = r[3] or "XX"
    return cc, cc


def _gz(rows: list[list]) -> bytes:
    doc = json.dumps({"v": 1, "f": FIELDS, "rows": rows}, ensure_ascii=False, separators=(",", ":")).encode()
    return gzip.compress(doc, 9, mtime=0)


def build(rows_iter, out_dir: Path, log=print) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    from .names import clean_company
    def labelled(it):
        for r in it:
            if len(r) < len(FIELDS):          # rows stored before the label existed: label them from the title
                r.extend(seniority.label(r[0]))
            yield r
    rows, dropped = dedupe(labelled(rows_iter))
    for r in rows:   # strip page words ("Careers", "Career Opportunities") that some APIs leave in company names
        c = clean_company(r[1])
        if c and c != r[1] and len(c) >= 2:
            r[1] = c
    dropped["country_corrected_to_US"] = fix_us_collisions(rows)
    dropped["country_filled_from_employer"] = fill_country(rows)
    groups: dict[str, tuple[str, list[list]]] = {}
    for r in rows:
        sid, cc = shard_id(r)
        groups.setdefault(sid, (cc, []))[1].append(r)
    for sid, (cc, lst) in groups.items():
        lst.sort(key=lambda r: (norm(r[1]), r[0].lower(), r[5]))
    old = {p.name for p in out_dir.glob("*.json.gz")}
    manifest_shards, written = [], set()
    for sid in sorted(groups):
        cc, lst = groups[sid]
        blob = _gz(lst)
        parts = [(sid, lst, blob)]
        if len(blob) > MAX_GZ:
            n = max(2, math.ceil(len(blob) / TARGET_GZ))
            while True:
                size = math.ceil(len(lst) / n)
                parts = []
                for i in range(n):
                    chunk = lst[i * size:(i + 1) * size]
                    if chunk:
                        parts.append((f"{sid}-{i + 1}", chunk, _gz(chunk)))
                if all(len(b) <= MAX_GZ for _, _, b in parts):
                    break
                n += 1
        for pid, chunk, b in parts:
            fname = f"{pid}.json.gz"
            (out_dir / fname).write_bytes(b)
            written.add(fname)
            manifest_shards.append({"id": pid, "country": cc, "file": fname, "count": len(chunk), "bytes": len(b)})
    for stale in old - written:
        (out_dir / stale).unlink()
    sources: dict[str, int] = {}
    for r in rows:
        sources[r[7]] = sources.get(r[7], 0) + 1
    manifest = {"version": 1, "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "total": len(rows),
                "base": "", "shards": manifest_shards, "sources": dict(sorted(sources.items(), key=lambda kv: -kv[1]))}
    tmp = out_dir / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, separators=(",", ":")))
    tmp.replace(out_dir / "manifest.json")
    levels = {seniority.NAMES[k]: v for k, v in sorted(collections.Counter(r[LV] for r in rows).items())}
    dropped["levels"] = levels
    dropped["level_source"] = dict(collections.Counter(r[LS] or "none" for r in rows))
    log(f"build: {len(rows)} rows in {len(manifest_shards)} shards; dropped {dropped}")
    return {"manifest": manifest, "dropped": dropped}
