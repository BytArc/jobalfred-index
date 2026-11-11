"""Careers pages that list their roles as plain links, with no job system behind them.

Typical: a Framer or Webflow careers page whose entries ("AI Forward Deployed Engineer · Lisbon · Learn more") link to a
Google Doc, a Notion page or a page on the company's own site. Plain rules, no AI:
  an entry is a link whose text starts with a job title: a role word (engineer, lead, head of, manager, ...) that the
  function rules (function.py) also recognise; the short parts after the title are read as its location when the
  geography rules know them. The same title linking to the same place is one role (its locations joined).
Only the careers page itself is read (robots.txt obeyed by the client); the linked documents are not fetched.
Tenant data: {"pages": [careers page URL], "name": company name}.
"""
from __future__ import annotations

import html as htmllib
import re
from urllib.parse import urljoin, urlsplit

from .. import geo
from ..model import Gone, make
from .base import check, slug_title

ATS = "careers-page"
KIND = "tenant"
WORKERS = 4
PRIORITY = 60

ANCHOR = re.compile(r"<a\b([^>]{0,2000})>(.{0,6000}?)</a>", re.I | re.S)
HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)
ROLE = re.compile(r"(?i)\b(engineer|developer|programmer|manager|lead|head of|director|designer|analyst|scientist|specialist|"
                  r"associate|intern|internship|officer|coordinator|consultant|representative|executive|architect|researcher|"
                  r"administrator|accountant|recruiter|technician|assistant|advisor|adviser|strategist|counsel|lawyer|"
                  r"writer|editor|marketer|operator|controller|partner|owner|nurse|physician|chef|driver|agent|"
                  r"vp|vice president|cto|cfo|coo|ceo|founding|fellow|apprentice|trainee|werkstudent|praktikant|"
                  r"desenvolvedor|engenheiro|gestor|responsável|ingénieur|développeur|chargé|ingeniero|desarrollador)\b")
NOT_TITLE = re.compile(r"(?i)^(careers?|jobs?|open (roles|positions)|join us|learn more|apply( now)?|see (all|more)|view (all|role|job)|"
                       r"read more|about|blog|contact|our team|meet the team|life at|spontaneous|open application|talent pool)\b")
# the link itself must look like one job posting: a job-like path on the company's site, or a shared document
JOB_PATH = re.compile(r"(?i)/(jobs?|careers?|positions?|vacanc(?:y|ies)|openings?|job-openings|open-roles|roles|"
                      r"opportunit(?:y|ies)|karriere|stellen(?:angebote)?|emplois?|offres?|carreiras?|vagas?|empleos?|"
                      r"ofertas?|lavora-con-noi|werken-bij|vacatures|jobb|rekry)/[^/?#]{3,}")
DOC_HOSTS = re.compile(r"(?i)(^|\.)(docs\.google\.com|drive\.google\.com|notion\.site|notion\.so)$")
SKIP_HOSTS = re.compile(r"(?i)(^|\.)(linkedin|twitter|x|facebook|instagram|youtube|glassdoor|indeed|welcometothejungle|"
                        r"wellfound|angel)\.[a-z.]+$")


def _blocks(inner: str) -> list[str]:
    parts = re.split(r"<[^>]+>", inner or "")
    out = []
    for p in parts:
        t = re.sub(r"\s+", " ", htmllib.unescape(p)).strip(" ·|•-–—→>")
        if t and len(t) <= 120:
            out.append(t)
    return out


def entries(page: str, page_url: str) -> list[dict]:
    """[{"title", "locs": [...], "url"}] for the role links on a careers page."""
    from .. import function
    found: dict[tuple[str, str], dict] = {}
    for attrs, inner in ANCHOR.findall(page or ""):
        m = HREF.search(attrs)
        if not m:
            continue
        href = m.group(1).strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(page_url, href)
        host = (urlsplit(url).hostname or "").lower()
        if not host or SKIP_HOSTS.search(host) or url.split("#")[0].rstrip("/") == page_url.split("#")[0].rstrip("/"):
            continue
        path = urlsplit(url).path
        if not (DOC_HOSTS.search(host) or JOB_PATH.search(path)):
            continue                                   # a product, blog or partner link, not a posting
        texts = _blocks(inner)
        if not texts:
            continue
        title, extra = texts[0], []
        if re.search(r"\s[|·•]\s", title):          # "Product Marketing Manager | Marketing | London"
            title, *extra = [x.strip() for x in re.split(r"\s[|·•]\s", title) if x.strip()]
        texts = [title] + extra + texts[1:]
        if not (4 <= len(title) <= 90) or NOT_TITLE.match(title) or not ROLE.search(title):
            continue
        fn, _ = function.label(title)
        if fn in ("", function.NOT_STATED):
            continue
        locs = [t for t in texts[1:6] if len(t) <= 60 and (geo.country_of(t) or re.search(r"(?i)\bremote\b", t))]
        e = found.setdefault((title.lower(), url), {"title": title, "locs": [], "url": url})
        for l in locs:
            if l not in e["locs"]:
                e["locs"].append(l)
    return list(found.values())


def parse(page: str, page_url: str, tenant: dict) -> list:
    company = tenant.get("name") or slug_title((urlsplit(page_url).hostname or "").split(".")[-2])
    out = []
    for e in entries(page, page_url):
        job = make(ATS, e["title"], company, e["locs"], e["url"],
                   remote_hint=any(re.search(r"(?i)\bremote\b", l) for l in e["locs"]) or None)
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    rows = []
    for page in tenant.get("pages") or []:
        r = check(client.get(page, max_bytes=3_000_000), f"careers-page/{tenant['key']}")
        rows.extend(parse(r.text, r.url or page, tenant))
    if not tenant.get("pages"):
        raise Gone(f"careers-page/{tenant['key']}: no page")
    return rows
