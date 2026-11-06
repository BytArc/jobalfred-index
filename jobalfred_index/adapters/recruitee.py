"""Recruitee public offers API: https://{company}.recruitee.com/api/offers/"""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "recruitee"
KIND = "tenant"
WORKERS = 6
PRIORITY = 21
URL = "https://{key}.recruitee.com/api/offers/"


def parse(data: dict, tenant: dict) -> list:
    out = []
    for j in (data or {}).get("offers", []):
        if j.get("status") not in (None, "published"):
            continue
        locs = []
        if j.get("locations"):
            for l in j["locations"]:
                locs.append(", ".join(x for x in (l.get("city"), l.get("state"), l.get("country")) if x))
        else:
            locs = [j.get("location") or ", ".join(x for x in (j.get("city"), j.get("country")) if x)]
        company = j.get("company_name") or tenant.get("name") or slug_title(tenant["key"])
        workplace = "remote" if j.get("remote") else ("hybrid" if j.get("hybrid") else "")
        sal = j.get("salary") or {}
        job = make(ATS, j.get("title"), company, locs, j.get("careers_url"), j.get("published_at") or j.get("created_at"),
                   cc_hint=j.get("country_code") or "", workplace=workplace,
                   smin=sal.get("min"), smax=sal.get("max"), cur=sal.get("currency") or "")
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"recruitee/{tenant['key']}"), tenant)
