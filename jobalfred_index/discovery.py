"""Tenant discovery: turn URLs into (ats, key, data) tenants, and find URLs for free.

Free, deterministic sources:
  * Common Crawl CDX index (public, no key)
  * crt.sh certificate transparency (public, no key; flaky, so we retry and report)
  * seed lists copied from the reference repos (data/seeds.json)
  * links seen while fetching (a Workday site found via a company page, and so on)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import unquote

from .polite import Client

BAD_TOKENS = {
    "", "embed", "api", "static", "assets", "www", "app", "jobs", "job", "careers", "career", "login", "sso",
    "search", "company", "companies", "about", "j", "_next", "favicon.ico", "robots.txt", "sitemap.xml",
    "vanityurl", "v1", "v0", "oembed", "widget", "health", "status", "privacy", "terms", "en", "docs", "help",
    "support", "blog", "pricing", "product", "customers", "partners", "demo", "contact", "undefined", "null",
    "test", "demo-company", "cdn", "mail", "smtp", "ftp", "admin", "dashboard", "signin", "signup", "register",
}
SLUG = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,60}"


def _tok(s: str) -> str:
    s = unquote(s).strip().strip("/")
    return s


# (ats, compiled regex, builder(match)->(key, data))
def _gh(m):
    return m.group(1), {}


def _wd(m):
    host_tenant, wd, site = m.group(1), m.group(2), m.group(3)
    return f"{host_tenant}.{wd}|{site}", {"tenant": host_tenant, "wd": wd, "site": site}


def _oracle(m):
    return f"{m.group(1)}|{m.group(2)}", {"host": m.group(1), "site": m.group(2)}


def _comeet(m):
    return f"{m.group(1)}/{m.group(2)}", {"slug": m.group(1), "uid": m.group(2)}


def _sub(m):
    return m.group(1).lower(), {}


def _personio(m):
    return m.group(1).lower(), {"tld": m.group(2)}


def _success(m):
    return m.group(1), {"company": m.group(1)}


PATTERNS: list[tuple[str, re.Pattern, callable]] = [
    ("greenhouse", re.compile(rf"https?://(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_(?:board|app)\?(?:[^#]*&)?for=)?({SLUG})", re.I), _gh),
    ("greenhouse", re.compile(rf"https?://(?:boards|job-boards)\.eu\.greenhouse\.io/({SLUG})", re.I), lambda m: (m.group(1), {"eu": True})),
    ("lever", re.compile(rf"https?://jobs\.lever\.co/({SLUG})", re.I), _gh),
    ("lever-eu", re.compile(rf"https?://jobs\.eu\.lever\.co/({SLUG})", re.I), _gh),
    ("ashby", re.compile(rf"https?://jobs\.ashbyhq\.com/({SLUG})", re.I), _gh),
    ("workable", re.compile(rf"https?://apply\.workable\.com/({SLUG})", re.I), _gh),
    ("smartrecruiters", re.compile(rf"https?://(?:jobs|careers)\.smartrecruiters\.com/({SLUG})", re.I), _gh),
    ("recruitee", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.recruitee\.com", re.I), _sub),
    ("teamtailor", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.teamtailor\.com", re.I), _sub),
    ("personio", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.jobs\.personio\.(de|com)", re.I), _personio),
    ("bamboohr", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.bamboohr\.com/(?:careers|jobs)", re.I), _sub),
    ("breezy", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.breezy\.hr", re.I), _sub),
    ("rippling", re.compile(r"https?://ats\.rippling\.com/([a-z0-9][a-z0-9-]{0,80})/jobs", re.I), _gh),
    ("pinpoint", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.pinpointhq\.com", re.I), _sub),
    ("jazzhr", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.applytojob\.com", re.I), _sub),
    ("comeet", re.compile(r"https?://www\.comeet\.(?:com|co)/jobs/([A-Za-z0-9._-]+)/([A-Z0-9]{2,3}\.[A-Z0-9]{3,5})", re.I), _comeet),
    ("workday", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.(wd\d{1,3})\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Za-z]{2}/)?(?:wday/cxs/[^/]+/)?([A-Za-z0-9_%-]{2,80})", re.I), _wd),
    ("oracle", re.compile(r"https?://([a-z0-9-]+\.fa\.[a-z0-9-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[a-z-]+/sites/([A-Za-z0-9_]+)", re.I), _oracle),
    ("eightfold", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.eightfold\.ai", re.I), _sub),
    ("icims", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.icims\.com", re.I), _sub),
    ("successfactors", re.compile(r"https?://career\d*\.successfactors\.(?:com|eu)/(?:career|sfcareer/jobreqcareer)\?[^#]*?company=([A-Za-z0-9_]+)", re.I), _success),
    ("jobs2web", re.compile(r"https?://([a-z0-9][a-z0-9-]{0,60})\.jobs2web\.com", re.I), _sub),
]

SITE_BAD = {"wday", "login", "job", "details", "en-us", "login", "userhome", "refreshfacet", "talentcommunity",
            "sitemap.xml", "robots", "robots.txt", "favicon.ico", "assets", "sso", "wday-cxs", "undefined", "apply", "jobs", "jobs.rss", "search", "searchresults", "jobtutorial", "jobs.rss", "sitemap", "cxs", "d", "wday"}


def classify(url: str):
    """Yield (ats, key, data) for every tenant a URL points at."""
    for ats, rx, build in PATTERNS:
        m = rx.match(url)
        if not m:
            continue
        key, data = build(m)
        key = _tok(key)
        low = key.lower()
        if ats in ("workday",):
            site = data.get("site", "")
            if site.lower() in SITE_BAD or data.get("tenant", "").lower() in ("www", "community", "impl", "wd5", "wd1", "wd3"):
                continue
            data["site"] = unquote(site)
            key = f"{data['tenant'].lower()}.{data['wd'].lower()}|{data['site'].lower()}"
            yield ats, key, data
            continue
        if ats in ("oracle", "comeet", "successfactors"):
            yield ats, key, data
            continue
        if low in BAD_TOKENS or len(low) < 2 or "." in low and ats in ("greenhouse", "lever", "lever-eu", "ashby", "workable", "smartrecruiters", "rippling"):
            continue
        if ats in ("greenhouse", "lever", "lever-eu", "ashby", "workable", "smartrecruiters", "rippling"):
            yield ats, (key if ats in ("smartrecruiters", "ashby") else low), data
        else:
            if low in ("www", "api", "app", "careers", "jobs", "support", "help", "blog", "status", "mail", "cdn", "static",
                       "assets", "docs", "developers", "partners", "login", "my", "go", "info", "e", "en"):
                continue
            yield ats, low, data


# -- Common Crawl ----------------------------------------------------------
CDX_BASE = "https://index.commoncrawl.org"

# (label, url query). Subdomain tenants use a domain wildcard; path tenants use a prefix.
CDX_QUERIES = [
    ("greenhouse", "boards.greenhouse.io/*"),
    ("greenhouse", "job-boards.greenhouse.io/*"),
    ("greenhouse", "boards.eu.greenhouse.io/*"),
    ("lever", "jobs.lever.co/*"),
    ("lever-eu", "jobs.eu.lever.co/*"),
    ("ashby", "jobs.ashbyhq.com/*"),
    ("workable", "apply.workable.com/*"),
    ("workday", "*.myworkdayjobs.com"),
    ("smartrecruiters", "jobs.smartrecruiters.com/*"),
    ("recruitee", "*.recruitee.com"),
    ("teamtailor", "*.teamtailor.com"),
    ("personio", "*.jobs.personio.de"),
    ("personio", "*.jobs.personio.com"),
    ("bamboohr", "*.bamboohr.com"),
    ("breezy", "*.breezy.hr"),
    ("rippling", "ats.rippling.com/*"),
    ("pinpoint", "*.pinpointhq.com"),
    ("jazzhr", "*.applytojob.com"),
    ("comeet", "www.comeet.com/jobs/*"),
    ("oracle", "*.oraclecloud.com"),
    ("eightfold", "*.eightfold.ai"),
    ("icims", "*.icims.com"),
    ("successfactors", "career*.successfactors.com/*"),
    ("jobs2web", "*.jobs2web.com"),
]


def latest_crawls(client: Client, n: int) -> list[str]:
    r = client.get(f"{CDX_BASE}/collinfo.json", robots=False)
    if not r.ok:
        return []
    return [c["id"] for c in (r.json() or [])][:n]


def _patient(client, url, **kw):
    """Common Crawl answers 503 or refuses connections when asked too fast: wait and retry, then give up."""
    for wait in (0, 20):
        if wait:
            time.sleep(wait)
        r = client.get(url, **kw)
        if r.status in (200, 404):
            return r
    return r


def cdx_pages(client: Client, crawl: str, query: str) -> int:
    r = _patient(client, f"{CDX_BASE}/{crawl}-index", params={"url": query, "showNumPages": "true", "output": "json"}, robots=False, timeout=60)
    if not r.ok:
        return 0
    d = r.json() or {}
    return int(d.get("pages", 0))


def cdx_fetch_page(client: Client, crawl: str, query: str, page: int) -> list[str]:
    r = _patient(client, f"{CDX_BASE}/{crawl}-index",
                   params={"url": query, "output": "json", "fl": "url", "page": str(page)}, robots=False, timeout=100)
    if not r.ok:
        return []
    urls = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            urls.append(json.loads(line)["url"])
        except (ValueError, KeyError):
            continue
    return urls


def run_cdx(client: Client, state, crawls: list[str], budget_s: float, log, max_pages_per_query: int = 40) -> dict:
    """Walk crawls newest first, query by query. Returns {ats: new_tenants}."""
    t0 = time.monotonic()
    new: dict[str, int] = {}
    stats = {"queries": 0, "pages": 0, "urls": 0, "errors": 0}
    consecutive = 0
    for crawl in crawls:
        for label, query in CDX_QUERIES:
            if time.monotonic() - t0 > budget_s:
                log(f"cdx: time box reached after {stats}")
                return {"new": new, **stats}
            pages = cdx_pages(client, crawl, query)
            stats["queries"] += 1
            if pages == 0:
                stats["errors"] += 1
                consecutive += 1
                if consecutive >= 4:
                    log("cdx: four queries in a row got no answer; Common Crawl is refusing us, stopping discovery from it")
                    return {"new": new, **stats, "stopped": "no answer"}
                continue
            consecutive = 0
            got = 0
            for page in range(min(pages, max_pages_per_query)):
                if time.monotonic() - t0 > budget_s:
                    break
                urls = cdx_fetch_page(client, crawl, query, page)
                stats["pages"] += 1
                stats["urls"] += len(urls)
                for u in urls:
                    for ats, key, data in classify(u):
                        if state.add_tenant(ats, key, data, f"cdx:{crawl}"):
                            new[ats] = new.get(ats, 0) + 1
                            got += 1
            log(f"cdx {crawl} {query}: {pages} pages, +{got} new tenants")
    return {"new": new, **stats}


# -- Certificate transparency ----------------------------------------------
CRT_QUERIES = [
    ("recruitee", "%.recruitee.com"), ("teamtailor", "%.teamtailor.com"), ("breezy", "%.breezy.hr"),
    ("bamboohr", "%.bamboohr.com"), ("pinpoint", "%.pinpointhq.com"), ("jazzhr", "%.applytojob.com"),
    ("personio", "%.jobs.personio.de"), ("personio", "%.jobs.personio.com"), ("workday", "%.myworkdayjobs.com"),
    ("eightfold", "%.eightfold.ai"), ("icims", "%.icims.com"), ("jobs2web", "%.jobs2web.com"),
]


def run_crtsh(client: Client, state, budget_s: float, log) -> dict:
    t0 = time.monotonic()
    out = {"queries": 0, "ok": 0, "names": 0, "new": {}}
    for ats, q in CRT_QUERIES:
        if time.monotonic() - t0 > budget_s:
            break
        out["queries"] += 1
        names = None
        for attempt in range(3):
            r = client.get("https://crt.sh/", params={"q": q, "output": "json", "exclude": "expired"}, robots=False)
            if r.ok:
                data = r.json()
                if isinstance(data, list):
                    names = data
                    break
            time.sleep(5 * (attempt + 1))
        if names is None:
            log(f"crt.sh {q}: no usable answer")
            continue
        out["ok"] += 1
        got = 0
        for rec in names:
            for n in str(rec.get("name_value", "")).splitlines():
                n = n.strip().lstrip("*.").lower()
                if not n:
                    continue
                out["names"] += 1
                for a, key, data in classify("https://" + n + "/"):
                    if a == "workday":
                        continue  # a bare host has no site name; Workday comes from CDX and seeds
                    if state.add_tenant(a, key, data, "crt.sh"):
                        out["new"][a] = out["new"].get(a, 0) + 1
                        got += 1
        log(f"crt.sh {q}: {len(names)} certs, +{got} new tenants")
    return out


# -- Seeds -------------------------------------------------------------------
def load_seeds(state, path: Path, log) -> dict:
    new: dict[str, int] = {}
    if not path.exists():
        return new
    doc = json.loads(path.read_text())
    for t in doc.get("tenants", []):
        if state.add_tenant(t["ats"], t["key"], t.get("data"), t.get("source", "seed")):
            new[t["ats"]] = new.get(t["ats"], 0) + 1
    for u in doc.get("urls", []):
        for ats, key, data in classify(u):
            if state.add_tenant(ats, key, data, "seed-url"):
                new[ats] = new.get(ats, 0) + 1
    log(f"seeds: {sum(new.values())} new tenants {new}")
    return new
