"""Lever Postings API: https://github.com/lever/postings-api (public, no key)."""
from __future__ import annotations

import re

from ..model import make
from .base import get_json, slug_title

ATS = "lever"
KIND = "tenant"
WORKERS = 4
PRIORITY = 11
URLS = {"lever": "https://api.lever.co/v0/postings/{key}?mode=json",
        "lever-eu": "https://api.eu.lever.co/v0/postings/{key}?mode=json"}


def description(j: dict) -> str:
    """The posting's text as the list call returns it: the description, then its lists (requirements, where languages are usually
    asked for), then the closing text. Read for seniority and languages, never stored."""
    parts = [j.get("descriptionPlain") or j.get("descriptionBodyPlain") or ""]
    for lst in j.get("lists") or []:
        parts.append((lst.get("text") or "") + "\n" + re.sub(r"<[^>]+>", "\n", lst.get("content") or ""))
    parts.append(j.get("additionalPlain") or "")
    return "\n".join(x for x in parts if x)


def parse(data: list, tenant: dict) -> list:
    out = []
    for j in data or []:
        cats = j.get("categories") or {}
        locs = [cats.get("location") or ""] + list(cats.get("allLocations") or [])
        sal = j.get("salaryRange") or {}
        interval = str(sal.get("interval", "")).lower()
        yearly = "year" in interval or "annual" in interval
        job = make(ATS, j.get("text"), tenant.get("name") or slug_title(tenant["key"]), locs, j.get("hostedUrl"),
                   j.get("createdAt"), cc_hint=j.get("country") or "", workplace=j.get("workplaceType") or "",
                   smin=sal.get("min") if yearly else None, smax=sal.get("max") if yearly else None,
                   cur=sal.get("currency") or "",
                   desc=description(j))
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    ats = tenant.get("_ats", "lever")
    return parse(get_json(client, URLS[ats].format(key=tenant["key"]), f"{ats}/{tenant['key']}"), tenant)
