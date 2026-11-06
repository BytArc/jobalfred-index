"""Personio public XML feed: https://{company}.jobs.personio.de/xml (also .com)."""
from __future__ import annotations

from ..model import Failed, make
from .base import check, parse_xml, slug_title, txt

ATS = "personio"
KIND = "tenant"
WORKERS = 6
PRIORITY = 22


def parse(text: str, tenant: dict) -> list:
    root = parse_xml(text)
    tld = tenant.get("tld", "de")
    out = []
    for p in root.iter("position"):
        pid = txt(p, "id")
        office = txt(p, "office")
        job = make(ATS, txt(p, "name"), tenant.get("name") or slug_title(tenant["key"]), [office],
                   f"https://{tenant['key']}.jobs.personio.{tld}/job/{pid}" if pid else "", txt(p, "createdAt"))
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    tld = tenant.get("tld", "de")
    r = check(client.get(f"https://{tenant['key']}.jobs.personio.{tld}/xml"), f"personio/{tenant['key']}")
    if "<workzag-jobs" not in r.text:
        raise Failed(f"personio/{tenant['key']}: not a Personio feed")
    return parse(r.text, tenant)
