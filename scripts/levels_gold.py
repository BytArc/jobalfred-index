"""Gold set for the level and years tags: a stratified sample of published roles, each posting's own text read once.

Usage:
  levels_gold.py draw SHARD_DIR N SEED      stratified draw over language x current level, spread over careers systems -> work/levels/draw.json
  levels_gold.py fetch [WORKERS]            read each drawn posting's public page or API once -> work/levels/pages.jsonl (resumable)

Public pages and public APIs only, through the index's polite client (honest user agent, robots.txt obeyed, a 403/429 or a bot
check leaves the host alone). Page text stays in work/ (not committed); the committed gold file keeps labels and short evidence only.
"""
from __future__ import annotations

import collections
import gzip
import html
import json
import math
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index.polite import Client  # noqa: E402

import os
WORK = root / "work" / "levels"
ROUND = os.environ.get("LEVELS_ROUND", "")          # "2": a second, fresh sample (draw2.json, pages2.jsonl), never overlapping the first
TAG = re.compile(r"<[^>]+>")
LANG_CC = {"pt": {"PT", "BR", "AO", "MZ"},
           "es": {"ES", "MX", "AR", "CO", "CL", "PE", "UY", "EC", "VE", "BO", "PY", "CR", "PA", "DO", "GT", "HN", "SV", "NI", "PR"},
           "fr": {"FR", "LU", "MA", "TN", "SN", "CI", "MC", "DZ", "CM"},
           "de": {"DE", "AT", "CH", "LI"},
           "it": {"IT", "SM"}}
_HINT = {"pt": r"\b(?:analista|assistente|vendedor|gerente|coordenador|engenheiro|estagio|estagiario|auxiliar|operador)\b|\w+(?:ção|ções)\b",
         "es": r"\b(?:asistente|coordinador|ingeniero|practicas|operario|jefe de|responsable de)\b|\w+ción\b",
         "fr": r"\b(?:chargé|chargée|ingénieur|technicien|conseiller|vendeur|stagiaire|alternance|h/f|f/h)\b",
         "de": r"\b(?:mitarbeiter|sachbearbeiter|leiter|referent|werkstudent|praktikum|kaufmann|kauffrau|m/w/d|w/m/d|m/f/d)\b",
         "it": r"\b(?:addetto|addetta|responsabile|impiegato|impiegata|ingegnere|stagista|tirocinio|commesso)\b"}
_HINT_RX = {k: re.compile(v, re.I) for k, v in _HINT.items()}
ALLOC = {"en": 480, "pt": 260, "es": 260, "fr": 260, "de": 260, "it": 220}


def lang_of(title: str, cc: str) -> str:
    for k, ccs in LANG_CC.items():
        if cc in ccs:
            return k
    for k, rx in _HINT_RX.items():
        if rx.search(title or ""):
            return k
    return "en"


def text_of(h: str) -> str:
    h = html.unescape(html.unescape(h or ""))
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|li|div|h\d|tr|ul)>", "\n", h)
    t = TAG.sub(" ", h)
    t = re.sub(r"[ \t\r\f ]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def load_rows(shard_dir: Path):
    rows, F = [], None
    for p in sorted(shard_dir.glob("*.json.gz")):
        if not p.name[:2].isupper():
            continue
        d = json.loads(gzip.decompress(p.read_bytes()))
        F = d["f"]
        rows += d["rows"]
    return F, rows


def draw(shard_dir: str, n: int, seed: int):
    F, rows = load_rows(Path(shard_dir))
    ix = {k: i for i, k in enumerate(F)}
    random.seed(seed)
    prev = set()
    for f in (root / "data" / "seniority").glob("*.jsonl"):
        prev |= {json.loads(l).get("url") for l in f.read_text().splitlines() if l.strip()}
    if ROUND and (WORK / "draw.json").exists():
        prev |= {p["url"] for p in json.load(open(WORK / "draw.json"))["picks"]}
    strata = collections.defaultdict(list)
    for r in rows:
        if r[5] in prev:
            continue
        lg = lang_of(r[0], r[3])
        grp = "i" if r[ix["ls"]] == "i" else f"s{r[ix['lv']]}"
        strata[(lg, grp)].append(r)
    scale = n / sum(ALLOC.values())
    picks = []
    for lg, quota in ALLOC.items():
        quota = round(quota * scale)
        groups = {g: lst for (l, g), lst in strata.items() if l == lg}
        w = {g: math.sqrt(len(lst)) for g, lst in groups.items()}
        tot = sum(w.values())
        for g, lst in groups.items():
            k = min(len(lst), max(8, round(quota * w[g] / tot)))
            by = collections.defaultdict(list)
            for r in lst:
                by[r[7]].append(r)
            srcs = list(by)
            sw = [math.sqrt(len(by[s])) for s in srcs]
            chosen = set()
            tries = 0
            while len(chosen) < k and tries < k * 20:
                tries += 1
                s = random.choices(srcs, sw)[0]
                r = random.choice(by[s])
                if r[5] in chosen:
                    continue
                chosen.add(r[5])
                picks.append({"title": r[0], "company": r[1], "loc": r[2], "cc": r[3], "url": r[5], "ats": r[7], "lang": lg, "stratum": g,
                              "lv": r[ix["lv"]], "ls": r[ix["ls"]], "fn": r[ix["fn"]], "ft": r[ix["ft"]], "co": r[ix["co"]],
                              "w": len(lst) / k})
    random.shuffle(picks)
    WORK.mkdir(parents=True, exist_ok=True)
    pop = collections.Counter((lang_of(r[0], r[3]), "i" if r[ix["ls"]] == "i" else f"s{r[ix['lv']]}") for r in rows if r[5] not in prev)
    json.dump({"picks": picks, "population": {f"{a}|{b}": v for (a, b), v in pop.items()}, "total": len(rows)},
              open(WORK / f"draw{ROUND}.json", "w"), ensure_ascii=False)
    print(len(picks), "drawn", collections.Counter(p["lang"] for p in picks), collections.Counter(p["ats"] for p in picks).most_common(14))


# -- reading one posting -------------------------------------------------------------------------------------------------
c = Client()
_lists: dict[str, dict] = {}
_lock = threading.Lock()


def _jsonld(body: str):
    for m in re.finditer(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', body):
        try:
            d = json.loads(m.group(1).strip())
        except ValueError:
            continue
        items = d if isinstance(d, list) else (d.get("@graph", [d]) if isinstance(d, dict) else [])
        for it in items:
            if isinstance(it, dict) and "JobPosting" in str(it.get("@type")):
                return it
    return None


def _cached_list(key: str, url: str, parse) -> dict:
    with _lock:
        if key in _lists:
            return _lists[key]
    try:
        x = c.get(url, headers={"Accept": "application/json"})
        val = parse(x) if x.status == 200 else {}
    except Exception:  # noqa: BLE001
        val = {}
    with _lock:
        _lists[key] = val
    return val


def fetch(p: dict) -> dict:
    u, ats = p["url"], p["ats"]
    out = {"url": u, "text": "", "native": {}, "how": ""}
    try:
        if ats == "workday":
            m = re.match(r"https://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Za-z]{2}/)?([^/]+)(/job/.+)$", u, re.I)
            if m:
                t, wd, site, path = m.groups()
                x = c.get(f"https://{t}.{wd}.myworkdayjobs.com/wday/cxs/{t}/{site}{path}", headers={"Accept": "application/json"})
                if x.status == 200:
                    info = (x.json() or {}).get("jobPostingInfo") or {}
                    out.update(text=text_of(info.get("jobDescription")), how="workday-cxs",
                               native={k: info.get(k) for k in ("timeType", "remoteType") if info.get(k)})
                    return out
                out["how"] = f"workday-{x.status}"
                return out
        elif ats == "oracle":
            m = re.match(r"https://([^/]+)/hcmUI/CandidateExperience/[a-z-]+/sites/([^/]+)/job/(\d+)", u)
            if m:
                h, site, jid = m.groups()
                x = c.get(f"https://{h}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails",
                          params={"expand": "all", "onlyData": "true", "finder": f'ById;Id="{jid}",siteNumber={site}'},
                          headers={"Accept": "application/json"})
                it = (((x.json() or {}).get("items") or [None])[0]) if x.status == 200 else None
                if it:
                    out.update(text=text_of("\n".join(str(it.get(k) or "") for k in (
                        "ShortDescriptionStr", "ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"))),
                        how="oracle-rest", native={k: it.get(k) for k in ("JobFunction", "JobLevel", "JobGrade", "WorkerType", "JobSchedule",
                                                                          "ContractType", "StudyLevel", "JobFamily") if it.get(k)})
                    return out
                out["how"] = f"oracle-{x.status}"
                return out
        elif ats == "greenhouse":
            m = re.search(r"greenhouse\.io/([A-Za-z0-9_-]+)/jobs/(\d+)", u)
            if m:
                x = c.get(f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}")
                if x.status == 200:
                    d = x.json() or {}
                    out.update(text=text_of(d.get("content")), how="greenhouse-api",
                               native={"metadata": d.get("metadata")} if d.get("metadata") else {})
                    return out
        elif ats == "lever":
            m = re.search(r"jobs\.(?:eu\.)?lever\.co/([^/]+)/([0-9a-f-]{36})", u)
            if m:
                api = "https://api.eu.lever.co" if ".eu." in u else "https://api.lever.co"
                x = c.get(f"{api}/v0/postings/{m.group(1)}/{m.group(2)}")
                if x.status == 200:
                    d = x.json() or {}
                    out.update(text=(d.get("descriptionPlain", "") + "\n" + "\n".join(
                        (l.get("text", "") + ":\n" + text_of(l.get("content", ""))) for l in d.get("lists", [])) + "\n" +
                        text_of(d.get("additional") or "")), how="lever-api",
                        native={"commitment": (d.get("categories") or {}).get("commitment")})
                    return out
        elif ats == "ashby":
            m = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", u)
            if m:
                lst = _cached_list("ashby:" + m.group(1), f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}",
                                   lambda x: {j["id"]: j for j in (x.json() or {}).get("jobs", [])})
                j = lst.get(m.group(2))
                if j:
                    out.update(text=j.get("descriptionPlain", ""), how="ashby-api", native={"employmentType": j.get("employmentType")})
                    return out
        elif ats == "recruitee":
            m = re.match(r"(https://[^/]+)/o/", u)
            if m:
                lst = _cached_list("recruitee:" + m.group(1), m.group(1) + "/api/offers/",
                                   lambda x: {o.get("careers_url"): o for o in (x.json() or {}).get("offers", [])})
                o = lst.get(u)
                if o:
                    out.update(text=text_of((o.get("description") or "") + "\n" + (o.get("requirements") or "")), how="recruitee-api",
                               native={k: o.get(k) for k in ("experience_code", "education_code", "employment_type_code") if o.get(k)})
                    return out
        elif ats == "breezy":
            m = re.match(r"(https://[^/]+)/p/", u)
            if m:
                lst = _cached_list("breezy:" + m.group(1), m.group(1) + "/json", lambda x: {j.get("url"): j for j in (x.json() or [])})
                j = lst.get(u)
                if j and j.get("description"):
                    out.update(text=text_of(j.get("description")), how="breezy-json", native={"type": j.get("type")})
                    return out
        elif ats == "bamboohr":
            m = re.match(r"(https://[^/]+)/careers/(\d+)", u)
            if m:
                x = c.get(f"{m.group(1)}/careers/{m.group(2)}/detail", headers={"Accept": "application/json"})
                if x.status == 200:
                    jo = ((x.json() or {}).get("result") or {}).get("jobOpening") or {}
                    out.update(text=text_of(jo.get("description")), how="bamboohr-detail",
                               native={k: jo.get(k) for k in ("minimumExperience", "employmentStatusLabel") if jo.get(k)})
                    return out
        x = c.get(u)                       # every other source: the posting's own page, JSON-LD first
        if x.status != 200:
            out["how"] = f"page-{x.status}"
            return out
        body = x.text
        jl = _jsonld(body)
        if jl and jl.get("description"):
            extra = "\n" + text_of(str(jl.get("qualifications"))) if jl.get("qualifications") else ""
            out.update(text=text_of(jl.get("description")) + extra, how="jsonld",
                       native={k: jl.get(k) for k in ("experienceRequirements", "educationRequirements", "employmentType") if jl.get(k)})
            return out
        if ats == "gupy":
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
            if m:
                try:
                    job = json.loads(m.group(1))["props"]["pageProps"]["job"]
                    out.update(text=text_of("\n".join(str(job.get(k) or "") for k in (
                        "description", "responsibilities", "prerequisites", "relevantExperiences"))), how="gupy-next", native={"type": job.get("type")})
                    return out
                except (KeyError, ValueError, TypeError):
                    pass
        out.update(text=text_of(body)[:12000], how="page-text")
    except Exception as e:  # noqa: BLE001
        out["how"] = "error:" + type(e).__name__
    return out


def do_fetch(workers: int = 12):
    d = json.load(open(WORK / f"draw{ROUND}.json"))
    done = set()
    pf = WORK / f"pages{ROUND}.jsonl"
    if pf.exists():
        done = {json.loads(l)["url"] for l in pf.read_text().split("\n") if l.strip()}
    todo = [p for p in d["picks"] if p["url"] not in done]
    print(len(todo), "to read", flush=True)
    n = [0, 0]
    with open(pf, "a") as fh, ThreadPoolExecutor(workers) as ex:
        for res in ex.map(fetch, todo):
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
            fh.flush()
            n[0] += 1
            n[1] += len(res["text"]) >= 200
            if n[0] % 50 == 0:
                print(n[0], "read,", n[1], "with text", flush=True)
    print("done", n, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "draw":
        draw(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif sys.argv[1] == "fetch":
        do_fetch(int(sys.argv[2]) if len(sys.argv) > 2 else 12)
