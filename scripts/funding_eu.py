"""Funding rounds for the startups in data/startups_eu.json, from EU-Startups articles (robots.txt allows all).

  python scripts/funding_eu.py archive   # every post in the site's sitemaps (first build, weekly top-up)
  python scripts/funding_eu.py rss       # the latest posts from its RSS feed (each run)

A post is a candidate when its URL reads like a round ("<company>-raises-e6-1-million-...") and the company part matches
one of our companies' names or domain labels. The article is then read and the round kept only when the article links
that company's own domain. Output: data/funding_eu.json {"built", "source", "rounds": {domain: [round]},
"companies": {domain: summary}}. No AI: plain patterns only.
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jobalfred_index import funding, startups  # noqa: E402
from jobalfred_index.polite import Client  # noqa: E402

OUT = ROOT / "data" / "funding_eu.json"
SITE = "https://www.eu-startups.com"


def load() -> dict:
    return json.loads(OUT.read_text()) if OUT.exists() else {"rounds": {}, "seen": []}


def company_index():
    pub = startups.load()
    idx: dict[str, list] = {}
    for c in pub.get("companies", []):
        for k in {startups._fold(c.get("name") or ""), startups._fold(c["domain"].split(".")[0])}:
            if len(k) >= 3:
                idx.setdefault(k, []).append(c)
    return idx


def candidates(urls, idx) -> list[tuple[str, dict, dict]]:
    out = []
    for u in urls:
        s = funding.parse_slug(u)
        if not s:
            continue
        for c in idx.get(startups._fold(s["company"]), []):
            out.append((u, c, s))
    return out


def confirm(client, items, doc) -> int:
    seen = set(doc.get("seen", []))
    # rounds read before the stricter rules (no stored context) are read again and replaced
    for dom, lst in doc.get("rounds", {}).items():
        for r in lst:
            if "stage_ctx" not in r:
                seen.discard(f"{r['url']}|{dom}")
    todo = [(u, c, s) for u, c, s in items if f"{u}|{c['domain']}" not in seen]
    # companies whose only evidence of VC backing is "Seedtable" first (a confirmed article gives public evidence), newest first
    todo.sort(key=lambda x: ((x[1].get("evidence") or ["Seedtable"]) == ["Seedtable"],
                             re.search(r"/(20\d\d/\d\d)/", x[0]).group(1)), reverse=True)
    added = 0
    for n, (u, c, s) in enumerate(todo, 1):
        if n > 1 and n % 10 == 1:
            doc["seen"] = sorted(seen)
            save(doc)
            print(f"{n - 1}/{len(todo)} articles read, {added} rounds added", flush=True)
        r = client.get(u, max_bytes=1_500_000)
        status = r.status
        if status == -2 or status == 429:
            print(f"stopped after {n - 1} articles: {r.reason}; the rest next time", flush=True)
            break                                          # a refusal or bot check is never worked around
        if status == 0 or status >= 500:
            continue                                       # not read this time: asked again next run
        art = funding.parse_article(r.text, r.url or u) if r.ok else None
        seen.add(f"{u}|{c['domain']}")
        if art and not art["not_equity"] and c["domain"] in art["domains"]:
            rnd = {"url": u, "date": art["date"] or re.search(r"/(20\d\d/\d\d)/", u).group(1).replace("/", "-") + "-01",
                   "stage": art["stage"] or s["stage"], "amount": art["amount"] or s["amount"],
                   "currency": art["currency"] or s["currency"], "total": art["total"],
                   "total_currency": art["total_currency"], "title": art["title"][:200],
                   "stage_ctx": art["stage_ctx"], "total_ctx": art["total_ctx"]}
            if not art["stage"]:
                rnd["stage"] = s["stage"]                  # a stage in the URL's own words still counts
            lst = doc["rounds"].setdefault(c["domain"], [])
            old = [x for x in lst if x["url"] == u]
            if old:
                lst[lst.index(old[0])] = rnd               # re-read under the current rules
            else:
                lst.append(rnd)
                added += 1
        elif art:
            lst = doc["rounds"].get(c["domain"], [])
            doc["rounds"][c["domain"]] = [x for x in lst if x["url"] != u]   # no longer counts (e.g. project finance)
            if not doc["rounds"][c["domain"]]:
                doc["rounds"].pop(c["domain"], None)
    doc["seen"] = sorted(seen)
    return added


def save(doc):
    doc["built"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc["source"] = "EU-Startups (www.eu-startups.com), article linked per round"
    doc["companies"] = {d: funding.summarise(rs) for d, rs in sorted(doc["rounds"].items())}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")


def newest(path: str) -> None:
    """Use the rounds file published on the release when it is newer than the committed one and not smaller."""
    try:
        rel = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        print("release rounds file unreadable: keeping the committed one")
        return
    cur = load()
    if rel.get("built", "") > cur.get("built", "") and len(rel.get("rounds", {})) >= len(cur.get("rounds", {})):
        OUT.write_text(json.dumps(rel, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"using the release rounds file built {rel.get('built')} ({len(rel['rounds'])} companies)")
    else:
        print(f"keeping the committed rounds file ({len(cur.get('rounds', {}))} companies)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "rss"
    if cmd == "newest":
        newest(sys.argv[2])
        return
    client = Client(timeout=30, retries=1)
    import os
    client.configure_host("www.eu-startups.com", gap=float(os.environ.get("GAP", "3")), inflight=1)   # bursts get a bot check
    doc = load()
    idx = company_index()
    if cmd == "archive":
        cache_p = ROOT / "work" / "eu_startups_posts.json"
        cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
        r = client.get(f"{SITE}/sitemap_index.xml")
        maps = [s for s in re.findall(r"<loc>([^<]+)</loc>", r.text) if "post-sitemap" in s]
        maps.sort(key=lambda m: -int(re.search(r"(\d*)\.xml$", m).group(1) or 1))      # newest posts first
        for m in maps:
            if m in cache and m != maps[0]:
                continue                                   # older sitemaps do not change; the newest is read again
            rr = client.get(m)
            if not rr.ok:
                print(f"{m}: HTTP {rr.status} {rr.reason}; stopping here, the rest next time", flush=True)
                break
            cache[m] = re.findall(r"<loc>([^<]+)</loc>", rr.text)
            cache_p.write_text(json.dumps(cache))
        urls = [u for m in maps for u in cache.get(m, [])]
        print(f"archive: {len(cache)} of {len(maps)} sitemaps read, {len(urls)} posts", flush=True)
    else:
        r = client.get(f"{SITE}/feed/")
        urls = re.findall(r"<link>(https://www\.eu-startups\.com/20[^<]+)</link>", r.text) if r.ok else []
        print(f"rss: {len(urls)} posts", flush=True)
    cand = candidates(urls, idx)
    print(f"candidates: {len(cand)} posts naming one of our companies", flush=True)
    added = confirm(client, cand, doc)
    save(doc)
    print(f"rounds added: {added}; companies with a round: {len(doc['rounds'])}", flush=True)


if __name__ == "__main__":
    main()
