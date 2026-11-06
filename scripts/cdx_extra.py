"""Serial, patient Common Crawl pass for chosen queries; writes a JSON file and can be re-run to resume.
Usage: cdx_extra.py OUT.json CRAWL [query-label ...]
One request at a time, 3 s apart; a page that fails is retried after 30 s, then left for the next run."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobalfred_index.polite import Client
from jobalfred_index import discovery as d

out, crawl, labels = sys.argv[1], sys.argv[2], set(sys.argv[3:])
c = Client(); c.configure_host("index.commoncrawl.org", gap=3.0, inflight=1)
found, done = {}, set()
if Path(out).exists():
    doc = json.load(open(out))
    found = {(t["ats"], t["key"]): t for t in doc["tenants"]}
    done = {tuple(x) for x in doc.get("done", [])}

def save():
    json.dump({"tenants": list(found.values()), "done": sorted(done)}, open(out, "w"))

def page_urls(query, p):
    for attempt in range(4):
        r = c.get(f"{d.CDX_BASE}/{crawl}-index", params={"url": query, "output": "json", "fl": "url", "page": str(p)}, robots=False, timeout=120)
        if r.status == 200:
            urls = []
            for l in r.text.splitlines():
                try:
                    urls.append(json.loads(l)["url"])
                except (ValueError, KeyError):
                    pass
            return urls
        print("   retry", p, r.status, r.reason, flush=True)
        time.sleep(30)
    return None

for label, q in d.CDX_QUERIES:
    if labels and label not in labels:
        continue
    n = None
    for attempt in range(4):
        n = d.cdx_pages.__wrapped__(c, crawl, q) if hasattr(d.cdx_pages, "__wrapped__") else None
        r = c.get(f"{d.CDX_BASE}/{crawl}-index", params={"url": q, "showNumPages": "true", "output": "json"}, robots=False, timeout=90)
        if r.status == 200:
            n = int((r.json() or {}).get("pages", 0)); break
        time.sleep(30)
    print(label, q, "pages", n, flush=True)
    for p in range(min(n or 0, 80)):
        if (label, crawl, p) in done:
            continue
        urls = page_urls(q, p)
        if urls is None:
            continue
        n0 = len(found)
        for u in urls:
            for ats, key, data in d.classify(u):
                found.setdefault((ats, key), {"ats": ats, "key": key, "data": data, "source": f"cdx:{crawl}"})
        done.add((label, crawl, p))
        print("  page", p, len(urls), "urls, +", len(found) - n0, flush=True)
        save()
save()
print("tenants", len(found))
