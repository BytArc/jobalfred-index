"""python -m jobalfred_index <command>

  run        discover tenants, fetch every source, build the shards (the daily job)
  discover   tenant discovery only
  fetch      fetch only
  build      rebuild shards from stored rows
  stats      print tenant counts
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import discovery, pipeline, probe, shards, startups
from .polite import Client
from .state import State

ROOT = Path(__file__).resolve().parent.parent
T0 = time.time()


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jobalfred_index")
    ap.add_argument("command", choices=["run", "discover", "fetch", "build", "stats", "names", "vceu"])
    ap.add_argument("--state", default=str(ROOT / "work" / "index.db"))
    ap.add_argument("--tenants", default=str(ROOT / "data" / "tenants.json.gz"), help="persistent tenant list (read and rewritten)")
    ap.add_argument("--seeds", default=str(ROOT / "data" / "seeds.json"))
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--minutes", type=float, default=270, help="total time box for the run")
    ap.add_argument("--discover-minutes", type=float, default=30)
    ap.add_argument("--crawls", type=int, default=3, help="Common Crawl snapshots to query")
    ap.add_argument("--only", default="", help="comma list of sources")
    ap.add_argument("--max-age-hours", type=float, default=0, help="skip tenants fetched more recently than this")
    ap.add_argument("--checkpoint-minutes", type=float, default=20)
    ap.add_argument("--limit", type=int, default=0, help="max tenants per source (testing)")
    ap.add_argument("--extra-tenants", default="", help="JSON file of extra tenants to add before fetching")
    ap.add_argument("--no-crtsh", action="store_true")
    ap.add_argument("--probe-max", type=int, default=20000, help="candidate slugs per ATS family from known company names (0 = off)")
    a = ap.parse_args(argv)
    if a.command == "vceu":   # its own state and output, so the main index is never touched
        if a.state == ap.get_default("state"):
            a.state = str(ROOT / "work" / "vceu.db")
        if a.out == ap.get_default("out"):
            a.out = str(ROOT / "dist-vc")

    run_id = time.strftime("%Y%m%d-%H%M%S")
    state = State(a.state, run_id)
    only = [s for s in a.only.split(",") if s]
    client = Client()
    client.configure_host("index.commoncrawl.org", gap=1.0, inflight=1)  # Common Crawl bans bursts; strictly one at a time
    client.configure_host("crt.sh", gap=2.0, inflight=1)
    client.configure_host(".myworkdayjobs.com", gap=0.08, inflight=14)
    client.configure_host("apply.careers.microsoft.com", gap=4.0, inflight=1)
    client.configure_host("www.themuse.com", gap=1.0)
    client.configure_host("apply.workable.com", gap=2.5, inflight=1)  # answered 429 at 2 requests a second
    client.configure_host("himalayas.app", gap=1.0)
    out_dir = Path(a.out)
    report: dict = {"run_id": run_id, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    if a.command == "stats":
        print(json.dumps(state.tenant_counts(), indent=1))
        return 0

    if a.command == "vceu":
        # only the startups' own boards; the main tenant list and shards are not read or written
        from . import vceu
        su = startups.load()
        startups.add_tenants(state, su)
        client.configure_host("join.com", gap=0.5, inflight=2)
        mine = startups.company_keys(su)
        names_ = sorted({ats for ats, _ in mine})
        report["fetch"] = pipeline.run_fetch(state, client, max(60, a.minutes * 60 - 300), names_, a.max_age_hours, out_dir,
                                             10 ** 9, log, a.limit or None)
        report["vceu"] = vceu.build(state, su, out_dir / "vc-eu.json.gz", log)["counts"]
        report["elapsed_seconds"] = round(time.time() - T0)
        rp = ROOT / "work" / f"report-vceu-{run_id}.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=1, default=str))
        return 0

    n = state.import_tenants(a.tenants)
    pipeline.ensure_seeds(state)
    log(f"imported {n} tenants from {a.tenants}")
    su = startups.load()
    log(f"startups: {startups.add_tenants(state, su)} new tenants from data/startups_eu.json "
        f"({len(su.get('tenants', []))} listed, {len(su.get('companies', []))} companies)")

    budget = a.minutes * 60
    if a.extra_tenants and Path(a.extra_tenants).exists():
        extra = json.loads(Path(a.extra_tenants).read_text())["tenants"]
        added = 0
        for t in extra:
            # a host found without its career-site name is skipped when a tenant with a site is already known
            if t["ats"] in ("workday", "oracle") and "|" not in t["key"]:
                with state.lock:
                    hit = state.db.execute("SELECT 1 FROM tenants WHERE ats=? AND key LIKE ? LIMIT 1", (t["ats"], t["key"] + "|%")).fetchone()
                if hit:
                    continue
            added += state.add_tenant(t["ats"], t["key"], t.get("data"), t.get("source", "extra"))
        log(f"extra tenants added: {added} of {len(extra)}")
    if a.command in ("fetch", "build"):
        discovery.load_seeds(state, Path(a.seeds), log)
    if a.command in ("run", "discover"):
        log("== discovery")
        report["seeds"] = discovery.load_seeds(state, Path(a.seeds), log)
        d_budget = a.discover_minutes * 60
        crawls = discovery.latest_crawls(client, a.crawls)
        crawls_all = crawls
        log(f"common crawl snapshots: {crawls}")
        report["cdx"] = discovery.run_cdx(client, state, crawls, d_budget, log)
        if not a.no_crtsh:
            report["crtsh"] = discovery.run_crtsh(client, state, min(300, d_budget / 4), log)
        report["tenant_counts"] = state.tenant_counts()
        n_exp = state.export_tenants(a.tenants)
        log(f"tenant list saved: {n_exp} tenants")
        for ats, c in sorted(report["tenant_counts"].items()):
            log(f"   {ats}: {c}")

    if a.command in ("run", "fetch"):
        def remaining():
            return max(60, budget - (time.time() - T0) - 300)
        report["fetch"] = {}
        if a.command == "run" and not only and a.probe_max:
            log("== fetch stage 1: open feeds and big-company sources (also feeds the probe with company names)")
            stage1 = ["amazon", "google", "apple", "uber", "eightfold", "remotive", "arbeitnow", "remoteok", "himalayas",
                      "jobicy", "themuse", "weworkremotely"]
            report["fetch"].update(pipeline.run_fetch(state, client, min(remaining(), 25 * 60), stage1, a.max_age_hours, out_dir,
                                                      a.checkpoint_minutes * 60, log, a.limit or None))
            if report.get("cdx", {}).get("stopped"):
                log("== discovery retry: Common Crawl refused us earlier, trying once more")
                report["cdx_retry"] = discovery.run_cdx(client, state, crawls, 15 * 60, log)
            log("== probe: company names to subdomain candidates")
            report["probe"] = probe.run_probe(state, a.probe_max, log)
            n_exp = state.export_tenants(a.tenants)
            log(f"== fetch stage 2: every other source (tenants fetched in the last hour are skipped)")
            report["fetch"].update(pipeline.run_fetch(state, client, remaining(), None, 1.0, out_dir,
                                                      a.checkpoint_minutes * 60, log, a.limit or None))
        else:
            log("== fetch")
            report["fetch"] = pipeline.run_fetch(state, client, remaining(), only or None, a.max_age_hours, out_dir,
                                                  a.checkpoint_minutes * 60, log, a.limit or None)

    if a.command == "names":
        from concurrent.futures import ThreadPoolExecutor
        from . import names
        todo = []
        repolished = 0
        for ats in sorted(names.NAME_FROM_PAGE):                  # clean the cached names again, no network
            for t in state.tenants(ats):
                nm = t.get("name")
                if nm and nm != names.UNDISCLOSED:
                    new = names.polish(nm, pipeline.tenant_slug(ats, t["key"]) or "", ())
                    if new != nm:
                        state.set_name(ats, t["key"], new, rewrite_rows=False)
                        repolished += 1
        log(f"names: {repolished} cached names cleaned")
        for ats in sorted(names.NAME_FROM_PAGE):
            for t in state.tenants(ats):
                nm = t.get("name")
                if nm and nm != names.UNDISCLOSED and names.clean_company(nm) == nm and not names._is_slug_of(nm, t):
                    continue
                todo.append((ats, t))
        log(f"names: {len(todo)} tenants need a name")
        urls = {}
        for ats, key, rows in state.iter_rows():
            urls[(ats, key)] = [r[5] for r in rows[:50]]
        done = {"n": 0, "page": 0, "fallback": 0}
        def one(item):
            ats, t = item
            name = names.resolve(client, ats, t, urls.get((ats, t["key"]), []))
            state.set_name(ats, t["key"], name)
            done["n"] += 1
            done["page" if name != names.UNDISCLOSED else "fallback"] += 1
            if done["n"] % 500 == 0:
                log(f"names: {done['n']}/{len(todo)}")
        with ThreadPoolExecutor(24) as ex:
            list(ex.map(one, todo))
        log(f"names done: {done}")

    if a.command in ("run", "fetch", "build", "names"):
        log("== build")
        res = shards.build(pipeline.iter_rows(state), out_dir, log)
        report["manifest"] = {k: res["manifest"][k] for k in ("total", "sources")}
        report["shards"] = [{k: s[k] for k in ("id", "count", "bytes")} for s in res["manifest"]["shards"]]
        report["dedupe"] = res["dropped"]

    state.export_tenants(a.tenants)
    report["tenant_counts"] = state.tenant_counts()
    report["http"] = dict(client.stats)
    report["blocked_hosts"] = dict(list(client.blocked.items())[:200])
    report["robots_denied_hosts"] = client.robots_denied_hosts
    report["elapsed_seconds"] = round(time.time() - T0)
    rp = ROOT / "work" / f"report-{run_id}.json"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=1, default=str))
    log(f"report written: {rp}  (elapsed {report['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
