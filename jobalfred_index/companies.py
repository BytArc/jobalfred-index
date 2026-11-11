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
    """code -> list, curated lists first, then indexes in GDP order; hand-added aliases (aliases.json) folded in."""
    out: dict[str, dict] = {}
    extra = json.loads((DATA / "aliases.json").read_text()).get("lists", {}) if (DATA / "aliases.json").exists() else {}
    for fn in ("curated.json", "indices.json"):
        p = DATA / fn
        if p.exists():
            doc = json.loads(p.read_text()).get("lists", {})
            for code, lst in sorted(doc.items(), key=lambda kv: kv[1].get("gdp_rank", 0)):
                more = extra.get(code, {})
                members = [{**m, "aliases": sorted(set(m.get("aliases") or []) | set(more[m["name"]]))} if m["name"] in more else m
                           for m in lst["members"]]
                out[code] = {**lst, "members": members, "curated": fn == "curated.json"}
    return out


# second-level names under a country code that are public suffixes: "hkex.com.hk", "hdfc.bank.in", "sanford.co.nz" are three-label domains
_SECOND = {"com", "co", "net", "org", "gov", "edu", "ac", "or", "ne", "go", "gob", "gouv", "bank", "ltd", "plc", "nic", "mil", "biz", "info",
           "firm", "gen", "ind", "nom", "res", "web", "sch", "med", "asso"}


def reg_domain(host: str) -> str:
    """The registrable domain of a host, with country-code second levels kept ("www.hkex.com.hk" -> "hkex.com.hk")."""
    parts = [x for x in (host or "").lower().strip(".").split(".") if x]
    if len(parts) < 2:
        return ""
    keep = 3 if len(parts) >= 3 and len(parts[-1]) == 2 and (parts[-2] in _SECOND or ".".join(parts[-2:]) in industry._SLD2) else 2
    return ".".join(parts[-keep:])


def _row_domain(url: str) -> str:
    host = (urlsplit(url or "").hostname or "").lower()
    if not host or any(host == h or host.endswith("." + h) for h in industry.ATS_HOSTS):
        return ""
    return reg_domain(host)


def _label(domain: str) -> str:
    d = reg_domain(domain)
    return norm(d.split(".")[0]) if d else ""


def index() -> dict:
    """{'names': norm name -> [group ids], 'domains': registrable domain -> group id, 'groups': [group], 'boards': {(ats, board): group id}}

    Two index members are one company when they share a Wikipedia article or a website (Airbus in the DAX and the CAC 40), never on a
    name alone: Merck in the S&P 500 and Merck in the DAX are two companies. A curated member joins the index member whose name, alias or
    website it shares (Google, alias Alphabet, is Alphabet in the S&P 500): its aliases are chosen by hand."""
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

        def union(keys_of):
            seen: dict[str, int] = {}
            for i, keys in keys_of:
                for k in keys:
                    if k in seen:
                        parent[find(i)] = find(seen[k])
                    else:
                        seen[k] = i

        def mnames(m):
            return {norm(n) for n in [m["name"]] + list(m.get("aliases") or []) if len(norm(n)) >= 2}

        def mdomain(m):
            return reg_domain(m["domain"]) if m.get("domain") else ""

        # A local listing of a foreign group (Abbott Laboratories Pakistan in the KSE 100, whose list links the parent's article) is not the
        # parent: when a member's article puts the head office abroad and that country's own index lists the same article, the member
        # stays on its own, with its index's country as head office. A shared website joins members only in the same head-office country.
        home_article = {(m.get("wiki"), lhq) for code, m, cur, lhq in members if m.get("wiki") and m.get("hq") == lhq}
        local = {i for i, (code, m, cur, lhq) in enumerate(members)
                 if m.get("wiki") and m.get("hq") and m["hq"] != lhq and (m["wiki"], m["hq"]) in home_article}
        union((i, set() if i in local else (({"w:" + m["wiki"]} if m.get("wiki") else set()) |
                                            ({"d:" + mdomain(m) + "@" + (m.get("hq") or lhq)} if mdomain(m) else set())))
              for i, (code, m, cur, lhq) in enumerate(members))
        by_key: dict[str, set[int]] = {}
        for i, (code, m, cur, _) in enumerate(members):
            if not cur:
                for k in {"n:" + n for n in mnames(m)} | ({"d:" + mdomain(m)} if mdomain(m) else set()):
                    by_key.setdefault(k, set()).add(i)
        for i, (code, m, cur, _) in enumerate(members):
            if cur:
                for k in {"n:" + n for n in mnames(m)} | ({"d:" + mdomain(m)} if mdomain(m) else set()):
                    hits = {find(j) for j in by_key.get(k, ())}
                    if len(hits) == 1:                # an alias shared by two different index companies joins neither
                        parent[find(i)] = hits.pop()
        groups: dict[int, dict] = {}
        for i, (code, m, cur, lhq) in enumerate(members):
            g = groups.setdefault(find(i), {"codes": [], "names": set(), "domains": set(), "hq": "", "lhq": "", "curated": False, "name": m["name"]})
            if code not in g["codes"]:
                g["codes"].append(code)
            g["names"] |= mnames(m)
            if mdomain(m):
                g["domains"].add(mdomain(m))
            g["hq"] = g["hq"] or (lhq if i in local else m.get("hq")) or ""
            g["lhq"] = g["lhq"] or lhq
            if i in local:
                g["domains"].discard(mdomain(m))         # the parent's website is the parent's
            g["curated"] = g["curated"] or cur
        out_groups, names, domains = [], {}, {}
        gid_of = {}
        for root_i, g in groups.items():
            gid_of[root_i] = len(gid_of)
        for g in groups.values():
            g["codes"].sort(key=lambda c: order.get(c, 999))
            g["hq"] = g["hq"] or g["lhq"]
            g["labels"] = set(g["names"]) | {_label(d) for d in g["domains"]}
            gid = len(out_groups)
            out_groups.append(g)
            for n in g["names"]:
                names.setdefault(n, []).append(gid)
            for d in g["domains"]:
                domains.setdefault(d, gid)
        # boards the probe found for a member (data/companies/tenants.json, each carrying the member's name and list): their rows belong
        # to the member whatever name the careers system shows ("Johnson Controls International" on jci.wd5.myworkdayjobs.com)
        boards = {}
        tp = DATA / "tenants.json"
        if tp.exists():
            for t in json.loads(tp.read_text()).get("tenants", []):
                ats = {"lever-eu": "lever"}.get(t["ats"], t["ats"])
                code = (t.get("source") or "").partition(":")[2]
                cands = names.get(norm((t.get("data") or {}).get("name") or ""), [])
                gid = next((g for g in cands if code in out_groups[g]["codes"]), cands[0] if len(cands) == 1 else None)
                if gid is not None and ats not in ("jsonld", "pagelist", "careers-page"):
                    boards[(ats, norm(t["key"].split("|")[0].split(".")[0].split("/")[0]))] = gid
                    boards[(ats, "=" + norm(t["data"]["name"]))] = gid      # for postings whose URL does not name the board
        member_gid = {(code, m["name"]): gid_of[find(i)] for i, (code, m, cur, _) in enumerate(members)}
        _idx.update(names=names, domains=domains, groups=out_groups, boards=boards, member_gid=member_gid)
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
    dom = _row_domain(url)
    return _label(dom), dom


KEY_TAIL = re.compile(r"(?:corporation|corp|inc|group|careers|career|jobs|global|usa|us|hq|holdings|holding|company|co)$")


def _key_matches(key: str, labels: set[str]) -> bool:
    if not key:
        return False
    keys = {key, KEY_TAIL.sub("", key)}                  # "eqtcorporation" is EQT's board
    for x in labels:
        if x and x in keys:
            return True
        if key == x or (len(x) >= 4 and (key.startswith(x) or x.startswith(key)) and abs(len(key) - len(x)) <= 4):
            return True
    return False


def _distinctive(name: str) -> bool:
    """Two words or more and ten letters or more: "Siemens Healthineers", "Fresenius Medical Care"; not "Sanford", "Next" or "Minor"."""
    return len(re.findall(r"[A-Za-z0-9]+", name or "")) >= 2 and len(norm(name)) >= 10


def learn_boards(rows, min_rows: int = 3) -> dict:
    """Boards a member uses, read from the rows themselves: a board (careers system and tenant) that carries a member's name for roles in
    the member's own head-office country is the member's, so its roles abroad are too (Novartis's Workday site lists roles in 60
    countries). A namesake abroad has no roles in the member's country on its board (Sanford Health is not Sanford Limited).
    rows: (company, url, ats, cc) tuples. Returns {(ats, board): group id}."""
    ix = index()
    votes: dict[tuple, dict[int, int]] = {}
    for name, url, ats, cc in rows:
        cands = ix["names"].get(norm(name))
        if not cands or not cc:
            continue
        for g in cands:
            if ix["groups"][g]["hq"] == cc:
                key, _ = board_of(url)
                if key:
                    v = votes.setdefault((ats, key), {})
                    v[g] = v.get(g, 0) + 1
    out = {}
    for b, v in votes.items():
        g, n = max(v.items(), key=lambda kv: kv[1])
        if n >= min_rows:
            out[b] = g
    return out


def match(name: str, url: str = "", ats: str = "", cc: str = "", learned: dict | None = None) -> int | None:
    """The company group a row's employer belongs to, or None. learned: boards from learn_boards over the same build."""
    ix = index()
    key, dom = board_of(url)
    if (ats, key) in ix["boards"]:
        return ix["boards"][(ats, key)]
    if learned and (ats, key) in learned:
        return learned[(ats, key)]
    if not key and (ats, "=" + norm(name)) in ix["boards"]:
        return ix["boards"][(ats, "=" + norm(name))]
    cands = ix["names"].get(norm(name), [])
    if len(cands) > 1:            # two listed companies share the name (Merck in the US, Merck in Germany): the head-office country decides
        cands = [g for g in cands if ix["groups"][g]["hq"] == cc] or [g for g in cands if (dom and dom in ix["groups"][g]["domains"])]
    gid = cands[0] if len(cands) == 1 else None
    if gid is not None:
        g = ix["groups"][gid]
        from .adapters import FEED_NAMES
        if dom and dom in g["domains"]:
            return gid
        if ats in FEED_NAMES or ats in ENTERPRISE_ATS:
            # a big careers system or a feed: the name is enough when it is distinctive or the role is in the company's own country;
            # otherwise the board has to be the member's (above). "Sanford" on Workday in the US is Sanford Health, not Sanford Limited.
            if g["curated"] or _distinctive(name) or (cc and cc == g["hq"]):
                return gid
        elif _key_matches(key, g["labels"]) and (g["curated"] or not cc or not g["hq"] or cc == g["hq"]):
            return gid
    if dom and dom in ix["domains"]:
        return ix["domains"][dom]
    return None


def membership(name: str, url: str = "", ats: str = "", cc: str = "", learned: dict | None = None) -> tuple[list[str], str]:
    """(codes, head-office country) for one row's employer; ([], "") when it is on no list."""
    gid = match(name, url, ats, cc, learned)
    if gid is None:
        return [], ""
    g = index()["groups"][gid]
    return list(g["codes"]), g["hq"]


CO, LR, LQ = 16, 17, 18        # positions after t c l cc r u p a smin smax cur lv ls in fn ft (checked against shards.FIELDS in the tests)


def assign(rows: list[list], log=print) -> dict:
    """Fill co for every row, and lr/lq (inferred) where the description stated nothing. One lookup per employer and board.
    Then the work type (worktype.assign) and, where no level is stated, the inferred level (levelinfer.assign)."""
    cache: dict[tuple, tuple[list[str], str]] = {}
    stated = inferred = unknown = listed = 0
    per_code: dict[str, int] = {}
    learned = learn_boards((r[1], r[5], r[7], r[3]) for r in rows)
    for r in rows:
        if len(r) <= LQ:
            r.extend([""] * (LQ + 1 - len(r)))
        key, dom = board_of(r[5])
        k = (r[1], r[7], key, dom, r[3])
        if k not in cache:
            cache[k] = membership(r[1], r[5], r[7], r[3], learned)
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
    # the other per-row labels that every row must carry, here so every caller (shards.build, vceu) labels a row completely
    from . import levelinfer, worktype
    stats["work_type"] = worktype.assign(rows, log=log)
    stats["level_inferred"] = levelinfer.assign(rows, log=log)
    return stats


def published_map() -> dict:
    """companies.json beside the manifest: code -> label, kind, country, source, retrieval date, member count."""
    out = {}
    for code, l in lists().items():
        out[code] = {"label": l["label"], "kind": "curated" if l["curated"] else "index", "country": "" if l["curated"] else l.get("hq", ""),
                     "source": l.get("source", ""), "retrieved": l.get("retrieved", ""), "members": len(l["members"])}
    return out
