"""Funding rounds from public news articles, read with plain patterns (no AI).

A round is kept only when the article links the company's own website, so a namesake is not matched. Each round keeps
its source URL as evidence. Totals: "to date" when the article states one, else "at least" the sum of rounds found.
"""
from __future__ import annotations

import html as htmllib
import re
from urllib.parse import urlsplit

from .startups import _fold, registrable

VERBS = r"(?:raises|raised|secures|secured|closes|closed|lands|bags|nabs|grabs|snaps-up|collects|pockets|gets|receives|scores|attracts|completes|announces)"
# slug: [city-based-]<company>-<verb>-<amount>...
SLUG = re.compile(rf"^(?:[a-z0-9-]+?-based-)?(?P<company>[a-z0-9-]{{2,60}}?)-{VERBS}-(?P<rest>.+)$")
SLUG_AMOUNT = re.compile(r"(?:^|-)(?:over-|nearly-|almost-|around-|about-)?(?P<cur>e|eur|usd|gbp|chf|sek|dkk|nok|pln|\$|£|€)?-?"
                         r"(?P<num>\d{1,4}(?:-\d{1,3})?)-?(?P<unit>million|m|billion|bn|b|k|thousand)(?:-|$)")
TEXT_AMOUNT = re.compile(r"(?P<cur>€|\$|£|CHF|SEK|DKK|NOK|PLN|EUR|USD|GBP)\s?(?P<num>\d{1,4}(?:[.,]\d{1,3})?)\s?"
                         r"(?P<unit>million|m\b|billion|bn\b|k\b|thousand)", re.I)
STAGES = [("pre_seed", r"pre[- ]?seed"), ("seed", r"\bseed\b"), ("series_a", r"series[- ]a\b"), ("series_b", r"series[- ]b\b"),
          ("series_c", r"series[- ]c\b"), ("series_d", r"series[- ]d\b"), ("series_e_plus", r"series[- ][e-h]\b"),
          ("growth", r"growth (?:round|equity|funding)")]
NOT_EQUITY = re.compile(r"(?i)valuation|debt|loan|credit facility|venture debt|grant|subsid|acquir|acquisition|merger|fund i|"
                        r"first close|final close|new fund|launches .{0,20}fund")
TOTAL = re.compile(r"(?i)(?:bring(?:s|ing)?|tak(?:es|ing)|total(?:s|ling)?)\s+(?:its|the company.s|their)?\s*(?:total\s+)?"
                   r"(?:funding|capital raised|investment|amount raised)?\s*(?:raised\s+)?(?:to date\s+)?(?:to|of)\s+"
                   r"(?:over\s+|more than\s+|nearly\s+|around\s+)?(?P<cur>€|\$|£|CHF|EUR|USD|GBP)\s?(?P<num>\d{1,4}(?:[.,]\d{1,3})?)\s?"
                   r"(?P<unit>million|m\b|billion|bn\b)")
CUR = {"e": "EUR", "eur": "EUR", "€": "EUR", "usd": "USD", "$": "USD", "gbp": "GBP", "£": "GBP", "chf": "CHF", "sek": "SEK",
       "dkk": "DKK", "nok": "NOK", "pln": "PLN"}


def _money(num: str, unit: str, sep: str = ".") -> float:
    n = float(num.replace("-", ".").replace(",", ".")) if num else 0.0
    u = unit.lower()
    return n * (1e9 if u in ("billion", "bn", "b") else 1e3 if u in ("k", "thousand") else 1e6)


def parse_slug(url: str) -> dict | None:
    """'.../2026/11/london-based-neobe-raises-e6-1-million-to-...' -> {'company': 'neobe', 'amount': 6.1e6, 'currency': 'EUR'}."""
    path = urlsplit(url).path.strip("/")
    m = re.match(r"(?:20\d\d)/(\d\d)/([^/]+)$", path)
    if not m:
        return None
    slug = m.group(2).lower()
    s = SLUG.match(slug)
    if not s:
        return None
    rest = s.group("rest")
    a = SLUG_AMOUNT.search(rest)
    if not a or re.search(r"valuation|debt|loan|grant|fund-i|first-close|final-close", rest):
        return None
    stage = next((k for k, rx in STAGES if re.search(rx.replace(r"\b", r"(?:^|-|$)").replace("[- ]", "-").replace(" ", "-"), rest)),
                 "")
    return {"company": s.group("company"), "amount": _money(a.group("num"), a.group("unit")),
            "currency": CUR.get((a.group("cur") or "e").lower(), "EUR"), "stage": stage}


def _text(page: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", t)))


def parse_article(page: str, url: str) -> dict:
    """Title, date, stage, amount (from the title), total to date (when stated), and the outbound domains."""
    title = ""
    m = re.search(r'<meta property="og:title" content="([^"]+)"', page or "") or re.search(r"<title>([^<]+)</title>", page or "")
    if m:
        title = htmllib.unescape(m.group(1)).split(" | ")[0].strip()
    d = re.search(r'"datePublished":"([0-9-]{10})|article:published_time" content="([0-9-]{10})', page or "")
    date = (d.group(1) or d.group(2)) if d else ""
    body = _text(page)
    art = re.search(r'<div class="td-post-content[^"]*">(.*?)<footer', page or "", re.S)
    body_html = art.group(1) if art else page or ""
    first = _text(body_html)[:3000]
    stage = next((k for k, rx in STAGES if re.search(rx, title, re.I)), "") or \
        next((k for k, rx in STAGES if re.search(rx + r"(?:\s+(?:funding|investment|financing|extension))?\s+round", first, re.I)), "")
    amt = TEXT_AMOUNT.search(title)
    tot = TOTAL.search(first)
    own = registrable(url)
    doms = []
    for h in re.findall(r'href="(https?://[^"]+)"', body_html):
        r = registrable(h)
        if r and r != own and r not in doms:
            doms.append(r)
    return {"title": title, "date": date, "stage": stage,
            "amount": _money(amt.group("num"), amt.group("unit")) if amt else None,
            "currency": CUR.get(amt.group("cur").lower(), amt.group("cur").upper()) if amt else "",
            "total": _money(tot.group("num"), tot.group("unit")) if tot else None,
            "total_currency": CUR.get(tot.group("cur").lower(), tot.group("cur").upper()) if tot else "",
            "not_equity": bool(NOT_EQUITY.search(title)), "domains": doms, "body_len": len(body)}


def summarise(rounds: list[dict]) -> dict:
    """Latest stage, total (stated to date, else at least the sum of rounds in one currency), latest round date and source."""
    if not rounds:
        return {}
    rs = sorted(rounds, key=lambda r: r.get("date") or "")
    last = rs[-1]
    stage = next((r["stage"] for r in reversed(rs) if r.get("stage")), "")
    stated = next((r for r in reversed(rs) if r.get("total")), None)
    if stated and (stated.get("date") or "") >= (last.get("date") or ""):
        total, cur, at_least = stated["total"], stated.get("total_currency") or stated.get("currency"), False
    else:
        cur = last.get("currency") or "EUR"
        total = sum(r["amount"] for r in rs if r.get("amount") and (r.get("currency") or "EUR") == cur)
        at_least = True
    return {"stage": stage, "total": round(total) if total else None, "currency": cur, "at_least": at_least,
            "date": last.get("date", ""), "source": last.get("url", ""), "rounds": len(rs)}


def matches(slug_company: str, company: dict) -> bool:
    a = _fold(slug_company)
    return bool(a) and len(a) >= 3 and a in (_fold(company.get("name") or ""), _fold(company["domain"].split(".")[0]))
