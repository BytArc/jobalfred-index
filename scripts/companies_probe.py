"""Find the careers systems of list members that have no roles in the index yet, reusing the VC session's probe (startups.probe_company).

Usage: companies_probe.py LIST [LIST ...] [--limit N] [--again]
       e.g. bigtech ailab   then   sp500 psi20 big4 consulting   then the other indexes by GDP rank
For each member that work/companies_coverage.json lists as missing (scripts/companies_coverage.py), and that was not probed before
(data/companies/probed.json; --again probes them anyway):
  1. its website: the curated domain or the one its Wikipedia infobox gives (scripts/companies_refresh.py). Never a guess: a member
     with no known website is recorded as no_website_found.
  2. startups.probe_company(client, website): reads the homepage and careers page(s) and names the ATS board, or says why it cannot
     (robots.txt, bot check, LinkedIn only, no adapter). Polite client, robots.txt obeyed, 403/429 and bot checks never worked around,
     no logins. LinkedIn, Indeed, Glassdoor and Naukri are never read.
  3. when the pages name no board: the member's own name tried on Lever and Ashby, kept only when the postings name the member.
Boards we have an adapter for go to data/companies/tenants.json (loaded by the nightly run with --extra-tenants) carrying the member's
name, so its rows are labelled with it. Every member's outcome goes to data/companies/probed.json (status, website, boards, date).
"""
import collections, json, sys, time
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
args = [a for a in sys.argv[1:] if not a.startswith("--")]
limit = 10 ** 9
if "--limit" in sys.argv:
    limit = int(sys.argv[sys.argv.index("--limit") + 1])
    args = [a for a in args if a != str(limit)]
again = "--again" in sys.argv
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


def one(job):
    code, name, display, domain = job
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
            if hit:
                res["tenants"] = list(res.get("tenants", [])) + [{"ats": hit, "key": slug, "data": {}}]
                res["status"], res["note"] = "ats", "board name checked against the postings"
                break
    return code, name, display, domain, res


t0 = time.time()
with ThreadPoolExecutor(12) as ex:
    results = list(ex.map(one, jobs))
have = {(t["ats"], t["key"]): t for t in tenants["tenants"]}
added = 0
today = time.strftime("%Y-%m-%d")
for code, name, display, domain, res in results:
    usable = [t for t in res.get("tenants", []) if t["ats"] in SOURCES and t["ats"] not in ROBOTS_BLOCKED_ATS]
    status = res.get("status") or ""
    if status == "ats" and not usable:
        status = "ats_no_adapter"
    probed.setdefault(code, {})[name] = {"status": status, "website": domain, "careers": res.get("careers", ""), "note": res.get("note", ""),
                                         "boards": [[t["ats"], t["key"]] for t in res.get("tenants", [])], "checked": today}
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
