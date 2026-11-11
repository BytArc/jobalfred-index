"""Industry of a company, and so of every role it posts. Rules and counted weights only: no AI at run time.

One label per company, copied onto its rows (field `in`, the industry code, after `ls`).

Signals, strongest first:
  1. an industry the source itself returns for the role (Jobicy jobIndustry, The Muse), when there is one
  2. the company's own homepage: title, description and site name, fetched once, cached in data/industry/homepages.json.gz,
     refreshed rarely, politely (robots.txt obeyed, the shared client's pacing, a blocked host is left alone)
  3. the company name, and the domain
  4. the mix of job titles the company posts (nurses point to health, underwriters to insurance)

The weights are data, versioned in the repo and rebuilt by `scripts/industry_train.py` from reader-labelled companies:
  data/industry/taxonomy.json   code -> label
  data/industry/lexicon.json    hand-written keywords per industry (seed knowledge, also used as pseudo-observations)
  data/industry/model.json      naive Bayes counts fitted to data/industry/labels.jsonl
Retraining is a commit of those files, not a code change.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

DATA = Path(__file__).resolve().parent.parent / "data" / "industry"
OTHER = "oth"
NOT_STATED = "0"            # the model is not sure enough to publish an industry (confidence below MIN_CONFIDENCE)
USE_OVERRIDES = True        # off only when measuring the model on companies a reader has labelled
UNDISCLOSED = "Undisclosed employer"

ATS_HOSTS = ("myworkdayjobs.com", "oraclecloud.com", "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "recruitee.com",
             "bamboohr.com", "breezy.hr", "teamtailor.com", "icims.com", "smartrecruiters.com", "applytojob.com", "gupy.io",
             "comeet.com", "comeet.co", "rippling.com", "personio.de", "personio.com", "pinpointhq.com", "jobs2web.com",
             "successfactors.com", "successfactors.eu", "taleo.net", "jobvite.com", "linkedin.com", "indeed.com", "myworkdaysite.com",
             "join.com", "gem.com", "remotive.com", "arbeitnow.com", "remoteok.com", "himalayas.app", "jobicy.com", "themuse.com",
             "weworkremotely.com", "amazon.jobs", "apple.com", "google.com", "careers.google.com", "eightfold.ai", "netflix.net")
PATH_ATS = ("boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io", "boards.eu.greenhouse.io", "jobs.lever.co",
            "jobs.eu.lever.co", "jobs.ashbyhq.com", "apply.workable.com", "ats.rippling.com", "jobs.smartrecruiters.com", "join.com")
_SLD2 = {"co.uk", "com.br", "com.au", "co.in", "co.jp", "com.mx", "co.za", "com.sg", "com.tr", "com.ar", "com.co", "co.nz", "org.uk", "com.pt"}
STOP = set("the and for with from your you our are was will inc llc ltd gmbh corp group company companies services service solutions "
           "worldwide global international limited holdings holding plc sas srl bv nv ag sa co jobs careers career work join".split())


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def words(s: str, minlen: int = 3) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9&]+", fold(s)) if len(w) >= minlen and w not in STOP]


def norm(name: str) -> str:
    from .shards import norm as n
    return n(name)


# -- grouping rows into companies ------------------------------------------------------------------------------------
def tenant_id(url: str) -> str:
    sp = urlsplit(url or "")
    host = (sp.hostname or "").lower()
    if host in PATH_ATS:
        seg = sp.path.strip("/").split("/", 1)[0]
        return f"{host}/{seg}".lower()
    return host


def group_key(name: str, url: str) -> str:
    """Rows of one company share a key. A row with no usable company name is grouped by its tenant instead."""
    k = norm(name or "")
    if not k or len(k) <= 3 or (name or "") in (UNDISCLOSED, "UNAVAILABLE"):
        return "~" + tenant_id(url)
    return "c:" + k


def row_meta(ats: dict, cc: dict) -> dict[str, float]:
    ta, tc = sum(ats.values()) or 1, sum(cc.values()) or 1
    out = {"a:" + k: 3.0 * v / ta for k, v in ats.items() if k}
    out.update({"cc:" + k: 2.0 * v / tc for k, v in cc.items() if k})
    return out


def own_domain(urls) -> str:
    """The registrable domain of the employer's own site, when its postings live on it."""
    counts: dict[str, int] = {}
    for u in urls:
        host = (urlsplit(u).hostname or "").lower()
        if not host or any(host == h or host.endswith("." + h) for h in ATS_HOSTS):
            continue
        parts = host.split(".")
        keep = 3 if ".".join(parts[-2:]) in _SLD2 else 2
        d = ".".join(parts[-keep:])
        counts[d] = counts.get(d, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0] if counts else ""


# -- the data files ----------------------------------------------------------------------------------------------------
_lock = threading.Lock()
_cache: dict[str, object] = {}


def _load(name: str):
    with _lock:
        if name not in _cache:
            p = DATA / name
            _cache[name] = json.loads(p.read_text()) if p.exists() else {}
        return _cache[name]


def taxonomy() -> dict[str, str]:
    return _load("taxonomy.json")


def reset_cache() -> None:
    with _lock:
        _cache.clear()


# -- the scorer ------------------------------------------------------------------------------------------------------
W_NAME, W_TITLES, W_HOME, W_META, W_LEX, LEX_CAP = 1.6, 0.6, 1.4, 1.0, 5.0, 3
TITLE_MASS = 10.0
MIN_CONFIDENCE = 0.9    # rules model: below this the industry is Not stated (chosen on a held-out sample, see README)


def features(name: str, title_words: dict[str, float] | None, home: str = "", domain: str = "", meta: dict[str, float] | None = None) -> dict[str, dict[str, float]]:
    """meta: how the company's rows are spread over ATS and countries, as shares ('a:ashby': 0.9, 'cc:PT': 0.4)."""
    nm = words(name)
    dm = re.split(r"[.-]", (domain or "").split(".")[0]) if domain else []
    g = {"n": {}, "t": {}, "h": {}, "x": dict(meta or {})}
    for w in nm + [d for d in dm if len(d) >= 4]:
        g["n"][w] = g["n"].get(w, 0) + 1
        # a long run-together name (healthpartners, microsoft) is matched by the keywords it contains
    flat = re.sub(r"[^a-z0-9]", "", fold(name + " " + (domain or "").split(".")[0]))
    for w in _lex_substrings(flat):
        g["n"][w] = g["n"].get(w, 0) + 1
    if title_words:
        top = sorted(title_words.items(), key=lambda kv: -kv[1])[:40]
        tot = sum(v for _, v in top) or 1.0
        for w, v in top:
            g["t"][w] = TITLE_MASS * v / tot
    for w in words(home):
        if w not in JOBWORDS:
            g["h"][w] = g["h"].get(w, 0) + 1
    g["l"] = _lex_hits(fold(name) + " . " + fold(home), flat)
    return g


def _lex_hits(text: str, flat: str) -> dict[str, float]:
    """How many distinct lexicon keywords of each industry the name and homepage text contain (the strongest, plainest evidence)."""
    lex = _load("lexicon.json")
    padded = " " + re.sub(r"[^a-z0-9]+", " ", text) + " "
    out: dict[str, float] = {}
    for code, kws in lex.items():
        n = 0
        for kw in kws:
            k = re.sub(r"[^a-z0-9]+", " ", fold(kw)).strip()
            if len(k) < 3:
                continue
            if (" " + k + " ") in padded or (len(k) >= 6 and k.replace(" ", "") in flat):
                n += 1
        if n:
            out[code] = float(min(n, LEX_CAP))
    return out


def _lex_substrings(flat: str) -> list[str]:
    """Keywords from the lexicon that appear inside a run-together name ('healthpartners' -> health)."""
    vocab = _load("model.json").get("name_substrings") or []
    return [w for w in vocab if len(w) >= 5 and w in flat and w != flat]


def scores(feat: dict[str, dict[str, float]]) -> dict[str, float]:
    m = _load("model.json")
    if not m:
        return {}
    classes = m["classes"]
    out = {c: math.log(m["prior"][c]) for c in classes}
    known = 0.0
    for gname, w in (("n", W_NAME), ("t", W_TITLES), ("h", W_HOME), ("x", W_META)):
        tab = m["groups"].get(gname)
        if not tab:
            continue
        if gname == "x":                      # where the postings live says little on its own: it never counts as evidence by itself
            tab = tab
        tot, V, alpha = tab["total"], tab["vocab"], m["alpha"]
        for f, v in feat[gname].items():
            row = tab["f"].get(f)
            if not row:
                continue
            if gname != "x":
                known += v
            for c in classes:
                out[c] += w * v * math.log((row.get(c, 0.0) + alpha) / (tot[c] + alpha * V))
    for c, n in (feat.get("l") or {}).items():
        if c in out:
            out[c] += W_LEX * n
            known += n
    out["_known"] = known
    return out


def classify_features(feat) -> tuple[str, float]:
    s = scores(feat)
    if not s or s.get("_known", 0) <= 0:
        return NOT_STATED, 0.0
    known = s.pop("_known")
    mx = max(s.values())
    z = sum(math.exp((v - mx) / max(1.0, known ** 0.5 * 0.9)) for v in s.values())
    best = max(s, key=s.get)
    conf = 1.0 / z
    if conf < MIN_CONFIDENCE:
        return NOT_STATED, conf
    return best, conf


def classify(name: str, title_words=None, home: str = "", domain: str = "", meta=None) -> tuple[str, float]:
    """(industry code, confidence) for one company from name, domain, homepage text and job-title mix."""
    ov = _load("overrides.json") if USE_OVERRIDES else {}
    k = norm(name)
    if k in ov:
        return ov[k], 1.0
    return classify_features(features(name, title_words, home, domain, meta))


# -- a source's own industry tag --------------------------------------------------------------------------------------
_NATIVE = [("health|hospital|medical|care", "hlt"), ("pharma|biotech|life ?science", "bio"), ("financ|banking|insurance|fintech", "fin"),
           ("software|saas|internet|information technology|it services", "sw"), ("artificial|machine learning", "sw"), ("cyber|security", "sec"),
           ("retail|e-?commerce", "ret"), ("consumer goods|cpg", "cpg"), ("education|e-?learning", "edu"), ("manufactur|industrial", "mfg"),
           ("energy|utilities|oil|renewable", "ene"), ("logistics|transport|shipping", "log"), ("automotive", "aut"),
           ("media|marketing|advertising|entertainment", "med"), ("gaming|games", "gam"), ("telecom", "tel"), ("consulting|legal|accounting", "pro"),
           ("staffing|recruit", "hr"), ("hospitality|travel|restaurant|tourism", "hos"), ("real estate|construction", "re"),
           ("agricultur|food", "cpg"), ("aerospace|defen[cs]e", "aer"), ("government|non-?profit|public sector", "pub"),
           ("semiconductor|hardware|electronics", "hw")]


def from_native(tag) -> str:
    """An industry code from a source's own industry label, or ''. Job categories ('Marketing & Sales') are not industries and are ignored by callers."""
    if not tag:
        return ""
    for t in (tag if isinstance(tag, (list, tuple)) else [tag]):
        s = fold(str(t))
        for rx, code in _NATIVE:
            if re.search(rx, s):
                return code
    return ""


# -- homepages ---------------------------------------------------------------------------------------------------------
HOME_TTL_DAYS = 180
FAIL_TTL_DAYS = 30
META = re.compile(r'<meta\s+[^>]*?(?:name|property)=["\'](description|og:description|og:site_name|og:title)["\'][^>]*?content=["\']([^"\']*)["\']', re.I | re.S)
META2 = re.compile(r'<meta\s+[^>]*?content=["\']([^"\']*)["\'][^>]*?(?:name|property)=["\'](description|og:description|og:site_name|og:title)["\']', re.I | re.S)
JOBWORDS = set("vacature vacatures jobs job careers career stellen stelle bewerb bewirb bewerben vagas vaga carreiras carreira werken werkenbij homepagina homepage empleo empleos ofertas trabajo trabajos recrutement offres emploi rekrytering lediga jobb jobba ledige tyopaikat avoimet hakemus apply hiring openings positions".split())
JUNK = re.compile(r"(?i)\b(for sale|buy (this|premium)? ?domain|domain (name )?(is )?for sale|just another wordpress|coming soon|parked|godaddy|porn|xxx|sex videos|casino bonus|account suspended|default web site)\b")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def parse_home(html: str) -> dict:
    import html as H
    t = TITLE.search(html or "")
    meta = {}
    for k, v in META.findall(html or ""):
        meta.setdefault(k.lower(), v)
    for v, k in META2.findall(html or ""):
        meta.setdefault(k.lower(), v)
    clean = lambda s: re.sub(r"\s+", " ", H.unescape(s or "")).strip()
    return {"t": clean(t.group(1))[:200] if t else "", "s": clean(meta.get("og:site_name"))[:80],
            "m": clean(meta.get("description") or meta.get("og:description"))[:400]}


def home_text(entry: dict | None) -> str:
    return " ".join((entry or {}).get(k, "") for k in ("t", "s", "m"))


class Homepages:
    """A small cache of company homepages, loaded from and saved to data/industry/homepages.json.gz.

    `client` is the shared polite client (honest User-Agent, robots.txt, per-host pacing, blocked hosts skipped), or None to
    read the cache only. At most `budget` new companies are fetched per run."""

    def __init__(self, path: Path | None = None, client=None, budget: int = 3000, log=print):
        self.path = Path(path) if path else DATA / "homepages.json.gz"
        self.client, self.budget, self.log = client, budget, log
        self.data: dict[str, dict] = {}
        self.fetched = 0
        self.lock = threading.Lock()
        if self.path.exists():
            with gzip.open(self.path, "rt", encoding="utf-8") as fh:
                self.data = json.load(fh)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.path, "wt", encoding="utf-8") as fh:
            json.dump(self.data, fh, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

    def get(self, key: str) -> dict | None:
        e = self.data.get(key)
        return e if e and e.get("t") is not None and (e.get("t") or e.get("m")) else None

    def stale(self, key: str, today: float | None = None) -> bool:
        e = self.data.get(key)
        if not e:
            return True
        age = ((today or time.time()) - e.get("ts", 0)) / 86400
        return age > (HOME_TTL_DAYS if (e.get("t") or e.get("m")) else FAIL_TTL_DAYS)

    def candidates(self, name: str, domain: str) -> list[str]:
        if domain:
            return [f"https://www.{domain}/", f"https://{domain}/"]
        slug = re.sub(r"[^a-z0-9]", "", fold(re.sub(r"\b(inc|llc|ltd|gmbh|corp|corporation|co|sa|ag|plc|group|holdings?)\b", " ", fold(name))))
        if len(slug) < 4:
            return []
        tlds = [".com", ".io", ".ai", ".co"]
        if slug.endswith("ai") and len(slug) > 4:
            tlds = [".ai", ".com", ".io", ".co"]
        return [f"https://{slug}{t}/" for t in tlds]

    def fetch(self, key: str, name: str, domain: str) -> dict:
        """Fetch one homepage. The page is kept only if it plausibly belongs to the company; otherwise the failure is cached."""
        entry = {"d": domain, "t": "", "s": "", "m": "", "ts": int(time.time())}
        if self.client is None:
            return entry
        want = set(words(name, 4)) or set(re.findall(r"[a-z]{4,}", fold(name)))
        for url in self.candidates(name, domain):
            r = self.client.get(url)
            if getattr(r, "status", 0) != 200:
                continue
            info = parse_home(r.text[:200000])
            if JUNK.search(" ".join(info.values())):
                continue                                   # parked domain, domain for sale, an unrelated site
            blob = fold(" ".join(info.values()) + " " + (urlsplit(getattr(r, "url", url) or url).hostname or ""))
            flat = re.sub(r"[^a-z0-9]", "", blob)
            ok = bool(domain) or any(w in blob or w in flat for w in want) or (len(re.sub(r"[^a-z0-9]", "", fold(name))) >= 5 and re.sub(r"[^a-z0-9]", "", fold(name)) in flat)
            if info["t"] or info["m"]:
                if ok:
                    entry.update(info)
                    entry["d"] = domain or (urlsplit(getattr(r, "url", url) or url).hostname or "").replace("www.", "")
                    return entry
        return entry

    def ensure(self, key: str, name: str, domain: str) -> dict | None:
        with self.lock:
            if not self.stale(key):
                return self.get(key)
            if self.client is None or self.fetched >= self.budget:
                return self.get(key)
            self.fetched += 1
        e = self.fetch(key, name, domain)
        with self.lock:
            self.data[key] = e
        return self.get(key)


# -- tagging rows --------------------------------------------------------------------------------------------------------
IN = 13        # position of the industry code in a row: after t c l cc r u p a smin smax cur lv ls


def group_rows(rows: list[list]) -> dict[str, dict]:
    """Rows of one company together: name, row count, title words, a few titles, urls, ATS and country mix."""
    groups: dict[str, dict] = {}
    for r in rows:
        k = group_key(r[1], r[5])
        g = groups.get(k)
        if g is None:
            g = groups[k] = {"name": r[1], "rows": 0, "words": {}, "urls": [], "tenant": tenant_id(r[5]), "ats": {}, "cc": {}, "titles": []}
        g["rows"] += 1
        g["ats"][r[7]] = g["ats"].get(r[7], 0) + 1
        g["cc"][r[3]] = g["cc"].get(r[3], 0) + 1
        if len(g["urls"]) < 12:
            g["urls"].append(r[5])
        if len(g["titles"]) < 10 and r[0] not in g["titles"]:
            g["titles"].append(r[0])
        if g["rows"] <= 60 or g["rows"] % 20 == 0:
            for w in words(r[0]):
                g["words"][w] = g["words"].get(w, 0) + 1
    return groups


def hand_label(key: str) -> str | None:
    """A company a reader labelled by hand always keeps that label."""
    return _load("overrides.json").get(key[2:]) if key.startswith("c:") and USE_OVERRIDES else None


def assign(rows: list[list], homepages: Homepages | None = None, threads: int = 12, log=print, ai=None, ai_client=None, ai_cap: int | None = None) -> dict:
    """Give every row an industry code (row[IN]). A company is labelled once and the label is copied to its rows.
    A company seen for the first time gets its homepage fetched and cached in this run (within the budget and the polite client's
    pacing); if the fetch fails, the name, domain and title signals decide. Rows that already carry a code from their source keep it."""
    groups = group_rows(rows)
    homepages = homepages or Homepages(client=None)
    todo = [(k, g) for k, g in groups.items() if k.startswith("c:") and homepages.stale(k)]
    todo.sort(key=lambda kg: -kg[1]["rows"])               # the biggest employers first, in case the budget runs out
    if homepages.client is not None and todo:
        from concurrent.futures import ThreadPoolExecutor
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=threads) as ex:
            list(ex.map(lambda kg: homepages.ensure(kg[0], kg[1]["name"], own_domain(kg[1]["urls"])), todo))
        log(f"industry: {homepages.fetched} homepages fetched for {len(todo)} companies without a fresh one, {int(time.time() - t0)}s")
        homepages.save()
    from . import ailabel
    ai = ai if ai is not None else ailabel.AiLabels()
    keys: dict[str, str] = {}
    units = []
    for k, g in groups.items():
        entry = homepages.get(k) if k.startswith("c:") else None
        g["entry"] = entry
        g["domain"] = own_domain(g["urls"]) or (entry or {}).get("d", "")
        keys[k] = ailabel.unit_key(k, g["domain"])
        if hand_label(k) is None and ai.get(keys[k]) is None and ai.get(k) is None:
            units.append({"key": keys[k], "rows": g["rows"], "text": ailabel.user_text(g["name"], g["domain"], entry, g["titles"])})
    if units and ai_cap != 0:
        ailabel.label_new(ai, units, cap=ai_cap if ai_cap is not None else ailabel.NIGHTLY_CAP, log=log, client=ai_client)
    label: dict[str, str] = {}
    source = {"hand": 0, "ai": 0, "rules": 0}
    for k, g in groups.items():
        code = hand_label(k)
        src = "hand"
        if code is None:
            got = ai.get(keys[k]) or ai.get(k)
            if got and got[1] >= ailabel.MIN_CONFIDENCE:
                code, src = got[0], "ai"
        if code is None:
            code, src = classify(g["name"], g["words"], home_text(g["entry"]), g["domain"], row_meta(g["ats"], g["cc"]))[0], "rules"
        label[k] = code
        source[src] += g["rows"]
    tagged = 0
    for r in rows:
        if len(r) <= IN:
            r.extend([""] * (IN + 1 - len(r)))
        if not r[IN]:
            r[IN] = label[group_key(r[1], r[5])]
        tagged += r[IN] not in ("", OTHER, NOT_STATED)
    stats = {"companies": len(groups), "rows": len(rows), "tagged": tagged, "other": len(rows) - tagged, "rows_by_source": source}
    log(f"industry: {stats}")
    return stats
