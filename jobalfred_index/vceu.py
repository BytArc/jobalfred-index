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

from . import names, seniority, shards

FIELDS = shards.FIELDS + ["d"]
BASIS = ("A company is listed when it is headquartered in Europe and backed by venture investors: shown on an investor's "
         "own public portfolio page or Y Combinator's directory (the evidence URL is given), or listed in Seedtable's "
         "startup database with a disclosed round from pre-seed to growth and USD 1M or more raised (evidence 'Seedtable'). "
         "Roles are read from each company's own careers system; collected is not the same as confirmed open.")


def build(state, doc: dict, out: Path, log=print) -> dict:
    """Rows of every listed company's boards from `state`, deduplicated, written gzipped to `out`. Returns the document
    without its rows (for logs and guards)."""
    owner: dict[tuple[str, str], dict] = {}
    for c in doc.get("companies", []):
        for ats, key in c.get("tenants", []):
            owner.setdefault((ats, key), c)
    per_company: dict[str, int] = {}
    rows, seen = [], set()
    for ats, key, trows in state.iter_rows():
        c = owner.get((ats, key))
        if c is None:
            continue
        slug = key.split("|")[0].split(".")[0]
        urls = [r[5] for r in trows[:30]]
        cache: dict[str, str] = {}
        for r in trows:
            k = shards.canon_url(r[5])
            if k in seen:
                continue
            seen.add(k)
            if r[1] not in cache:
                cache[r[1]] = names.polish(r[1], slug, urls) or c.get("name") or r[1]
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
        companies.append({"name": c.get("name"), "domain": c["domain"], "country": c.get("country") or "",
                          "evidence": c.get("evidence") or ["Seedtable"], "boards": c.get("tenants", []),
                          "roles": per_company.get(c["domain"], 0)})
    counts = dict(doc.get("counts") or {})
    counts.update({"companies_with_careers_system": len(companies),
                   "companies_with_roles": sum(1 for c in companies if c["roles"]),
                   "roles": len(rows)})
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
