"""European VC-backed startups: find each company's careers system from its own website, and mark its rows.

A company is given as its website. We read its homepage and, when one is linked, its careers page (robots.txt obeyed,
our own User-Agent, the polite client's pacing), and look for the applicant-tracking system the page links to or
embeds. A found ATS becomes a tenant that the daily run fetches like any other. Career pages with schema.org
JobPosting markup and no known ATS become a `jsonld` tenant read page by page.

Nothing here reads LinkedIn, an aggregator or a VC portfolio job board: a LinkedIn jobs link is only noted, never fetched.

data/startups_eu.json (committed) holds the tenants found this way and the companies they belong to (name, domain,
headquarters country, and the evidence that venture investors back them). vceu.py turns it into vc-eu.json.gz.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .discovery import classify

# -- domains ------------------------------------------------------------------------------------------------------
# Two-label public suffixes we meet on European and startup sites, plus hosting platforms where each customer
# is its own subdomain (so "acme.webflow.io" is the company, not "webflow.io").
_SUFFIX2 = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "ltd.uk", "plc.uk", "net.uk", "com.pl", "com.pt", "com.es", "com.gr",
    "com.cy", "com.mt", "co.at", "or.at", "co.il", "com.tr", "com.ua", "com.br", "com.au", "co.in", "co.jp", "com.mx",
    "co.za", "com.sg", "com.ar", "com.co", "co.nz", "com.hr", "com.ro", "co.hu", "com.ee", "com.lv", "com.lt", "co.no",
    "co.dk", "co.ee", "com.fr", "com.de", "com.it", "com.ng", "com.eg", "co.ke", "com.hk", "com.tw", "co.kr", "com.cn",
    "webflow.io", "framer.website", "framer.ai", "framer.app", "github.io", "notion.site", "wixsite.com", "squarespace.com",
    "herokuapp.com", "vercel.app", "netlify.app", "pages.dev", "carrd.co", "super.site", "softr.app", "bubbleapps.io",
}


def host_of(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    try:
        h = (urlsplit(url).hostname or "").lower().strip(".")
    except ValueError:
        return ""
    return h


def registrable(host_or_url: str) -> str:
    """example.com from https://www.careers.example.com/x; acme.co.uk from jobs.acme.co.uk."""
    h = host_of(host_or_url) if ("/" in host_or_url or ":" in host_or_url) else (host_or_url or "").lower().strip(".")
    if not h or re.fullmatch(r"[\d.]+", h):
        return ""
    parts = h.split(".")
    if len(parts) < 2:
        return ""
    keep = 3 if ".".join(parts[-2:]) in _SUFFIX2 else 2
    return ".".join(parts[-keep:]) if len(parts) >= keep else h


# -- careers links ------------------------------------------------------------------------------------------------
_CAREER_WORDS = (r"careers?|jobs?|join(?:[-_ ]?(?:us|the[-_ ]?team|our[-_ ]?team))?|work[-_ ]?(?:with|for)[-_ ]?us|working[-_ ]?at|"
                 r"vacanc(?:y|ies)|open[-_ ]?(?:positions|roles)|openings|hiring|we[-_ ]?are[-_ ]?hiring|"
                 r"karriere|stellen(?:angebote)?|jobangebote|emplois?|carri[eè]res?|recrutement|nous[-_ ]?rejoindre|rejoignez[-_ ]?nous|"
                 r"trabaja[-_ ]?con[-_ ]?nosotros|empleo|carreras|[uú]nete|lavora[-_ ]?con[-_ ]?noi|carriere|posizioni[-_ ]?aperte|"
                 r"vacatures|werken[-_ ]?bij|carreiras|trabalhe[-_ ]?conosco|junte[-_ ]?se|praca|kariera|rekrytointi|ura|"
                 r"lediga[-_ ]?tjanster|jobb(?:a)?|karri[aä]r|stillinger|ledige[-_ ]?stillinger|arbejd(?:e|sliv)?")
_CAREER_PATH = re.compile(rf"(?i)(?:^|/)(?:{_CAREER_WORDS})(?:/|$|\.html?$|\?|#)")
_CAREER_TEXT = re.compile(r"(?i)^\s*(?:careers?|jobs?|join\s+(?:us|the\s+team|our\s+team)|we.?re\s+hiring|work\s+(?:with|for)\s+us|"
                          r"open\s+(?:positions|roles)|vacancies|karriere|jobs?\s*&\s*karriere|stellenangebote|carri[eè]res?|"
                          r"emplois?|nous\s+rejoindre|rejoignez.nous|recrutement|empleo|trabaja\s+con\s+nosotros|[uú]nete|carreras|"
                          r"lavora\s+con\s+noi|carriere|vacatures|werken\s+bij|carreiras|trabalhe\s+conosco|kariera|praca|"
                          r"lediga\s+tj[aä]nster|jobba\s+hos\s+oss|karri[aä]r|ledige\s+stillinger|hiring)\s*[!→›>]*\s*$")
_ANCHOR = re.compile(r"<a\b([^>]{0,2000})>(.{0,3000}?)</a>", re.I | re.S)
_HREF = re.compile(r"""href\s*=\s*["']([^"'#][^"']*)["']""", re.I)
_URL = re.compile(r"https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s\"'<>\\)\]}]*)?")


def careers_links(html: str, base_url: str) -> list[str]:
    """Careers pages a homepage links to: on the company's own domain (any subdomain) or on an ATS host.
    Best first: an anchor whose text says careers beats a path that says careers."""
    domain = registrable(base_url)
    scored: dict[str, int] = {}
    for attrs, inner in _ANCHOR.findall(html or ""):
        m = _HREF.search(attrs)
        if not m:
            continue
        href = m.group(1).strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(base_url, href)
        host = host_of(url)
        path = urlsplit(url).path or "/"
        text = re.sub(r"<[^>]+>", " ", inner)
        text = re.sub(r"\s+", " ", text).strip()
        score = 0
        if _CAREER_TEXT.match(text):
            score += 3
        if _CAREER_PATH.search(path) and not re.search(r"(?i)/(blog|news|press|posts?|article)s?/", path):
            score += 2
        sub = host.split(".")[0]
        if registrable(host) == domain and sub in ("careers", "jobs", "career", "karriere", "join", "work", "hiring", "talent"):
            score += 3
        if not score:
            continue
        if registrable(host) != domain and not list(classify(url)) and not DETECT_ONLY_RX.search(url):
            continue  # a careers link to someone else's site that is not an ATS: not this company's page
        url = url.split("#", 1)[0]
        scored[url] = max(scored.get(url, 0), score)
    return [u for u, _ in sorted(scored.items(), key=lambda kv: -kv[1])]


# -- ATS detection ------------------------------------------------------------------------------------------------
# Patterns the URL classifier in discovery.py does not cover (API and embed URLs of ATSs we have adapters for).
_EXTRA = [
    ("greenhouse", re.compile(r"(?i)greenhouse\.io/embed/job_board/js\?(?:[^\"'<>\s]*&)?for=([A-Za-z0-9_.-]+)")),
    ("greenhouse", re.compile(r"(?i)boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_.-]+)")),
    ("lever", re.compile(r"(?i)//api\.lever\.co/v0/postings/([A-Za-z0-9_.-]+)")),
    ("lever-eu", re.compile(r"(?i)//api\.eu\.lever\.co/v0/postings/([A-Za-z0-9_.-]+)")),
    ("ashby", re.compile(r"(?i)api\.ashbyhq\.com/posting-api/job-board/([A-Za-z0-9_.%-]+)")),
    ("workable", re.compile(r"(?i)apply\.workable\.com/api/v[0-9]/(?:widget/)?accounts/([A-Za-z0-9_-]+)")),
    ("workable", re.compile(r"(?i)//(?!www\.|apply\.|jobs\.|resources\.|help\.|api\.)([a-z0-9][a-z0-9-]{1,60})\.workable\.com")),
    ("bamboohr", re.compile(r"(?i)//(?!www\.|api\.|help\.|partners\.|marketplace\.)([a-z0-9][a-z0-9-]{1,60})\.bamboohr\.com/js/embed")),
]
_EXTRA_NEEDLE = ["greenhouse.io/embed", "boards-api.greenhouse", "api.lever.co", "api.eu.lever.co", "api.ashbyhq.com",
                 "apply.workable.com/api", ".workable.com", ".bamboohr.com/js/embed"]
# embeds configured in a page script rather than by URL
_SCRIPT_EMBEDS = [
    ("lever", "leverjobsoptions", re.compile(r"leverJobsOptions\s*=\s*\{[^}]{0,200}?accountName\s*:\s*[\"']([A-Za-z0-9_.-]+)", re.I)),
    ("bamboohr", "bamboohr", re.compile(r"id=[\"']BambooHR[\"'][^>]{0,80}data-domain=[\"']([a-z0-9][a-z0-9-]{1,60})\.bamboohr\.com", re.I)),
]
_BAD_KEYS = {"embed", "api", "v1", "jobs", "careers", "job", "www", "widget", "accounts", "js", "posting-api", "job-board"}

# ATSs and career-site hosts we can recognise but have no adapter for (or must not read). Counted, not fetched.
DETECT_ONLY = [
    ("hibob", r"([a-z0-9][a-z0-9-]*)\.careers\.hibob\.com"),
    ("factorial", r"([a-z0-9][a-z0-9-]*)\.factorialhr\.[a-z]{2,3}/?(?:[\"'#?]|$|job)"),
    ("homerun", r"([a-z0-9][a-z0-9-]*)\.homerun\.co\b"),
    ("welcometothejungle", r"welcometothejungle\.com/[a-z]{2}/companies/([A-Za-z0-9_-]+)"),
    ("welcomekit", r"([a-z0-9][a-z0-9-]*)\.welcomekit\.co"),
    ("jobylon", r"(?:emp|jobs)\.jobylon\.com/(?:[a-z]{2}/)?(?:companies|jobs)/([A-Za-z0-9_-]+)"),
    ("softgarden", r"([a-z0-9][a-z0-9-]*)\.softgarden\.io"),
    ("dvinci", r"([a-z0-9][a-z0-9-]*)\.dvinci(?:-easy|-hr)?\.(?:com|de)"),
    ("jobvite", r"jobs\.jobvite\.com/([A-Za-z0-9_-]+)"),
    ("dover", r"app\.dover\.(?:io|com)/(?:jobs|apply)/([A-Za-z0-9_-]+)"),
    ("polymer", r"jobs\.polymer\.co/([A-Za-z0-9_-]+)"),
    ("wellfound", r"wellfound\.com/company/([A-Za-z0-9_-]+)"),
    ("wellfound", r"angel\.co/company/([A-Za-z0-9_-]+)"),
    ("notion", r"([a-z0-9][a-z0-9-]*)\.notion\.site"),
    ("zohorecruit", r"([a-z0-9][a-z0-9-]*)\.zohorecruit\.(?:com|eu|in)"),
    ("manatal", r"careers-page\.com/([A-Za-z0-9_-]+)"),
    ("talentsoft", r"([a-z0-9][a-z0-9-]*)\.talent-soft\.com"),
    ("taleo", r"([a-z0-9][a-z0-9-]*)\.taleo\.net"),
    ("hirehive", r"([a-z0-9][a-z0-9-]*)\.hirehive\.com"),
    ("freshteam", r"([a-z0-9][a-z0-9-]*)\.freshteam\.com"),
    ("trakstar", r"([a-z0-9][a-z0-9-]*)\.hire\.trakstar\.com"),
    ("kenjo", r"([a-z0-9][a-z0-9-]*)\.kenjo\.io"),
    ("bizneo", r"([a-z0-9][a-z0-9-]*)\.bizneohr\.com"),
    ("onlyfy", r"([a-z0-9][a-z0-9-]*)\.onlyfy\.jobs"),
    ("onlyfy", r"([a-z0-9][a-z0-9-]*)\.prescreenapp\.io"),
    ("rexx", r"([a-z0-9][a-z0-9-]*)\.rexx-recruitment\.com"),
    ("rexx", r"([a-z0-9][a-z0-9-]*)\.rexx-systems\.com"),
    ("taleez", r"taleez\.com/careers/([A-Za-z0-9_-]+)"),
    ("flatchr", r"careers\.flatchr\.io/(?:[a-z]{2}/)?company/([A-Za-z0-9_-]+)"),
    ("teamdash", r"([a-z0-9][a-z0-9-]*)\.teamdash\.com"),
    ("traffit", r"([a-z0-9][a-z0-9-]*)\.traffit\.com"),
    ("talentlyft", r"([a-z0-9][a-z0-9-]*)\.talentlyft\.com"),
    ("recruitcrm", r"recruitcrm\.io/jobs/([A-Za-z0-9_-]+)"),
    ("eploy", r"([a-z0-9][a-z0-9-]*)\.eploy\.(?:net|co\.uk)"),
    ("umantis", r"([a-z0-9][a-z0-9-]*)\.umantis\.com"),
]
DETECT_ONLY_RX = re.compile("|".join(f"(?:{p})" for _, p in DETECT_ONLY), re.I)


def _needle(pattern: str) -> str:
    """The longest plain piece of a pattern (for example 'careers.hibob.com'): a cheap test before the regex runs."""
    pieces = re.split(r"\(\?:|\(|\)|\[[^\]]*\]|[*+?{}|^$]|\\[dwsb]", pattern)
    best = max((x.replace("\\", "") for x in pieces), key=len)
    return best.lower()


_DETECT_ONLY_C = [(n, re.compile(p, re.I), _needle(p)) for n, p in DETECT_ONLY]
_DETECT_SKIP = {"www", "app", "api", "apidoc", "help", "support", "jobs", "careers", "blog", "static", "assets", "cdn", "docs", "status",
                "developers", "academy", "community", "partners", "integrations", "marketplace", "login", "signup"}

# Hosted career sites served on the company's own domain: recognised by the platform's asset hosts in the page.
_CUSTOM_DOMAIN = [
    ("teamtailor", re.compile(r"(?i)teamtailor-cdn\.com|assets-aws\.teamtailor|content=\"Teamtailor\"|powered by teamtailor")),
    ("recruitee", re.compile(r"(?i)recruitee-careers|careers-page-recruitee|recruiteecdn\.com|\"poweredBy\":\"Recruitee\"|powered by recruitee")),
]
# ATSs we have an adapter for but whose robots.txt disallows us (see README): recorded as found-but-blocked.
ROBOTS_BLOCKED_ATS = {"personio", "smartrecruiters", "pinpoint"}
_LINKEDIN = re.compile(r"(?i)https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company/[^\"'<>\s/]+/jobs|jobs/)")
_LD_JOB = re.compile(r"(?i)\"@type\"\s*:\s*\[?\s*\"JobPosting\"")


def _urls_in(html: str) -> list[str]:
    text = (html or "").replace("\\/", "/").replace("&amp;", "&")
    return _URL.findall(text)


def detect(html: str, page_url: str = "") -> dict:
    """What a page shows about the company's careers system.
    Returns {"tenants": {(ats, key): data}, "other": {name: key}, "linkedin": bool, "jsonld": bool, "custom": [ats]}."""
    text = (html or "").replace("\\/", "/").replace("&amp;", "&")
    urls = _URL.findall(text) + ([page_url] if page_url else [])
    # every pattern below is about a URL: run them over the URLs on the page, not over the whole page (minified
    # scripts make a whole-page scan with a leading character class very slow)
    blob = " ".join(dict.fromkeys(urls))
    tenants: dict[tuple[str, str], dict] = {}
    for u in dict.fromkeys(urls):
        for ats, key, data in classify(u):
            tenants.setdefault((ats, key), data)
    low = blob.lower()
    for (ats, rx), needle in zip(_EXTRA, _EXTRA_NEEDLE):
        if needle not in low:
            continue
        for m in rx.finditer(blob):
            key = m.group(1).strip(".-")
            if key.lower() in _BAD_KEYS or len(key) < 2:
                continue
            key = key if ats in ("ashby",) else key.lower()
            tenants.setdefault((ats, key), {})
    tlow = text[:2_000_000].lower()
    for ats, needle, rx in _SCRIPT_EMBEDS:
        if needle in tlow:
            m = rx.search(text)
            if m and m.group(1).lower() not in _BAD_KEYS:
                tenants.setdefault((ats, m.group(1).lower()), {})
    # an ATS's own pages link to the vendor's marketing site and to example boards: ignore keys that are the vendor
    tenants = {k: v for k, v in tenants.items() if k[1].lower() not in _BAD_KEYS}
    other: dict[str, str] = {}
    for name, rx, needle in _DETECT_ONLY_C:
        if needle not in low:
            continue
        for m in rx.finditer(blob):
            key = m.group(1).lower()
            if key in _DETECT_SKIP:
                continue
            other.setdefault(name, key)
            break
    custom = [ats for ats, rx in _CUSTOM_DOMAIN if rx.search(text[:400_000])]
    return {"tenants": tenants, "other": other, "linkedin": bool(_LINKEDIN.search(text)),
            "jsonld": bool(_LD_JOB.search(text)), "custom": custom}


def _job_links(html: str, page_url: str, limit: int = 40) -> list[str]:
    """Same-host links that look like single job pages, for JSON-LD reading."""
    from .adapters.jsonld import job_links
    return job_links(html, page_url, limit)


MAX_PAGE = 1_500_000   # bytes read from one page; ATS links and embeds sit well inside this


def probe_company(client, website: str, max_pages: int = 4) -> dict:
    """Read a company's homepage and careers page(s); return what was found. Network; never raises."""
    res: dict = {"website": website, "status": "", "tenants": [], "other": {}, "careers": "", "linkedin": False, "pages": 0}
    host = host_of(website)
    if not host:
        res["status"] = "no_website"
        return res
    home = f"https://{host}/"
    try:
        r = client.get(home, max_bytes=MAX_PAGE)
    except Exception as e:  # the client never raises on HTTP, but a bad URL can
        res["status"], res["note"] = "site_unreachable", type(e).__name__
        return res
    res["pages"] += 1
    if r.status == -1:
        res["status"] = "site_robots"
        return res
    if r.status in (401, 403, 429, -2) or r.reason == "bot challenge":
        res["status"] = "site_blocked"
        res["note"] = f"HTTP {r.status} {r.reason}".strip()
        return res
    if r.status != 200:
        res["status"] = "site_unreachable"
        res["note"] = f"HTTP {r.status} {r.reason}".strip()
        return res
    final = r.url or home
    found = {"tenants": {}, "other": {}, "linkedin": False, "jsonld_pages": [], "custom": {}, "pagelist": ""}

    def absorb(d: dict, url: str):
        for k, v in d["tenants"].items():
            found["tenants"].setdefault(k, v)
        for k, v in d["other"].items():
            found["other"].setdefault(k, v)
        found["linkedin"] = found["linkedin"] or d["linkedin"]
        if d["jsonld"]:
            found["jsonld_pages"].append(url)
        for ats in d["custom"]:
            found["custom"].setdefault(ats, host_of(url))

    absorb(detect(r.text, final), final)
    links = careers_links(r.text, final)
    tried = set()
    dom = registrable(final)
    # no careers link on the homepage: the common places, before calling it "no careers page"
    guesses = [] if links else [urljoin(final, p) for p in ("/careers", "/jobs", "/join", "/join-us", "/company/careers",
                                                            "/about/careers")] + [f"https://careers.{dom}/", f"https://jobs.{dom}/"]
    for u in (links[:max_pages] if links else guesses):
        if u in tried or u.rstrip("/") == final.rstrip("/"):
            continue
        tried.add(u)
        if list(classify(u)) or DETECT_ONLY_RX.search(u):
            absorb(detect("", u), u)          # the link itself names the ATS: nothing to fetch
            res["careers"] = res["careers"] or u
            continue
        if _LINKEDIN.match(u):
            found["linkedin"] = True
            continue
        p = client.get(u, max_bytes=MAX_PAGE)
        res["pages"] += 1
        if p.status != 200:
            continue
        if not links and registrable(p.url or u) != dom and not list(classify(p.url or u)):
            continue                     # a guessed path that redirects to another company's site is not this one's page
        res["careers"] = res["careers"] or (p.url or u)
        d = detect(p.text, p.url or u)
        absorb(d, p.url or u)
        if not d["tenants"] and not d["other"] and not d["jsonld"]:
            # careers page with no ATS in sight: roles listed as plain links (adapters/pagelist), else JobPosting markup
            from .adapters import pagelist
            if pagelist.entries(p.text, p.url or u):
                found["pagelist"] = p.url or u
            jl = _job_links(p.text, p.url or u, 3)
            if jl:
                q = client.get(jl[0], max_bytes=MAX_PAGE)
                res["pages"] += 1
                if q.status == 200 and _LD_JOB.search(q.text):
                    found["jsonld_pages"].append(p.url or u)
        if found["tenants"]:
            break
    tenants = []
    for (ats, key), data in found["tenants"].items():
        tenants.append({"ats": ats, "key": key, "data": data})
    for ats, h in found["custom"].items():
        if not any(t["ats"] == ats for t in tenants) and h:
            tenants.append({"ats": ats, "key": h, "data": {"host": h}})
    res["tenants"] = tenants
    res["other"] = found["other"]
    res["linkedin"] = found["linkedin"]
    usable = [t for t in tenants if t["ats"] not in ROBOTS_BLOCKED_ATS]
    if usable:
        res["status"] = "ats"
    elif tenants:
        res["status"] = "ats_robots_blocked"
    elif found["jsonld_pages"]:
        page = found["jsonld_pages"][0]
        res["tenants"] = [{"ats": "jsonld", "key": host_of(page) + urlsplit(page).path.rstrip("/"),
                           "data": {"host": host_of(page), "pages": [page]}}]
        res["status"] = "jsonld"
    elif found["pagelist"]:
        page = found["pagelist"]
        res["tenants"] = [{"ats": "pagelist", "key": host_of(page) + urlsplit(page).path.rstrip("/"), "data": {"pages": [page]}}]
        res["status"] = "careers_page_list"
    elif found["other"]:
        res["status"] = "ats_no_adapter"
    elif res["careers"] and found["linkedin"]:
        res["status"] = "linkedin_only"
    elif res["careers"]:
        res["status"] = "careers_no_ats"
    elif found["linkedin"]:
        res["status"] = "linkedin_only"
    else:
        res["status"] = "no_careers_page"
    return res


# Job boards and job platforms: listed as startups, but their boards carry other employers' roles.
EXCLUDE_DOMAINS = {"jobgether.com"}
# news and data sites an investor's company pages link as coverage: never a portfolio company
MEDIA = re.compile(r"(?i)^(axios|bizjournals|fortune|forbes|bloomberg|reuters|wsj|nytimes|nypost|washingtonpost|businesswire|"
                   r"prnewswire|globenewswire|accesswire|newswire|prweb|venturebeat|wired|zdnet|cnbc|cnn|bbc|theverge|ft|"
                   r"economist|yahoo|msn|medium|substack|crunchbase|cbinsights|tracxn|pitchbook|dealroom|glassdoor|linkedin|"
                   r"builtin|geekwire|siliconangle|businessinsider|insider|time|inc|entrepreneur|fastcompany|marketwatch|"
                   r"theinformation|sifted|eu-startups|techcrunch|theguardian|guardian|thetimes|telegraph|independent|"
                   r"adweek|adage|adexchanger|crn|computerweekly|datanami|cmswire|pymnts|finextra|thefintechtimes|"
                   r"fiercehealthcare|freightwaves|marketscreener|pehub|bostonglobe|latimes|ajc|usatoday|cbsnews|"
                   r"techradar|engadget|mashable|wikipedia|youtube|apple|google|github|twitter|x|facebook|instagram|bcorporation|bcorp)\.(com|co\.uk|org|net|eu)$")


_BIG: dict | None = None


def big_listed(domain: str) -> str:
    """The list code (a stock index such as sp500, or big tech, Big 4, consulting; data/companies) when the company is
    a listed or large company rather than a startup. AI labs are not counted: most are VC-backed startups."""
    global _BIG
    if _BIG is None:
        from . import companies
        _BIG = {m["domain"]: code for code, v in companies.lists().items() if code != "ailab"
                for m in v["members"] if m.get("domain")}
    return _BIG.get(domain, "")


def excluded(domain: str) -> bool:
    """Never listed as a startup: a job platform we were wrongly pointed to, or a news or data site."""
    return domain in EXCLUDE_DOMAINS or bool(MEDIA.match(domain or ""))

# -- the committed list and the vc mark ---------------------------------------------------------------------------
DATA = Path(__file__).resolve().parent.parent / "data" / "startups_eu.json"


def load(path: str | Path | None = None) -> dict:
    p = Path(path or DATA)
    if not p.exists():
        return {"v": 1, "tenants": [], "companies": []}
    return json.loads(p.read_text())


def add_tenants(state, doc: dict) -> int:
    """Every tenant found from a startup's own website goes into the run (the release tenant list may predate it)."""
    n = 0
    for t in doc.get("tenants", []):
        if state.add_tenant(t["ats"], t["key"], t.get("data") or {}, "startup"):
            n += 1
    return n


def company_keys(doc: dict) -> set[tuple[str, str]]:
    return {(ats, key) for c in doc.get("companies", []) for ats, key in c.get("tenants", [])}


# -- second pass: the company's name on the ATS's public endpoints ------------------------------------------------
# Many careers pages load their roles with JavaScript, so the page as served names no ATS. For those companies we
# try the board names the company would most likely use (its domain label, its name run together or hyphenated) on
# the public endpoints of the ATSs we read, and keep a board only when the board itself names the company.
_TRANSLIT = str.maketrans({"æ": "ae", "Æ": "AE", "ø": "o", "Ø": "O", "ß": "ss", "œ": "oe", "Œ": "OE", "đ": "d", "ł": "l", "Ł": "L"})


def _fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", (s or "").translate(_TRANSLIT))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"\b(inc|ltd|limited|gmbh|ag|sa|sas|sarl|bv|nv|ab|as|oy|aps|plc|llc|srl|spa|se|holding|group|hq|the)\b\.?", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def guess_slugs(name: str, domain: str) -> list[str]:
    label = (domain or "").split(".")[0].lower()
    folded = _fold(name)
    hyph = re.sub(r"[^a-z0-9]+", "-", re.sub(r"\b(gmbh|ltd|limited|inc|sas|ag|bv|ab|oy|aps|plc|llc|srl|spa)\b", " ",
                                                (name or "").lower())).strip("-")
    out = []
    for s in (label, folded, hyph):
        if s and 3 <= len(s) <= 40 and s not in out and s not in _BAD_KEYS:
            out.append(s)
    return out


def names_match(board_name: str, name: str, domain: str) -> bool:
    a, b, label = _fold(board_name), _fold(name), _fold((domain or "").split(".")[0])
    if not a:
        return False
    if a == b or (a == label and (len(label) >= 5 or label == b)):   # a short domain label alone is too weak
        return True
    # "Mistral AI" and "Mistral", "Acme Labs" and "Acme": one is the other plus a short tail
    for x in (b, label):
        if len(x) >= 4 and (a.startswith(x) or x.startswith(a)) and abs(len(a) - len(x)) <= 4:
            return True
    return False


def _text_names(text: str, name: str, domain: str) -> bool:
    """The postings' own text names the company (for APIs that carry no company field)."""
    low = (text or "").lower()
    n = (name or "").lower().strip()
    return bool(n and len(n) >= 3 and re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", low)) or \
        bool(domain and domain.lower() in low)


GUESS_ATS = ("greenhouse", "lever", "ashby", "recruitee", "teamtailor", "join", "workable")


def verify_board(client, ats: str, slug: str, name: str, domain: str) -> str:
    """'yes' when the board exists and names the company, 'no' when it does not, 'unknown' when we could not tell."""
    from .adapters import base
    try:
        if ats == "greenhouse":
            r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}")
            if r.status in (404, 410):
                return "no"
            d = r.json() if r.ok else None
            return "unknown" if d is None else ("yes" if names_match(d.get("name") or "", name, domain) else "no")
        if ats == "lever":
            r = client.get(f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=3")
            if r.status in (404, 410):
                return "no"
            d = r.json() if r.ok else None
            if not isinstance(d, list):
                return "unknown"
            return "yes" if d and _text_names(" ".join((p.get("descriptionPlain") or "") + " " + (p.get("additionalPlain") or "")
                                                       for p in d), name, domain) else "no"
        if ats == "ashby":
            r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            if r.status in (404, 410):
                return "no"
            d = r.json() if r.ok else None
            if not isinstance(d, dict):
                return "unknown"
            jobs = d.get("jobs") or []
            return "yes" if jobs and _text_names(" ".join((j.get("descriptionPlain") or "")[:4000] for j in jobs[:3]),
                                                 name, domain) else "no"
        if ats == "recruitee":
            r = client.get(f"https://{slug}.recruitee.com/api/offers/")
            if r.status in (404, 410):
                return "no"
            d = r.json() if r.ok else None
            if not isinstance(d, dict):
                return "unknown"
            offers = d.get("offers") or []
            return "yes" if offers and names_match(offers[0].get("company_name") or "", name, domain) else "no"
        if ats == "teamtailor":
            r = client.get(f"https://{slug}.teamtailor.com/jobs.rss")
            if r.status in (404, 410):
                return "no"
            if not r.ok:
                return "unknown"
            try:
                title = base.txt(base.parse_xml(r.text), "channel/title")
            except Exception:
                return "no"
            return "yes" if names_match(title, name, domain) else "no"
        if ats == "join":
            from .adapters import join
            r = client.get(f"https://join.com/companies/{slug}")
            if r.status in (404, 410):
                return "no"
            if not r.ok:
                return "unknown"
            pd = join.page_data(r.text)
            return "yes" if names_match((pd.get("company") or {}).get("name") or "", name, domain) else "no"
        if ats == "workable":
            r = client.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
            if r.status in (404, 410):
                return "no"
            d = r.json() if r.ok else None
            return "unknown" if not isinstance(d, dict) else ("yes" if names_match(d.get("name") or "", name, domain) else "no")
    except Exception:
        return "unknown"
    return "unknown"
