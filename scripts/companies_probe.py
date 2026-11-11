"""Find the careers systems of list members that have no roles in the index yet, reusing the VC session's probe (startups.probe_company).

Usage: companies_probe.py LIST [LIST ...] [--limit N]       e.g. bigtech ailab big4 consulting      then sp500 psi20
For each member listed in work/companies_coverage.json as missing (scripts/companies_coverage.py):
  1. a website: the curated domain, else the validated guess industry.Homepages makes from the name (the page must name the company);
  2. startups.probe_company(client, website): reads its careers page(s) and names the ATS tenant, or says why it cannot (robots, bot
     check, LinkedIn only, no adapter) - polite client, robots.txt obeyed, nothing bypassed, no logins.
Writes data/companies/tenants.json ({"tenants": [...]}, loaded by `--extra-tenants`), data/companies/domains.json (member -> domain,
used for list matching) and work/companies_probe.json (status per member, for the report).
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import companies, industry, startups
from jobalfred_index.polite import Client
from jobalfred_index.startups import ROBOTS_BLOCKED_ATS

args = [a for a in sys.argv[1:] if not a.startswith("--")]
limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10 ** 9
if "--limit" in sys.argv:
    args = [a for a in args if not a.isdigit()]
cov = json.loads((root / "work" / "companies_coverage.json").read_text())
lists = companies.lists()
D = root / "data" / "companies"
tenants_p, domains_p = D / "tenants.json", D / "domains.json"
tenants = json.loads(tenants_p.read_text()) if tenants_p.exists() else {"tenants": []}
domains = json.loads(domains_p.read_text()) if domains_p.exists() else {}
client = Client()
hp = industry.Homepages(client=client, budget=10 ** 6)
jobs = []
for code in args:
    members = {m["name"]: m for m in lists[code]["members"]}
    for name in cov[code]["missing"][:limit]:
        jobs.append((code, name, members[name].get("domain", "")))


def one(job):
    code, name, domain = job
    if not domain:
        e = hp.fetch("c:" + industry.norm(name), name, "")
        domain = e.get("d") if (e.get("t") or e.get("m")) else ""
    if not domain:
        return code, name, "", {"status": "no_website_found", "tenants": []}
    try:
        res = startups.probe_company(client, "https://" + domain)
    except Exception as e:
        return code, name, domain, {"status": "probe_error", "note": type(e).__name__, "tenants": []}
    if not [t for t in res.get("tenants", []) if t["ats"] not in ROBOTS_BLOCKED_ATS]:
        # second pass, as the VC probe does, but only on boards whose postings must mention the company's name or domain (Lever, Ashby): a bare name match on
        # Workable or Greenhouse also matches unrelated small firms called Meta or Bain, and a big firm must never get another firm's roles
        for slug in startups.guess_slugs(name, domain):
            hit = next((a for a in ("lever", "ashby") if startups.verify_board(client, a, slug, name, domain) == "yes"), None)
            if hit:
                res["tenants"] = list(res.get("tenants", [])) + [{"ats": hit, "key": slug, "data": {}}]
                res["status"] = "ats"
                res["note"] = "board name guess"
                break
    return code, name, domain, res


t0 = time.time()
with ThreadPoolExecutor(12) as ex:
    results = list(ex.map(one, jobs))
have = {(t["ats"], t["key"]) for t in tenants["tenants"]}
report, added = {}, 0
for code, name, domain, res in results:
    report.setdefault(code, {})[name] = {"domain": domain, "status": res.get("status"), "careers": res.get("careers", ""), "note": res.get("note", ""),
                                         "tenants": [[t["ats"], t["key"]] for t in res.get("tenants", [])]}
    if domain:
        domains.setdefault(code, {})[name] = domain
    for t in res.get("tenants", []):
        if t["ats"] in ROBOTS_BLOCKED_ATS or (t["ats"], t["key"]) in have:
            continue
        have.add((t["ats"], t["key"]))
        tenants["tenants"].append({"ats": t["ats"], "key": t["key"], "data": t.get("data") or {}, "source": f"companies:{code}"})
        added += 1
tenants_p.write_text(json.dumps(tenants, ensure_ascii=False, indent=0))
domains_p.write_text(json.dumps(domains, ensure_ascii=False, indent=0))
(root / "work" / "companies_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
import collections
for code in args:
    c = collections.Counter(v["status"] for v in report.get(code, {}).values())
    print(code, dict(c))
print(f"{added} new tenants in {int(time.time() - t0)}s; http {dict(client.stats)}; blocked hosts {list(client.blocked.items())[:10]}")
