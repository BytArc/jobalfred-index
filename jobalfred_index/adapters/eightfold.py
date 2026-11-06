"""Eightfold / Phenom-style career APIs that serve Netflix, Microsoft and many others.

Two shapes, both public and both called by the career site itself:
  /api/apply/v2/jobs?domain=...&start=..&num=..     (Netflix)
  /api/pcsx/search?domain=...&start=..              (Microsoft; its robots.txt allows /api/pcsx)
Tenant data: {"host": "explore.jobs.netflix.net", "domain": "netflix.com", "mode": "apply"|"pcsx",
              "name": "Netflix", "job_url": "https://jobs.netflix.com/jobs/{ats_job_id}"}
"""
from __future__ import annotations

from ..model import Failed, make
from .base import check, slug_title

ATS = "eightfold"
KIND = "tenant"
WORKERS = 4
PRIORITY = 6
MAX_JOBS = 20000


def parse(d: dict, tenant: dict) -> list:
    out = []
    company = tenant.get("name") or slug_title(tenant["host"].split(".")[0])
    if tenant.get("mode") == "pcsx":
        positions = (d.get("data") or {}).get("positions") or []
        for j in positions:
            pid = j.get("id")
            url = f"https://{tenant['host']}/careers/job/{pid}" if pid else ""
            job = make(ATS, j.get("name"), company, list(j.get("locations") or []), url, j.get("postedTs"),
                       workplace=str(j.get("workLocationOption") or ""))
            if job:
                out.append(job)
        return out
    for j in d.get("positions") or []:
        locs = list(j.get("locations") or [j.get("location") or ""])
        jid = j.get("ats_job_id") or j.get("id")
        tmpl = tenant.get("job_url") or ("https://" + tenant["host"] + "/careers/job/{id}")
        url = j.get("canonicalPositionUrl") or tmpl.format(ats_job_id=jid, id=j.get("id"))
        wl = str(j.get("work_location_option") or "")
        job = make(ATS, j.get("name") or j.get("posting_name"), company, locs, url, j.get("t_create"),
                   workplace="remote" if wl == "remote" else ("hybrid" if wl == "hybrid" else ""))
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    if "host" not in tenant:  # found by discovery: guess the usual domain; a wrong guess answers with no positions
        tenant = {**tenant, "host": f"{tenant['key']}.eightfold.ai", "domain": f"{tenant['key']}.com", "mode": "apply"}
    host, domain, mode = tenant["host"], tenant["domain"], tenant.get("mode", "apply")
    rows, start = [], 0
    step = 10 if mode == "pcsx" else 100
    while start < MAX_JOBS:
        if mode == "pcsx":
            r = client.get(f"https://{host}/api/pcsx/search", params={"domain": domain, "query": "", "start": start, "sort_by": "timestamp"})
        else:
            r = client.get(f"https://{host}/api/apply/v2/jobs", params={"domain": domain, "start": start, "num": step, "query": ""})
        if r.status != 200:
            if start == 0:
                check(r, f"eightfold/{tenant['key']}")
            break
        d = r.json()
        if not isinstance(d, dict):
            raise Failed(f"eightfold/{tenant['key']}: not JSON")
        part = parse(d, tenant)
        raw = len((d.get("data") or {}).get("positions") or []) if mode == "pcsx" else len(d.get("positions") or [])
        rows.extend(part)
        total = int(((d.get("data") or {}).get("count") if mode == "pcsx" else d.get("count")) or 0)
        start += raw or step
        if raw == 0 or (total and start >= total):
            break
    return rows
