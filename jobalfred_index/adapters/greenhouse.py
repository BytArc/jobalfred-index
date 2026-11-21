"""Greenhouse Job Board API: https://developers.greenhouse.io/job-board.html (public, no key).

The list is read with content=true (the same single request per board, about 13 KB more per role), so the description is read for the
level, years, languages and work type as it is collected, and never stored. JOBALFRED_GREENHOUSE_CONTENT=0 turns it off.
A board's own level field (custom metadata named "Seniority", "Job level", "Experience level" and the like) is read as the source's tag.
"""
from __future__ import annotations

import html
import os
import re
from datetime import date

from ..model import clean, make, day
from .base import get_json, slug_title

ATS = "greenhouse"
KIND = "tenant"
WORKERS = 6
PRIORITY = 10
URL = "https://boards-api.greenhouse.io/v1/boards/{key}/jobs"
CONTENT = os.environ.get("JOBALFRED_GREENHOUSE_CONTENT", "1") != "0"
_LEVEL_FIELD = re.compile(r"seniority|job level|experience level|career level|level of experience|experience type|grade|career stage|"
                          r"nivel|niveau|senioritat|livello|campus vs", re.I)


def level_fields(metadata) -> list[str]:
    """Values of a board's own level fields (custom metadata), as strings."""
    out = []
    for md in metadata or []:
        if not isinstance(md, dict) or not _LEVEL_FIELD.search(str(md.get("name", ""))):
            continue
        v = md.get("value")
        if isinstance(v, list):
            out += [str(x) for x in v if x]
        elif v not in (None, ""):
            out.append(str(v))
    return out


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
        content = j.get("content")
        desc = clean(html.unescape(content)) if content else None
        job = make(ATS, j.get("title"), company, locs, j.get("absolute_url"),
                   j.get("first_published") or j.get("updated_at"), workplace=workplace, desc=desc,
                   level_native=level_fields(j.get("metadata")) or None)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    url = URL.format(key=tenant["key"]) + ("?content=true" if CONTENT else "")
    return parse(get_json(client, url, f"greenhouse/{tenant['key']}"), tenant)
