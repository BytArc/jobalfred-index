"""Which well-known lists a company belongs to (field co), and the language inference that uses the company's head-office country.

Lists are versioned data: data/companies/curated.json (big tech, AI labs, Big 4, consultancies, edited by hand) and
data/companies/indices.json (stock-index constituents from Wikipedia with source and date, scripts/companies_refresh.py, refreshed monthly).
One company can sit on several lists (Alphabet is in the S&P 500 and is Google in big tech): members that share a name, an alias or a
verified website are one company and get every code.

A row's employer is a member when
  * its name (or an alias) matches and the posting is on a feed, on an enterprise careers system, or on a board whose name is the
    member's own ("boards.greenhouse.io/anthropic" for Anthropic, not "targetitalia.teamtailor.com" for Target), or
  * its postings live on the member's own website (the domain from its Wikipedia infobox or the curated list; never a guessed one).
For an index member (not a curated one) a small-business board also has to be in the member's head-office country, so a namesake
start-up abroad is not tagged.

co: codes joined by commas ("bigtech,sp500"), curated lists first, then indexes by GDP rank; "" when the company is on no list.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit

from . import industry, language
from .industry import norm

DATA = Path(__file__).resolve().parent.parent / "data" / "companies"
CURATED_ORDER = ("bigtech", "ailab", "big4", "consulting")
# careers systems a namesake small firm does not run under a big company's bare name
ENTERPRISE_ATS = {"workday", "oracle", "successfactors", "jobs2web", "eightfold", "icims", "smartrecruiters", "google", "apple", "amazon", "uber"}
PATH_HOSTS = set(industry.PATH_ATS)
_lock = threading.Lock()
_idx: dict = {}


def lists() -> dict:
    """code -> list, curated lists first, then indexes in GDP order."""
    out: dict[str, dict] = {}
    for fn in ("curated.json", "indices.json"):
        p = DATA / fn
        if p.exists():
            doc = json.loads(p.read_text()).get("lists", {})
            for code, lst in sorted(doc.items(), key=lambda kv: kv[1].get("gdp_rank", 0)):
                out[code] = {**lst, "curated": fn == "curated.json"}
    return out


def _label(domain: str) -> str:
    parts = (domain or "").lower().split(".")
    keep = 3 if ".".join(parts[-2:]) in industry._SLD2 else 2
    return norm(parts[-keep]) if len(parts) >= keep else ""


def index() -> dict:
    """{'names': norm name -> group id, 'domains': registrable domain -> group id, 'groups': [group]}"""
    with _lock:
        if _idx:
            return _idx
        ls = lists()
        order = {c: i for i, c in enumerate(ls)}
        members = []                                  # (code, member, curated, list hq)
        for code, lst in ls.items():
            for m in lst["members"]:
                members.append((code, m, lst["curated"], lst.get("hq", "")))
        parent = list(range(len(members)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        seen: dict[str, int] = {}
        for i, (code, m, cur, _) in enumerate(members):
            keys = {"n:" + norm(n) for n in [m["name"]] + list(m.get("aliases") or []) if len(norm(n)) >= 2}
            if m.get("domain"):
                keys.add("d:" + industry.own_domain(["https://" + m["domain"] + "/"]))
            for k in keys:
                if k in ("n:", "d:"):
                    continue
                if k in seen:
                    parent[find(i)] = find(seen[k])
                else:
                    seen[k] = i
        groups: dict[int, dict] = {}
        for i, (code, m, cur, lhq) in enumerate(members):
            g = groups.setdefault(find(i), {"codes": [], "names": set(), "domains": set(), "hq": "", "lhq": "", "curated": False, "name": m["name"]})
            if code not in g["codes"]:
                g["codes"].append(code)
            g["names"] |= {norm(n) for n in [m["name"]] + list(m.get("aliases") or []) if len(norm(n)) >= 2}
            if m.get("domain"):
                g["domains"].add(industry.own_domain(["https://" + m["domain"] + "/"]))
            g["hq"] = g["hq"] or m.get("hq") or ""
            g["lhq"] = g["lhq"] or lhq
            g["curated"] = g["curated"] or cur
        out_groups, names, domains = [], {}, {}
        for g in groups.values():
            g["codes"].sort(key=lambda c: order.get(c, 999))
            g["hq"] = g["hq"] or g["lhq"]
            g["labels"] = set(g["names"]) | {_label(d) for d in g["domains"]}
            gid = len(out_groups)
            out_groups.append(g)
            for n in g["names"]:
                names.setdefault(n, gid)
            for d in g["domains"]:
                domains.setdefault(d, gid)
        # boards the probe found for a member (data/companies/tenants.json, each carrying the member's name): their rows belong to the
        # member whatever name the careers system shows ("Johnson Controls International" on jci.wd5.myworkdayjobs.com)
        boards = {}
        tp = DATA / "tenants.json"
        if tp.exists():
            for t in json.loads(tp.read_text()).get("tenants", []):
                ats = {"lever-eu": "lever"}.get(t["ats"], t["ats"])
                gid = names.get(norm((t.get("data") or {}).get("name") or ""))
                if gid is not None and ats not in ("jsonld", "pagelist", "careers-page"):
                    boards[(ats, norm(t["key"].split("|")[0].split(".")[0].split("/")[0]))] = gid
                    boards[(ats, "=" + norm(t["data"]["name"]))] = gid      # for postings whose URL does not name the board
        _idx.update(names=names, domains=domains, groups=out_groups, boards=boards)
        return _idx


def reset() -> None:
    with _lock:
        _idx.clear()


def board_of(url: str) -> tuple[str, str]:
    """(board name, own domain) of a posting URL: the tenant's name on an ATS, or the employer's own registrable domain."""
    sp = urlsplit(url or "")
    host = (sp.hostname or "").lower()
    if not host:
        return "", ""
    segs = [s for s in sp.path.split("/") if s]
    if host in PATH_HOSTS:
        if host == "join.com" and len(segs) > 1:
            return norm(segs[1]), ""
        if host == "apply.workable.com" and segs and segs[0] == "j":
            return "", ""                     # a short link (apply.workable.com/j/ID) does not name the board
        return (norm(segs[0]) if segs else ""), ""
    if host.endswith("comeet.com") and len(segs) > 1:
        return norm(segs[1]), ""
    if any(host == h or host.endswith("." + h) for h in industry.ATS_HOSTS):
        return norm(host.split(".")[0]), ""
    dom = industry.own_domain([url])
    return _label(dom), dom


def _key_matches(key: str, labels: set[str]) -> bool:
    if not key:
        return False
    for x in labels:
        if key == x or (len(x) >= 4 and (key.startswith(x) or x.startswith(key)) and abs(len(key) - len(x)) <= 4):
            return True
    return False


def match(name: str, url: str = "", ats: str = "", cc: str = "") -> int | None:
    """The company group a row's employer belongs to, or None."""
    ix = index()
    key, dom = board_of(url)
    if (ats, key) in ix["boards"]:
        return ix["boards"][(ats, key)]
    if not key and (ats, "=" + norm(name)) in ix["boards"]:
        return ix["boards"][(ats, "=" + norm(name))]
    gid = ix["names"].get(norm(name))
    if gid is not None:
        g = ix["groups"][gid]
        from .adapters import FEED_NAMES
        if ats in FEED_NAMES or ats in ENTERPRISE_ATS or (dom and dom in g["domains"]):
            return gid
        if _key_matches(key, g["labels"]) and (g["curated"] or not cc or not g["hq"] or cc == g["hq"]):
            return gid
    if dom and dom in ix["domains"]:
        return ix["domains"][dom]
    return None


def membership(name: str, url: str = "", ats: str = "", cc: str = "") -> tuple[list[str], str]:
    """(codes, head-office country) for one row's employer; ([], "") when it is on no list."""
    gid = match(name, url, ats, cc)
    if gid is None:
        return [], ""
    g = index()["groups"][gid]
    return list(g["codes"]), g["hq"]


CO, LR, LQ = 16, 17, 18        # positions after t c l cc r u p a smin smax cur lv ls in fn ft (checked against shards.FIELDS in the tests)


def assign(rows: list[list], log=print) -> dict:
    """Fill co for every row, and lr/lq (inferred) where the description stated nothing. One lookup per employer and board."""
    cache: dict[tuple, tuple[list[str], str]] = {}
    stated = inferred = unknown = listed = 0
    per_code: dict[str, int] = {}
    for r in rows:
        if len(r) <= LQ:
            r.extend([""] * (LQ + 1 - len(r)))
        key, dom = board_of(r[5])
        k = (r[1], r[7], key, dom, r[3])
        if k not in cache:
            cache[k] = membership(r[1], r[5], r[7], r[3])
        codes, hq = cache[k]
        r[CO] = ",".join(codes)
        if codes:
            listed += 1
            for c in codes:
                per_code[c] = per_code.get(c, 0) + 1
        if r[LQ] == "s" and r[LR]:
            stated += 1
        else:
            langs = language.national(hq) or language.national(r[3])
            if langs:
                r[LR], r[LQ] = ",".join(langs), "i"
                inferred += 1
            else:
                r[LR], r[LQ] = "", ""
                unknown += 1
    stats = {"rows_on_a_list": listed, "lang_stated": stated, "lang_inferred": inferred, "lang_unknown": unknown, "per_list": per_code}
    log(f"companies: {stats}")
    return stats


def published_map() -> dict:
    """companies.json beside the manifest: code -> label, kind, country, source, retrieval date, member count."""
    out = {}
    for code, l in lists().items():
        out[code] = {"label": l["label"], "kind": "curated" if l["curated"] else "index", "country": "" if l["curated"] else l.get("hq", ""),
                     "source": l.get("source", ""), "retrieved": l.get("retrieved", ""), "members": len(l["members"])}
    return out
