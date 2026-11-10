"""Gupy career pages (Brazil): https://{company}.gupy.io/ embeds the full job list as JSON in __NEXT_DATA__."""
from __future__ import annotations

import json
import re

from ..model import Failed, make
from .base import check, slug_title

ATS = "gupy"
KIND = "tenant"
WORKERS = 6
PRIORITY = 35


def parse(html: str, tenant: dict) -> list:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    pp = json.loads(m.group(1)).get("props", {}).get("pageProps", {})
    cp = pp.get("careerPage") or {}
    company = cp.get("name") or tenant.get("name") or slug_title(tenant["key"])
    out = []
    for j in pp.get("jobs") or []:
        if "talent_pool" in str(j.get("type", "")):
            continue
        wp = j.get("workplace") or {}
        a = wp.get("address") or {}
        locs = [", ".join(x for x in (a.get("city"), a.get("state"), a.get("country")) if x)]
        wt = str(wp.get("workplaceType", "")).lower()
        workplace = "remote" if wt == "remote" else ("hybrid" if wt == "hybrid" else "")
        job = make(ATS, j.get("title"), company, locs, f"https://{tenant['key']}.gupy.io/jobs/{j.get('id')}",
                   j.get("publishedDate") or "", workplace=workplace, cc_hint="BR" if str(a.get("country", "")).lower() in ("brasil", "brazil") else "", native=j.get("type"))
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    r = check(client.get(f"https://{tenant['key']}.gupy.io/"), f"gupy/{tenant['key']}")
    if "__NEXT_DATA__" not in r.text:
        raise Failed(f"gupy/{tenant['key']}: unexpected page")
    return parse(r.text, tenant)
