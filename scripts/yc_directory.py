"""YC's public company directory: one page per company, listed in https://www.ycombinator.com/companies/sitemap.

robots.txt allows /companies/<slug> (it disallows /companies?* query pages, which we never ask for). One request at a
time, a gap between requests, our own User-Agent. Saves every company's name, website, country, location, batch and
status to work/yc_companies.json, resumable: pages already read are not asked for again.

Usage: python scripts/yc_directory.py [--gap 0.7] [--limit N]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jobalfred_index.polite import Client  # noqa: E402

SITEMAP = "https://www.ycombinator.com/companies/sitemap"
OUT = ROOT / "work" / "yc_companies.json"
PAGE = re.compile(r'data-page="([^"]*)"')
COMPANY = re.compile(r"^https://www\.ycombinator\.com/companies/([a-z0-9][a-z0-9-]*)$")


def parse_company(text: str) -> dict | None:
    m = PAGE.search(text)
    if not m:
        return None
    try:
        doc = json.loads(html.unescape(m.group(1)))
    except ValueError:
        return None
    c = (doc.get("props") or {}).get("company")
    if not isinstance(c, dict):
        return None
    return {k: c.get(k) for k in ("slug", "name", "website", "country", "location", "city", "batch", "ycdc_status", "team_size",
                                  "tags", "one_liner")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=float, default=0.7)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh-countries", default="", help="read again the companies already saved with these countries "
                    "(comma list of ISO codes, or 'europe'), e.g. to pick up fields added since")
    a = ap.parse_args()
    client = Client()
    client.configure_host("www.ycombinator.com", gap=a.gap, inflight=1)
    done = json.loads(OUT.read_text()) if OUT.exists() else {"companies": {}, "failed": {}}
    r = client.get(SITEMAP)
    if not r.ok:
        print(f"sitemap: HTTP {r.status} {r.reason}")
        return 1
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", r.text) if COMPANY.match(u.strip())]
    again = set()
    if a.refresh_countries:
        want = a.refresh_countries.upper().split(",")
        europe = set("AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT XK LV LI LT LU MT MD MC ME NL MK NO PL PT RO RU "
                     "SM RS SK SI ES SE CH TR UA GB VA GI IM JE GG FO".split())
        again = {s for s, c in done["companies"].items() if (c.get("country") in europe if want == ["EUROPE"] else c.get("country") in want)}
    todo = [u for u in urls if COMPANY.match(u).group(1) not in done["companies"] or COMPANY.match(u).group(1) in again]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(urls)} company pages, {len(todo)} to read", flush=True)
    t0 = time.time()
    for i, u in enumerate(todo, 1):
        slug = COMPANY.match(u).group(1)
        r = client.get(u)
        if r.ok:
            c = parse_company(r.text)
            if c:
                done["companies"][slug] = c
            else:
                done["failed"][slug] = "no company data"
        else:
            done["failed"][slug] = f"HTTP {r.status} {r.reason}"
            if r.status in (429, 403, -2):
                print(f"stopping: {r.status} {r.reason}", flush=True)
                break
        if i % 200 == 0 or i == len(todo):
            OUT.write_text(json.dumps(done, separators=(",", ":")))
            print(f"{i}/{len(todo)} read, {len(done['companies'])} companies, {int(time.time() - t0)}s", flush=True)
    OUT.write_text(json.dumps(done, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
