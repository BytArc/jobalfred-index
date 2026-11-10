"""JOIN company career pages: https://join.com/companies/{company}

The page is served with its data in a __NEXT_DATA__ script (pageData.jobs.items, five roles a page, ?page=N for more).
robots.txt allows /companies/. One shared host, so the client's per-host pacing applies to every tenant.
"""
from __future__ import annotations

import json
import re

from ..model import Failed, Gone, make
from .base import check, slug_title

ATS = "join"
KIND = "tenant"
WORKERS = 2
PRIORITY = 34
URL = "https://join.com/companies/{key}"
MAX_PAGES = 30
NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def page_data(html: str) -> dict:
    m = NEXT.search(html or "")
    if not m:
        return {}
    try:
        return ((json.loads(m.group(1)).get("props") or {}).get("pageProps") or {}).get("pageData") or {}
    except ValueError:
        return {}


def parse(pd: dict, tenant: dict) -> list:
    company = ((pd.get("company") or {}).get("name")) or tenant.get("name") or slug_title(tenant["key"])
    out = []
    for j in ((pd.get("jobs") or {}).get("items") or []):
        city = j.get("city") or {}
        loc = ", ".join(x for x in (city.get("cityName"), city.get("countryName")) if x)
        cc = ((j.get("country") or {}).get("iso3166") or "")
        wt = (j.get("workplaceType") or "").upper()
        workplace = {"REMOTE": "remote", "HYBRID": "hybrid"}.get(wt, "")
        slug = j.get("idParam") or j.get("id")
        if not slug:
            continue
        job = make(ATS, j.get("title"), company, [loc], f"https://join.com/companies/{tenant['key']}/{slug}", j.get("createdAt"),
                   cc_hint=cc, workplace=workplace)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    base = URL.format(key=tenant["key"])
    r = check(client.get(base), f"join/{tenant['key']}")
    pd = page_data(r.text)
    if not pd.get("company"):
        raise Gone(f"join/{tenant['key']}: no such company")
    rows = parse(pd, tenant)
    pages = int(((pd.get("jobs") or {}).get("pagination") or {}).get("pageCount") or 1)
    for n in range(2, min(pages, MAX_PAGES) + 1):
        p = client.get(f"{base}?page={n}")   # query in the URL, so the robots.txt check sees it
        if p.status != 200:
            if rows:
                break
            raise Failed(f"join/{tenant['key']}: page {n} HTTP {p.status}")
        rows.extend(parse(page_data(p.text), tenant))
    return rows
