"""Workday candidate-experience JSON (CXS), the same endpoint the public career site calls.

POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
Pages of 20. The total is only filled on the first page. Posted dates are relative text
("Posted 3 Days Ago"), so we turn them into an approximate day; "30+ Days Ago" becomes 30 days.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import quote

from .. import geo
from ..model import Failed, Gone, make
from .base import check, slug_title

ATS = "workday"
KIND = "tenant"
WORKERS = 48
PRIORITY = 5
PAGE = 20
MAX_JOBS = 20000   # per site; a safety net, no real site is close


def _posted(text: str, today: date | None = None) -> str:
    today = today or date.today()
    t = (text or "").lower()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*days?", t)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    return ""


def _country_from_slug(path: str) -> tuple[str, str]:
    """externalPath looks like /job/Israel-Tel-Aviv/Title_REQ. Returns (location text, ISO code)."""
    m = re.match(r"/job/([^/]+)/", path or "")
    if not m:
        return "", ""
    parts = m.group(1).split("-")
    text = " ".join(parts)
    for n in (3, 2, 1):
        cand = " ".join(parts[:n]).lower()
        if cand in geo.NAME2CC:
            return text, geo.NAME2CC[cand]
    if parts[0].upper() in geo.VALID_CC and len(parts[0]) == 2 and parts[0].upper() != "IN":
        return text, parts[0].upper()
    if parts[0].upper() == "US" or (len(parts) > 1 and parts[0].upper() in geo.US_STATES and len(parts[0]) == 2):
        return text, "US"
    return text, geo.country_of(", ".join(parts), text)


def parse(data: dict, tenant: dict, today: date | None = None) -> list:
    out = []
    host = f"{tenant['tenant']}.{tenant['wd']}.myworkdayjobs.com"
    company = tenant.get("name") or slug_title(tenant["tenant"])
    for j in (data or {}).get("jobPostings", []):
        path = j.get("externalPath") or ""
        loc_text = j.get("locationsText") or ""
        slug_loc, slug_cc = _country_from_slug(path)
        multi = bool(re.match(r"\d+ locations?", loc_text.lower()))
        loc = slug_loc if multi or not loc_text else loc_text
        cc = geo.country_of(loc_text) if not multi and loc_text else ""
        cc = cc or slug_cc
        url = f"https://{host}/en-US/{quote(tenant['site'])}{path}"
        job = make(ATS, j.get("title"), company, [loc] + ([loc_text] if multi else []), url, _posted(j.get("postedOn", ""), today),
                   cc_hint=cc, workplace="remote" if "remote" in (loc_text + path).lower() else "")
        if job:
            out.append(job)
    return out


_TAIL = re.compile(r"\s*[-|:]?\s*\b(careers?|jobs?|career site|external|recruiting|candidate experience|opportunit\w*|portal|hiring|"
                   r"work with us|join us|search)\b.*$", re.I)


def company_name(html: str) -> str:
    """The career site's own title (og:title), minus words like Careers. Empty if there is none."""
    m = re.search(r'property="og:title"\s+content="([^"]+)"', html) or re.search(r'content="([^"]+)"\s+property="og:title"', html)
    if not m:
        return ""
    name = _TAIL.sub("", re.sub(r"&amp;", "&", m.group(1))).strip(" -|:")
    return name if 2 <= len(name) <= 60 else ""


def sites_from_robots(text: str, host: str) -> list[str]:
    """A Workday host's robots.txt names each public career site in its Sitemap lines: https://host/SITE/siteMap.xml"""
    out = []
    for m in re.finditer(r"(?im)^\s*sitemap:\s*https?://" + re.escape(host) + r"/([A-Za-z0-9_%-]+)/siteMap\.xml", text):
        if m.group(1) not in out and m.group(1).lower() not in ("wday", "login"):
            out.append(m.group(1))
    return out


def fetch(client, tenant: dict) -> list:
    if not tenant.get("site"):  # found from host names only: ask the host which career sites it has
        host = f"{tenant['tenant']}.{tenant['wd']}.myworkdayjobs.com"
        r = check(client.get(f"https://{host}/robots.txt", robots=False), f"workday/{tenant['key']}")
        sites = sites_from_robots(r.text, host)
        if not sites:
            raise Gone(f"workday/{tenant['key']}: no career site listed")
        rows, worked, last = [], [], None
        for site in sites[:3]:
            try:
                rows.extend(fetch(client, {**tenant, "site": site, "key": f"{tenant['key']}|{site.lower()}"}))
                worked.append(site)
            except (Gone, Failed) as e:   # one listed site may not be a public job site; try the others
                last = e
        if not worked:
            raise last or Gone(f"workday/{tenant['key']}: no usable career site")
        tenant["site"] = worked[0]
        return rows
    if not tenant.get("name"):
        page = client.get(f"https://{tenant['tenant']}.{tenant['wd']}.myworkdayjobs.com/en-US/{quote(tenant['site'])}")
        if page.status == 200:
            tenant["name"] = company_name(page.text)
    base = f"https://{tenant['tenant']}.{tenant['wd']}.myworkdayjobs.com/wday/cxs/{tenant['tenant']}/{tenant['site']}/jobs"
    rows, offset, total = [], 0, None
    while offset < MAX_JOBS:
        r = client.post(base, json={"appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": ""},
                        headers={"Accept": "application/json", "Content-Type": "application/json"})
        if r.status in (400, 422) and offset == 0:
            raise Gone(f"workday/{tenant['key']}: no such site (HTTP {r.status})")
        if r.status != 200 and offset > 0:
            break  # keep the pages already read
        r = check(r, f"workday/{tenant['key']}")
        d = r.json()
        if not isinstance(d, dict):
            raise Failed(f"workday/{tenant['key']}: not JSON")
        if total is None:
            total = int(d.get("total") or 0)
        page = d.get("jobPostings") or []
        rows.extend(parse(d, tenant))
        if not page or offset + PAGE >= total:
            break
        offset += PAGE
    return rows
