"""BambooHR public careers list: https://{company}.bamboohr.com/careers/list"""
from __future__ import annotations

from ..model import Gone, make
from .base import check, slug_title

ATS = "bamboohr"
KIND = "tenant"
WORKERS = 6
PRIORITY = 23
URL = "https://{key}.bamboohr.com/careers/list"


def parse(data: dict, tenant: dict) -> list:
    out = []
    for j in (data or {}).get("result", []):
        loc = j.get("location") or {}
        ats_loc = j.get("atsLocation") or {}
        locs = [", ".join(x for x in (loc.get("city"), loc.get("state") or ats_loc.get("province"), ats_loc.get("country")) if x)]
        wt = str(j.get("locationType", ""))
        workplace = "remote" if (j.get("isRemote") or wt == "1") else ("hybrid" if wt == "2" else "")
        job = make(ATS, j.get("jobOpeningName"), tenant.get("name") or slug_title(tenant["key"]), locs,
                   f"https://{tenant['key']}.bamboohr.com/careers/{j.get('id')}", "", workplace=workplace)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    r = check(client.get(URL.format(key=tenant["key"]), headers={"Accept": "application/json"}), f"bamboohr/{tenant['key']}")
    data = r.json()
    if data is None:  # an unknown subdomain answers with BambooHR's marketing page, HTTP 200
        raise Gone(f"bamboohr/{tenant['key']}: no such company")
    return parse(data, tenant)
