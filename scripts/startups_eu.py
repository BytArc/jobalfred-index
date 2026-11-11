"""European VC-backed startups: company list, overlap with known tenants, careers-system probe, publish, roles read.

  python scripts/startups_eu.py companies   # merge Seedtable pages, YC directory, VC portfolio pages -> work/vc_eu_companies.json
  python scripts/startups_eu.py measure     # how many company domains already have a tenant (latest release tenant list)
  python scripts/startups_eu.py probe       # read each missing company's own site for its ATS -> work/startups_probe.json
  python scripts/startups_eu.py guess       # second pass: board names on ATS endpoints, kept when the board names the company
  python scripts/startups_eu.py publish     # data/startups_eu.json (public) + work/startups_eu_private.json (stage data)
  python scripts/startups_eu.py roles       # fetch every startup tenant once, count roles -> work/startups_roles.json
  python scripts/startups_eu.py report      # numbers for REPORT.md -> work/startups_report.json

Inputs (all in work/, which is gitignored):
  seedtable_raw/<stage>-<page>.json   pages of the owner's Seedtable connector (list_companies, hq_continent=Europe,
                                      min_raised=1000000, one funding stage per file). Private: never published.
  yc_companies.json                   scripts/yc_directory.py
  vc_portfolios.json                  scripts/vc_portfolios.py
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jobalfred_index import geo, startups  # noqa: E402
from jobalfred_index.startups import registrable, ROBOTS_BLOCKED_ATS  # noqa: E402

WORK = ROOT / "work"
COMPANIES = WORK / "vc_eu_companies.json"
PROBE = WORK / "startups_probe.json"
PRIVATE = WORK / "startups_eu_private.json"
ROLES = WORK / "startups_roles.json"
RELEASE_TENANTS = WORK / "release" / "tenants.json.gz"
# REGION=world: the rest of the world, added in country batches (cmd_world); its own company list and public file,
# sharing the probe, name-check and roles caches with Europe (a domain's careers system does not depend on the region)
import os as _os
REGION = _os.environ.get("REGION", "eu")
if REGION == "world":
    COMPANIES = WORK / "vc_world_companies.json"
    PRIVATE = WORK / "startups_world_private.json"
    startups.DATA = ROOT / "data" / "startups_world.json"
JOBS_COV = WORK / ("coverage-jobs-latest.json" if REGION != "world" else "coverage-jobs-latest-world.json")
ADAPTED = {"join", "welcomekit", "gem"}   # recognised as detect-only by the probe, read by an adapter now


def adapted_tenant(name: str, key: str) -> dict:
    if name == "welcomekit":   # Welcome Kit career sites carry JobPosting markup on each job page
        host = f"{key}.welcomekit.co"
        return {"ats": "jsonld", "key": host, "data": {"host": host, "pages": [f"https://{host}/"]}}
    return {"ats": name, "key": key, "data": {}}

EUROPE = set("AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT XK LV LI LT LU MT MD MC ME NL MK NO PL PT RO RU SM "
             "RS SK SI ES SE CH TR UA GB VA GI IM JE GG FO".split())
# ccTLDs that place a company in Europe when no list says where it is (used only for portfolio-page companies).
EU_TLD = {"de": "DE", "fr": "FR", "es": "ES", "it": "IT", "nl": "NL", "be": "BE", "se": "SE", "dk": "DK", "no": "NO", "fi": "FI",
          "ie": "IE", "uk": "GB", "pt": "PT", "at": "AT", "ch": "CH", "pl": "PL", "cz": "CZ", "sk": "SK", "hu": "HU", "ro": "RO",
          "bg": "BG", "gr": "GR", "hr": "HR", "si": "SI", "rs": "RS", "ee": "EE", "lv": "LV", "lt": "LT", "lu": "LU", "mt": "MT",
          "cy": "CY", "ua": "UA", "is": "IS", "li": "LI", "eu": ""}
NOT_A_SITE = re.compile(r"(?i)^(linkedin|facebook|instagram|twitter|x|crunchbase|medium|github|angel|wellfound|google|apple|youtube|"
                        r"t|bit|linktr|notion|wix|webflow|framer|carrd|substack|f6s|eu-startups|dealroom|pitchbook)\.[a-z.]+$")
# links on a portfolio company page that point at press coverage, not at the company
NEWSY = re.compile(r"(?i)(news|magazine|journal|press|times|blog|insider|review|daily|weekly|podcast|gazette|herald|tribune|"
                   r"techcrunch|sifted|wired|forbes|fortune|venturebeat|tech\.eu|finextra|altfi|uktn|businesscloud)")
COUNTRY_NAME_FIX = {"Czech Republic": "CZ", "North Macedonia": "MK", "Kosovo": "XK", "Bosnia and Herzegovina": "BA",
                    "Turkey": "TR", "Russia": "RU", "San Marino": "SM", "Liechtenstein": "LI", "United Kingdom": "GB"}


def cc_of(country: str | None) -> str:
    if not country:
        return ""
    if len(country) == 2 and country.isupper():
        return country
    return COUNTRY_NAME_FIX.get(country) or geo.country_of(country) or ""


def site_domain(website: str | None) -> str:
    d = registrable(website or "")
    return "" if not d or NOT_A_SITE.match(d) else d


# -- 1. company list ----------------------------------------------------------------------------------------------
def cmd_companies() -> dict:
    out: dict[str, dict] = {}
    counts = collections.Counter()
    for f in sorted(glob.glob(str(WORK / "seedtable_raw" / "*.json"))):
        for c in json.load(open(f)).get("data", []):
            counts["seedtable_rows"] += 1
            d = site_domain(c.get("website"))
            if not d:
                counts["seedtable_no_website"] += 1
                continue
            rec = out.setdefault(d, {"domain": d, "name": c.get("name"), "website": c.get("website"), "sources": []})
            if "seedtable" in rec["sources"]:
                counts["seedtable_same_domain_twice"] += 1
                continue
            rec["sources"].append("seedtable")
            rec.update({"country": cc_of(c.get("country")), "city": c.get("city"), "stage": c.get("fundingStage"),
                        "last_round": (c.get("lastFundingDate") or "")[:10], "total_funding": c.get("totalFunding"),
                        "seedtable_id": c.get("id"), "hq_from": "seedtable"})
    counts["seedtable_domains"] = sum(1 for r in out.values() if "seedtable" in r["sources"])
    # country listings without the funding filter (work/seedtable_listings/<CC>-*.json): a country's startups that Seedtable
    # lists with no disclosed round. Added as backing "listed" (not claimed as VC-backed) so their roles are read too.
    for f in sorted(glob.glob(str(WORK / "seedtable_listings" / "*.json"))):
        for c in json.load(open(f)).get("data", []):
            d = site_domain(c.get("website"))
            if not d or d in out or c.get("status") not in (None, "active"):
                continue
            out[d] = {"domain": d, "name": c.get("name"), "website": c.get("website"), "sources": ["seedtable-listing"],
                      "country": cc_of(c.get("country")), "city": c.get("city"), "stage": c.get("fundingStage"),
                      "seedtable_id": c.get("id"), "hq_from": "seedtable", "backing": "listed"}
            counts["seedtable_listing_added"] += 1

    yc_path = WORK / "yc_companies.json"
    if yc_path.exists():
        yc = json.load(open(yc_path))["companies"]
        counts["yc_read"] = len(yc)
        for slug, c in yc.items():
            if (c.get("country") or "") not in EUROPE:
                continue
            counts["yc_europe"] += 1
            if c.get("ycdc_status") != "Active":
                counts["yc_europe_not_active"] += 1
                continue
            d = site_domain(c.get("website"))
            if not d:
                counts["yc_europe_no_website"] += 1
                continue
            counts["yc_europe_active"] += 1
            rec = out.setdefault(d, {"domain": d, "name": c.get("name"), "website": c.get("website"), "sources": []})
            if "yc" not in rec["sources"]:
                rec["sources"].append("yc")
            rec.setdefault("country", c.get("country"))
            rec.setdefault("hq_from", "yc")
            rec["yc"] = {"slug": slug, "batch": c.get("batch"), "country": c.get("country")}
            rec.setdefault("evidence", []).append(f"https://www.ycombinator.com/companies/{slug}")
    pf_path = WORK / "vc_portfolios.json"
    hq_seen = hq_known()
    if pf_path.exists():
        pf = json.load(open(pf_path))
        for inv, rec_inv in pf.items():
            page = (rec_inv.get("pages") or [""])[0]
            for d in rec_inv.get("domains", []):
                if NOT_A_SITE.match(d) or NEWSY.search(d.split(".")[0]):
                    continue
                counts["portfolio_links"] += 1
                rec = out.get(d)
                if rec is None:
                    tld = d.rsplit(".", 1)[-1]
                    h = hq_seen.get(d) or {}
                    if h.get("country") in EUROPE and not big_listed(d) and not startups.excluded(d):
                        rec = out.setdefault(d, site_hq_record(d, h))      # its own site says where it is
                        counts["portfolio_new_european_by_site"] += 1
                    elif tld not in EU_TLD:
                        counts["portfolio_domain_not_known_european"] += 1
                        continue
                    else:
                        rec = out.setdefault(d, {"domain": d, "name": d.split(".")[0].replace("-", " ").title(),
                                                 "website": f"https://{d}/", "sources": [], "country": EU_TLD[tld],
                                                 "hq_from": "cctld"})
                        counts["portfolio_new_european_by_cctld"] += 1
                if "portfolio" not in rec["sources"]:
                    rec["sources"].append("portfolio")
                rec.setdefault("investors", [])
                if inv not in rec["investors"]:
                    rec["investors"].append(inv)
                    rec.setdefault("evidence", []).append(page or inv)
    counts["companies"] = len(out)
    counts["by_source_combo"] = dict(collections.Counter("+".join(sorted(r["sources"])) for r in out.values()))
    doc = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "counts": dict(counts),
           "companies": sorted(out.values(), key=lambda r: r["domain"])}
    COMPANIES.write_text(json.dumps(doc, indent=0, ensure_ascii=False))
    print(json.dumps(dict(counts), indent=1))
    return doc


# -- 1b. the rest of the world, a batch of countries at a time (public sources only) ---------------------------------
def cmd_world(countries: list[str]) -> dict:
    """Add the startups headquartered in `countries` (ISO codes) to the world list: Y Combinator's directory (its page
    gives the headquarters), plus the investors' portfolio pages for companies whose headquarters YC confirms.
    Europe stays in its own list. Existing entries are kept, so batches accumulate."""
    countries = [c.upper() for c in countries if c.upper() not in EUROPE]
    doc = json.load(open(COMPANIES)) if COMPANIES.exists() else {"companies": [], "batches": []}
    have = {r["domain"]: r for r in doc["companies"]}
    yc = json.load(open(WORK / "yc_companies.json"))["companies"]
    pf = json.load(open(WORK / "vc_portfolios.json")) if (WORK / "vc_portfolios.json").exists() else {}
    by_dom: dict[str, list] = {}
    for inv, rec in pf.items():
        for d in rec.get("domains", []):
            by_dom.setdefault(d, []).append((inv, (rec.get("pages") or [inv])[0]))
    added = collections.Counter()
    for slug, c in yc.items():
        if c.get("country") not in countries or c.get("ycdc_status") != "Active":
            continue
        d = site_domain(c.get("website"))
        if not d:
            continue
        if d in have:                                  # already listed: only gains investor pages read since
            rec = have[d]
            for inv, page in by_dom.get(d, []):
                if page not in rec.setdefault("evidence", []):
                    rec["evidence"].append(page)
                    rec.setdefault("investors", []).append(inv)
                    if "portfolio" not in rec["sources"]:
                        rec["sources"].append("portfolio")
            continue
        rec = {"domain": d, "name": c.get("name"), "website": c.get("website"), "country": c["country"], "sources": ["yc"],
               "hq_from": "yc", "yc": {"slug": slug, "batch": c.get("batch"), "country": c["country"], "tags": c.get("tags")},
               "evidence": [f"https://www.ycombinator.com/companies/{slug}"]}
        for inv, page in by_dom.get(d, []):
            rec.setdefault("investors", []).append(inv)
            rec["evidence"].append(page)
            if "portfolio" not in rec["sources"]:
                rec["sources"].append("portfolio")
        have[d] = rec
        added[c["country"]] += 1
    hq_seen = hq_known()
    for d, pages in fund_only_domains(set(have)).items():
        h = hq_seen.get(d) or {}
        if h.get("country") not in countries:
            continue
        rec = site_hq_record(d, h)
        rec["sources"] = ["portfolio"]
        rec["investors"] = sorted({inv for inv, _ in pages})
        rec["evidence"] = list(dict.fromkeys(page for _, page in pages))
        have[d] = rec
        added[h["country"] + " (own site)"] += 1
    doc["companies"] = sorted(have.values(), key=lambda r: r["domain"])
    doc["batches"] = list(dict.fromkeys((doc.get("batches") or []) + countries))
    doc["built"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc["counts"] = {"companies": len(doc["companies"]), "by_country": dict(collections.Counter(r["country"] for r in doc["companies"]))}
    COMPANIES.write_text(json.dumps(doc, indent=0, ensure_ascii=False))
    print(f"world list: +{sum(added.values())} companies {dict(added)}; {len(doc['companies'])} in all; batches {doc['batches']}")
    return doc


# -- 1c. companies known only from investors' pages: headquarters from their own sites (jobalfred_index/hq.py) ----------
HQ_CACHE = WORK / "hq_sites.json"
HQ_PER_RUN = 400            # company sites read for their headquarters per weekly refresh
big_listed = startups.big_listed


def hq_known() -> dict:
    """domain -> HQ record ({"country": "" } when the site states none) from this Mac's reads and the published lists."""
    out: dict = {}
    for path in (ROOT / "data" / "startups_eu.json", ROOT / "data" / "startups_world.json"):
        if path.exists():
            for d, c in (json.load(open(path)).get("hq") or {}).items():
                out.setdefault(d, {"country": c})
    if HQ_CACHE.exists():
        out.update(json.load(open(HQ_CACHE)))
    return out


def site_hq_record(d: str, h: dict) -> dict:
    """A company list entry for a company known from investors' pages whose own site gives its headquarters."""
    name = (h.get("name") or "").strip()
    label, fn = startups._fold(d.split(".")[0]), startups._fold(name)
    if not name or len(name) > 40 or not fn or not (label in fn or (len(fn) >= 3 and fn in label)):
        name = d.split(".")[0].replace("-", " ").title()        # the site's title does not name the company
    return {"domain": d, "name": name, "website": f"https://{d}/", "sources": [], "country": h["country"], "hq_from": "site",
            "hq_url": h.get("url") or f"https://{d}/", "hq_text": (h.get("evidence") or "")[:160]}


def fund_only_domains(listed: set[str]) -> dict[str, list]:
    """domain -> [(investor, page)] for investors' portfolio links that are not listed yet and could be a company."""
    pf = json.load(open(WORK / "vc_portfolios.json")) if (WORK / "vc_portfolios.json").exists() else {}
    out: dict[str, list] = {}
    for inv, rec in pf.items():
        page = (rec.get("pages") or [inv])[0]
        for d in rec.get("domains", []):
            if d in listed or NOT_A_SITE.match(d) or NEWSY.search(d.split(".")[0]) or startups.excluded(d) or big_listed(d):
                continue
            out.setdefault(d, []).append((inv, page))
    return out


def read_hq(domains: list[str], minutes: float, log=print, workers: int = 40) -> dict:
    """Read each company's own site for its headquarters (hq.read); returns {domain: record}."""
    from jobalfred_index import hq
    from jobalfred_index.polite import Client
    client = Client(timeout=15, retries=1)
    client.deadline = time.time() + minutes * 60
    out: dict = {}

    def one(d):
        if time.time() > client.deadline:
            return d, None
        try:
            return d, hq.read(client, d)
        except Exception as e:
            return d, {"domain": d, "status": "error", "note": type(e).__name__}

    with ThreadPoolExecutor(workers) as ex:
        for i, (d, r) in enumerate(ex.map(one, domains), 1):
            if r is not None and r.get("status") not in ("error",) and "run time box" not in (r.get("note") or ""):
                out[d] = {k: v for k, v in r.items() if k != "pages"}
            if i % 250 == 0:
                log(f"hq: {i}/{len(domains)} read, {sum(1 for x in out.values() if x.get('country'))} with a country")
    return out


def cmd_hq(minutes: float = 90) -> None:
    listed = {c["domain"] for f in ("vc_eu_companies.json", "vc_world_companies.json") if (WORK / f).exists()
              for c in json.load(open(WORK / f))["companies"]}
    known = json.load(open(HQ_CACHE)) if HQ_CACHE.exists() else {}
    todo = sorted(d for d in fund_only_domains(listed) if d not in known)
    print(f"hq: {len(todo)} companies known only from investors' pages to read", flush=True)
    chunk = 500
    for i in range(0, len(todo), chunk):
        got = read_hq(todo[i:i + chunk], minutes, log=lambda m: print(m, flush=True))
        known.update(got)
        HQ_CACHE.write_text(json.dumps(known, indent=0, ensure_ascii=False))
        print(f"hq: {len(known)} read; " + json.dumps(collections.Counter(v.get("status") for v in known.values())), flush=True)


def cmd_investors() -> dict:
    """Add the investors themselves (data/vc_investors.json) to the world list as kind "investor", so the roles VC firms
    post on their own careers systems are read like a startup's. Evidence: the firm's own site."""
    doc = json.load(open(COMPANIES)) if COMPANIES.exists() else {"companies": [], "batches": []}
    have = {r["domain"]: r for r in doc["companies"]}
    inv = json.loads((ROOT / "data" / "vc_investors.json").read_text())["investors"]
    added = 0
    for name, v in inv.items():
        d = site_domain((v.get("pages") or [""])[0])
        if not d or d in have:
            continue
        have[d] = {"domain": d, "name": name, "website": f"https://{d}/", "country": v.get("country", ""), "sources": ["investor"],
                   "kind": "investor", "evidence": [f"https://{d}/"]}
        added += 1
    doc["companies"] = sorted(have.values(), key=lambda r: r["domain"])
    COMPANIES.write_text(json.dumps(doc, indent=0, ensure_ascii=False))
    print(f"investors added: {added}; world list {len(doc['companies'])}")
    return doc


# -- 2. overlap with the tenants we already have ------------------------------------------------------------------
SLUG_ATS = {"greenhouse", "lever", "lever-eu", "ashby", "workable", "recruitee", "teamtailor", "bamboohr", "breezy", "personio",
            "smartrecruiters", "pinpoint", "jazzhr", "rippling", "gupy"}


def norm(s: str) -> str:
    s = re.sub(r"(?i)\b(inc|ltd|limited|gmbh|ag|sa|sas|bv|ab|as|oy|aps|plc|llc|srl|spa|se|technologies|labs|group|hq|io|ai|app)\b\.?", " ", s or "")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def tenant_index(path: Path = RELEASE_TENANTS):
    doc = json.load(gzip.open(path, "rt"))
    by_slug, by_name, by_host = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
    live = set()
    for t in doc["tenants"]:
        if t.get("dead"):
            continue
        ats, key, data = t["ats"], t["key"], t.get("data") or {}
        live.add((ats, key))
        if ats in SLUG_ATS:
            by_slug[key.lower()].add((ats, key))
        nm = norm(data.get("name") or "")
        if len(nm) >= 3:
            by_name[nm].add((ats, key))
        for h in (data.get("host"), data.get("domain")):
            d = registrable(h or "")
            if d and ats in ("jsonld", "eightfold", "teamtailor", "recruitee", "icims"):
                by_host[d].add((ats, key))
    return live, by_slug, by_name, by_host


def cmd_measure() -> dict:
    doc = json.load(open(COMPANIES))
    live, by_slug, by_name, by_host = tenant_index()
    c = collections.Counter()
    for r in doc["companies"]:
        d = r["domain"]
        label = d.split(".")[0]
        hits = {"host": by_host.get(d, set()),
                "slug": by_slug.get(label.lower(), set()) | by_slug.get(norm(r.get("name") or ""), set()),
                "name": by_name.get(norm(r.get("name") or ""), set())}
        r["_known"] = {k: sorted(map(list, v)) for k, v in hits.items() if v}
        if hits["host"]:
            c["by_host"] += 1
        if hits["slug"]:
            c["by_slug"] += 1
        if hits["name"]:
            c["by_name"] += 1
        if hits["host"] or hits["name"] or (hits["slug"] and len(label) >= 5):
            c["any_strong"] += 1
        if any(hits.values()):
            c["any"] += 1
    c["companies"] = len(doc["companies"])
    c["tenants_in_release_list"] = len(live)
    COMPANIES.write_text(json.dumps(doc, indent=0, ensure_ascii=False))
    print(json.dumps(dict(c), indent=1))
    return dict(c)


# -- 3. probe -----------------------------------------------------------------------------------------------------
def cmd_probe(workers: int = 64, limit: int = 0) -> None:
    """Companies not yet in the probe file are read; delete an entry to have it read again."""
    from jobalfred_index.polite import Client
    doc = json.load(open(COMPANIES))
    done = json.load(open(PROBE)) if PROBE.exists() else {}
    todo = [r for r in doc["companies"] if r["domain"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"probe: {len(done)} done, {len(todo)} to go", flush=True)
    client = Client(timeout=15, retries=1)
    t0, n = time.time(), 0

    def one(r):
        try:
            return r["domain"], startups.probe_company(client, r.get("website") or ("https://" + r["domain"]))
        except Exception as e:  # never lose the run to one odd site
            return r["domain"], {"status": "probe_error", "note": f"{type(e).__name__}: {e}"[:200], "tenants": [], "other": {}}

    with ThreadPoolExecutor(workers) as ex:
        for dom, res in ex.map(one, todo):
            done[dom] = res
            n += 1
            if n % 500 == 0:
                PROBE.write_text(json.dumps(done, separators=(",", ":")))
                st = collections.Counter(v["status"] for v in done.values())
                print(f"{n}/{len(todo)} {int(time.time() - t0)}s {client.stats['requests']} req {client.stats['bytes'] // 1_000_000} MB "
                      f"{dict(st.most_common(6))}", flush=True)
    PROBE.write_text(json.dumps(done, separators=(",", ":")))
    print(json.dumps(collections.Counter(v["status"] for v in done.values()), indent=1))


# -- 3b. second pass: board names on the ATSs' public endpoints, kept only when the board names the company ----------
GUESS = WORK / "startups_guess.json"
GUESS_STATUSES = {"careers_no_ats", "no_careers_page", "linkedin_only", "site_robots", "site_blocked"}


def cmd_guess(minutes: float = 100, only: str = "", gap: float = 0.0) -> None:
    import threading
    from jobalfred_index.polite import Client
    doc = json.load(open(COMPANIES))
    probe = json.load(open(PROBE))
    out_path = WORK / f"startups_guess_{only.replace(',', '_')}.json" if only else GUESS
    done = json.load(open(out_path)) if out_path.exists() else {}
    for f in glob.glob(str(WORK / "startups_guess*.json")):      # what another pass already settled is not asked again
        if Path(f) != out_path:
            for dom, a in json.load(open(f)).items():
                for ats, sl in a.items():
                    for k, v in sl.items():
                        if v in ("yes", "no"):
                            done.setdefault(dom, {}).setdefault(ats, {}).setdefault(k, v)
    lock = threading.Lock()
    client = Client(timeout=20, retries=1)
    client.configure_host("apply.workable.com", gap=max(2.5, gap), inflight=1)
    if gap:   # a gentler pace for the subdomain platforms, which answered 429 at the default family pace
        for fam in (".recruitee.com", ".teamtailor.com"):
            client.configure_host(fam, gap=gap, inflight=2)
    client.deadline = time.time() + minutes * 60
    use = [a for a in startups.GUESS_ATS if not only or a in only.split(",")]
    plan: dict[str, list] = {a: [] for a in startups.GUESS_ATS}
    order = {"careers_no_ats": 0, "linkedin_only": 1, "no_careers_page": 2, "site_robots": 3, "site_blocked": 4}
    for r in sorted(doc["companies"], key=lambda r: order.get((probe.get(r["domain"]) or {}).get("status"), 9)):
        p = probe.get(r["domain"]) or {}
        if p.get("status") not in GUESS_STATUSES:
            continue
        slugs = startups.guess_slugs(r.get("name") or "", r["domain"])[:2]
        for ats in startups.GUESS_ATS:
            if ats == "workable" and p.get("status") != "careers_no_ats":
                continue        # one request per 2.5 s: spend it where a careers page exists
            for sl in (slugs[:1] if ats == "workable" else slugs):
                if (done.get(r["domain"], {}).get(ats) or {}).get(sl) not in ("yes", "no") and ats in use:
                    plan[ats].append((r, sl))       # an earlier "unknown" (host refused us that run) is asked again
    print("guess plan: " + ", ".join(f"{a}={len(v)}" for a, v in plan.items()), flush=True)
    counts = collections.Counter()

    def run(ats, items, workers):
        def one(item):
            r, sl = item
            v = startups.verify_board(client, ats, sl, r.get("name") or "", r["domain"])
            with lock:
                done.setdefault(r["domain"], {}).setdefault(ats, {})[sl] = v
                counts[(ats, v)] += 1
        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(one, items))

    workers = {"greenhouse": 3, "lever": 3, "ashby": 3, "join": 2, "recruitee": 6, "teamtailor": 6, "workable": 1}
    threads = [threading.Thread(target=run, args=(a, plan[a], workers[a]), daemon=True) for a in use]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(60)
        with lock:
            out_path.write_text(json.dumps(done, separators=(",", ":")))
            yes = {a: counts[(a, "yes")] for a in use}
            print(f"guess {int(time.time() - client.deadline + minutes * 60)}s {client.stats['requests']} req yes={yes} "
                  f"unknown={sum(v for (a, k), v in counts.items() if k == 'unknown')}", flush=True)
    out_path.write_text(json.dumps(done, separators=(",", ":")))
    print(json.dumps({f"{a}:{v}": n for (a, v), n in sorted(counts.items())}, indent=1))


# -- 4. publish ---------------------------------------------------------------------------------------------------
def vc_evidence(r: dict) -> list[str]:
    return list(dict.fromkeys(r.get("evidence") or []))


def hq_in_europe(r: dict) -> bool:
    return (r.get("country") or "") in EUROPE or r.get("hq_from") == "seedtable" or (r.get("hq_from") == "cctld")


def investor_own_board(t: dict, r: dict) -> bool:
    """A board that is the investor's own: named like the firm (greenhouse/generalcatalyst, ashby/firstround), or a careers
    page on the firm's own domain that is not a portfolio job board (jobs.<domain>, /jobs)."""
    from urllib.parse import urlsplit
    if t["ats"] in ("pagelist", "jsonld"):
        page = ((t.get("data") or {}).get("pages") or ["https://" + t["key"]])[0]
        sp = urlsplit(page)
        own = registrable(sp.hostname or "")             # project-a.com's site moved to project-a.vc: same name counts
        return ((own == r["domain"] or own.split(".")[0] == r["domain"].split(".")[0]) and not (sp.hostname or "").startswith("jobs.")
                and not re.match(r"(?i)^/(jobs|portfolio-jobs|talent)", sp.path or "/"))
    slug = startups._fold(t["key"].split("|")[0].split("/")[0].split(".")[0])
    names_ = {startups._fold(r["domain"].split(".")[0])} | {startups._fold(w) for w in re.findall(r"[A-Za-z0-9]{3,}", r.get("name") or "")}
    names_ -= {"", "capital", "ventures", "partners", "group", "fund", "the", "vc"}
    return any(n and (n in slug or (len(slug) >= 4 and slug in n)) for n in names_)


def startups_ats_ok() -> set[str]:
    from jobalfred_index.adapters import SOURCES
    return set(SOURCES) | set(ROBOTS_BLOCKED_ATS)


def cmd_publish() -> dict:
    doc = json.load(open(COMPANIES))
    probe = json.load(open(PROBE))
    guess: dict = {}
    for f in sorted(glob.glob(str(WORK / "startups_guess*.json"))):
        for dom, a in json.load(open(f)).items():
            for ats, sl in a.items():
                for k, v in sl.items():
                    if v == "yes" or k not in guess.get(dom, {}).get(ats, {}):
                        guess.setdefault(dom, {}).setdefault(ats, {})[k] = v
    render = json.load(open(WORK / "render_probe.json")) if (WORK / "render_probe.json").exists() else {}
    # a board that answered 404/410 when read and never answered well is not published (it would be asked every day)
    gone = set()
    if ROLES.exists():
        gone = {(t["ats"], t["key"]) for t in json.load(open(ROLES))["tenants"] if t.get("gone") and not t["ok"]}
    tenants: dict[tuple[str, str], dict] = {}
    companies, private, checked = [], [], []
    status, waiting = collections.Counter(), collections.Counter()
    for r in doc["companies"]:
        p = dict(probe.get(r["domain"]) or {})
        found_by = "page" if p.get("tenants") else ""
        rp = render.get(r["domain"]) or {}
        if rp.get("tenants") and not [t for t in p.get("tenants", []) if t["ats"] not in ROBOTS_BLOCKED_ATS]:
            # systems the company's own careers page loads when opened in a browser (found once; read without one)
            p["tenants"] = list(p.get("tenants", [])) + [t for t in rp["tenants"] if t["ats"] in startups_ats_ok()]
            found_by = found_by or "render"
        if rp.get("custom") and rp.get("careers") and not p.get("tenants"):
            host = startups.host_of(rp["careers"])
            p["tenants"] = [{"ats": a, "key": host, "data": {"host": host}} for a in rp["custom"]]
            found_by = found_by or "render"
        if rp.get("other") and not p.get("other"):
            p["other"] = rp["other"]
        for ats, slugs in (guess.get(r["domain"]) or {}).items():
            for sl, verdict in slugs.items():
                weak = (sl == r["domain"].split(".")[0] and len(sl) < 5 and sl != startups._fold(r.get("name") or "")
                        and r.get("kind") != "investor")        # investors' guessed boards were each checked by hand
                has = [t for t in p.get("tenants", []) if t["ats"] == ats and (r.get("kind") != "investor" or investor_own_board(t, r))]
                if verdict == "yes" and not weak and not has:
                    p["tenants"] = list(p.get("tenants", [])) + [{"ats": ats, "key": sl, "data": {}, "named": True}]
                    found_by = found_by or "name"
                    break
        for name, key in (p.get("other") or {}).items():      # found as detect-only, adapter built since
            if name in ADAPTED and not [t for t in p.get("tenants", []) if t["ats"] not in ROBOTS_BLOCKED_ATS]:
                p["tenants"] = list(p.get("tenants", [])) + [adapted_tenant(name, key)]
                found_by = found_by or "page"
        ts = [t for t in p.get("tenants", []) if t["ats"] not in ROBOTS_BLOCKED_ATS and (t["ats"], t["key"]) not in gone]
        if r.get("kind") == "investor":
            ts = [t for t in ts if investor_own_board(t, r)]   # a VC's site links its portfolio's boards: only its own count
        if len(ts) > 5:
            # a site that links many companies' job boards (a customer wall, a jobs directory) is not one careers system:
            # keep only boards named like the company itself
            me = {startups._fold(r.get("name") or ""), startups._fold(r["domain"].split(".")[0])} - {""}
            ts = [t for t in ts if any(m and (m in startups._fold(t["key"]) or startups._fold(t["key"].split("|")[0].split(".")[0]) in m)
                                       for m in me)]
        if ts and p.get("status") in ("ats_no_adapter", "linkedin_only", "careers_no_ats", "no_careers_page"):
            p["status"] = "ats"
        for t in ts:
            tenants.setdefault((t["ats"], t["key"]), t.get("data") or {})
        if ts and not startups.excluded(r["domain"]):
            entry = {"name": r.get("name"), "domain": r["domain"], "country": r.get("country") or "",
                     "evidence": vc_evidence(r) or ["Seedtable"], "tenants": [[t["ats"], t["key"]] for t in ts],
                     "backing": "listed" if r.get("backing") == "listed" and not vc_evidence(r) else "vc"}
            if r.get("kind") == "investor":
                entry["kind"], entry["backing"] = "investor", ""
            if (r.get("yc") or {}).get("batch"):
                entry["yc_batch"] = r["yc"]["batch"]       # public, from the company's YC page
            if r.get("hq_from") == "site":
                entry["hq_url"] = r.get("hq_url")          # the company's own page that says where it is
            named = [[t["ats"], t["key"]] for t in ts if t.get("named")]
            if named:
                entry["named"] = named
            companies.append(entry)
        allt = p.get("tenants", [])
        if allt and not ts:
            for t in allt:
                if t["ats"] in ROBOTS_BLOCKED_ATS:
                    waiting[t["ats"]] += 1
                    break
        st_ = "readable" if ts else (p.get("status") or "not_probed")
        status[st_] += 1
        checked.append([r["domain"], st_])
        private.append({k: r.get(k) for k in ("domain", "name", "country", "city", "stage", "last_round", "total_funding",
                                              "seedtable_id", "sources", "investors", "hq_from")} |
                       {"probe": p.get("status"), "found_by": found_by if ts else "",
                        "tenants": [[t["ats"], t["key"]] for t in allt],
                        "other": p.get("other"), "careers": p.get("careers"), "readable": bool(ts)})
    public = {
        "v": 1,
        "about": ("European VC-backed startups and the careers systems they publish roles on, found from each company's own "
                  "website (homepage and careers page, robots.txt obeyed) or by its name on the ATS's public board. "
                  "evidence: the investor's own public portfolio page or Y Combinator page, else 'Seedtable'. "
                  "hq_url: for a company known only from investors' pages, its own page that gives its headquarters. "
                  "No funding stage is published."),
        "built": time.strftime("%Y-%m-%d", time.gmtime()),
        "counts": {"companies_checked": len(doc["companies"]), "by_status": dict(status.most_common()),
                   "waiting_on_permission": dict(waiting),
                   **({"coverage_jobs": json.load(open(JOBS_COV))} if JOBS_COV.exists() else {})},
        "tenants": [{"ats": a, "key": k, "data": d} for (a, k), d in sorted(tenants.items())],
        "companies": sorted(companies, key=lambda e: e["domain"]),
        "checked": sorted(checked),
        # every company site read for its headquarters (hq.py): country, or "" when the site states none
        "hq": {d: h.get("country") or "" for d, h in sorted(hq_known().items())},
    }
    if REGION == "world":
        public["batches"] = doc.get("batches") or []
    startups.DATA.write_text(json.dumps(public, ensure_ascii=False, separators=(",", ":")) + "\n")
    PRIVATE.write_text(json.dumps({"note": "PRIVATE: Seedtable-derived fields. Never publish.", "companies": private},
                                  ensure_ascii=False))
    print(f"published {len(public['tenants'])} tenants, {len(companies)} companies -> {startups.DATA}  {public['counts']}")
    return public


# -- 5. roles: fetch every startup tenant once ------------------------------------------------------------------
def cmd_roles(minutes: float = 60, skip: str = "", only: str = "") -> None:
    """Incremental: tenants read in the last 12 hours are not asked again, so this can run after each new batch."""
    from jobalfred_index import pipeline
    from jobalfred_index.adapters import SOURCES
    from jobalfred_index.polite import Client
    from jobalfred_index.state import State
    pub = startups.load()
    db = WORK / "startups.db"
    state = State(db, time.strftime("%Y%m%d-%H%M%S"))
    for t in pub["tenants"]:
        state.add_tenant(t["ats"], t["key"], t.get("data") or {}, "startup")
    # tenants of startups that were already in the index before this work, so their roles count too
    priv = json.load(open(PRIVATE))
    for c in priv["companies"]:
        for ats, key in c["tenants"]:
            if ats not in ROBOTS_BLOCKED_ATS:
                state.add_tenant(ats, key, {}, "startup")
    client = Client()
    client.configure_host("apply.workable.com", gap=2.5, inflight=1)
    names = [n for n in SOURCES if (not only or n in only.split(",")) and n not in skip.split(",")]
    res = pipeline.run_fetch(state, client, minutes * 60, names, 12, WORK / "startups-dist", 10 ** 9, print)
    per = {}
    for ats, key, rows in state.iter_rows():
        per[f"{ats}|{key}"] = len(rows)
    with state.lock:
        status = state.db.execute("SELECT ats,key,status,n_jobs,last_ok IS NOT NULL,note,gone_runs FROM tenants").fetchall()
    old = json.load(open(ROLES))["fetch"] if ROLES.exists() else {}
    ROLES.write_text(json.dumps({"fetch": {**old, **res}, "rows": per,
                                 "tenants": [{"ats": a, "key": k, "status": s, "n": n, "ok": bool(o), "note": note, "gone": g}
                                             for a, k, s, n, o, note, g in status]}, indent=0))
    print(f"roles: {sum(per.values())} rows from {sum(1 for v in per.values() if v)} tenants with roles")


# -- 6. numbers for the report ------------------------------------------------------------------------------------
def cmd_report() -> dict:
    doc = json.load(open(COMPANIES))
    priv = json.load(open(PRIVATE))["companies"]
    roles = json.load(open(ROLES)) if ROLES.exists() else {"rows": {}, "tenants": []}
    pub = startups.load()
    rows = roles["rows"]
    ok = {f"{t['ats']}|{t['key']}" for t in roles["tenants"] if t["ok"]}
    out: dict = {"companies": len(priv), "list_counts": doc["counts"]}
    st = collections.Counter(c["probe"] or "not_probed" for c in priv)
    out["probe_status"] = dict(st.most_common())
    ats_found = collections.Counter()
    no_adapter = collections.Counter()
    for c in priv:
        for ats, _k in c["tenants"]:
            ats_found[ats] += 1
        for name in (c.get("other") or {}):
            no_adapter[name] += 1
    out["ats_found_companies"] = dict(ats_found.most_common())
    out["no_adapter_companies"] = dict(no_adapter.most_common())
    with_roles = read = 0
    roles_total = 0
    by_stage = collections.defaultdict(lambda: collections.Counter())
    for c in priv:
        keys = [f"{a}|{k}" for a, k in c["tenants"] if a not in ROBOTS_BLOCKED_ATS]
        n = sum(rows.get(k, 0) for k in keys)
        answered = any(k in ok for k in keys)
        stage = c.get("stage") or ("yc" if "yc" in (c.get("sources") or []) else "portfolio")
        by_stage[stage]["companies"] += 1
        if keys:
            by_stage[stage]["careers_system_found"] += 1
        if answered:
            read += 1
            by_stage[stage]["read"] += 1
        if n:
            with_roles += 1
            roles_total += n
            by_stage[stage]["with_roles"] += 1
            by_stage[stage]["roles"] += n
    out.update({"companies_read": read, "companies_with_roles": with_roles, "roles_collected": roles_total,
                "by_stage": {k: dict(v) for k, v in sorted(by_stage.items())},
                "vc_marked_companies": len(pub["vc"]),
                "vc_marked_roles": sum(rows.get(f"{a}|{k}", 0) for e in pub["vc"] for a, k in e["tenants"]),
                "public_tenants": len(pub["tenants"])})
    found_by = collections.Counter(c.get("found_by") or "" for c in priv if c.get("found_by"))
    out["found_by"] = dict(found_by)
    tstat = collections.Counter()
    for t in roles.get("tenants", []):
        tstat["read" if t["ok"] else ("gone" if t["status"] == "dead" or "HTTP 404" in (t["note"] or "") else "failed")] += 1
        if t["ok"] and not t["n"]:
            tstat["read_no_roles"] += 1
    out["tenant_fetch"] = dict(tstat)
    fails = collections.Counter()
    for t in roles.get("tenants", []):
        if not t["ok"]:
            fails[f"{t['ats']}: {re.sub(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.|/-]+: ', '', t['note'] or 'not reached')[:60]}"] += 1
    out["tenant_failures"] = dict(fails.most_common(12))
    (WORK / "startups_report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


# -- weekly refresh from public sources only (runs in CI: no Seedtable, no private files) --------------------------
def cmd_refresh(minutes: float = 60) -> None:
    """Grow data/startups_eu.json from Y Combinator's directory (work/yc_companies.json) and investors' portfolio pages
    (work/vc_portfolios.json), and look again at every checked company we cannot read yet. Companies already listed
    keep their entry; a new public evidence URL is added to it."""
    from jobalfred_index.polite import Client
    pub = startups.load()
    checked = {d: st for d, st in pub.get("checked", [])}
    comp = {c["domain"]: c for c in pub.get("companies", [])}
    tenants = {(t["ats"], t["key"]): t for t in pub.get("tenants", [])}
    found: dict[str, dict] = {}            # domain -> {name, country, evidence}
    yc_path, pf_path = WORK / "yc_companies.json", WORK / "vc_portfolios.json"
    region = EUROPE if REGION != "world" else set(pub.get("batches") or [])
    yc_country = {}
    if yc_path.exists():
        for slug, c in json.load(open(yc_path))["companies"].items():
            d = site_domain(c.get("website"))
            if d:
                yc_country[d] = c.get("country")
            if d and c.get("country") in region and c.get("ycdc_status") == "Active":
                found.setdefault(d, {"name": c.get("name"), "country": c.get("country"), "evidence": []})["evidence"].append(
                    f"https://www.ycombinator.com/companies/{slug}")
    hq_map = {d: {"country": c} for d, c in (pub.get("hq") or {}).items()}
    if HQ_CACHE.exists():
        hq_map.update(json.load(open(HQ_CACHE)))
    to_read: set[str] = set()
    if pf_path.exists():
        for inv, rec in json.load(open(pf_path)).items():
            page = (rec.get("pages") or [inv])[0]
            for d in rec.get("domains", []):
                if NOT_A_SITE.match(d) or NEWSY.search(d.split(".")[0]):
                    continue
                tld = d.rsplit(".", 1)[-1]
                site = hq_map.get(d) or {}
                by_site = site.get("country") in region and not big_listed(d) and not startups.excluded(d)
                if REGION == "world":
                    if d not in checked and d not in found and yc_country.get(d) not in region and not by_site:
                        if d not in hq_map and d not in yc_country:
                            to_read.add(d)       # its own site may say where it is: read below, added next week
                        continue                 # outside Europe: added where YC or its own site confirms its headquarters
                elif d not in checked and d not in found and tld not in EU_TLD and not by_site:
                    if d not in hq_map:
                        to_read.add(d)
                    continue                     # HQ unknown and not a European domain: not added
                e = found.setdefault(d, ({k: v for k, v in site_hq_record(d, site).items() if k in ("name", "country", "hq_from",
                                                                                                   "hq_url", "hq_text")}
                                         if by_site and d not in checked else
                                         {"name": d.split(".")[0].replace("-", " ").title(), "country": EU_TLD.get(tld, "")}))
                e.setdefault("evidence", [])
                if page not in e["evidence"]:
                    e["evidence"].append(page)
    for d, e in found.items():                   # better evidence for companies already listed
        if d in comp:
            ev = [x for x in comp[d].get("evidence", []) if x != "Seedtable"]
            comp[d]["evidence"] = list(dict.fromkeys(ev + e["evidence"])) or ["Seedtable"]
    if to_read:
        got = read_hq(sorted(to_read)[:HQ_PER_RUN], minutes=min(20, minutes / 3))
        for d, h in got.items():
            hq_map[d] = h
        print(f"refresh: headquarters read on {len(got)} companies' own sites, "
              f"{sum(1 for h in got.values() if h.get('country') in region)} in this region (added next run)", flush=True)
    pub["hq"] = {d: h.get("country") or "" for d, h in sorted(hq_map.items())}
    new = [d for d in found if d not in checked]
    again = [d for d, st in checked.items() if st != "readable"]
    todo = new + again
    print(f"refresh: {len(found)} companies from public sources, {len(new)} new; {len(again)} unreadable ones looked at again",
          flush=True)
    client = Client(timeout=15, retries=1)
    client.deadline = time.time() + minutes * 60
    results: dict[str, dict] = {}

    def one(d):
        try:
            return d, startups.probe_company(client, f"https://{d}/")
        except Exception as e:
            return d, {"status": "probe_error", "tenants": [], "note": type(e).__name__}

    with ThreadPoolExecutor(48) as ex:
        for d, res in ex.map(one, todo):
            if res.get("note") == "run time box reached" or (res.get("note") or "").startswith("HTTP -2"):
                continue                         # not reached this week: keep what we knew
            results[d] = res
    # name check for new companies only (the checked ones had theirs)
    for d in new:
        res = results.get(d) or {}
        if res.get("status") not in GUESS_STATUSES or time.time() > client.deadline:
            continue
        for ats in ("greenhouse", "ashby", "lever", "teamtailor", "recruitee", "join"):
            hit = next((sl for sl in startups.guess_slugs(found[d]["name"] or "", d)[:2]
                        if startups.verify_board(client, ats, sl, found[d]["name"] or "", d) == "yes"), None)
            if hit:
                res.setdefault("tenants", []).append({"ats": ats, "key": hit, "data": {}, "named": True})
                break
    became = 0
    for d, res in results.items():
        ts = [t for t in res.get("tenants", []) if t["ats"] not in ROBOTS_BLOCKED_ATS]
        for name, key in (res.get("other") or {}).items():
            if name in ADAPTED and not ts:
                ts.append(adapted_tenant(name, key))
        if ts:
            info = found.get(d) or {}
            c = comp.setdefault(d, {"name": info.get("name") or d.split(".")[0].replace("-", " ").title(), "domain": d,
                                    "country": info.get("country") or "", "evidence": info.get("evidence") or ["Seedtable"],
                                    "tenants": []})
            if info.get("hq_from") == "site" and "hq_url" not in c:
                c["hq_url"] = info.get("hq_url")
            for t in ts:
                tenants.setdefault((t["ats"], t["key"]), {k: v for k, v in t.items() if k != "named"})
                if [t["ats"], t["key"]] not in c["tenants"]:
                    c["tenants"].append([t["ats"], t["key"]])
                    if t.get("named"):
                        c.setdefault("named", []).append([t["ats"], t["key"]])
            became += checked.get(d) != "readable"
            checked[d] = "readable"
        else:
            checked[d] = res.get("status") or "not_probed"
    status = collections.Counter(checked.values())
    pub["built"] = time.strftime("%Y-%m-%d", time.gmtime())
    pub["counts"] = {**pub.get("counts", {}), "companies_checked": len(checked), "by_status": dict(status.most_common()),
                     "refreshed": {"new_companies": len(new), "looked_at_again": len(again), "became_readable": became}}
    pub["tenants"] = [tenants[k] for k in sorted(tenants)]
    pub["companies"] = sorted(comp.values(), key=lambda c: c["domain"])
    pub["checked"] = sorted([d, st] for d, st in checked.items())
    startups.DATA.write_text(json.dumps(pub, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"refresh: {became} companies became readable; {len(pub['companies'])} companies, {len(checked)} checked")


# -- coverage: a random sample, re-read live ---------------------------------------------------------------------
NOT_READABLE_PAGE = {"careers_no_ats", "ats_no_adapter", "ats_robots_blocked", "linkedin_only", "ats"}
NO_PAGE = {"no_careers_page"}
SITE_CLOSED = {"site_robots", "site_blocked", "site_unreachable", "no_website", "not_probed"}


def coverage(doc: dict, vc_file: Path, n: int = 200, seed: str = "") -> dict:
    """Sample n checked companies. For each one we read, read its boards again now and compare the count with the file.
    For the rest, say why it is not covered. Plain counts, no estimate beyond the sample."""
    import random
    from jobalfred_index.adapters import SOURCES
    from jobalfred_index.model import Failed, Gone
    from jobalfred_index.polite import Client
    body = json.loads(gzip.decompress(vc_file.read_bytes()))
    in_file = {c["domain"]: c for c in body["companies"]}
    readable = {d: {"tenants": c["boards"]} for d, c in in_file.items()}     # the boards the file actually uses
    checked = doc.get("checked") or [[d, "readable"] for d in readable]
    rnd = random.Random(seed or body["built"][:10])
    sample = rnd.sample(checked, min(n, len(checked)))
    client = Client(timeout=30, retries=1)
    client.configure_host("apply.workable.com", gap=2.5, inflight=1)
    out = collections.Counter()
    diffs = []

    def live(dom):
        total, failed = 0, False
        for ats, key in readable[dom]["tenants"]:
            t = next((x for x in doc["tenants"] if x["ats"] == ats and x["key"] == key), {"data": {}})
            try:
                total += len(SOURCES[ats].fetch(client, {**(t.get("data") or {}), "key": key, "_ats": ats}))
            except Gone:
                pass
            except (Failed, Exception):
                failed = True
        return dom, total, failed

    rd = [d for d, st in sample if d in readable]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(live, rd))
    for dom, now, failed in res:
        had = (in_file.get(dom) or {}).get("roles", 0)
        if failed:
            out["read_failed_now"] += 1
            continue
        out["read_with_roles" if had else "read_no_roles"] += 1
        if now == had:
            out["count_same_now"] += 1
        elif had and abs(now - had) <= max(1, 0.1 * max(now, had)):
            out["count_within_10pct"] += 1
        else:
            out["count_differs"] += 1
            diffs.append([dom, had, now])
    for dom, st in sample:
        if dom in readable:
            continue
        if st == "readable":            # its board was rejected at build time (another company's, a platform, a namesake)
            out["board_rejected"] += 1
            continue
        out["careers_page_not_readable" if st in NOT_READABLE_PAGE else
            "no_careers_page_found" if st in NO_PAGE else "site_not_readable"] += 1
    read = out["read_with_roles"] + out["read_no_roles"] + out["read_failed_now"]
    known_page = read + out["careers_page_not_readable"] + out["board_rejected"]
    res = {"sample": len(sample), "seed": seed or body["built"][:10], **dict(out),
           "pct_sample_read": round(100 * read / max(1, len(sample)), 1),
           "pct_of_known_careers_pages_read": round(100 * read / max(1, known_page), 1),
           "pct_counts_match_live": round(100 * (out["count_same_now"] + out["count_within_10pct"]) /
                                          max(1, read - out["read_failed_now"]), 1),
           "differs": diffs[:20]}
    return res


def cmd_coverage(vc_path: str, n: int = 200) -> None:
    """Measure on a sample and write the result into the vc-eu file's counts (and work/coverage-*.json)."""
    path = Path(vc_path)
    res = coverage(startups.load(), path, n)
    body = json.loads(gzip.decompress(path.read_bytes()))
    body["counts"]["coverage_sample"] = {k: v for k, v in res.items() if k != "differs"}
    path.write_bytes(gzip.compress(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(), 9, mtime=0))
    (WORK / f"coverage-{res['seed']}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def cmd_newest(path: str) -> None:
    """Use a company list published on the release (by the weekly refresh) when it is newer than the committed one
    and not much smaller."""
    try:
        rel = json.load(open(path))
    except (OSError, ValueError):
        print("release company list unreadable: keeping the committed one")
        return
    cur = startups.load()
    if rel.get("built", "") > cur.get("built", "") and len(rel.get("companies", [])) >= 0.9 * len(cur.get("companies", [])):
        startups.DATA.write_text(json.dumps(rel, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"using the release company list built {rel.get('built')} ({len(rel['companies'])} companies)")
    else:
        print(f"keeping the committed company list built {cur.get('built')} ({len(cur.get('companies', []))} companies)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    if cmd == "companies":
        cmd_companies()
    elif cmd == "measure":
        cmd_measure()
    elif cmd == "probe":
        cmd_probe(limit=int(arg or 0))
    elif cmd == "guess":
        cmd_guess(float(arg or 100), only=(sys.argv[3] if len(sys.argv) > 3 else ""),
                  gap=float(sys.argv[4]) if len(sys.argv) > 4 else 0.0)
    elif cmd == "publish":
        cmd_publish()
    elif cmd == "hq":
        cmd_hq(float(arg or 90))
    elif cmd == "investors":
        cmd_investors()
    elif cmd == "world":
        cmd_world(arg.split(","))
    elif cmd == "newest":
        cmd_newest(arg)
    elif cmd == "refresh":
        cmd_refresh(float(arg or 60))
    elif cmd == "coverage":
        cmd_coverage(arg or "dist-vc/vc-eu.json.gz", int(sys.argv[3]) if len(sys.argv) > 3 else 200)
    elif cmd == "roles":
        cmd_roles(float(arg or 60), skip=(sys.argv[3] if len(sys.argv) > 3 else ""), only=(sys.argv[4] if len(sys.argv) > 4 else ""))
    elif cmd == "report":
        cmd_report()
    else:
        print(__doc__)
