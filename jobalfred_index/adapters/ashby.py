"""Ashby public job posting API: https://developers.ashbyhq.com/docs/public-job-posting-api (public, no key)."""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "ashby"
KIND = "tenant"
WORKERS = 4
PRIORITY = 12
URL = "https://api.ashbyhq.com/posting-api/job-board/{key}?includeCompensation=true"


def _salary(j: dict):
    comp = j.get("compensation") or {}
    for tier in comp.get("compensationTiers") or []:
        for c in tier.get("components") or []:
            if c.get("compensationType") == "Salary" and "YEAR" in str(c.get("interval", "")).upper() and c.get("minValue"):
                return c.get("minValue"), c.get("maxValue"), c.get("currencyCode") or ""
    return None, None, ""


def parse(data: dict, tenant: dict) -> list:
    out = []
    for j in (data or {}).get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location") or "" for s in j.get("secondaryLocations") or []]
        addr = ((j.get("address") or {}).get("postalAddress") or {})
        smin, smax, cur = _salary(j)
        job = make(ATS, j.get("title"), tenant.get("name") or slug_title(tenant["key"]), locs, j.get("jobUrl"),
                   j.get("publishedAt"), cc_hint=addr.get("addressCountry") or "",
                   workplace=j.get("workplaceType") or "", remote_hint=bool(j.get("isRemote")) and
                   str(j.get("workplaceType", "")).lower() != "hybrid", smin=smin, smax=smax, cur=cur)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"ashby/{tenant['key']}"), tenant)
