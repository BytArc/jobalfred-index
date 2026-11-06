"""Breezy HR public JSON: https://{company}.breezy.hr/json"""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "breezy"
KIND = "tenant"
WORKERS = 6
PRIORITY = 30
URL = "https://{key}.breezy.hr/json"


def parse(data: list, tenant: dict) -> list:
    out = []
    for j in data or []:
        loc = j.get("location") or {}
        country = (loc.get("country") or {}).get("id") or ""
        locs = [loc.get("name") or ""]
        rd = (loc.get("remote_details") or {}).get("value") or ""
        workplace = "remote" if loc.get("is_remote") and rd != "hybrid" else rd
        company = (j.get("company") or {}).get("name") or tenant.get("name") or slug_title(tenant["key"])
        job = make(ATS, j.get("name"), company, locs, j.get("url"), j.get("published_date"),
                   cc_hint=country if len(country) == 2 else "", workplace=workplace)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"breezy/{tenant['key']}"), tenant)
