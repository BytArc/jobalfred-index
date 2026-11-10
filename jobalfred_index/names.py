"""Company names from what employers publish, never from a bare tenant code.

Order of preference, one or two requests per tenant, cached in the tenant record (data.name) so a daily run does not repeat them:
  1. the career site's own page title, og:site_name or og:title
  2. the hiring organisation the posting itself names (Workday posting JSON, JSON-LD)
  3. the employer's own domain, when the posting lives on it (careers.example.com gives Example)
  4. the tenant slug, only when it reads like a name (no platform or HR-code tokens)
  5. "Undisclosed employer"
"""
from __future__ import annotations

import html
import re
from urllib.parse import quote, urlsplit

UNDISCLOSED = "Undisclosed employer"

# words that describe the page, not the employer
_PAGE = (r"careers?|career\s*(?:site|page|portal|opportunities)|jobs?|job\s*(?:board|search|openings|portal)|openings?|"
         r"vacanc(?:y|ies)|recruit(?:ing|ment)|talent\s*acquisition|candidate\s*experience(?:\s*page)?|external|"
         r"opportunit(?:y|ies)|portal|hiring|work\s*with\s*us|join\s*(?:us|our\s*team)|home\w*|welcome\w*|"
         r"current\s*openings|talent\s*acquisition(?:\s*team)?|recruit(?:ing|ment)\s*team|hiring\s*team|apply|search|site|section|page|external\s*career\s*site|global|worldwide|en-us|us|usa")
_LEAD = re.compile(rf"^\s*(?:{_PAGE})\s*(?:at|with|@|[-|:–—]|\bl\b)\s*|^\s*(?:jobs?|careers?)\s+(?!(?:for|of|the|in|and|to|at)\b)(?=\S{{3}})", re.I)
_TAIL = re.compile(rf"\s*(?:[-|:–—,]\s*)?\b(?:{_PAGE})\b(?:\s+(?:{_PAGE})\b)*\s*$", re.I)
_LEGAL = re.compile(r"[,\s]+(?:inc\.?|incorporated|llc|l\.l\.c\.?|ltd\.?|limited|plc|gmbh|ag|s\.?a\.?|b\.?v\.?|n\.?v\.?|corp\.?|corporation|"
                    r"co\.?|p\.?c\.?|l\.?p\.?|llp|pty|pte|s\.?r\.?l\.?|oy|ab|a/s|as|kg|se)\.?$", re.I)
# a slogan on the career page, not the employer
_TAGLINE = re.compile(r"\b(join|energize|confidence|every turn|today|your|you|we are|make|build your|discover|explore|find your|start your|"
                      r"start|grow|shape|imagine|inspire|empower|anywhere|team!)\b", re.I)
GENERIC = {"", "careers", "jobs", "career", "job search", "homepage", "home", "welcome", "login", "sign in", "page not found",
           "not found", "error", "404", "loading", "untitled", "candidate experience", "external", "bamboohr", "workday", "oracle",
           "teamtailor", "lever", "ashby", "greenhouse", "recruitee", "breezy", "workable", "icims", "the new main layout (career page)",
           # words a career site uses for the visitor, not for the employer
           "student", "students", "traveler", "traveller", "candidate", "candidates", "employee", "employees", "applicant",
           "applicants", "intern", "interns", "internship", "staff", "team", "general", "our", "user", "guest", "member", "members",
           "hello", "main", "default", "new", "test", "company", "organization", "organisation", "employer", "recruiting", "hiring",
           "join", "apply", "search", "job", "open positions", "open roles", "career opportunities", "work with us", "professional",
           "professionals", "experienced professionals", "veterans", "graduates", "talent", "vision", "anywhere",
           "early", "offers", "benelux", "employment channel", "espace recrutement", "espace candidat", "recrutement", "candidature",
           "offres d emploi", "empleo", "vagas", "trabalhe conosco", "board & commission member", "experienced hire", "campus", "university", "emea", "apac", "latam"}
# tokens that mark a platform pod name or an internal HR code, not an employer
_NOISE = re.compile(r"(saas|faprod|prod\d*|preprod|\bwd\d+\b|^wd\d+$|\bfa\b|\bhcm\b|\bext\d*\b|\bocs\b|\bcx\d*\b|\brec\b|\bats\b|^cdn|"
                    r"\bhr\b|\bhris\b|\bnoreply\b|\bem\d\b|\bus\d\b|\bsite\d*\b|[0-9]{3,})", re.I)

ATS_HOSTS = ("myworkdayjobs.com", "oraclecloud.com", "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "recruitee.com",
             "bamboohr.com", "breezy.hr", "teamtailor.com", "icims.com", "smartrecruiters.com", "applytojob.com", "gupy.io",
             "comeet.com", "comeet.co", "rippling.com", "personio.de", "personio.com", "pinpointhq.com", "jobs2web.com",
             "successfactors.com", "successfactors.eu", "taleo.net", "jobvite.com", "linkedin.com", "indeed.com", "join.com")
_SLD2 = {"co.uk", "com.br", "com.au", "co.in", "co.jp", "com.mx", "co.za", "com.sg", "com.tr", "com.ar", "com.co", "co.nz", "org.uk"}


def clean_company(raw: str | None) -> str:
    """A company name from a page title or similar, or '' when it is not one."""
    if not raw:
        return ""
    s = html.unescape(str(raw))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" \t\r\n-|:–—,.")
    m = re.match(r"(?i)^join\s+(?:the\s+)?(.+?)\s+(?:team|family)\s*[!.]*$", s) or re.match(r"(?i)^welcome\s+to\s+(?:the\s+)?([^!?]{2,40})$", s)
    if m and not re.search(r"(?i)\b(career|careers|portal|site|page)\b", m.group(1)):
        s = m.group(1)
    s = re.sub(r"^\((?:USA|US|UK|CA|EU)\)\s+", "", s)                          # "(USA) CoolIT" -> "CoolIT"
    s = re.sub(r"^(?:\d{1,3}|[A-Z]{1,3}\d{1,3})\s+(?=[A-Za-z])", "", s)        # "02 CACI", "LE21 Patheon", "UM04 University"
    s = re.sub(r"^(?:[A-Z]{2,4}\s+){1,2}(?=[A-Z][a-z]{3,})", "", s) if re.match(r"^(?:[A-Z]{2,4}\s+){2}[A-Z][a-z]{3,}", s) else s
    for _ in range(3):
        s2 = _LEAD.sub("", s).strip()
        s2 = _TAIL.sub("", s2).strip(" -|:–—,.")
        if s2 == s:
            break
        s = s2
    s = _LEGAL.sub("", s).strip(" ,.")
    if s.lower() in GENERIC or len(s) < 2 or len(s) > 60:
        return ""
    if _TAGLINE.search(s) or re.search(r"/\d*$|/[A-Z]{1,3}$", s):
        return ""
    if (s.isupper() and len(s.split()) >= 5) or re.search(r"\.\s+[A-Z][a-z]+\.", s) or re.search(r"(?i)\bat work$", s):
        return ""                                       # a slogan
    if s.endswith(("!", "?")) or re.search(r"(?i)\b(career|careers|portal|openings|vacancies|job\s*board)\b", s):
        return ""                                       # a phrase about the career site, not an employer
    if _NOISE.search(s) or "{{" in s or "http" in s.lower():
        return ""
    return s


def looks_like_name(s: str) -> bool:
    """A name an employer published about itself (page title, posting). Short names such as NMC or JPMC are fine."""
    if not s or s == UNDISCLOSED or _NOISE.search(s):
        return False
    return len(re.sub(r"[^A-Za-z]", "", s)) >= 2


def slug_reads_like_name(s: str) -> bool:
    """Stricter, for names guessed from a tenant slug: no platform tokens, no HR codes, no 3-4 letter codes."""
    if not looks_like_name(s):
        return False
    words = s.split()
    letters = re.sub(r"[^A-Za-z]", "", s)
    if len(letters) < 5 or all(len(w) <= 3 for w in words):
        return False
    if re.search(r"hr$", letters, re.I) or not re.search(r"[aeiouyAEIOUY]", letters):
        return False
    if len(words) == 1 and len(letters) <= 5 and not re.search(r"[aeiouy][^aeiouy][aeiouy]|[aeiouy]{2}", letters, re.I):
        return False
    return True


def domain_name(urls) -> str:
    """Employer name from its own domain: the most common non-ATS host among the posting URLs."""
    counts: dict[str, int] = {}
    for u in urls:
        host = (urlsplit(u).hostname or "").lower()
        if not host or any(host == h or host.endswith("." + h) for h in ATS_HOSTS):
            continue
        parts = host.split(".")
        keep = 3 if ".".join(parts[-2:]) in _SLD2 else 2
        label = parts[-keep] if len(parts) >= keep else parts[0]
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return ""
    label = max(counts.items(), key=lambda kv: kv[1])[0]
    label = re.sub(r"[-_]+", " ", label)
    return label.title() if slug_reads_like_name(label.title()) else ""


def slug_name(slug: str) -> str:
    """The tenant slug as a name, only if it reads like one."""
    s = re.sub(r"[-_.]+", " ", slug or "").strip()
    cand = " ".join(w for w in s.split() if not _NOISE.search(w))
    cand = cand.title() if cand.islower() else cand
    return cand if slug_reads_like_name(cand) else ""


def best(page_title: str = "", org: str = "", urls=(), slug: str = "") -> str:
    for c in (clean_company(page_title), clean_company(org)):
        if c and looks_like_name(c):
            return c
    return domain_name(urls) or slug_name(slug) or UNDISCLOSED


# -- network lookups (one or two requests per tenant) ------------------------
def _meta(page: str) -> str:
    for rx in (r'property="og:site_name"\s+content="([^"]*)"', r'content="([^"]*)"\s+property="og:site_name"',
               r'property="og:title"\s+content="([^"]*)"', r'content="([^"]*)"\s+property="og:title"', r"<title[^>]*>([^<]*)<"):
        m = re.search(rx, page, re.I)
        if m:
            c = clean_company(m.group(1))
            if c and looks_like_name(c):
                return c
    return ""


def lookup(client, ats: str, tenant: dict) -> str:
    """Ask the employer's own site for its name. Returns '' when nothing usable is published."""
    key = tenant["key"]
    try:
        if ats == "workday":
            t, wd, site = tenant["tenant"], tenant["wd"], tenant["site"]
            base = f"https://{t}.{wd}.myworkdayjobs.com"
            r = client.get(f"{base}/en-US/{quote(site)}")
            name = _meta(r.text) if r.status == 200 else ""
            if name:
                return name
            j = client.post(f"{base}/wday/cxs/{t}/{site}/jobs", json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
                            headers={"Accept": "application/json", "Content-Type": "application/json"})
            path = ((j.json() or {}).get("jobPostings") or [{}])[0].get("externalPath") if j.status == 200 else None
            if path:
                d = client.get(f"{base}/wday/cxs/{t}/{site}{path}")
                org = ((d.json() or {}).get("hiringOrganization") or {}).get("name") if d.status == 200 else ""
                c = clean_company(org)
                return c if c and looks_like_name(c) else ""
        elif ats == "oracle":
            r = client.get(f"https://{tenant['host']}/hcmUI/CandidateExperience/en/sites/{tenant['site']}")
            return _meta(r.text) if r.status == 200 else ""
        elif ats == "lever":
            r = client.get(f"https://jobs.lever.co/{key}")
            return _meta(r.text) if r.status == 200 else ""
        elif ats == "lever-eu":
            r = client.get(f"https://jobs.eu.lever.co/{key}")
            return _meta(r.text) if r.status == 200 else ""
        elif ats == "ashby":
            r = client.get(f"https://jobs.ashbyhq.com/{key}")
            return _meta(r.text) if r.status == 200 else ""
        elif ats == "bamboohr":
            r = client.get(f"https://{key}.bamboohr.com/careers")
            m = re.search(r'og:site_name"\s+content="([^"]*)"', r.text) if r.status == 200 else None
            c = clean_company(m.group(1)) if m else ""
            return c if c and looks_like_name(c) else ""
    except Exception:
        return ""
    return ""


NEEDS_LOOKUP = {"workday", "oracle", "lever", "lever-eu", "ashby", "bamboohr"}
# sources whose API gives no company name: the row company is always the resolved tenant name
NAME_FROM_PAGE = NEEDS_LOOKUP | {"jazzhr", "comeet", "rippling", "pinpoint", "personio"}


def resolve(client, ats: str, tenant: dict, urls=()) -> str:
    """Name for a tenant: the cached one, else a lookup, else the fallbacks. The result is stored in tenant['name']."""
    slug0 = tenant.get("tenant") or tenant["key"].split("|")[0].split(".")[0]
    cached = clean_company(tenant.get("name"))
    if cached and looks_like_name(cached) and (slug_reads_like_name(cached) or not _is_slug_of(cached, tenant)):
        cached = polish(cached, slug0, urls)
        tenant["name"] = cached
        return cached
    got = lookup(client, ats, tenant) if ats in NEEDS_LOOKUP else ""
    slug = tenant.get("tenant") or tenant["key"].split("|")[0].split(".")[0]
    name = polish(got, slug, urls) if got else best(urls=urls, slug=slug if ats not in ("oracle",) else "")
    tenant["name"] = name
    return name


def _is_slug_of(name: str, tenant: dict) -> bool:
    """True when a stored name is just the tenant slug title-cased, i.e. a guess, not something the employer published."""
    flat = re.sub(r"[^a-z0-9]", "", name.lower())
    slug = re.sub(r"[^a-z0-9]", "", (tenant.get("tenant") or tenant["key"].split("|")[0].split(".")[0]).lower())
    return flat == slug or flat == re.sub(r"[^a-z0-9]", "", tenant["key"].lower())


# -- legal entities and branch labels -> the employer's own brand --------------------------------------------------
def _folded_countries() -> set[str]:
    from .geo import NAME2CC, fold
    words = {fold(k) for k in NAME2CC if len(k) >= 4}
    words |= {"uk", "u.k", "usa", "us", "u.s", "uae", "eu", "korea", "britain", "united kingdom", "united states"}
    # country names as employers write them in other languages
    words |= {"tunisie", "maroc", "algerie", "allemagne", "espagne", "italie", "suisse", "belgique", "brasil", "polska", "norge",
              "osterreich", "magyarorszag", "hrvatska", "ceska", "slovensko", "turquie", "pays-bas", "royaume-uni", "etats-unis", "mexique"}
    return words


_REGIONS = {"europe", "emea", "apac", "latam", "international", "asia pacific", "north america", "middle east", "africa", "asia", "mena"}
_COUNTRIES = _folded_countries()
_LEGAL_TOK = (r"inc|incorporated|llc|l\.l\.c|ltd|limited|plc|gmbh|ag|sa|s\.a|s\.a\.s|sas|sarl|srl|s\.r\.l|spa|s\.p\.a|bv|b\.v|nv|n\.v|"
              r"ab|as|a/s|aps|oy|oyj|kg|kft|pty|pvt|pte|co|corp|corporation|lda|ltda|sdn|bhd|p\.c|pc|llp|lp|cv|se|sl|s\.l|slu|kk|k\.k|"
              r"eireli|ulc|pllc|ou|zrt|s\.l\.u|sp\.?\s*z\s*o\.?\s*o\.?|z\s*o\.?\s*o\.?|private|pty\.?\s*ltd|pvt\.?\s*ltd")
_TRAIL_LEGAL = re.compile(rf"[\s,.-]+(?:{_LEGAL_TOK})\.?\s*$", re.I)
_BRANCH = re.compile(r"(?i)^.*?\b(?:branch|representative|regional|liaison|head)\s+office\s+(?:of|for)\s+|^.*?\bsubsidiary\s+of\s+")
_PAREN = re.compile(r"\s*\(([^)]{1,30})\)")
_REMOVABLE = re.compile(rf"(?i)^(?:{_LEGAL_TOK}|branch|office|of|the|and|representative|regional|\d+|[a-z]\.?)$")


_COUNTRIES_DOTLESS = {x.replace(".", "") for x in _COUNTRIES}


def _is_geo_word(w: str) -> bool:
    from .geo import fold
    f = fold(w).strip(".:,()")
    return f in _COUNTRIES or f in _REGIONS or f.replace(".", "") in _COUNTRIES_DOTLESS


def _letters(s: str) -> int:
    return len(re.sub(r"[^A-Za-z]", "", s))


def strip_entity(c: str) -> str:
    """Remove branch prefixes, country words and legal suffixes from a legal-entity string."""
    from .geo import fold
    s = c
    s = re.sub(r"^\s*([A-Za-z .]{2,25}):\s+", lambda m: "" if _is_geo_word(m.group(1)) else m.group(0), s)   # "Spain: Spain Branch ..."
    s = re.sub(r"^\s*(?:UK|US|USA|EU|UAE|U\.K\.?|U\.S\.A?\.?)\s*[|:/]\s*", "", s)             # "UK | FNZ Global Management"
    s = _BRANCH.sub("", s)
    s = re.sub(r"^\s*(?:united states|united kingdom|usa|u\.s\.a?|uk|u\.k)\s+\d+\s+", "", s, flags=re.I)  # "United States 1 AB Car ..."
    for m in list(_PAREN.finditer(s)):
        inner = m.group(1).strip()
        if _is_geo_word(inner) or re.fullmatch(rf"(?i){_LEGAL_TOK}", inner):
            s = s.replace(m.group(0), "")
    for _ in range(4):                                   # legal suffixes and trailing country words, repeatedly
        before = s
        s = _TRAIL_LEGAL.sub("", s).strip(" ,.-")
        words = s.split()
        if len(words) >= 2:
            last2 = " ".join(words[-2:]) if len(words) >= 3 else ""
            for tail in (last2, words[-1]):
                if tail and _is_geo_word(tail):
                    rest = s[: len(s) - len(tail)].rstrip(" ,-.")
                    if (_letters(rest) >= 4 or (rest.isupper() and _letters(rest) >= 3)) and rest.split()[-1].lower() not in ("of", "de", "do", "da", "du", "der", "the", "and", "for", "la", "le", "el", "in"):
                        s = rest
                        break
        if s == before:
            break
    return s.strip(" ,.-")


def slug_span(c: str, slug: str) -> str:
    """The run of words in c that spells the tenant slug (the employer's own brand), when everything else is a
    country, legal or branch word. 'US Innovex' with slug 'innovex' gives 'Innovex'."""
    flat = re.sub(r"[^a-z0-9]", "", (slug or "").lower())
    if len(flat) < 3:
        return ""
    words = [w for w in re.split(r"[\s/]+", c) if w]
    parts = []
    for w in words:
        parts.extend(x for x in w.split("-") if x)
    for i in range(len(parts)):
        acc = ""
        for j in range(i, len(parts)):
            acc += re.sub(r"[^a-z0-9]", "", parts[j].lower())
            if acc == flat:
                outside = parts[:i] + parts[j + 1:]
                if (i, j) != (0, len(parts) - 1) and all(
                        _is_geo_word(o) or _REMOVABLE.match(o.strip(".,()")) or o.strip(".,()").isdigit()
                        or (o.isupper() and len(o) <= 3) or o.strip(".,:()").lower() in ("branch", "office", "of") for o in outside):
                    return " ".join(parts[i:j + 1])
                break
            if len(acc) > len(flat):
                break
    return ""


def _fallback(slug: str, urls) -> str:
    return domain_name(urls) or slug_name(slug) or UNDISCLOSED


def polish(company: str, slug: str = "", urls=(), allow_domain: bool = True) -> str:
    """The employer's brand from whatever name string we hold: strips legal suffixes, country words and branch labels,
    prefers the brand spelled by the tenant slug, drops generic words. 'Undisclosed employer' when nothing real is left."""
    if company == UNDISCLOSED:
        return company
    use_urls = urls if allow_domain else ()
    c = clean_company(company)
    if not c or c.lower() in GENERIC:
        return _fallback(slug, use_urls)
    span = slug_span(c, slug)
    if span and _letters(span) >= 4:
        return span
    flat_slug = re.sub(r"[^a-z0-9]", "", (slug or "").lower())
    if flat_slug and flat_slug not in re.sub(r"[^a-z0-9]", "", c.lower()):
        m = re.match(r"^(?:UK|US|USA|EU|UAE)\s+(\S.*)$", c)      # "US Innovex" inside the IQVIA tenant: a legal entity, not a brand
        if m and _letters(m.group(1)) >= 4:
            c = m.group(1)
    e = strip_entity(c)
    if e != c:
        if (_letters(e) >= 4 or (e.isupper() and _letters(e) >= 3)) and e.lower() not in GENERIC and not _NOISE.search(e):
            return e
        return _fallback(slug, use_urls)
    if re.match(r"^(?:UK|US|USA|EU|UAE)\s+\S{1,3}$", c):      # "UK WIP": a country label plus a code
        return _fallback(slug, use_urls)
    return c
