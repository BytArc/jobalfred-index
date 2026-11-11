"""Company domains from investors' own public portfolio pages (evidence for the `vc` mark).

For each investor below we read its portfolio page(s) as served (no JavaScript run), robots.txt obeyed, our own
User-Agent, and keep the outbound links to company websites. Social sites, the investor's own domain and web-platform
hosts are dropped. Output: work/vc_portfolios.json {investor: {"pages": [...], "status": {...}, "domains": [...]}}.

Never used to read jobs: portfolio job boards (Getro, Consider) are not touched.

Usage: python scripts/vc_portfolios.py [--only "Index Ventures,Atomico"]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jobalfred_index.polite import Client  # noqa: E402
from jobalfred_index.startups import registrable, host_of  # noqa: E402

OUT = ROOT / "work" / "vc_portfolios.json"

# Large, active European venture investors, each with the portfolio page(s) it publishes. Pages that paginate list
# every page we read. A page that serves its list only through JavaScript yields nothing and is reported as such.
# Investors and their portfolio pages live in data/vc_investors.json (also used to name a company's backers).
_INV = json.loads((ROOT / "data" / "vc_investors.json").read_text())["investors"]
INVESTORS: dict[str, list[str]] = {k: v["pages"] for k, v in _INV.items() if k != "Y Combinator"}
# Investors whose list page is drawn by JavaScript but who publish one page per company in their sitemap
DETAIL: dict[str, tuple[str, str]] = {k: tuple(v["detail"]) for k, v in _INV.items() if v.get("detail")}
DETAIL_SKIP = re.compile(r"(?i)/(portfolio|companies|company)/(exits?|country|focus-area|sector|stage|page|category|all|filter)s?/?$")

SKIP_HOSTS = re.compile(
    r"(?i)(^|\.)(linkedin|twitter|x|facebook|instagram|youtube|youtu|medium|github|crunchbase|tiktok|t|bit|lnkd|apple|google|"
    r"googleapis|gstatic|googletagmanager|google-analytics|doubleclick|cloudflare|cloudfront|amazonaws|akamaihd|jsdelivr|unpkg|"
    r"webflow|website-files|framer|framerusercontent|wixstatic|wix|squarespace|squarespace-cdn|wordpress|wp|gravatar|typekit|"
    r"fonts|hubspot|hs-scripts|hsforms|hscollectedforms|hs-analytics|hubspotusercontent|cookiebot|cookielaw|onetrust|usercentrics|"
    r"vimeo|spotify|soundcloud|substack|mailchimp|list-manage|calendly|typeform|notion|figma|w3|schema|ogp|gmpg|sentry|"
    r"intercom|zendesk|segment|hotjar|plausible|vercel|netlify|cdn|getro|consider|workatastartup|ycombinator|"
    r"apps|play|itunes|maps|goo|wikipedia|bloomberg|techcrunch|ft|reuters|forbes|sifted|eu-startups|businessinsider|"
    r"theguardian|nytimes|wsj|cnbc|tech|prnewswire|businesswire|globenewswire|europa|gov|ec|dealroom|pitchbook|"
    r"greenhouse|lever|ashbyhq|workable|teamtailor|recruitee|personio|smartrecruiters|bamboohr|breezy|join|welcometothejungle)\.[a-z.]+$")
LINK = re.compile(r"""(?:href\s*=\s*["']|["'](?:url|website|link|href|websiteUrl|website_url)["']\s*:\s*["'])(https?://[^"'\s<>]+)""", re.I)


def domains_on(html: str, page_url: str, own: str) -> set[str]:
    out = set()
    text = (html or "").replace("\\/", "/")
    for u in LINK.findall(text):
        u = urljoin(page_url, u)
        h = host_of(u)
        d = registrable(h)
        if not d or d == own or SKIP_HOSTS.search(d) or SKIP_HOSTS.search(h):
            continue
        if re.search(r"\.(png|jpe?g|svg|gif|webp|css|js|pdf|woff2?)$", urlsplit(u).path, re.I):
            continue
        out.add(d)
    return out


def detail_pages(client, host: str, pattern: str, limit: int = 1500) -> list[str]:
    rx = re.compile(pattern, re.I)
    q = client.robots_sitemaps("https", host) or [f"https://{host}/sitemap.xml"]
    seen, out, n = set(), [], 0
    while q and n < 15:
        sm = q.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        n += 1
        r = client.get(sm)
        if r.status != 200:
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text):
            if re.search(r"\.xml(\.gz)?$", loc):
                q.append(loc)
            elif rx.search(urlsplit(loc).path) and not DETAIL_SKIP.search(urlsplit(loc).path) and loc not in out:
                out.append(loc)
    return out[:limit]


def from_details(client, inv: str, host: str, pattern: str) -> tuple[set[str], int, int]:
    """One company page each: keep the outbound domain(s) that are not on most pages (site-wide links)."""
    from concurrent.futures import ThreadPoolExecutor
    pages = detail_pages(client, host, pattern)
    own = registrable(host)

    def one(u):
        r = client.get(u)
        return domains_on(r.text, r.url or u, own) if r.status == 200 else None

    with ThreadPoolExecutor(3) as ex:
        found = [d for d in ex.map(one, pages) if d is not None]
    freq: dict[str, int] = {}
    for d in found:
        for x in d:
            freq[x] = freq.get(x, 0) + 1
    common = {x for x, n in freq.items() if len(found) >= 10 and n >= max(3, len(found) * 0.2)}
    out = set()
    for d in found:
        out |= d - common
    return out, len(pages), len(found)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    client = Client(timeout=30, retries=1)
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    for inv, pages in INVESTORS.items():
        if only and inv not in only:
            continue
        rec = {"pages": [], "status": {}, "domains": []}
        doms: set[str] = set()
        for p in pages:
            r = client.get(p)
            rec["status"][p] = r.status if r.status != -1 else "robots.txt disallows"
            if r.status != 200:
                continue
            own = registrable(r.url or p)
            found = domains_on(r.text, r.url or p, own)
            if found:
                rec["pages"].append(r.url or p)
            doms |= found
        if inv in DETAIL:
            host, pattern = DETAIL[inv]
            more, n_pages, n_read = from_details(client, inv, host, pattern)
            rec["status"]["company pages"] = f"{n_read} of {n_pages} read"
            if more:
                rec["pages"].append(f"https://{host}/ (company pages listed in its sitemap)")
            doms |= more
        rec["domains"] = sorted(doms)
        done[inv] = rec
        print(f"{inv}: {len(doms)} domains  {rec['status']}", flush=True)
    OUT.write_text(json.dumps(done, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
