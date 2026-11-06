"""Apple Careers: jobs.apple.com search pages embed their results as JSON (server-rendered)."""
from __future__ import annotations

import json
import re

from ..model import Failed, make
from .base import check

ATS = "apple"
KIND = "single"
WORKERS = 1
PRIORITY = 4
URL = "https://jobs.apple.com/en-us/search"
MAX_PAGES = 400


def hydration(html: str) -> dict:
    m = re.search(r'__staticRouterHydrationData\s*=\s*JSON\.parse\("((?:[^"\\]|\\.)*)"\)', html)
    if not m:
        return {}
    return json.loads(json.loads('"' + m.group(1) + '"'))


def parse(html: str, tenant=None) -> tuple[list, int]:
    search = (hydration(html).get("loaderData") or {}).get("search") or {}
    out = []
    for j in search.get("searchResults") or []:
        locs = [", ".join(x for x in (l.get("city") or l.get("name"), l.get("stateProvince"), l.get("countryName")) if x)
                for l in j.get("locations") or []]
        jid = j.get("positionId") or j.get("id")
        slug = j.get("transformedPostingTitle") or ""
        url = f"https://jobs.apple.com/en-us/details/{jid}/{slug}" if jid else ""
        job = make(ATS, j.get("postingTitle"), "Apple", locs, url, j.get("postDateInGMT") or j.get("postingDate"),
                   workplace="remote" if j.get("homeOffice") else "")
        if job:
            out.append(job)
    return out, int(search.get("totalRecords") or 0)


def fetch(client, tenant=None) -> list:
    rows, total = [], None
    for page in range(1, MAX_PAGES + 1):
        r = check(client.get(URL, params={"page": page, "sort": "newest"}), "apple")
        part, n = parse(r.text)
        if total is None:
            total = n
        if not part:
            break
        rows.extend(part)
        if total and page * 20 >= total:
            break
    if not rows:
        raise Failed("apple: no rows (page layout changed?)")
    return rows
