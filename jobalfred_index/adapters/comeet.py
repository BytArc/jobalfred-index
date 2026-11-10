"""Comeet careers API. The public careers page embeds the company uid and a read token;
the same JSON the page loads is then read from careers-api."""
from __future__ import annotations

import re

from ..model import Failed, make
from .base import check, get_json, slug_title

ATS = "comeet"
KIND = "tenant"
WORKERS = 4
PRIORITY = 34


def page_token(html: str) -> tuple[str, str]:
    uid = re.search(r'"company[-_]uid"\s*:\s*"([^"]+)"', html) or re.search(r'"uid"\s*:\s*"([A-Z0-9]{2,3}\.[A-Z0-9]{3,5})"', html)
    tok = re.search(r'"token"\s*:\s*"([A-Za-z0-9]{8,})"', html)
    return (uid.group(1) if uid else ""), (tok.group(1) if tok else "")


def parse(data: list, tenant: dict) -> list:
    out = []
    for j in data or []:
        loc = j.get("location") or {}
        locs = [loc.get("name") or ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)]
        job = make(ATS, j.get("name"), tenant.get("name") or slug_title(tenant["slug"]), locs,
                   j.get("url_active_page") or j.get("url_comeet_hosted_page"), j.get("time_updated"),
                   cc_hint=loc.get("country") or "", remote_hint=bool(loc.get("is_remote")),
                   native=j.get("experience_level"))
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    page = check(client.get(f"https://www.comeet.com/jobs/{tenant['slug']}/{tenant['uid']}"), f"comeet/{tenant['key']}")
    uid, tok = page_token(page.text)
    nm = re.search(r'COMPANY_DATA\s*=\s*\{"name":\s*"([^"]+)"', page.text)
    if nm:
        tenant["name"] = nm.group(1)
    if not uid or not tok:
        raise Failed(f"comeet/{tenant['key']}: no token on page")
    data = get_json(client, f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions",
                    f"comeet/{tenant['key']}", params={"token": tok, "details": "false"})
    return parse(data, tenant)
