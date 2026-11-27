"""Collect a training set for the level and years models: postings read through the nightly's own adapters and polite client, from
careers systems whose list request returns the description. Each posting keeps its title, the careers system's own level and years
fields, the description (cut to 6,000 characters) and what the rules state (levels.stated). Written to WORK/corpus.jsonl.gz, which
stays on this machine: job descriptions are the employers' text and are never committed or published.

    python3 scripts/levels_corpus.py work/levels/corpus --per-source 250 --minutes 40

Tenants are drawn at random (fixed seed) from the published tenant list, live ones only. Nothing is retried after a refusal; the
client honours robots.txt and its per-host pace exactly as the nightly does.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobalfred_index import levels, model  # noqa: E402
from jobalfred_index.adapters import SOURCES  # noqa: E402
from jobalfred_index.polite import Client  # noqa: E402

DESC_SOURCES = ["greenhouse", "lever", "ashby", "recruitee", "teamtailor", "breezy"]
MAX_DESC = 6000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", type=Path)
    ap.add_argument("--tenants", default=str(Path(__file__).resolve().parent.parent / "data" / "tenants.json.gz"))
    ap.add_argument("--per-source", type=int, default=250)
    ap.add_argument("--minutes", type=float, default=40)
    ap.add_argument("--seed", type=int, default=27)
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    out_path = a.work / "corpus.jsonl.gz"

    raw = json.load(gzip.open(a.tenants))
    items = raw if isinstance(raw, list) else raw.get("tenants", raw)
    rnd = random.Random(a.seed)
    plan = []
    for src in DESC_SOURCES:
        pool = [t for t in items if (t.get("ats") or t.get("a")) == src and not t.get("dead") and not t.get("gone")]
        rnd.shuffle(pool)
        plan += [(src, t) for t in pool[:a.per_source]]
    rnd.shuffle(plan)
    print(f"plan: {len(plan)} tenants over {', '.join(DESC_SOURCES)}", flush=True)

    lock = threading.Lock()
    out = gzip.open(out_path, "wt", encoding="utf-8")
    counts = {"rows": 0, "with_desc": 0, "level_stated": 0, "years_stated": 0, "tenants_ok": 0, "tenants_failed": 0}
    current = threading.local()

    def recorder(orig):
        def make(ats, title, company, locs, url, posted="", **kw):
            job = orig(ats, title, company, locs, url, posted, **kw)
            if job is None:
                return job
            desc = kw.get("desc") or ""
            native, level_native, years_native = kw.get("native"), kw.get("level_native"), kw.get("years_native")
            tags = [t for t in ((native if isinstance(native, (list, tuple)) else [native]) +
                                (level_native if isinstance(level_native, (list, tuple)) else [level_native])) if t]
            sl, ss, yx, ys = levels.stated(title, tags or None, desc or None, years_native)
            row = {"src": getattr(current, "src", ats), "ats": ats, "title": job.title, "company": job.company, "cc": job.cc,
                   "url": job.url, "fn": job.row()[14], "native": [str(t)[:80] for t in tags][:6],
                   "years_native": years_native if isinstance(years_native, (int, float, str)) else None,
                   "desc": str(desc)[:MAX_DESC], "sl": sl, "ss": ss, "yx": yx, "ys": ys}
            with lock:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts["rows"] += 1
                counts["with_desc"] += bool(desc)
                counts["level_stated"] += ss in levels.STATED
                counts["years_stated"] += ys == "s"
            return job
        return make

    for src in DESC_SOURCES:
        mod = SOURCES[src].module
        if hasattr(mod, "make"):
            mod.make = recorder(model.make)

    client = Client()
    client.deadline = time.time() + a.minutes * 60

    def one(item):
        src, tenant = item
        current.src = src
        try:
            SOURCES[src].fetch(client, tenant)
            with lock:
                counts["tenants_ok"] += 1
        except Exception:
            with lock:
                counts["tenants_failed"] += 1

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, _ in enumerate(ex.map(one, plan), 1):
            if i % 100 == 0:
                print(f"{i}/{len(plan)} tenants, {counts} ({time.time() - t0:.0f} s)", flush=True)
    out.close()
    print(f"done in {time.time() - t0:.0f} s: {counts} -> {out_path}; requests {client.stats}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
