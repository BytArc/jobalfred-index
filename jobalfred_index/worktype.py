"""Work type of every role: field wt, 1 remote, 2 hybrid, 3 on site; field ws, "s" stated or "i" inferred. Every row gets one.

Stated, strongest first: the source's own workplace or remote flag (Lever, Ashby, Greenhouse, Workable, Oracle, ...), the location or
title ("Remote - Portugal", "Hybrid"; the r field), then the description where the source returns it ("this is a hybrid role", "three
days a week in the office", "fully remote", "on-site role"; plain phrases, "hybrid cloud" or "remote monitoring" do not count). A
remote-only job board is a statement too. When nothing is stated the role is inferred on site, unless most of the company's roles
in the same build are stated remote, then remote. Deterministic, no AI, no network; the description is read at ingestion, never stored.
"""
from __future__ import annotations

import re

REMOTE, HYBRID, ONSITE = 1, 2, 3
NAMES = {REMOTE: "remote", HYBRID: "hybrid", ONSITE: "on site"}
WT, WS = 19, 20            # positions after ... co lr lq (checked against shards.FIELDS in the tests)
R = 4                      # the r field: 0 on site or not stated, 1 hybrid, 2 remote

WORKPLACE = {"remote": REMOTE, "fully_remote": REMOTE, "telecommute": REMOTE, "full_remote": REMOTE, "fully remote": REMOTE,
             "remote-first": REMOTE, "remote_only": REMOTE, "hybrid": HYBRID, "onsite": ONSITE, "on-site": ONSITE, "on_site": ONSITE,
             "on site": ONSITE, "office": ONSITE, "in-office": ONSITE, "in_office": ONSITE, "inoffice": ONSITE, "in office": ONSITE}
_N = r"(?:[1-4]|one|two|three|four)"
DESC_HYBRID = re.compile(
    r"(?<![a-z])(?:hybrid (?:role|position|job|work\w*|model|schedule|set-?up|arrangement|environment|opportunity|policy|basis)|"
    r"(?:this|the) (?:role|position|job) is hybrid|on a hybrid basis|" + _N + r" days? (?:a|per|each) week (?:in|at|from) (?:the |our )?"
    r"(?:office|hq|headquarters|studio|hub)|in (?:the )?office " + _N + r" days|modelo h[ií]brido|regime h[ií]brido|trabajo h[ií]brido|"
    r"modalidad h[ií]brida|modalidade h[ií]brida|hybride[sn]? (?:arbeiten|arbeitsmodell)|t[ée]l[ée]travail partiel|mode hybride)", re.I)
DESC_REMOTE = re.compile(
    r"(?<![a-z])(?:fully remote|100% remote|remote[- ](?:first|only)|(?:this|the) (?:role|position|job) is (?:fully |100% )?remote|"
    r"remote (?:role|position|job|opportunity)|work from home (?:role|position|job)|home[- ]based (?:role|position)|teletrabajo 100|"
    r"100% (?:remoto|teletrabajo|t[ée]l[ée]travail)|totalmente remot[oa]|trabalho remoto|full[- ]remote|t[ée]l[ée]travail (?:complet|total))", re.I)
DESC_ONSITE = re.compile(
    r"(?<![a-z])(?:on-?site (?:role|position|job)|(?:this|the) (?:role|position|job) is (?:fully |100% )?(?:on-?site|office[- ]based|in[- ]office)|"
    r"fully on-?site|100% on-?site|in-office (?:role|position)|office[- ]based (?:role|position)|(?:5|five) days (?:a|per) week (?:in|at) "
    r"(?:the |our )?office|100% presencial|trabajo presencial|trabalho presencial|modalidad presencial|modalidade presencial)", re.I)


def stated(workplace: str = "", r: int = 0, desc: str | None = None) -> tuple[int, str]:
    """(wt, "s") when the source, the location, the title or the description states the work type; (0, "") when nothing does."""
    w = WORKPLACE.get((workplace or "").strip().lower())
    if w:
        return w, "s"
    if r == 2:
        return REMOTE, "s"
    if r == 1:
        return HYBRID, "s"
    if desc:
        t = desc[:30000]
        if DESC_HYBRID.search(t):
            return HYBRID, "s"
        if DESC_REMOTE.search(t):
            return REMOTE, "s"
        if DESC_ONSITE.search(t):
            return ONSITE, "s"
    return 0, ""


def assign(rows: list[list], log=print) -> dict:
    """Every row ends with wt and ws. Stored rows from before the field get it from r; the rest are inferred per company."""
    from .industry import group_key
    for r in rows:
        if len(r) <= WS:
            r.extend([""] * (WS + 1 - len(r)))
        if r[WS] != "s":
            if r[R] == 2:
                r[WT], r[WS] = REMOTE, "s"
            elif r[R] == 1:
                r[WT], r[WS] = HYBRID, "s"
            else:
                r[WT], r[WS] = 0, ""
    per: dict[str, list[int]] = {}
    keys = []
    for r in rows:
        k = group_key(r[1], r[5])
        keys.append(k)
        c = per.setdefault(k, [0, 0])
        c[0] += 1
        c[1] += r[WS] == "s" and r[WT] == REMOTE
    stats = {"stated": 0, "inferred_onsite": 0, "inferred_remote": 0}
    for r, k in zip(rows, keys):
        if r[WS] == "s":
            stats["stated"] += 1
            continue
        n, remote = per[k]
        if remote * 2 > n:                       # most of the company's roles are stated remote
            r[WT], r[WS] = REMOTE, "i"
            stats["inferred_remote"] += 1
        else:
            r[WT], r[WS] = ONSITE, "i"
            stats["inferred_onsite"] += 1
    log(f"work type: {stats}")
    return stats
