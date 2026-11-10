"""Google Careers XML feed: https://www.google.com/about/careers/applications/jobs/feed.xml"""
from __future__ import annotations

import re

from ..model import make
from .base import check

ATS = "google"
KIND = "single"
WORKERS = 1
PRIORITY = 3
URL = "https://www.google.com/about/careers/applications/jobs/feed.xml"
CC = {"UK": "GB"}


def _t(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    return m.group(1).strip() if m else ""


def parse(text: str, tenant=None) -> list:
    out = []
    for m in re.finditer(r"<job>(.*?)</job>", text, re.S):
        dm = re.search(r"<description>(.*?)</description>", m.group(1), re.S)
        b = re.sub(r"<description>.*?</description>", "", m.group(1), flags=re.S)
        locs, cc = [], ""
        for lb in re.findall(r"<location>(.*?)</location>", b, re.S):
            parts = [_t(lb, "city"), _t(lb, "state"), _t(lb, "country")]
            locs.append(", ".join(p for p in parts if p))
            cc = cc or parts[2]
        cc = CC.get(cc, cc)
        workplace = "remote" if _t(b, "isRemote") == "Yes" else ("hybrid" if _t(b, "isHybrid") == "Yes" else "")
        job = make(ATS, _t(b, "title"), _t(b, "employer") or "Google", locs, _t(b, "url"), _t(b, "published"),
                   cc_hint=cc if len(cc) == 2 else "", workplace=workplace, desc=dm.group(1) if dm else "")
        if job:
            out.append(job)
    return out


def fetch(client, tenant=None) -> list:
    return parse(check(client.get(URL), "google").text)
