"""Where a company is headquartered, read from its own website. Plain rules: no AI, no paid data, no third-party sites.

Pages read (robots.txt obeyed by the client): the homepage, then up to three of the company's own pages whose link says
contact, about, company, imprint/impressum, legal notice, privacy or terms (privacy policies and legal notices usually
name the company and its address). Evidence, strongest first:
  1. schema.org markup (JSON-LD) for an organisation: its address's country, else its region or town
  2. a sentence naming the headquarters: "headquartered in Austin", "HQ: London", "Registered office: ...", "Sitz: Berlin"
  3. a postal address: "San Francisco, CA 94105", "London EC2A 4NE", "10115 Berlin", "75011 Paris"
  4. "based in X" said of the company ("We are a team based in Lisbon")
The first level that points to one country decides; a level whose evidence names several countries about equally
(offices on several continents) does not, and the next level is tried. Every answer keeps its page and the text.
"""
from __future__ import annotations

import html as htmllib
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlsplit

from . import geo
from .startups import registrable

MAX_PAGE = 1_500_000
MORE_PAGES = 3
_LINK_WORDS = re.compile(r"(?i)\b(contact|contact us|about|about us|company|our company|who we are|imprint|impressum|"
                         r"legal notice|legal|mentions l[ée]gales|aviso legal|privacy|privacy policy|terms|offices?|locations?)\b")
_LINK_PATH = re.compile(r"(?i)/(contact|contact-us|about|about-us|company|imprint|impressum|legal|legal-notice|"
                        r"mentions-legales|aviso-legal|privacy|privacy-policy|terms|offices|locations)(/|$|\.html?)")
_PRIORITY = ["contact", "imprint", "impressum", "legal", "mentions", "aviso", "about", "company", "office", "location",
             "privacy", "terms"]
_ANCHOR = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"'#]+)[\"'][^>]*>(.{0,300}?)</a>", re.I | re.S)
_LDJSON = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.I | re.S)
_DROP = re.compile(r"<(script|style|noscript|svg|template)\b.*?</\1>", re.I | re.S)
_BLOCK = re.compile(r"<(?:br|/p|/div|/li|/h[1-6]|/tr|/td|/address|/footer|/section|/span)\b[^>]*>", re.I)

_HQ_WORD = (r"(?:headquartered|head-quartered|hq'?d)\s+(?:in|at)|(?:global |corporate |company |our )?(?:headquarters|"
            r"head office|main office|registered office|registered address|corporate office|hq)\s*(?:is |are )?"
            r"(?:in|at|:|–|-|located in)|sitz(?:\s+der\s+gesellschaft)?\s*:|si[èe]ge social\s*:?|sede (?:social|legal)\s*:?")
_HQ = re.compile(rf"(?i)\b(?:{_HQ_WORD})\s*(?P<p>[^\n.;|]{{2,140}})")
_US_ADDR = re.compile(r"\b(?P<p>[A-Z][A-Za-z.'\- ]{1,30},\s*(?:" + "|".join(sorted(geo.US_STATES)) +
                      r")\.?\s+\d{5}(?:-\d{4})?)\b")
_UK_ADDR = re.compile(r"\b(?P<p>(?:London|Manchester|Edinburgh|Cambridge|Oxford|Bristol|Leeds|Glasgow|Birmingham|"
                      r"Belfast|Cardiff|Brighton)\b[ ,]{1,3}[A-Z]{1,2}\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2})\b")
_EU_ADDR = re.compile(r"(?<![\d./©-])(?<!© )\b(?P<p>\d{4,5}\s+(?P<city>[A-ZÄÖÜÉ][\wäöüßéèàçñ\-]{2,25}))\b")
_BASED = re.compile(r"(?i)(?:\bwe(?:'re| are)\b|\bour (?:team|company|office) is\b|\bis a\b[^.\n]{0,80}?)\s*(?:[^.\n]{0,40}?\s)?"
                    r"(?<![-\w])based in (?P<p>[A-Z][^\n.;,|(]{2,60}(?:,\s*[A-Z][^\n.;,|(]{2,40})?)")


def text_of(page: str) -> str:
    t = _DROP.sub(" ", page or "")
    t = _BLOCK.sub("\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = htmllib.unescape(t)
    t = re.sub(r"[ \t\r\f\v\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def _orgs(node):
    if isinstance(node, list):
        for x in node:
            yield from _orgs(x)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and re.search(r"Organization|Corporation|LocalBusiness|Company", t) for t in types):
            yield node
        for k in ("@graph", "publisher", "author", "provider", "brand", "parentOrganization"):
            if k in node:
                yield from _orgs(node[k])


def _addr_country(addr) -> str:
    for a in (addr if isinstance(addr, list) else [addr]):
        if isinstance(a, str):
            c = geo.country_of(a)
        elif isinstance(a, dict):
            ctry = a.get("addressCountry")
            if isinstance(ctry, dict):
                ctry = ctry.get("name") or ctry.get("identifier") or ""
            ctry = str(ctry or "").strip()
            c = (geo.country_of(hint=ctry) or geo.country_of(ctry)) if ctry else ""   # "IN" is India here, not Indiana
            if not c:
                c = geo.country_of(", ".join(str(a.get(k) or "") for k in ("addressLocality", "addressRegion")).strip(", "))
        else:
            c = ""
        if c:
            return c
    return ""


def from_jsonld(page: str) -> list[tuple[str, str]]:
    out = []
    for raw in _LDJSON.findall(page or ""):
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        for org in _orgs(data):
            for key in ("address", "location"):
                v = org.get(key)
                if isinstance(v, dict) and "address" in v:
                    v = v["address"]
                c = _addr_country(v) if v else ""
                if c:
                    out.append((c, f"schema.org {org.get('@type')} address: {json.dumps(v, ensure_ascii=False)[:140]}"))
                    break
    return out


# an address given for someone else: a GDPR representative, a regulator, a court, a registered agent
_OTHERS = re.compile(r"(?i)(representative|vertreter|repr[ée]sentant|data protection|\bdpo\b|supervisory|authority|"
                     r"commissioner|\bcnil\b|beh[öo]rde|ombuds|arbitrat|\bcourt\b|tribunal|registered agent|"
                     r"agent for service|lodge a complaint)")


def _for_others(text: str, m) -> bool:
    before = "\n".join(text[max(0, m.start() - 400): m.start()].split("\n")[-2:])[-160:]   # its line and the one before
    return bool(_OTHERS.search(before))


def _snip(text: str, m) -> str:
    return re.sub(r"\s+", " ", text[max(0, m.start() - 20): m.end() + 10]).strip()[:160]


def from_text(text: str) -> dict[int, list[tuple[str, str]]]:
    """{level: [(country, evidence text)]} for levels 2-4."""
    out: dict[int, list] = {2: [], 3: [], 4: []}
    for m in _HQ.finditer(text):
        if _for_others(text, m):
            continue
        place = re.split(r"\s+(?:and|with|where|while|but|since|for)\s+", m.group("p").strip(" :-–"))[0]
        c = geo.country_of(place)
        if c:
            out[2].append((c, _snip(text, m)))
    for m in _US_ADDR.finditer(text):
        if not _for_others(text, m):
            out[3].append(("US", _snip(text, m)))
    for m in _UK_ADDR.finditer(text):
        if not _for_others(text, m):
            out[3].append(("GB", _snip(text, m)))
    for m in _EU_ADDR.finditer(text):
        if _for_others(text, m):
            continue
        c = geo.CITIES.get(geo.fold(m.group("city")))
        if c and c not in ("US", "CA", "AU", "IN"):
            out[3].append((c, _snip(text, m)))
    for m in _BASED.finditer(text):
        c = geo.country_of(m.group("p"))
        if c:
            out[4].append((c, _snip(text, m)))
    return out


def decide(found: dict[int, list[tuple[str, str, str]]]) -> dict | None:
    """found: {level: [(country, url, evidence)]} -> {"country", "level", "url", "evidence"} or None."""
    for level in sorted(found):
        ev = found[level]
        if not ev:
            continue
        n = Counter(c for c, _, _ in ev)
        (top, k), rest = n.most_common(1)[0], sum(n.values()) - n.most_common(1)[0][1]
        if k > 2 * rest:                         # one country clearly ahead at this level
            c, url, text = next(e for e in ev if e[0] == top)
            return {"country": top, "level": level, "url": url, "evidence": text}
    return None


def more_pages(page: str, base: str) -> list[str]:
    own = registrable(urlsplit(base).hostname or "")
    seen, cands = set(), []
    for href, inner in _ANCHOR.findall(page or ""):
        u = urljoin(base, href.strip())
        sp = urlsplit(u)
        if sp.scheme not in ("http", "https") or registrable(sp.hostname or "") != own:
            continue
        label = re.sub(r"<[^>]+>|\s+", " ", inner).strip()
        if not (_LINK_PATH.search(sp.path) or (len(label) <= 40 and _LINK_WORDS.search(label))):
            continue
        key = sp._replace(fragment="", query="").geturl().rstrip("/")
        if key in seen or key == base.rstrip("/"):
            continue
        seen.add(key)
        word = (sp.path + " " + label).lower()
        rank = next((i for i, w in enumerate(_PRIORITY) if w in word), len(_PRIORITY))
        cands.append((rank, key))
    return [u for _, u in sorted(cands)[:MORE_PAGES]]


_SITE_NAME = re.compile(r"""<meta[^>]+property=["']og:site_name["'][^>]*content=["']([^"']{2,60})["']""", re.I)
_TITLE = re.compile(r"<title[^>]*>(.{2,200}?)</title>", re.I | re.S)


def site_name(page: str) -> str:
    """The company's name as its homepage gives it: og:site_name, else the title's part that names the brand."""
    m = _SITE_NAME.search(page or "")
    if m:
        return htmllib.unescape(m.group(1)).strip()
    m = _TITLE.search(page or "")
    if not m:
        return ""
    parts = [p.strip() for p in re.split(r"\s[|\-–—:·•]\s", htmllib.unescape(re.sub(r"\s+", " ", m.group(1)))) if p.strip()]
    short = [p for p in parts if len(p) <= 30]
    return (short[-1] if len(parts) > 1 and short else parts[0] if parts else "")[:60]


# a homepage served by a blog or site platform speaks for the platform, not the company
PLATFORMS = {"medium", "substack", "notion", "linktree", "carrd", "wix", "squarespace", "wordpress", "wordpress.com", "webflow",
             "framer", "ghost", "tumblr", "blogger", "github", "google sites", "godaddy", "hubspot", "beehiiv"}


def read(client, domain: str) -> dict:
    """{"domain", "status", "country"?, "level"?, "url"?, "evidence"?, "pages"} for one company's site."""
    res = {"domain": domain, "pages": []}
    home = None
    for start in (f"https://{domain}/", f"https://www.{domain}/"):
        r = client.get(start, max_bytes=MAX_PAGE)
        if r.status == -1:
            res["status"] = "robots"
            return res
        if r.ok and r.text:
            home = r
            break
    if home is None:
        res["status"] = "unreachable"
        return res
    found: dict[int, list] = {1: [], 2: [], 3: [], 4: []}

    def add(page_text: str, raw: str, url: str):
        res["pages"].append(url)
        for c, ev in from_jsonld(raw):
            found[1].append((c, url, ev))
        for lvl, items in from_text(page_text).items():
            found[lvl].extend((c, url, ev) for c, ev in items)

    base = home.url or f"https://{domain}/"
    res["name"] = site_name(home.text)
    if res["name"].strip().lower() in PLATFORMS:
        res["status"] = "platform_page"
        return res
    add(text_of(home.text), home.text, base)
    got = decide({k: v for k, v in found.items() if k <= 2})
    if not got:
        for u in more_pages(home.text, base):
            r = client.get(u, max_bytes=MAX_PAGE)
            if r.ok and r.text:
                add(text_of(r.text), r.text, r.url or u)
            if decide({k: v for k, v in found.items() if k <= 2}):
                break
        got = decide(found)
    res["status"] = "found" if got else "not_stated"
    if got:
        res.update(got)
    return res
