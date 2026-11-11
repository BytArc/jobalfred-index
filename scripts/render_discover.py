"""Rendered discovery: for companies whose careers page names no careers system in the served HTML, open the page in
a browser once and record the systems it loads (page links and network requests) and the job links it shows.
Resumable; results in work/render_probe.json. publish (scripts/startups_eu.py) turns systems with an adapter into
tenants that the daily runs read through the public endpoint, without a browser.

  python scripts/render_discover.py [statuses] [workers] [minutes]
  statuses: comma list of probe statuses (default careers_no_ats,linkedin_only)
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "work" / "render_probe.json"
_R = None


def _init():
    global _R
    from jobalfred_index.polite import Client
    import render_probe
    _R = render_probe.Renderer(Client(timeout=30, retries=1))
    from multiprocessing.util import Finalize
    Finalize(None, _R.close, exitpriority=10)          # the browser closes with the worker, never left behind


def one(item):
    import render_probe
    dom, careers = item
    try:
        res = render_probe.look(_R, "https://" + dom, careers or "")
    except Exception as e:
        return dom, {"state": "error", "note": type(e).__name__}
    s = res.get("systems") or {}
    return dom, {"state": res["state"], "careers": res.get("careers", careers),
                 "tenants": [{"ats": a, "key": k, "data": d} for (a, k), d in (s.get("tenants") or {}).items()],
                 "other": s.get("other") or {}, "custom": s.get("custom") or [], "jsonld": bool(s.get("jsonld")),
                 "jobs": sorted(res.get("jobs") or [])[:200], "n_jobs": len(res.get("jobs") or [])}


def main():
    statuses = set((sys.argv[1] if len(sys.argv) > 1 else "careers_no_ats,linkedin_only").split(","))
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    minutes = float(sys.argv[3]) if len(sys.argv) > 3 else 120
    probe = json.loads((ROOT / "work" / "startups_probe.json").read_text())
    pub = json.loads((ROOT / "data" / "startups_eu.json").read_text())
    readable = {d for d, st in pub["checked"] if st == "readable"}
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    retry = {"home_unreachable", "careers_unreachable", "home_error", "careers_error", "error"}
    todo = [(d, (probe.get(d) or {}).get("careers", "")) for d, st in pub["checked"]
            if d not in readable and (probe.get(d) or {}).get("status") in statuses
            and (d not in done or done[d].get("state") in retry)]
    print(f"render: {len(todo)} companies to open ({len(done)} done before)", flush=True)
    deadline = time.time() + minutes * 60
    n = 0
    pool = mp.get_context("spawn").Pool(workers, initializer=_init)
    try:
        for i in range(0, len(todo), 50):          # batches, so a time box never has to kill a worker (and its browser)
            if time.time() > deadline:
                print("time box reached", flush=True)
                break
            for dom, rec in pool.imap_unordered(one, todo[i:i + 50], chunksize=1):
                done[dom] = rec
                n += 1
            OUT.write_text(json.dumps(done, separators=(",", ":")))
            found = sum(1 for d, r in done.items() if r.get("tenants"))
            print(f"{n}/{len(todo)} opened; {found} with a careers system", flush=True)
    finally:
        OUT.write_text(json.dumps(done, separators=(",", ":")))
        pool.close()                               # workers exit normally and close their browsers
        pool.join()
    OUT.write_text(json.dumps(done, separators=(",", ":")))
    import collections
    print(json.dumps(collections.Counter(r.get("state") for r in done.values()).most_common(), indent=0))
    print("with a careers system:", sum(1 for r in done.values() if r.get("tenants")))


if __name__ == "__main__":
    main()
