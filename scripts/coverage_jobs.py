"""Job-weighted coverage on a random sample of checked companies (measurement only, run on this machine).

For each sampled company: the roles its careers page shows now (its careers system's public board read live where we
know or can see the system; otherwise the job links on the rendered careers page) against the roles vc-eu.json.gz
holds for it. A company whose site we may not or cannot open is "unknown" and left out of both sides, and counted.
A company with no careers page and no roles on its site counts as 0 roles seen.

  python scripts/coverage_jobs.py [N] [seed] [vc-eu.json.gz]   -> work/coverage-jobs-<seed>.json
"""
from __future__ import annotations

import gzip
import json
import multiprocessing as mp
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

UNKNOWN_STATUS = {"site_robots", "site_blocked", "site_unreachable", "not_probed", "no_website"}
_R = None
_C = None


def _init():
    global _R, _C
    from jobalfred_index.polite import Client
    import render_probe
    _C = Client(timeout=30, retries=1)
    _C.configure_host("apply.workable.com", gap=2.5, inflight=1)
    _R = render_probe.Renderer(_C)
    from multiprocessing.util import Finalize
    Finalize(None, _R.close, exitpriority=10)          # the browser closes with the worker, never left behind


def live_count(boards, tenants_data) -> tuple[int, bool]:
    from jobalfred_index.adapters import SOURCES
    from jobalfred_index.model import Gone
    total, ok = 0, True
    for ats, key in boards:
        if ats not in SOURCES or ats in ("personio", "smartrecruiters", "pinpoint"):
            ok = False
            continue
        try:
            total += len(SOURCES[ats].fetch(_C, {**tenants_data.get((ats, key), {}), "key": key, "_ats": ats}))
        except Gone:
            pass
        except Exception:
            ok = False
    return total, ok


def one(item):
    import render_probe
    dom, status, file_c, careers, tenants_data = item
    rec = {"domain": dom, "status": status}
    try:
        if file_c:
            seen, ok = live_count(file_c["boards"], tenants_data)
            if not ok:                                   # a failed read is asked again once, never counted as 0
                time.sleep(3)
                seen, ok = live_count(file_c["boards"], tenants_data)
            rec.update(kind="read", ours=file_c["roles"], seen=seen if ok else None)
            return rec
        if status in UNKNOWN_STATUS:
            rec.update(kind="unknown", reason=status)
            return rec
        res = render_probe.look(_R, "https://" + dom, careers or "")
        rec["state"] = res["state"]
        if not res["state"] in ("rendered", "no_careers_page"):
            rec.update(kind="unknown", reason=res["state"])
            return rec
        systems = res["systems"] or {}
        found = [[a, k] for (a, k) in (systems.get("tenants") or {})]
        rec["systems"] = found
        rec["other"] = systems.get("other") or {}
        rec["careers"] = res.get("careers", "")
        links = len(res["jobs"])
        if not links and res.get("text"):
            tdir = ROOT / "work" / "coverage-text"
            tdir.mkdir(exist_ok=True)
            (tdir / f"{dom}.txt").write_text(f"{res.get('careers','')}\n\n" + res["text"])
        seen, ok = (live_count(found, {}) if found else (0, False))
        if found and ok and seen >= links:
            rec.update(kind="seen_board", ours=0, seen=seen, links=links)
        else:
            rec.update(kind="seen_page", ours=0, seen=links, board=seen if found else None)
        return rec
    except Exception as e:
        rec.update(kind="unknown", reason=f"error {type(e).__name__}")
        return rec


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seed = sys.argv[2] if len(sys.argv) > 2 else time.strftime("jobs-%Y-%m-%d")
    vc_path = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "dist-vc" / "vc-eu.json.gz"
    import os
    region = os.environ.get("REGION", "eu")
    pub = json.loads((ROOT / "data" / ("startups_world.json" if region == "world" else "startups_eu.json")).read_text())
    body = json.loads(gzip.decompress(vc_path.read_bytes()))
    in_file = {c["domain"]: c for c in body["companies"]}
    probe = json.loads((ROOT / "work" / "startups_probe.json").read_text()) if (ROOT / "work" / "startups_probe.json").exists() else {}
    tdata = {(t["ats"], t["key"]): t.get("data") or {} for t in pub["tenants"]}
    sample = random.Random(seed).sample(pub["checked"], min(n, len(pub["checked"])))
    items = [(d, st, in_file.get(d), (probe.get(d) or {}).get("careers", ""), tdata) for d, st in sample]
    import os
    pool = mp.get_context("spawn").Pool(int(os.environ.get("WORKERS", "2")), initializer=_init)
    try:
        recs = pool.map(one, items, chunksize=1)
    finally:
        pool.close()          # workers exit normally, so each closes its browser
        pool.join()
    PENDING = {"personio", "pinpoint", "smartrecruiters"}
    for r in recs:
        if r["kind"] in ("seen_page", "seen_board") and r.get("seen"):
            ats = {a for a, _ in (r.get("systems") or [])}
            r["behind"] = ("permission_pending" if ats & PENDING else
                           "linkedin_only" if r.get("status") == "linkedin_only" else
                           "not_read_yet")
    known = [r for r in recs if r["kind"] != "unknown" and r.get("seen") is not None]
    seen = sum(r["seen"] for r in known)
    ours = sum(min(r.get("ours") or 0, r["seen"]) for r in known)
    out = {
        "sample": len(recs), "seed": seed,
        "companies_known": len(known),
        "companies_unknown": len(recs) - len(known),
        "unknown_reasons": dict(__import__("collections").Counter(r.get("reason") or "live read failed" for r in recs
                                                                   if r not in known)),
        "roles_seen": seen, "roles_ours_matching": ours,
        "pct_roles_covered": round(100 * ours / max(1, seen), 1),
        "roles_seen_by_kind": {k: sum(r["seen"] for r in known if r["kind"] == k) for k in ("read", "seen_board", "seen_page")},
        "companies_by_kind": dict(__import__("collections").Counter(r["kind"] for r in recs)),
    }
    behind = __import__("collections").Counter()
    for r in known:
        if r.get("behind"):
            behind[r["behind"]] += r["seen"]
    out["roles_not_covered_by_reason"] = dict(behind)
    # the ceiling: roles we could read within the rules = all seen minus those behind a permission we do not have
    # (LinkedIn is never read). Companies whose site we may not open are counted, not estimated.
    blocked = behind.get("permission_pending", 0) + behind.get("linkedin_only", 0)
    out["ceiling_pct_of_seen_roles"] = round(100 * (seen - blocked) / max(1, seen), 1)
    out["companies_we_may_not_open"] = out["companies_unknown"]
    out["region"] = region
    (ROOT / "work" / f"coverage-jobs-{region}-{seed}.json").write_text(json.dumps({"summary": out, "companies": recs}, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
