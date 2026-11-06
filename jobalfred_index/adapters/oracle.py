"""Oracle Recruiting Cloud (Candidate Experience) public REST, the call the career site makes.

GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&finder=findReqs;siteNumber=...
"""
from __future__ import annotations

from ..model import Failed, Gone, make
from .base import check, slug_title

ATS = "oracle"
KIND = "tenant"
WORKERS = 12
PRIORITY = 15
PAGE = 50
MAX_JOBS = 20000


def parse(data: dict, tenant: dict) -> list:
    out = []
    host, site = tenant["host"], tenant["site"]
    company = tenant.get("name") or slug_title(host.split(".")[0])
    for item in (data or {}).get("items", []):
        for j in item.get("requisitionList") or []:
            locs = [j.get("PrimaryLocation") or ""] + [s.get("Name") or "" for s in j.get("secondaryLocations") or []]
            wt = str(j.get("WorkplaceTypeCode") or j.get("WorkplaceType") or "").lower()
            workplace = "remote" if "remote" in wt else ("hybrid" if "hybrid" in wt else "")
            job = make(ATS, j.get("Title"), company, locs,
                       f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j.get('Id')}",
                       j.get("PostedDate"), cc_hint=j.get("PrimaryLocationCountry") or "", workplace=workplace)
            if job:
                out.append(job)
    return out


def active_sites(client, host: str, key: str) -> list[str]:
    r = check(client.get(f"https://{host}/hcmRestApi/resources/latest/recruitingCESites",
                         params={"onlyData": "true", "limit": "50"}, headers={"Accept": "application/json"}), f"oracle/{key}")
    d = r.json() or {}
    sites = [i.get("SiteNumber") for i in d.get("items", []) if i.get("StatusCode") == "ORA_ACTIVE" and i.get("SiteNumber")]
    return sites[:3]


def fetch(client, tenant: dict) -> list:
    if not tenant.get("site"):  # found from the host name only: ask the host which career sites are active
        sites = active_sites(client, tenant["host"], tenant["key"])
        if not sites:
            raise Gone(f"oracle/{tenant['key']}: no active career site")
        rows = []
        for site in sites:
            rows.extend(fetch(client, {**tenant, "site": site}))
        return rows
    url = f"https://{tenant['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    rows, offset = [], 0
    while offset < MAX_JOBS:
        finder = f"findReqs;siteNumber={tenant['site']},limit={PAGE},offset={offset},sortBy=POSTING_DATES_DESC"
        r = check(client.get(url, params={"onlyData": "true", "expand": "requisitionList.secondaryLocations", "finder": finder},
                             headers={"Accept": "application/json"}), f"oracle/{tenant['key']}")
        d = r.json()
        if not isinstance(d, dict):
            raise Failed(f"oracle/{tenant['key']}: not JSON")
        items = d.get("items") or []
        total = int(items[0].get("TotalJobsCount") or 0) if items else 0
        page = parse(d, tenant)
        n_raw = len(items[0].get("requisitionList") or []) if items else 0
        rows.extend(page)
        offset += PAGE
        if n_raw == 0 or offset >= total:
            break
    return rows
