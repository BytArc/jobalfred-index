"""Draw a random sample of untagged roles, fetch each public job page, and print the evidence a reader needs to judge the level.

Usage:
  seniority_sample.py draw ROUND N SEED     draw + fetch + save work/sen/round-ROUND.json, print a compact view
  seniority_sample.py show ROUND            print the compact view again
Public pages and public APIs only, honest user agent, robots.txt obeyed, 403/429 skip the row.
"""
import collections, gzip, html, json, random, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import seniority
from jobalfred_index.polite import Client
from jobalfred_index.state import State

UNTAGGED = {"workday", "oracle", "greenhouse", "lever", "ashby", "jazzhr", "bamboohr", "breezy", "gupy", "teamtailor", "recruitee",
            "icims", "comeet", "google", "apple", "eightfold", "arbeitnow", "weworkremotely", "remoteok", "rippling"}
STRATA = [("PT", 0.12), ("ES", 0.10), ("FR", 0.10), ("DE", 0.10), ("IT", 0.07), ("NL", 0.07), ("BR", 0.12), ("GB", 0.10), ("US", 0.12), ("IN", 0.05), ("CA", 0.05)]
c = Client()
TAG = re.compile(r"<[^>]+>")


def text_of(h: str) -> str:
    h = html.unescape(html.unescape(h or ""))
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|li|div|h\d|tr)>", "\n", h)
    return re.sub(r"[ \t\r\f]+", " ", TAG.sub(" ", h)).replace("\n ", "\n").strip()


def fetch_text(row, keymap, boards):
    u, ats = row[5], row[7]
    try:
        if ats == "workday":
            m = re.match(r"https://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/en-US/([^/]+)(/job/.+)$", u, re.I)
            if not m: return None
            t, wd, site, path = m.groups()
            x = c.get(f"https://{t}.{wd}.myworkdayjobs.com/wday/cxs/{t}/{site}{path}")
            return text_of(((x.json() or {}).get("jobPostingInfo") or {}).get("jobDescription")) if x.status == 200 else None
        if ats == "oracle":
            m = re.match(r"https://([^/]+)/hcmUI/CandidateExperience/[a-z-]+/sites/([^/]+)/job/(\d+)", u)
            if not m: return None
            h, site, jid = m.groups()
            x = c.get(f"https://{h}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails",
                      params={"expand": "all", "onlyData": "true", "finder": f'ById;Id="{jid}",siteNumber={site}'}, headers={"Accept": "application/json"})
            it = (((x.json() or {}).get("items") or [None])[0]) if x.status == 200 else None
            return text_of(" ".join(str(it.get(k) or "") for k in ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"))) if it else None
        if ats == "greenhouse":
            tok, m = keymap.get(u), re.search(r"(?:jobs/|gh_jid=)(\d+)", u)
            if not tok or not m: return None
            x = c.get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{m.group(1)}")
            return text_of((x.json() or {}).get("content")) if x.status == 200 else None
        if ats == "lever":
            tok, m = keymap.get(u), re.search(r"([0-9a-f-]{36})", u)
            if not tok or not m: return None
            x = c.get(f"https://api.lever.co/v0/postings/{tok}/{m.group(1)}")
            d = x.json() if x.status == 200 else None
            return (d.get("descriptionPlain", "") + " " + " ".join(text_of(l.get("content", "")) for l in d.get("lists", []))) if d else None
        if ats == "ashby":
            tok, m = keymap.get(u), re.search(r"([0-9a-f-]{36})", u)
            if not tok or not m: return None
            if tok not in boards:
                b = c.get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")
                boards[tok] = {j["id"]: j.get("descriptionPlain", "") for j in (b.json() or {}).get("jobs", [])} if b.status == 200 and b.json() else {}
            return boards[tok].get(m.group(1))
        x = c.get(u)
        if x.status != 200: return None
        body = x.text
        m = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.){80,})"', body)
        if m:
            try: return text_of(json.loads('"' + m.group(1) + '"'))
            except ValueError: pass
        return text_of(body)[:8000]
    except Exception:
        return None


def evidence(txt: str) -> str:
    t = re.sub(r"\s+", " ", txt)
    low = seniority.fold(t)
    ys = []
    for m in seniority.YEARS_SIMPLE.finditer(low):
        ys.append(t[max(0, m.start() - 35): m.end() + 30].strip())
        if len(ys) >= 3: break
    cues = [w for w in ("entry level", "no experience", "graduate", "mentor", "manage a team", "direct reports", "lead a team", "report to", "budget", "internship", "student", "stakeholder", "strategy")
            if w in low]
    return f"yrs={ys} cues={cues} | {t[:170]}"


def draw(rnd, n, seed):
    random.seed(seed)
    prev = set()
    for f in (root / "data" / "seniority").glob("labels-r*.jsonl"):
        prev |= {json.loads(l)["url"] for l in f.read_text().splitlines() if l.strip()}
    m = json.load(open(root / "dist" / "manifest.json"))
    pool = collections.defaultdict(list)
    for s in m["shards"]:
        for r in json.loads(gzip.decompress((root / "dist" / s["file"]).read_bytes()))["rows"]:
            if r[7] in UNTAGGED and r[5] not in prev and r[3]:
                pool[r[3]].append(r)
    st = State(root / "work" / "index.db", "sen")
    keymap = {}
    for ats, key, rows in st.iter_rows():
        if ats in ("greenhouse", "lever", "ashby"):
            for r in rows: keymap[r[5]] = key
    picks = []
    for cc, w in STRATA:
        k = max(1, round(n * w))
        lst = pool.get(cc, [])
        by = collections.defaultdict(list)
        for r in lst: by[r[7]].append(r)
        srcs = list(by)
        for _ in range(k):          # spread over sources first, then over rows
            if not srcs: break
            s = random.choice(srcs)
            picks.append(random.choice(by[s]))
    boards = {}
    with ThreadPoolExecutor(8) as ex:
        texts = list(ex.map(lambda r: fetch_text(r, keymap, boards), picks))
    out = []
    for r, tx in zip(picks, texts):
        if not tx or len(tx) < 120: continue
        lv, ls = seniority.label(r[0], None, None)
        out.append({"title": r[0], "company": r[1], "ats": r[7], "cc": r[3], "url": r[5], "pred": lv, "pred_src": ls,
                    "pred_desc": seniority.from_description(tx), "ev": evidence(tx), "text": tx[:6000]})
    json.dump(out, open(root / "work" / "sen" / f"round-{rnd}.json", "w"))
    print(len(picks), "drawn,", len(out), "with a readable page")


def show(rnd, blind=False):
    for i, o in enumerate(json.load(open(root / "work" / "sen" / f"round-{rnd}.json"))):
        p = "" if blind else f" | P={seniority.NAMES[o['pred']][:5]}/{seniority.NAMES[o['pred_desc']][:5]}"
        print(f"[{i}] {o['ats'][:4]} {o['cc']} | {o['title'][:70]}{p} | {o['ev'][:300]}")


if __name__ == "__main__":
    if sys.argv[1] == "draw": draw(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else: show(sys.argv[2], blind="--blind" in sys.argv)
