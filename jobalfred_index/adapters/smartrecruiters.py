"""SmartRecruiters Posting API: https://developers.smartrecruiters.com/docs/posting-api

api.smartrecruiters.com/robots.txt disallows every crawler except LinkedInBot, so the shared
client refuses these requests and the source reports itself as blocked. The adapter stays so
that the index can use it the day the policy changes, or with a written agreement.
"""
from __future__ import annotations

from ..model import make
from .base import check

ATS = "smartrecruiters"
KIND = "tenant"
WORKERS = 4
PRIORITY = 40
URL = "https://api.smartrecruiters.com/v1/companies/{key}/postings"
PAGE = 100


def parse(data: dict, tenant: dict) -> list:
    out = []
    for j in (data or {}).get("content", []):
        loc = j.get("location") or {}
        locs = [", ".join(x for x in (loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()) if x)]
        company = (j.get("company") or {}).get("name") or tenant["key"]
        url = f"https://jobs.smartrecruiters.com/{(j.get('company') or {}).get('identifier') or tenant['key']}/{j.get('id')}"
        job = make(ATS, j.get("name"), company, locs, url, j.get("releasedDate"),
                   cc_hint=loc.get("country") or "", remote_hint=bool(loc.get("remote")))
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    rows, offset = [], 0
    while True:
        r = check(client.get(URL.format(key=tenant["key"]), params={"limit": PAGE, "offset": offset}),
                  f"smartrecruiters/{tenant['key']}")
        d = r.json() or {}
        rows.extend(parse(d, tenant))
        offset += PAGE
        if offset >= int(d.get("totalFound") or 0) or not d.get("content"):
            return rows
