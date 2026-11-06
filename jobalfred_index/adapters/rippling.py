"""Rippling ATS public board API: api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "rippling"
KIND = "tenant"
WORKERS = 4
PRIORITY = 31
URL = "https://api.rippling.com/platform/api/ats/v1/board/{key}/jobs"


def parse(data: list, tenant: dict) -> list:
    out = []
    for j in data or []:
        wl = j.get("workLocation") or {}
        job = make(ATS, j.get("name"), tenant.get("name") or slug_title(tenant["key"]), [wl.get("label") or ""],
                   j.get("url"), "")
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"rippling/{tenant['key']}"), tenant)
