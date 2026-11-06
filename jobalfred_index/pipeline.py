"""Run every source: tenants in parallel per source, per-host limits in the client, failures contained."""
from __future__ import annotations

import collections
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

from . import names, shards
from .adapters import SOURCES
from .polite import Client, HOST_SKIPPED, ROBOTS_BLOCKED
from .model import Failed, Gone
from .state import State

SINGLES = {
    "amazon": "main", "google": "main", "apple": "main", "uber": "main",
    "remotive": "main", "arbeitnow": "main", "remoteok": "main", "himalayas": "main", "jobicy": "main",
    "themuse": "main", "weworkremotely": "main",
}
# Meta is deliberately absent: its robots.txt header forbids automated collection without written permission.
# Shopify is absent: its career pages carry no JobPosting JSON-LD in the served HTML.
SEED_TENANTS = [
    ("eightfold", "explore.jobs.netflix.net|netflix.com", {"host": "explore.jobs.netflix.net", "domain": "netflix.com", "mode": "apply",
                                                           "name": "Netflix", "job_url": "https://jobs.netflix.com/jobs/{ats_job_id}"}),
    ("eightfold", "apply.careers.microsoft.com|microsoft.com", {"host": "apply.careers.microsoft.com", "domain": "microsoft.com",
                                                               "mode": "pcsx", "name": "Microsoft"}),
]


def ensure_seeds(state: State) -> None:
    for name, key in SINGLES.items():
        state.add_tenant(name, key, {}, "builtin")
    for ats, key, data in SEED_TENANTS:
        state.add_tenant(ats, key, data, "builtin")


class Progress:
    def __init__(self, name: str, total: int):
        self.name, self.total = name, total
        self.ok = self.gone = self.failed = self.jobs = 0
        self.reasons: collections.Counter = collections.Counter()
        self.started = time.monotonic()
        self.finished: float | None = None
        self.aborted = ""
        self.lock = threading.Lock()

    def line(self) -> str:
        done = self.ok + self.gone + self.failed
        return (f"[{self.name}] {done}/{self.total} tenants  ok={self.ok} gone={self.gone} failed={self.failed}  "
                f"jobs={self.jobs}  {int(time.monotonic() - self.started)}s" + (f"  ABORTED: {self.aborted}" if self.aborted else ""))

    def as_dict(self) -> dict:
        end = self.finished or time.monotonic()
        return {"tenants": self.total, "ok": self.ok, "gone": self.gone, "failed": self.failed, "jobs": self.jobs,
                "seconds": round(end - self.started), "aborted": self.aborted,
                "top_failures": self.reasons.most_common(5)}


def reason_key(msg: str) -> str:
    import re
    msg = re.sub(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.|-]+: ", "", msg)
    return msg[:90]


def run_source(src, tenants: list[dict], state: State, client: Client, deadline: float, prog: Progress, log) -> None:
    def work(t: dict):
        if time.monotonic() > deadline:
            return
        key = t["key"]
        t = {**t, "_ats": src.name}
        try:
            jobs = src.fetch(client, t)
            for j in jobs:
                j.ats = src.out
            if src.name in names.NAME_FROM_PAGE:
                name = names.resolve(client, src.name, t, [j.url for j in jobs[:50]])
                for j in jobs:
                    j.company = name
            company = t.get("name")
            state.save_result(src.name, key, [j.row() for j in jobs], company)
            with prog.lock:
                prog.ok += 1
                prog.jobs += len(jobs)
        except Gone as e:
            state.mark_gone(src.name, key, str(e))
            with prog.lock:
                prog.gone += 1
        except Failed as e:
            state.mark_failed(src.name, key, str(e))
            with prog.lock:
                prog.failed += 1
                prog.reasons[reason_key(str(e))] += 1
        except Exception as e:  # an adapter bug must never stop the run
            state.mark_failed(src.name, key, f"{type(e).__name__}: {e}")
            with prog.lock:
                prog.failed += 1
                prog.reasons[f"{type(e).__name__}: {str(e)[:70]}"] += 1
        with prog.lock:
            if prog.failed >= 25 and prog.ok == 0 and prog.gone == 0 and not prog.aborted:
                prog.aborted = "every request failed: " + (prog.reasons.most_common(1)[0][0] if prog.reasons else "")

    with ThreadPoolExecutor(max_workers=src.workers, thread_name_prefix=src.name) as ex:
        pending = set()
        it = iter(tenants)
        while True:
            while len(pending) < src.workers * 2 and not prog.aborted and time.monotonic() < deadline:
                t = next(it, None)
                if t is None:
                    break
                pending.add(ex.submit(work, t))
            if not pending:
                break
            done, pending = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
            if prog.aborted or time.monotonic() > deadline:
                for f in pending:
                    f.cancel()
                pending = {f for f in pending if not f.cancelled()}
                if not pending:
                    break
    prog.finished = time.monotonic()


def iter_rows(state: State):
    for _ats, _key, rows in state.iter_rows():
        yield from rows


def run_fetch(state: State, client: Client, budget_s: float, only: list[str] | None, max_age_hours: float,
              out_dir: Path, checkpoint_s: float, log, limit: int | None = None) -> dict:
    t0 = time.monotonic()
    deadline = t0 + budget_s
    client.deadline = time.time() + budget_s + 180   # in-flight sources get three minutes of grace
    plan = []
    for name, src in sorted(SOURCES.items(), key=lambda kv: kv[1].priority):
        if only and name not in only:
            continue
        tenants = state.tenants(name, max_age_hours=max_age_hours)
        if limit:
            tenants = tenants[:limit]
        if tenants:
            plan.append((src, tenants))
    log("fetch plan: " + ", ".join(f"{s.name}={len(t)}" for s, t in plan))
    progs = {s.name: Progress(s.name, len(t)) for s, t in plan}
    threads = []
    for src, tenants in plan:
        th = threading.Thread(target=run_source, args=(src, tenants, state, client, deadline, progs[src.name], log),
                              name=f"src-{src.name}", daemon=True)
        th.start()
        threads.append(th)
    last_ck = time.monotonic()
    while any(t.is_alive() for t in threads):
        time.sleep(20)
        log(f"-- {int(time.monotonic() - t0)}s elapsed, {client.stats['requests']} requests, {client.stats['bytes'] // 1_000_000} MB")
        for p in progs.values():
            if p.finished is None or time.monotonic() - p.finished < 40:
                log("   " + p.line())
        if time.monotonic() - last_ck > checkpoint_s:
            last_ck = time.monotonic()
            try:
                shards.build(iter_rows(state), out_dir, log)
            except Exception as e:
                log(f"checkpoint build failed: {e}")
    for p in progs.values():
        log("   " + p.line())
    return {name: p.as_dict() for name, p in progs.items()}
