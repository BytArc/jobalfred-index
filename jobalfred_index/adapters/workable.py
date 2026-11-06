"""Workable public widget API: https://apply.workable.com/api/v1/widget/accounts/{slug}"""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "workable"
KIND = "tenant"
WORKERS = 6
PRIORITY = 20
URL = "https://apply.workable.com/api/v1/widget/accounts/{key}"


def parse(data: dict, tenant: dict) -> list:
    out = []
    company = (data or {}).get("name") or tenant.get("name") or slug_title(tenant["key"])
    for j in (data or {}).get("jobs", []):
        locs = []
        for l in j.get("locations") or []:
            locs.append(", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x))
        if not locs:
            locs = [", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)]
        url = j.get("url") or j.get("shortlink") or ""
        job = make(ATS, j.get("title"), company, locs, url, j.get("published_on") or j.get("created_at"),
                   workplace="remote" if j.get("telecommuting") else "")
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"workable/{tenant['key']}"), tenant)
