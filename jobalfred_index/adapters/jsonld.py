"""Generic adapter: sitemap, then schema.org JobPosting JSON-LD on each job page.

Employers publish JobPosting markup so that search engines can read their jobs
(https://developers.google.com/search/docs/appearance/structured-data/job-posting).
Used for career sites with no API: iCIMS, SuccessFactors, Taleo, Shopify and so on.

Only crawlable pages are read: robots.txt is checked for the sitemap and for every page.
Tenant data: {"sitemaps": [...], "name": "Company", "include": "regex", "max": 1500}
"""
from __future__ import annotations

import gzip
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import urlsplit

from ..model import Failed, Gone, make, day
from .base import check, parse_xml, slug_title

ATS = "jsonld"
KIND = "tenant"
WORKERS = 10
PRIORITY = 50
DEFAULT_MAX = 400
JOBLIKE = re.compile(r"/(jobs?|careers?|positions?|vacanc(?:y|ies)|openings?|requisition|opportunit\w*|postings?|stellen|emploi|vagas?)/[^/]+", re.I)
SKIP_PAGE = re.compile(r"/(search|results|category|categories|department|location|locations|tag|teams?)/?($|\?)", re.I)

LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)


def _flatten(node):
    if isinstance(node, list):
        for n in node:
            yield from _flatten(n)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _flatten(node["@graph"])


def postings(html: str) -> list[dict]:
    out = []
    for raw in LD.findall(html):
        raw = raw.strip()
        try:
            doc = json.loads(raw)
        except ValueError:
            try:
                doc = json.loads(re.sub(r"[\x00-\x1f]", " ", raw))
            except ValueError:
                continue
        for n in _flatten(doc):
            t = n.get("@type") or n.get("type")
            ts = t if isinstance(t, list) else [t]
            if "JobPosting" in ts:
                out.append(n)
    return out


def _s(v) -> str:
    if isinstance(v, dict):
        return str(v.get("name") or v.get("@id") or "")
    return str(v or "")


def to_job(p: dict, page_url: str, company_default: str):
    locs, cc = [], ""
    jl = p.get("jobLocation")
    for l in (jl if isinstance(jl, list) else [jl]) if jl else []:
        if not isinstance(l, dict):
            continue
        a = l.get("address") or {}
        if isinstance(a, str):
            locs.append(a)
            continue
        country = _s(a.get("addressCountry"))
        cc = cc or (country if len(country) == 2 else "")
        locs.append(", ".join(x for x in (_s(a.get("addressLocality")), _s(a.get("addressRegion")), country) if x))
    remote = "TELECOMMUTE" in str(p.get("jobLocationType", "")).upper()
    if remote and not locs:
        req = p.get("applicantLocationRequirements")
        for r in (req if isinstance(req, list) else [req]) if req else []:
            locs.append(_s(r))
    valid = day(p.get("validThrough"))
    if valid and valid < date.today().isoformat():
        return None
    sal = p.get("baseSalary") or {}
    val = sal.get("value") if isinstance(sal, dict) else None
    smin = smax = None
    unit = ""
    cur = ""
    if isinstance(val, dict):
        smin, smax = val.get("minValue") or val.get("value"), val.get("maxValue") or val.get("value")
        unit = str(val.get("unitText", "")).upper()
        cur = sal.get("currency") or ""
    if unit and unit not in ("YEAR", "ANNUAL", "YEARLY"):
        smin = smax = None
        cur = ""
    org = p.get("hiringOrganization")
    company = _s(org) or company_default
    return make(ATS, p.get("title"), company, locs, page_url, p.get("datePosted"),
                cc_hint=cc, remote_hint=remote, smin=smin, smax=smax, cur=cur)


def parse(html: str, page_url: str, tenant: dict) -> list:
    out = []
    default = tenant.get("name") or slug_title(urlsplit(page_url).hostname.split(".")[-2])
    for p in postings(html):
        j = to_job(p, page_url, default)
        if j:
            out.append(j)
    return out


def parse_sitemap(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Returns (child sitemap urls, [(page url, lastmod)])."""
    root = parse_xml(text)
    kids = [(e.findtext("loc") or "").strip() for e in root.iter("sitemap")]
    pages = [((e.findtext("loc") or "").strip(), (e.findtext("lastmod") or "")) for e in root.iter("url")]
    return [k for k in kids if k], [p for p in pages if p[0]]


def collect_urls(client, sitemaps: list[str], include: str | None, limit: int) -> list[str]:
    rx = re.compile(include) if include else None
    seen, pages, queue, fetched = set(), [], list(sitemaps), 0
    while queue and fetched < 60:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        r = client.get(sm)
        if r.status in (404, 410):
            continue
        if r.status != 200:
            raise Failed(f"sitemap {sm}: HTTP {r.status} {r.reason}")
        fetched += 1
        body = r.content
        if sm.endswith(".gz") or body[:2] == b"\x1f\x8b":
            try:
                body = gzip.decompress(body)
            except OSError:
                pass
        try:
            kids, pgs = parse_sitemap(body.decode("utf-8", "replace"))
        except Exception:
            continue
        queue.extend(kids)
        pages.extend(pgs)
    chosen = [(u, m) for u, m in pages if (rx.search(u) if rx else JOBLIKE.search(urlsplit(u).path) and not SKIP_PAGE.search(urlsplit(u).path))]
    chosen.sort(key=lambda x: x[1], reverse=True)
    return [u for u, _ in chosen[:limit]]


def fetch(client, tenant: dict) -> list:
    sitemaps = tenant.get("sitemaps") or []
    if not tenant.get("host"):
        suffix = {"icims": "icims.com", "jobs2web": "jobs2web.com"}.get(tenant.get("_ats", ""), "")
        if suffix:
            tenant = {**tenant, "host": f"{tenant['key']}.{suffix}"}
    if not sitemaps:
        host = tenant.get("host")
        from ..polite import family
        # robots.txt is cached per platform family, so its Sitemap lines belong to one sample tenant, not to this host
        sitemaps = ([f"https://{host}/sitemap.xml"] if family(host) != host
                    else client.robots_sitemaps("https", host) or [f"https://{host}/sitemap.xml"])
    urls = collect_urls(client, sitemaps, tenant.get("include"), int(tenant.get("max") or DEFAULT_MAX))
    if not urls:
        raise Gone(f"jsonld/{tenant['key']}: no job pages in sitemap")

    def one(u):
        r = client.get(u)
        if r.status != 200:
            return []
        return parse(r.text, r.url or u, tenant)

    rows = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for part in ex.map(one, urls):
            rows.extend(part)
    return rows
