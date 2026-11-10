"""vc-eu.json.gz: roles at VC-backed startups headquartered in Europe, read from each company's own careers system.

A separate release asset, so the main shards (read by released extensions) never change. Same row layout as a shard,
plus a company domain column `d` and a `companies` list:

  {"v": 1, "built": ISO, "f": [... shard fields ..., "d"], "rows": [[...]],
   "counts": {...}, "basis": "...",
   "companies": [{"name", "domain", "country", "evidence": [url or "Seedtable"], "boards": [[ats, key]], "roles": n}]}

Built from data/startups_eu.json (the committed company list and their careers systems) and the rows the fetch stored.
"""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from . import names, seniority, shards, startups

EUROPE = set("AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT XK LV LI LT LU MT MD MC ME NL MK NO PL PT RO RU SM "
             "RS SK SI ES SE CH TR UA GB VA GI IM JE GG FO".split())


def same_company(board_name: str, c: dict) -> bool:
    if not board_name or board_name == names.UNDISCLOSED:
        return True
    a, n = startups._fold(board_name), startups._fold(c.get("name") or "")
    label = startups._fold(c["domain"].split(".")[0])
    return startups.names_match(board_name, c.get("name") or "", c["domain"]) or bool(
        (label and len(label) >= 4 and label in a) or (n and len(n) >= 4 and (n in a or a in n)))


ENTERPRISE = {"workday", "oracle", "successfactors", "icims", "jobs2web"}


def board_problem(c: dict, named: bool, rows: list, ats: str = "") -> str:
    """Why a board's rows should not be listed under this company, or ''."""
    if not rows:
        return ""
    from collections import Counter
    who = Counter(r[1] for r in rows)
    top, n = who.most_common(1)[0]
    if len(who) > 5 and n / len(rows) < 0.6:
        return "many employers on one board (a job platform)"
    if not same_company(top, c):
        return "the board belongs to another company (often the buyer of an acquired startup)"
    if len(rows) > 20 and (named or (top == names.UNDISCLOSED and ats in ENTERPRISE)):
        eu = sum(1 for r in rows if r[3] in EUROPE or r[4] == 2) / len(rows)
        if eu < 0.25:
            return ("found by name only and its roles are mostly outside Europe (likely a namesake)" if named else
                    "an enterprise board with no employer name and roles mostly outside Europe (likely an acquirer)")
    return ""

FIELDS = shards.FIELDS + ["d"]
BASIS = ("A company is listed when it is headquartered in Europe and backed by venture investors: shown on an investor's "
         "own public portfolio page or Y Combinator's directory (the evidence URL is given), or listed in Seedtable's "
         "startup database with a disclosed round from pre-seed to growth and USD 1M or more raised (evidence 'Seedtable'). "
         "Roles are read from each company's own careers system; collected is not the same as confirmed open.")


def build(state, doc: dict, out: Path, log=print) -> dict:
    """Rows of every listed company's boards from `state`, deduplicated, written gzipped to `out`. Returns the document
    without its rows (for logs and guards)."""
    owner: dict[tuple[str, str], dict] = {}
    named = set()
    for c in doc.get("companies", []):
        if c["domain"] in startups.EXCLUDE_DOMAINS:
            continue
        for ats, key in c.get("tenants", []):
            owner.setdefault((ats, key), c)
        named |= {(a, k) for a, k in c.get("named", [])}
    dropped: dict[str, int] = {}
    dropped_boards: set = set()
    per_company: dict[str, int] = {}
    rows, seen = [], set()
    for ats, key, trows in state.iter_rows():
        c = owner.get((ats, key))
        if c is None:
            continue
        slug = key.split("|")[0].split(".")[0]
        urls = [r[5] for r in trows[:30]]
        cache: dict[str, str] = {}
        polished = [names.polish(r[1], slug, urls) or r[1] for r in trows]
        why = board_problem(c, (ats, key) in named, [[t[0], p] + list(t[2:]) for t, p in zip(trows, polished)], ats)
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            dropped_boards.add((ats, key))
            continue
        for r in trows:
            k = shards.canon_url(r[5])
            if k in seen:
                continue
            seen.add(k)
            if r[1] not in cache:
                nm = names.polish(r[1], slug, urls)
                cache[r[1]] = c.get("name") or r[1] if (not nm or nm == names.UNDISCLOSED) else nm
            r = list(r)
            if len(r) < len(shards.FIELDS):          # rows stored before the seniority label existed
                r.extend(seniority.label(r[0]))
            r = r[:len(shards.FIELDS)]
            r[1] = cache[r[1]]
            rows.append(r + [c["domain"]])
            per_company[c["domain"]] = per_company.get(c["domain"], 0) + 1
    rows.sort(key=lambda r: (shards.norm(r[1]), r[0].lower(), r[5]))
    companies = []
    for c in doc.get("companies", []):
        boards = [b for b in c.get("tenants", []) if tuple(b) not in dropped_boards]
        if c["domain"] in startups.EXCLUDE_DOMAINS or not boards:
            continue
        companies.append({"name": c.get("name"), "domain": c["domain"], "country": c.get("country") or "",
                          "evidence": c.get("evidence") or ["Seedtable"], "boards": boards,
                          "roles": per_company.get(c["domain"], 0)})
    counts = dict(doc.get("counts") or {})
    counts.update({"companies_with_careers_system": len(companies),
                   "companies_with_roles": sum(1 for c in companies if c["roles"]),
                   "roles": len(rows), "boards_dropped": dropped})
    head = {"v": 1, "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "basis": BASIS, "counts": counts,
            "f": FIELDS}
    body = {**head, "rows": rows, "companies": companies}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_bytes(gzip.compress(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(), 9, mtime=0))
    tmp.replace(out)
    log(f"vc-eu: {len(rows)} roles from {counts['companies_with_roles']} companies "
        f"({counts['companies_with_careers_system']} with a careers system we read) -> {out} ({out.stat().st_size} bytes)")
    return head
