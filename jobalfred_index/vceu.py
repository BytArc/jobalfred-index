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

from . import companies as colists, industry, names, seniority, shards, startups, vcindustry

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
        hq = (c.get("country") or "").upper()          # judged against the company's own region: Europe, or its HQ country
        home, where = (EUROPE, "Europe") if (not hq or hq in EUROPE) else ({hq}, hq)
        share = sum(1 for r in rows if r[3] in home or r[4] == 2) / len(rows)
        if share < 0.25:
            return (f"found by name only and its roles are mostly outside {where} (likely a namesake)" if named else
                    f"an enterprise board with no employer name and roles mostly outside {where} (likely an acquirer)")
    return ""

FIELDS = shards.FIELDS + ["d", "gs", "gt", "gc", "gl", "gd", "gu", "gi"]
# d: company domain. Funding of the company, from public news (data/funding_eu.json), copied onto each of its rows:
# gs latest stage, gt total raised, gc its currency, gl 1 when the total is "at least" (summed from rounds found),
# gd date of the latest round found, gu that article. Empty when no round was found.
# gi: the company's backers named by public evidence (Y Combinator, investors' own portfolio pages), joined by "|".
INVESTORS = Path(__file__).resolve().parent.parent / "data" / "vc_investors.json"


def investor_hosts() -> dict[str, str]:
    """registrable domain of an investor's site -> investor name (from data/vc_investors.json)."""
    if not INVESTORS.exists():
        return {}
    out = {}
    for name, v in json.loads(INVESTORS.read_text())["investors"].items():
        for page in v.get("pages", []) + ([f"https://{v['detail'][0]}/"] if v.get("detail") else []):
            d = startups.registrable(page)
            if d:
                out.setdefault(d, name)
    return out


def backers_of(c: dict, hosts: dict[str, str]) -> list[dict]:
    """[{"name", "url"}] from the company's public evidence; Y Combinator carries its batch when known."""
    out, seen = [], set()
    for ev in c.get("evidence") or []:
        name = hosts.get(startups.registrable(ev.split(" ")[0])) if ev.startswith("http") else None
        if not name or name in seen:
            continue
        seen.add(name)
        b = {"name": name, "url": ev.split(" ")[0]}
        if name == "Y Combinator" and c.get("yc_batch"):
            b["batch"] = c["yc_batch"]
        out.append(b)
    return out
FUNDING = Path(__file__).resolve().parent.parent / "data" / "funding_eu.json"


def funding_of() -> tuple[dict, dict]:
    """(summary per domain, round article URLs per domain, newest first)."""
    if not FUNDING.exists():
        return {}, {}
    try:
        doc = json.loads(FUNDING.read_text())
    except ValueError:
        return {}, {}
    urls = {d: [r["url"] for r in sorted(rs, key=lambda r: r.get("date") or "", reverse=True)]
            for d, rs in (doc.get("rounds") or {}).items()}
    return doc.get("companies") or {}, urls
BASIS = ("A company is listed when it is headquartered in Europe and backed by venture investors: shown on an investor's "
         "own public portfolio page or Y Combinator's directory (the evidence URL is given), or listed in Seedtable's "
         "startup database with a disclosed round from pre-seed to growth and USD 1M or more raised (evidence 'Seedtable'). "
         "Roles are read from each company's own careers system; collected is not the same as confirmed open. "
         "Companies with backing 'listed' are startups Seedtable lists with no disclosed round: included for their roles, "
         "not claimed as VC-backed.")


BASIS_WORLD = ("A company is listed when it is backed by venture investors: shown on Y Combinator's public directory or an investor's "
               "own public portfolio page (the evidence URL is given), or, in Europe, listed in Seedtable's startup database with a "
               "disclosed round from pre-seed to growth and USD 1M or more raised (evidence 'Seedtable'). hq_country is where it is "
               "headquartered. kind 'investor' marks a VC firm's own roles. Roles are read from each company's own careers system; "
               "collected is not the same as confirmed open.")


def union(docs: list[dict]) -> dict:
    """One list from several (Europe and the world batches), for vc-world.json.gz. Counts kept per region."""
    seen, companies, tenants = set(), [], {}
    for d in docs:
        for t in d.get("tenants", []):
            tenants.setdefault((t["ats"], t["key"]), t)
        for c in d.get("companies", []):
            if c["domain"] not in seen:
                seen.add(c["domain"])
                companies.append(c)
    return {"companies": companies, "tenants": list(tenants.values()), "basis": BASIS_WORLD,
            "counts": {"by_region": {d.get("region", str(i)): d.get("counts") or {} for i, d in enumerate(docs)}}}


def build(state, doc: dict, out: Path, log=print, homepages=None) -> dict:
    """Rows of every listed company's boards from `state`, deduplicated, written gzipped to `out`. Returns the document
    without its rows (for logs and guards)."""
    owner: dict[tuple[str, str], dict] = {}
    named = set()
    for c in doc.get("companies", []):
        if startups.excluded(c["domain"]):
            continue
        for ats, key in c.get("tenants", []):
            owner.setdefault((ats, key), c)
        named |= {(a, k) for a, k in c.get("named", [])}
    dropped: dict[str, int] = {}
    dropped_boards: set = set()
    per_company: dict[str, int] = {}
    fund, round_urls = funding_of()
    hosts = investor_hosts()
    backers = {c["domain"]: backers_of(c, hosts) for c in doc.get("companies", [])}

    def ftail(dom):
        f = fund.get(dom) or {}
        return [f.get("stage") or "", f.get("total"), f.get("currency") or "", 1 if f.get("at_least") else 0,
                f.get("date") or "", f.get("source") or ""] if f else ["", None, "", 0, "", ""]
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
            r = shards.complete(r)[:len(shards.FIELDS)]   # stored rows lacking newer label columns get them; industry is filled below
            r[1] = cache[r[1]]
            rows.append(r + [c["domain"]] + ftail(c["domain"]) + ["|".join(b["name"] for b in backers.get(c["domain"], []))])
            per_company[c["domain"]] = per_company.get(c["domain"], 0) + 1
    rows.sort(key=lambda r: (shards.norm(r[1]), r[0].lower(), r[5]))
    # industry: a reader's hand label first, then public evidence (vcindustry: the funding article's description, YC tags),
    # then industry.assign's own sources (stored labels, the local model above its cutoff), then Not stated
    listed = [c for c in doc.get("companies", []) if c["domain"] in per_company or c.get("tenants")]
    vcin = vcindustry.labels(listed)
    di = len(shards.FIELDS)                        # the d column
    vc_rows = 0
    for r in rows:
        lab = vcin.get(r[di])
        if lab and not r[industry.IN] and industry.hand_label(industry.group_key(r[1], r[5])) is None:
            r[industry.IN] = lab["code"]
            vc_rows += 1
    industry.assign(rows, homepages, log=log)      # same model as the main index; first-seen companies are fetched when a Homepages is given
    colists.assign(rows, log=log)                  # list membership (co) and languages (lr, lq), as in the main index
    companies = []
    for c in doc.get("companies", []):
        boards = [b for b in c.get("tenants", []) if tuple(b) not in dropped_boards]
        if startups.excluded(c["domain"]) or not boards:
            continue
        evidence = c.get("evidence") or ["Seedtable"]
        if evidence == ["Seedtable"] and round_urls.get(c["domain"]):
            evidence = round_urls[c["domain"]][:2]      # a public article on its funding round replaces "Seedtable"
        entry = {"name": c.get("name"), "domain": c["domain"], "country": c.get("country") or "", "hq_country": c.get("country") or "",
                 "evidence": evidence, "boards": boards, "roles": per_company.get(c["domain"], 0),
                 "backing": c.get("backing") if c.get("kind") == "investor" else (c.get("backing") or "vc"),
                 "kind": c.get("kind") or "startup"}
        if fund.get(c["domain"]):
            entry["funding"] = fund[c["domain"]]
        if vcin.get(c["domain"]):
            entry["industry"] = vcin[c["domain"]]      # code, source, evidence phrase and its URL
        if backers.get(c["domain"]):
            entry["backers"] = backers[c["domain"]]
        companies.append(entry)
    counts = dict(doc.get("counts") or {})
    counts.update({"companies_with_careers_system": len(companies),
                   "companies_with_roles": sum(1 for c in companies if c["roles"]),
                   "roles": len(rows), "boards_dropped": dropped,
                   "companies_with_funding": sum(1 for c in companies if c.get("funding")),
                   "industry_rows_tagged": sum(1 for r in rows if r[industry.IN] not in ("", industry.OTHER, industry.NOT_STATED)),
                   "industry_from_public_evidence": {"companies": sum(1 for c in companies if c.get("industry")), "rows": vc_rows},
                   "evidence_public": sum(1 for c in companies if c["evidence"] != ["Seedtable"]),
                   "companies_with_backers": sum(1 for c in companies if c.get("backers")),
                   "companies_listed_not_vc": sum(1 for c in companies if c.get("backing") == "listed"),
                   "investor_firms": {"with_careers_system": sum(1 for c in companies if c.get("kind") == "investor"),
                                      "with_roles": sum(1 for c in companies if c.get("kind") == "investor" and c["roles"]),
                                      "roles": sum(c["roles"] for c in companies if c.get("kind") == "investor")},
                   "evidence_seedtable_only": sum(1 for c in companies if c["evidence"] == ["Seedtable"]),
                   "companies_with_stage": sum(1 for c in companies if (c.get("funding") or {}).get("stage")),
                   "companies_with_total": sum(1 for c in companies if (c.get("funding") or {}).get("total"))})
    head = {"v": 1, "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "basis": doc.get("basis") or BASIS, "counts": counts,
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
