"""Lever Postings API: https://github.com/lever/postings-api (public, no key)."""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "lever"
KIND = "tenant"
WORKERS = 4
PRIORITY = 11
URLS = {"lever": "https://api.lever.co/v0/postings/{key}?mode=json",
        "lever-eu": "https://api.eu.lever.co/v0/postings/{key}?mode=json"}


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
                   cur=sal.get("currency") or "")
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    ats = tenant.get("_ats", "lever")
    return parse(get_json(client, URLS[ats].format(key=tenant["key"]), f"{ats}/{tenant['key']}"), tenant)
