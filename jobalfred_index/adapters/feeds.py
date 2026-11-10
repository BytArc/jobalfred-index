"""Open job feeds that allow reuse without a key.

Each feed asks for attribution and a link back. We keep the feed's own job URL (as the terms
require), mark every row with the feed name in the ATS field, and list the terms in ATTRIBUTION.md.
Feed rows lose to the employer's own ATS row for the same role when the index is deduplicated.
"""
from __future__ import annotations

import re
import time

from ..model import Failed, make
from .base import check, get_json, parse_xml, txt

# These are separate sources, one adapter entry each.
KIND = "single"
WORKERS = 1
PRIORITY = 1


def remotive_parse(d: dict, tenant=None) -> list:
    out = []
    for j in (d or {}).get("jobs", []):
        job = make("remotive", j.get("title"), j.get("company_name"), [j.get("candidate_required_location") or ""],
                   j.get("url"), j.get("publication_date"), remote_hint=True, desc=j.get("description") or "")
        if job:
            out.append(job)
    return out


def remotive_fetch(client, tenant=None):
    return remotive_parse(get_json(client, "https://remotive.com/api/remote-jobs", "remotive"), tenant)


def arbeitnow_parse(d: dict, tenant=None) -> list:
    out = []
    for j in (d or {}).get("data", []):
        job = make("arbeitnow", j.get("title"), j.get("company_name"), [j.get("location") or ""],
                   j.get("url"), j.get("created_at"), remote_hint=bool(j.get("remote")), desc=j.get("description") or "")
        if job:
            out.append(job)
    return out


def arbeitnow_fetch(client, tenant=None):
    rows = []
    for page in range(1, 31):
        d = get_json(client, "https://www.arbeitnow.com/api/job-board-api", "arbeitnow", params={"page": page})
        part = arbeitnow_parse(d)
        rows.extend(part)
        if not (d.get("data") and (d.get("links") or {}).get("next")):
            break
    return rows


def remoteok_parse(d: list, tenant=None) -> list:
    out = []
    for j in d or []:
        if not isinstance(j, dict) or "position" not in j:
            continue
        job = make("remoteok", j.get("position"), j.get("company"), [j.get("location") or ""], j.get("url") or j.get("apply_url"),
                   j.get("date"), remote_hint=True, smin=j.get("salary_min") or None, smax=j.get("salary_max") or None,
                   cur="USD" if j.get("salary_min") else "", desc=j.get("description") or "")
        if job:
            out.append(job)
    return out


def remoteok_fetch(client, tenant=None):
    return remoteok_parse(get_json(client, "https://remoteok.com/api", "remoteok"), tenant)


def himalayas_parse(d: dict, tenant=None) -> list:
    out = []
    for j in (d or {}).get("jobs", []):
        annual = str(j.get("salaryPeriod", "")).lower() in ("annual", "yearly", "year")
        job = make("himalayas", j.get("title"), j.get("companyName"), list(j.get("locationRestrictions") or []),
                   j.get("applicationLink") or j.get("guid"), j.get("pubDate"), remote_hint=True,
                   smin=j.get("minSalary") if annual else None, smax=j.get("maxSalary") if annual else None,
                   cur=j.get("currency") or "", native=j.get("seniority"), desc=j.get("excerpt") or "")
        if job:
            out.append(job)
    return out


def himalayas_fetch(client, tenant=None, max_requests: int = 400):
    rows, cursor = [], None
    for _ in range(max_requests):
        params = {"limit": 20}
        if cursor:
            params["cursor"] = cursor
        d = get_json(client, "https://himalayas.app/jobs/api", "himalayas", params=params)
        rows.extend(himalayas_parse(d))
        cursor = d.get("nextCursor")
        if not cursor or not d.get("jobs"):
            break
    return rows


def jobicy_parse(d: dict, tenant=None) -> list:
    out = []
    for j in (d or {}).get("jobs", []):
        annual = str(j.get("salaryPeriod", "")).lower() in ("yearly", "year", "annual")
        geo = j.get("jobGeo") or ""
        job = make("jobicy", j.get("jobTitle"), j.get("companyName"), [geo], j.get("url"), j.get("pubDate"),
                   remote_hint=True, smin=j.get("salaryMin") if annual else None, smax=j.get("salaryMax") if annual else None,
                   cur=j.get("salaryCurrency") or "", native=j.get("jobLevel"), desc=j.get("jobDescription") or "")
        if job:
            out.append(job)
    return out


def jobicy_fetch(client, tenant=None):
    d = get_json(client, "https://jobicy.com/api/v2/remote-jobs", "jobicy", params={"count": 100})
    return jobicy_parse(d)


def muse_parse(d: dict, tenant=None) -> list:
    out = []
    for j in (d or {}).get("results", []):
        locs = [l.get("name") or "" for l in j.get("locations") or []]
        url = (j.get("refs") or {}).get("landing_page")
        job = make("themuse", j.get("name"), (j.get("company") or {}).get("name"), locs, url, j.get("publication_date"), native=[l.get("name") for l in j.get("levels") or []], desc=j.get("contents") or "")
        if job:
            out.append(job)
    return out


def muse_fetch(client, tenant=None, max_pages: int = 99):   # the API refuses page 100 and above
    rows = []
    for page in range(1, max_pages + 1):
        d = get_json(client, "https://www.themuse.com/api/public/jobs", "themuse", params={"page": page})
        rows.extend(muse_parse(d))
        if page >= int(d.get("page_count") or 0):
            break
    return rows


def wwr_parse(text: str, tenant=None) -> list:
    root = parse_xml(text)
    out = []
    for it in root.iter("item"):
        title = txt(it, "title")
        company, _, role = title.partition(": ")
        if not role:
            company, role = "", title
        region = txt(it, "region")
        job = make("weworkremotely", role, company, [region or txt(it, "country")], txt(it, "link"), txt(it, "pubDate"),
                   remote_hint=True, desc=txt(it, "description"))
        if job:
            out.append(job)
    return out


WWR_FEEDS = ["remote-jobs", "categories/remote-programming-jobs", "categories/remote-design-jobs",
             "categories/remote-marketing-jobs", "categories/remote-sales-and-marketing-jobs",
             "categories/remote-customer-support-jobs", "categories/remote-product-jobs",
             "categories/remote-devops-sysadmin-jobs", "categories/all-other-remote-jobs",
             "categories/remote-management-and-finance-jobs"]


def wwr_fetch(client, tenant=None):
    rows = []
    for feed in WWR_FEEDS:
        r = client.get(f"https://weworkremotely.com/{feed}.rss")
        if r.status == 200:
            rows.extend(wwr_parse(r.text))
        elif feed == WWR_FEEDS[0]:
            check(r, "weworkremotely")
    return rows


# name -> fetch function; the pipeline treats each as its own source
FEEDS = {
    "remotive": remotive_fetch, "arbeitnow": arbeitnow_fetch, "remoteok": remoteok_fetch,
    "himalayas": himalayas_fetch, "jobicy": jobicy_fetch, "themuse": muse_fetch, "weworkremotely": wwr_fetch,
}
