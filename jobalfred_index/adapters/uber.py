"""Uber careers search JSON. uber.com/robots.txt disallows */api/, so the client refuses this
request and the source reports itself as blocked. Kept for the day the policy changes."""
from __future__ import annotations

from ..model import make
from .base import check

ATS = "uber"
KIND = "single"
WORKERS = 1
PRIORITY = 60
URL = "https://www.uber.com/api/loadSearchJobsResults?localeCode=en"


def parse(d: dict, tenant=None) -> list:
    out = []
    for j in ((d or {}).get("data") or {}).get("results", []):
        locs = [", ".join(x for x in (l.get("city"), l.get("countryName")) for _ in [0] if x)
                for l in (j.get("allLocations") or [])]
        job = make(ATS, j.get("title"), "Uber", locs, f"https://www.uber.com/us/en/careers/list/{j.get('id')}/", j.get("creationDate"))
        if job:
            out.append(job)
    return out


def fetch(client, tenant=None) -> list:
    rows, page = [], 1
    while page <= 50:
        r = check(client.post(URL, json={"params": {"page": page}}, headers={"Content-Type": "application/json", "x-csrf-token": "x"}), "uber")
        d = r.json() or {}
        part = parse(d)
        if not part:
            break
        rows.extend(part)
        page += 1
    return rows
