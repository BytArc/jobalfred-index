"""Find the careers systems of list members that have no roles in the index yet, reusing the VC session's probe (startups.probe_company).

Usage: companies_probe.py LIST [LIST ...] [--limit N] [--again] [--threads N]
       e.g. bigtech ailab   then   sp500 psi20 big4 consulting   then the other indexes by GDP rank
For each member that work/companies_coverage.json lists as missing (scripts/companies_coverage.py), and that was not probed before
(data/companies/probed.json; --again probes them anyway):
  1. its website: the curated domain or the one its Wikipedia infobox gives (scripts/companies_refresh.py). Never a guess: a member
     with no known website is recorded as no_website_found.
  2. startups.probe_company(client, website): reads the homepage and careers page(s) and names the ATS board, or says why it cannot
     (robots.txt, bot check, LinkedIn only, no adapter). Polite client, robots.txt obeyed, 403/429 and bot checks never worked around,
     no logins. LinkedIn, Indeed, Glassdoor and Naukri are never read.
  3. when the pages name no board: the member's own name tried on Lever and Ashby, kept only when the postings name the member.
  4. every board found is read once with the index's own adapter, as the nightly run will; a board that answers 403, is closed by
     robots.txt, no longer exists or does not fit the adapter is recorded with that status and not kept.
Boards we have an adapter for go to data/companies/tenants.json (loaded by the nightly run with --extra-tenants) carrying the member's
name, so its rows are labelled with it. Every member's outcome goes to data/companies/probed.json (status, website, boards, date).
"""
import collections, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import companies, startups
from jobalfred_index.adapters import SOURCES
from jobalfred_index.polite import Client
from jobalfred_index.startups import ROBOTS_BLOCKED_ATS
sys.path.insert(0, str(root / "scripts"))
from companies_refresh import clean_name

EXCLUDED = ("linkedin.", "indeed.", "glassdoor.", "naukri.")
MIN_PAGE_ROLES = 3     # a careers page that shows one or two role-like links is a page about careers, not a list of roles
# a careers page about people, stories or culture lists people, not roles
NOT_A_JOBS_PAGE = re.compile(r"(?i)stor(?:y|ies)|people|team|culture|life-at|blog|news|events?/")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
limit = 10 ** 9
if "--limit" in sys.argv:
    limit = int(sys.argv[sys.argv.index("--limit") + 1])
    args = [a for a in args if a != str(limit)]
again = "--again" in sys.argv
threads = 12
if "--threads" in sys.argv:
    threads = int(sys.argv[sys.argv.index("--threads") + 1])
    args = [a for a in args if a != str(threads)]
cov = json.loads((root / "work" / "companies_coverage.json").read_text())
lists = companies.lists()
D = root / "data" / "companies"
tenants_p, probed_p = D / "tenants.json", D / "probed.json"
tenants = json.loads(tenants_p.read_text()) if tenants_p.exists() else {"tenants": []}
probed = json.loads(probed_p.read_text()) if probed_p.exists() else {}
client = Client()
jobs = []
for code in args:
    members = {m["name"]: m for m in lists[code]["members"]}
    todo = [n for n in cov[code]["missing"] if again or n not in probed.get(code, {})]
    for name in todo[:limit]:
        m = members[name]
        display = name if lists[code]["curated"] else (clean_name(name) or name)
        jobs.append((code, name, display, m.get("domain", "")))


def in_country(ats, slug, display, hq) -> bool:
    try:
        return any(j.cc == hq for j in SOURCES[ats].fetch(client, {"key": slug, "name": display, "_ats": ats}))
    except Exception:
        return False


def one(job):
    code, name, display, domain = job
    curated = lists[code]["curated"]
    hq = next((m.get("hq") or lists[code].get("hq", "") for m in lists[code]["members"] if m["name"] == name), "")
    if not domain:
        return code, name, display, "", {"status": "no_website_found", "tenants": []}
    if any(x in domain for x in EXCLUDED):
        return code, name, display, domain, {"status": "excluded_site", "tenants": []}
    try:
        res = startups.probe_company(client, "https://" + domain)
    except Exception as e:
        return code, name, display, domain, {"status": "probe_error", "note": type(e).__name__, "tenants": []}
    if not [t for t in res.get("tenants", []) if t["ats"] not in ROBOTS_BLOCKED_ATS] and res.get("status") not in ("site_blocked", "site_robots"):
        # the VC probe's second pass, only on boards whose postings must name the company (Lever, Ashby): a bare name match on Workable
        # or Greenhouse also matches unrelated small firms called Meta or Bain, and a big firm must never get another firm's roles
        for slug in startups.guess_slugs(display, domain):
            hit = next((a for a in ("lever", "ashby") if startups.verify_board(client, a, slug, display, domain) == "yes"), None)
            if hit and not curated and hq and not in_country(hit, slug, display, hq):
                res["note"] = f"{hit} board '{slug}' names {display} but has no role in {hq}: a namesake, not kept"
                hit = None
            if hit:
                res["tenants"] = list(res.get("tenants", [])) + [{"ats": hit, "key": slug, "data": {}}]
                res["status"], res["note"] = "ats", "board name checked against the postings"
                break
    return code, name, display, domain, res


def read_board(t: dict, display: str) -> tuple[int, str]:
    """Read a found board once with the index's own adapter, as the nightly run will: (roles, "") or (0, why it cannot be read)."""
    src = SOURCES[t["ats"]]
    try:
        jobs = src.fetch(client, {"key": t["key"], **(t.get("data") or {}), "name": display, "_ats": t["ats"]})
        return len(jobs), ""
    except Exception as e:                                         # Failed and Gone carry the reason; anything else is an adapter mismatch
        msg = str(e)
        if "robots" in msg:
            return 0, "ats_robots_blocked"
        if "403" in msg or "forbidden" in msg or "challenge" in msg or "429" in msg:
            return 0, "ats_blocked"
        if type(e).__name__ in ("Gone",) or "no such site" in msg or "422" in msg or "404" in msg:
            return 0, "ats_gone"
        return 0, "ats_no_adapter"


def own_board(t, display, domain) -> bool:
    """A small-business board linked from a member's site must carry the member's own name (kkr.com links a board called "stage")."""
    if t["ats"] in companies.ENTERPRISE_ATS or t["ats"] in ("jsonld", "pagelist", "jobs2web", "careers-page"):
        return True
    labels = {companies.norm(display), companies._label(domain)}
    return companies._key_matches(companies.norm(t["key"].split("|")[0].split(".")[0]), labels)


t0 = time.time()
with ThreadPoolExecutor(threads) as ex:          # one member per thread; the client paces every host on its own
    results = list(ex.map(one, jobs))
have = {(t["ats"], t["key"]): t for t in tenants["tenants"]}
added = 0
today = time.strftime("%Y-%m-%d")
picked = []
for code, name, display, domain, res in results:
    usable = [t for t in res.get("tenants", []) if t["ats"] in SOURCES and t["ats"] not in ROBOTS_BLOCKED_ATS
              and not (t["ats"] == "pagelist" and NOT_A_JOBS_PAGE.search(t["key"])) and own_board(t, display, domain)]
    picked.append(usable)
with ThreadPoolExecutor(threads) as ex:
    reads = list(ex.map(lambda ud: [read_board(t, ud[1]) for t in ud[0]], [(u, r[2]) for u, r in zip(picked, results)]))
for (code, name, display, domain, res), usable0, read in zip(results, picked, reads):
    usable = [t for t, (n, err) in zip(usable0, read) if not err and not (t["ats"] in ("pagelist", "jsonld") and n < MIN_PAGE_ROLES)]
    status = res.get("status") or ""
    if status in ("ats", "jsonld", "careers_page_list") and not usable:
        errs = [err for _, err in read if err]
        status = errs[0] if errs else ("careers_no_ats" if status != "ats" else "ats_no_adapter")
    probed.setdefault(code, {})[name] = {"status": status, "website": domain, "careers": res.get("careers", ""), "note": res.get("note", ""),
                                         "boards": [[t["ats"], t["key"]] for t in res.get("tenants", [])],
                                         "read": [[t["ats"], t["key"], n] for t, (n, err) in zip(usable0, read) if t in usable], "checked": today}
    for t in usable:
        k = (t["ats"], t["key"])
        if k in have:
            have[k].setdefault("data", {}).setdefault("name", display)
            continue
        rec = {"ats": t["ats"], "key": t["key"], "data": {**(t.get("data") or {}), "name": display}, "source": f"companies:{code}"}
        tenants["tenants"].append(rec)
        have[k] = rec
        added += 1
tenants["tenants"].sort(key=lambda t: (t["source"], t["ats"], t["key"]))
tenants_p.write_text(json.dumps(tenants, ensure_ascii=False, indent=0))
probed_p.write_text(json.dumps(probed, ensure_ascii=False, indent=1))
for code in args:
    print(code, dict(collections.Counter(v["status"] for v in probed.get(code, {}).values())))
print(f"{len(results)} members probed, {added} new boards in {int(time.time() - t0)}s; http {dict(client.stats)}; "
      f"blocked hosts {list(client.blocked.items())[:12]}")
