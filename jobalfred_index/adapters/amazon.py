"""Amazon.jobs public search JSON (https://www.amazon.jobs/en/search.json), the call the site itself makes.

One query returns at most 10000 hits, so we walk country by country, and split the US by job category.
"""
from __future__ import annotations

import json

from ..model import Failed, make
from .base import check

ATS = "amazon"
KIND = "single"
WORKERS = 1
PRIORITY = 2
URL = "https://www.amazon.jobs/en/search.json"
PAGE = 100
COUNTRIES = ("USA IND GBR DEU FRA ESP ITA IRL NLD POL LUX ROU PRT CAN MEX BRA JPN SGP AUS CHN ARE ZAF SAU EGY TUR SWE "
             "AUT CZE BEL CRI CHL COL ARG ISR KOR MYS PHL VNM HKG TWN NZL BGR GRC HUN DNK NOR FIN CHE PER PAN MAR NGA "
             "KEN IDN THA PAK BGD LKA QAT KWT BHR").split()
US_CATEGORIES = ("software-development operations-it-support-engineering fulfillment-operations-management "
                 "project-program-product-management-technical customer-service business-intelligence data-science "
                 "finance-accounting human-resources sales-advertising-account-management marketing-pr "
                 "hardware-development machine-learning-science research-science solutions-architect "
                 "systems-quality-security-engineering supply-chain-transportation-management legal "
                 "fulfillment-operations-management-2 facilities-maintenance-real-estate editorial-writing-content-management "
                 "business-merchant-development buying-planning-instock-management audio-video-photography-production "
                 "investigation-loss-prevention-security administrative-support ads-product-management "
                 "project-program-product-management-non-tech medical-health-safety").split()


def _cc(j: dict) -> str:
    for raw in j.get("locations") or []:
        try:
            return json.loads(raw).get("countryIso2a") or ""
        except (ValueError, AttributeError):
            continue
    return ""


def _native(j: dict):
    """Amazon flags interns and people managers on the posting itself."""
    if j.get("is_intern"):
        return "intern"
    if j.get("is_manager"):
        return "manager"
    return None


def parse(data: dict, tenant=None) -> list:
    out = []
    for j in (data or {}).get("jobs", []):
        title = j.get("title")
        job = make(ATS, title, "AWS" if j.get("business_category") == "aws" else "Amazon", [j.get("location") or ""],
                   f"https://www.amazon.jobs{j['job_path']}" if j.get("job_path") else "", j.get("posted_date"),
                   cc_hint=_cc(j), native=_native(j),
                   desc=" ".join(str(j.get(k) or "") for k in ("basic_qualifications", "description_short", "description")))
        if job:
            out.append(job)
    return out


def fetch(client, tenant=None) -> list:
    seen, rows = set(), []

    def walk(extra: dict) -> int:
        offset, total = 0, 0
        while offset < 10000:
            r = client.get(URL, params={"offset": offset, "result_limit": PAGE, "sort": "recent", **extra})
            if r.status != 200:
                if offset == 0:
                    check(r, "amazon")
                return total
            d = r.json() or {}
            total = int(d.get("hits") or 0)
            page = d.get("jobs") or []
            for raw in page:
                key = raw.get("id_icims") or raw.get("job_path")
                if key in seen:
                    continue
                seen.add(key)
                rows.extend(parse({"jobs": [raw]}))
            offset += PAGE
            if not page or offset >= total:
                break
        return total

    for c in COUNTRIES:
        total = walk({"normalized_country_code[]": c})
        if c == "USA" and total >= 10000:
            for cat in US_CATEGORIES:
                walk({"normalized_country_code[]": c, "category[]": cat})
    if not rows:
        raise Failed("amazon: no rows")
    return rows
