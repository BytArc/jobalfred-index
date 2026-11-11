"""Is a company still a startup? Read from its English Wikipedia article's infobox (en.wikipedia.org/wiki/<title>,
robots.txt obeyed, one request at a time). Plain rules, no AI.

Used only to take companies out of the startup lists, never to add them:
  listed on a stock exchange ("Traded as", or Type "Public"), owned by another company ("Parent", or Type
  "Subsidiary"), or gone ("Fate": acquired, merged, defunct, bankrupt).
An article counts only when its infobox Website is the company's own domain, so a namesake's article is never used.
"""
from __future__ import annotations

import html as htmllib
import re
from urllib.parse import quote

from .startups import registrable

_INFOBOX = re.compile(r'<table class="infobox[^"]*"[^>]*>(.*?)</table>', re.S)
_ROW = re.compile(r'<th[^>]*class="infobox-label"[^>]*>(.*?)</th>\s*<td[^>]*class="infobox-data[^"]*"[^>]*>(.*?)</td>', re.S)
_HREF = re.compile(r'href="(https?://[^"]+)"')


def _text(fragment: str) -> str:
    t = re.sub(r"<style\b.*?</style>|<sup\b.*?</sup>", " ", fragment or "", flags=re.S)
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t).strip()


def infobox(page: str) -> tuple[dict[str, str], str]:
    """({label: text}, website domain) from the first infobox of an article."""
    m = _INFOBOX.search(page or "")
    if not m:
        return {}, ""
    rows, site = {}, ""
    for k, v in _ROW.findall(m.group(1)):
        label = _text(k)
        rows[label] = _text(v)
        if label.lower() in ("website", "url"):
            href = _HREF.search(v)
            site = registrable(href.group(1)) if href else registrable("https://" + rows[label].replace(" ", ""))
    return rows, site


# "Traded as" names a stock exchange or a ticker ("Nasdaq : RUN", "LSE : SOPH"), not just a legal name ("Preply Inc.")
_EXCHANGE = re.compile(r"(?i)\b(nyse|nasdaq|lse|aim|euronext|tsx|tsxv|asx|six swiss|xetra|fwb|otc(?:qx|qb| markets)?|hkex|sehk|"
                       r"sse|szse|bse|nse|tse|jpx|krx|kosdaq|omx|bme|borsa|wse|tase|sgx|b3|bmv|jse|ticker)\b|"
                       r"\b[A-Z][A-Za-z]{1,10}\s*:\s*[A-Z0-9][A-Z0-9.]{0,7}\b")


def verdict(rows: dict[str, str]) -> tuple[str, str] | None:
    """(reason, the infobox text that says so) when the article shows the company is not a startup, else None."""
    get = {k.lower(): v for k, v in rows.items()}
    if _EXCHANGE.search(get.get("traded as") or ""):
        return "listed", "Traded as: " + get["traded as"][:120]
    typ = get.get("type") or get.get("company type") or ""
    if re.search(r"(?i)\bpublic\b", typ) and not re.search(r"(?i)\b(benefit|charter|non-?profit)\b", typ):
        return "listed", "Type: " + typ[:120]
    fate = get.get("fate") or ""
    if re.search(r"(?i)\b(acquired|merged|defunct|bankrupt|dissolved|liquidat)", fate):
        return "gone", "Fate: " + fate[:120]
    if get.get("parent") or re.search(r"(?i)\bsubsidiary\b", typ):
        return "owned", ("Parent: " + get["parent"][:120]) if get.get("parent") else "Type: " + typ[:120]
    return None


def titles(name: str, domain: str) -> list[str]:
    base = re.sub(r"\s+", " ", (name or "").strip())
    label = domain.split(".")[0].replace("-", " ").title()
    out = []
    for t in (base, f"{base} (company)", f"{base}, Inc.", label, f"{label} (company)"):
        if t and t not in out:
            out.append(t)
    return out


def check(client, name: str, domain: str) -> dict:
    """{"domain", "status": "not_startup" | "article_ok" | "no_article", "reason"?, "detail"?, "url"?}"""
    for t in titles(name, domain):
        url = "https://en.wikipedia.org/wiki/" + quote(t.replace(" ", "_"), safe="_(),.'")
        r = client.get(url)
        if not r.ok or not r.text:
            continue
        rows, site = infobox(r.text)
        if site != domain:
            continue                                   # another company's article, or no website to tie it to us
        v = verdict(rows)
        res = {"domain": domain, "url": r.url or url}
        if v:
            res.update(status="not_startup", reason=v[0], detail=v[1])
        else:
            res["status"] = "article_ok"
        return res
    return {"domain": domain, "status": "no_article"}
