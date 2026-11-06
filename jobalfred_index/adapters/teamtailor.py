"""Teamtailor career-site RSS: https://{company}.teamtailor.com/jobs.rss"""
from __future__ import annotations

from ..model import make
from .base import check, parse_xml, slug_title, txt

ATS = "teamtailor"
KIND = "tenant"
WORKERS = 6
PRIORITY = 32
URL = "https://{key}.teamtailor.com/jobs.rss"


def parse(text: str, tenant: dict) -> list:
    root = parse_xml(text)
    company = txt(root, "channel/title") or tenant.get("name") or slug_title(tenant["key"])
    out = []
    for it in root.iter("item"):
        locs, cc = [], ""
        for loc in it.iter("location"):
            city, country = txt(loc, "city"), txt(loc, "country")
            locs.append(", ".join(x for x in (city or txt(loc, "name"), country) if x))
            cc = cc or country
        rs = txt(it, "remoteStatus").lower()
        workplace = {"fully": "remote", "full": "remote", "remote": "remote", "hybrid": "hybrid"}.get(rs, "")
        job = make(ATS, txt(it, "title"), company, locs, txt(it, "link"), txt(it, "pubDate"), workplace=workplace)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    r = check(client.get(URL.format(key=tenant["key"])), f"teamtailor/{tenant['key']}")
    try:
        return parse(r.text, tenant)
    except Exception as e:  # malformed feed
        from ..model import Failed
        raise Failed(f"teamtailor/{tenant['key']}: {type(e).__name__}")
