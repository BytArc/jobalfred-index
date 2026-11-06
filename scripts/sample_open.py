"""Random sample of built roles, re-checked against the employer's own system today.

open    the employer's system still serves the posting
closed  it answers 404 or an empty result for that posting id
unknown 403, 429, a challenge, robots.txt, a timeout, or a URL we cannot map to a check (never counted as closed)
Same rules as the crawl: honest User-Agent, per-host pacing, robots.txt, stop on 403/429.
Usage: sample_open.py N_PER_SOURCE
"""
import collections, gzip, json, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, unquote
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index.polite import Client, HOST_SKIPPED, ROBOTS_BLOCKED
from jobalfred_index.state import State

N = int(sys.argv[1]) if len(sys.argv) > 1 else 250
SOURCES = ["workday", "oracle", "greenhouse", "ashby", "lever", "amazon"]
random.seed(20261106)
m = json.load(open(root / "dist" / "manifest.json"))
by = collections.defaultdict(list)
for s in m["shards"]:
    for r in json.loads(gzip.decompress((root / "dist" / s["file"]).read_bytes()))["rows"]:
        if r[7] in SOURCES:
            by[r[7]].append(r)
# tenant key per URL, so custom-domain Greenhouse and Lever URLs can be checked through the board API
st = State(root / "work" / "index.db", "q")
url2key = {}
for ats, key, rows in st.iter_rows():
    if ats in ("greenhouse", "lever", "ashby"):
        for r in rows:
            url2key[r[5]] = key

c = Client()
board_cache = {}

def result(status, content=b""):
    if status == 200:
        return "open"
    if status in (404, 410):
        return "closed"
    return "unknown"

def check(r):
    src, url = r[7], r[5]
    try:
        if src == "greenhouse":
            tok = url2key.get(url); m_ = re.search(r"(?:jobs/|gh_jid=)(\d+)", url)
            if not tok or not m_: return "unknown", "cannot map"
            x = c.get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{m_.group(1)}")
        elif src == "lever":
            tok = url2key.get(url); m_ = re.search(r"([0-9a-f-]{36})", url)
            if not tok or not m_: return "unknown", "cannot map"
            x = c.get(f"https://api.lever.co/v0/postings/{tok}/{m_.group(1)}")
        elif src == "ashby":
            tok = url2key.get(url); m_ = re.search(r"([0-9a-f-]{36})", url)
            if not tok or not m_: return "unknown", "cannot map"
            if tok not in board_cache:
                b = c.get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")
                board_cache[tok] = ({j["id"] for j in (b.json() or {}).get("jobs", [])} if b.status == 200 and b.json() else b.status)
            ids = board_cache[tok]
            if isinstance(ids, int):
                return ("closed", "board gone") if ids in (404, 410) else ("unknown", f"HTTP {ids}")
            return ("open", "") if m_.group(1) in ids else ("closed", "not on board")
        elif src == "workday":
            m_ = re.match(r"https://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/en-US/([^/]+)(/job/.+)$", url, re.I)
            if not m_: return "unknown", "cannot map"
            t, wd, site, path = m_.groups()
            x = c.get(f"https://{t}.{wd}.myworkdayjobs.com/wday/cxs/{t}/{site}{path}")
        elif src == "oracle":
            m_ = re.match(r"https://([^/]+)/hcmUI/CandidateExperience/[a-z-]+/sites/([^/]+)/job/(\d+)", url)
            if not m_: return "unknown", "cannot map"
            h, site, jid = m_.groups()
            x = c.get(f"https://{h}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails",
                      params={"expand": "all", "onlyData": "true", "finder": f'ById;Id="{jid}",siteNumber={site}'},
                      headers={"Accept": "application/json"})
            if x.status == 200:
                d = x.json()
                return (("open", "") if d and d.get("items") else ("closed", "empty result"))
        elif src == "amazon":
            x = c.get(url)
        if x.status in (HOST_SKIPPED, ROBOTS_BLOCKED, 0):
            return "unknown", x.reason or str(x.status)
        return result(x.status), (f"HTTP {x.status}" if x.status != 200 else "")
    except Exception as e:
        return "unknown", type(e).__name__

out = {}
for src in SOURCES:
    pool = by[src]
    sample = random.sample(pool, min(N, len(pool)))
    t0 = time.time()
    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(check, sample))
    cnt = collections.Counter(r for r, _ in res)
    why = collections.Counter(w for r, w in res if r != "open")
    n = len(sample)
    known = cnt["open"] + cnt["closed"]
    out[src] = {"built_rows_in_source": len(pool), "sampled": n, "open": cnt["open"], "closed": cnt["closed"],
                "unknown": cnt["unknown"], "open_rate_of_all": round(cnt["open"] / n, 3),
                "open_rate_of_checked": round(cnt["open"] / known, 3) if known else None,
                "reasons": dict(why.most_common(5)), "seconds": round(time.time() - t0),
                "examples_closed": [s[5] for s, (r, _) in zip(sample, res) if r == "closed"][:3]}
    print(src, json.dumps(out[src]), flush=True)
out["_blocked_hosts"] = c.blocked
Path(root / "work" / "quality-sample.json").write_text(json.dumps(out, indent=1))
