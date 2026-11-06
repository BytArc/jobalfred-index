"""Pinpoint public postings feed: https://{company}.pinpointhq.com/postings.json"""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "pinpoint"
KIND = "tenant"
WORKERS = 4
PRIORITY = 33
URL = "https://{key}.pinpointhq.com/postings.json"


def parse(data: dict, tenant: dict) -> list:
    out = []
    for j in (data or {}).get("data", []):
        loc = j.get("location") or {}
        locs = [loc.get("name") or ", ".join(x for x in (loc.get("city"), loc.get("province")) if x)]
        smin = j.get("compensation_minimum") if j.get("compensation_frequency") in ("yearly", "annual", "year") else None
        smax = j.get("compensation_maximum") if smin is not None else None
        job = make(ATS, j.get("title"), tenant.get("name") or slug_title(tenant["key"]), locs, j.get("url"),
                   j.get("published_at") or j.get("created_at") or "", workplace=j.get("workplace_type") or "",
                   smin=smin, smax=smax, cur=j.get("compensation_currency") or "")
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"pinpoint/{tenant['key']}"), tenant)
