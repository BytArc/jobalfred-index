"""Gem public Job Board API: https://api.gem.com/job_board/v0/{board}/job_posts/ (no key; the API the hosted board
https://jobs.gem.com/{board} reads)."""
from __future__ import annotations

from ..model import make
from .base import get_json, slug_title

ATS = "gem"
KIND = "tenant"
WORKERS = 3
PRIORITY = 24
URL = "https://api.gem.com/job_board/v0/{key}/job_posts/"


def parse(data, tenant: dict) -> list:
    company = tenant.get("name") or slug_title(tenant["key"].split("-gmbh")[0])
    out = []
    for j in data if isinstance(data, list) else []:
        locs = [(o.get("location") or {}).get("name") or o.get("name") for o in (j.get("offices") or [])]
        if not any(locs):
            locs = [(j.get("location") or {}).get("name")]
        lt = (j.get("location_type") or "").lower()
        workplace = "remote" if lt == "remote" else ("hybrid" if lt == "hybrid" else "")
        job = make(ATS, j.get("title"), company, [x for x in locs if x], j.get("absolute_url"),
                   j.get("first_published_at") or j.get("created_at"), workplace=workplace,
                   desc=(j.get("content_plain") or "")[:6000])
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    return parse(get_json(client, URL.format(key=tenant["key"]), f"gem/{tenant['key']}"), tenant)
