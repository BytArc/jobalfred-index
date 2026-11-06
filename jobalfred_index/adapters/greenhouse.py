"""Greenhouse Job Board API: https://developers.greenhouse.io/job-board.html (public, no key)."""
from __future__ import annotations

from datetime import date

from ..model import make, day
from .base import get_json, slug_title

ATS = "greenhouse"
KIND = "tenant"
WORKERS = 6
PRIORITY = 10
URL = "https://boards-api.greenhouse.io/v1/boards/{key}/jobs"


def parse(data: dict, tenant: dict) -> list:
    out = []
    today = date.today().isoformat()
    for j in (data or {}).get("jobs", []):
        deadline = day(j.get("application_deadline"))
        if deadline and deadline < today:
            continue
        workplace = ""
        for md in j.get("metadata") or []:
            if str(md.get("name", "")).lower() in ("workplace type", "work type", "location type") and isinstance(md.get("value"), str):
                workplace = md["value"]
        locs = [(j.get("location") or {}).get("name") or ""]
        company = j.get("company_name") or tenant.get("name") or slug_title(tenant["key"])
        job = make(ATS, j.get("title"), company, locs, j.get("absolute_url"),
                   j.get("first_published") or j.get("updated_at"), workplace=workplace)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"greenhouse/{tenant['key']}"), tenant)
