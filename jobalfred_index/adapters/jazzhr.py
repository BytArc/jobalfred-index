"""JazzHR career pages: https://{company}.applytojob.com/apply/jobs/ (server-rendered table, no JSON API)."""
from __future__ import annotations

import re

from ..model import Failed, Gone, make
from .base import check, slug_title

ATS = "jazzhr"
KIND = "tenant"
WORKERS = 6
PRIORITY = 36
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
LINK = re.compile(r'<a class="job_title_link" href="(?:https?://[^/"]+)?/apply/jobs/details/([A-Za-z0-9]+)[^"]*">([^<]{1,300})</a>')
CELL = re.compile(r"<td>\s*([^<]{0,200}?)\s*</td>")


def parse(html: str, tenant: dict) -> list:
    out = []
    for row in TR.findall(html):
        m = LINK.search(row)
        if not m:
            continue
        jid, title = m.groups()
        cells = CELL.findall(row[m.end():])
        loc = cells[0] if cells else ""
        job = make(ATS, title, tenant.get("name") or slug_title(tenant["key"]), [loc],
                   f"https://{tenant['key']}.applytojob.com/apply/jobs/details/{jid}", "")
        if job:
            out.append(job)
    return out


def fetch(client, tenant: dict) -> list:
    r = check(client.get(f"https://{tenant['key']}.applytojob.com/apply/jobs/"), f"jazzhr/{tenant['key']}")
    if "Inactive" in r.text[:3000] and "job_title_link" not in r.text:
        raise Gone(f"jazzhr/{tenant['key']}: inactive account")
    if "jobs_table" not in r.text and "job_listings" not in r.text:
        raise Failed(f"jazzhr/{tenant['key']}: unexpected page")
    return parse(r.text, tenant)
