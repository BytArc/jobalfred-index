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
STAGES = [("pre_seed", r"pre[- ]?seed"), ("seed", r"(?<!pre-)(?<!pre )(?<!pre)\bseed\b"), ("pre_series_a", r"pre[- ]series[- ]a\b"),
          ("series_a", r"(?<!pre-)(?<!pre )series[- ]a\b"), ("series_b", r"series[- ]b\b"),
          ("series_c", r"series[- ]c\b"), ("series_d", r"series[- ]d\b"), ("series_e_plus", r"series[- ][e-h]\b"),
          ("growth", r"growth (?-i:round|equity|funding|investment)\b")]   # lower case: a page's "Funding" label is not one
NOT_EQUITY = re.compile(r"(?i)valuation|debt|loan|credit facility|venture debt|grant|subsid|acquir|acquisition|merger|fund i|"
                        r"first close|final close|new fund|launches .{0,20}fund|\bprojects?\b|\bBESS\b|portfolio financ|"
                        r"asset[- ]backed|asset financ|project financ|warehouse facility|bond")
TOTAL = re.compile(r"(?i)(?:bring(?:s|ing)?|tak(?:es|ing)|total(?:s|ling)?)\s+(?:its|the company.s|their)?\s*(?:total\s+)?"
                   r"(?:funding|capital raised|investment|amount raised)?\s*(?:raised\s+)?(?:to date\s+)?(?:to|of)\s+"
                   r"(?P<q>over\s+|more than\s+|nearly\s+|around\s+)?(?P<cur>€|\$|£|CHF|EUR|USD|GBP)\s?(?P<num>\d{1,4}(?:[.,]\d{1,3})?)\s?"
                   r"(?P<unit>million|m\b|billion|bn\b)")
# a "total" next to these words is not money raised to date
NOT_TOTAL = re.compile(r"(?i)\bdebt\b|\bloans?\b|credit|to raise|aims? to|plans? to|seeks? to|target|valuation|revenue|grant")


def stage_near(text: str, amount_num: str = "") -> str:
    """The stage named closest to the round's amount in `text` ('' if none). Without an amount, the first named."""
    pos = text.find(amount_num) if amount_num else -1
    best, dist = "", 10 ** 9
    for k, rx in STAGES:
        for m in re.finditer(rx, text, re.I):
            d = abs(m.start() - pos) if pos >= 0 else m.start()
            if d < dist:
                best, dist = k, d
    return best


def total_in(text: str) -> tuple:
    """(total, currency, at_least) stated in text, or (None, '', False)."""
    for m in TOTAL.finditer(text or ""):
        win = text[max(0, m.start() - 60): m.end() + 60]
        if NOT_TOTAL.search(win):
            continue
        cur = CUR.get(m.group("cur").lower(), m.group("cur").upper())
        return _money(m.group("num"), m.group("unit")), cur, bool(m.group("q") and m.group("q").strip().lower() in ("over", "more than"))
    return None, "", False
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
    amt = TEXT_AMOUNT.search(title)
    stage = stage_near(title)
    stage_ctx = title if stage else ""
    if not stage and amt:
        # a stage named in the text counts only next to this round's amount ("a €12 million Series A round"),
        # so an earlier round mentioned further down is not taken for this one; the nearest named stage wins
        num = re.escape(amt.group("num"))
        for m in re.finditer(num + r"\s?(?:million|m\b|billion|bn\b|k\b)", first, re.I):
            win = first[max(0, m.start() - 120): m.end() + 120]
            hit = stage_near(win, amt.group("num"))
            if hit:
                stage, stage_ctx = hit, win
                break
    total, total_cur, total_at_least = total_in(first)
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
            "total": total, "total_currency": total_cur, "total_at_least": total_at_least,
            "not_equity": bool(NOT_EQUITY.search(title)), "domains": doms, "body_len": len(body),
            "stage_ctx": stage_ctx[:300], "total_ctx": first[max(0, tot.start() - 80): tot.end() + 40] if tot else ""}


def reparse(r: dict) -> dict:
    """Apply the current rules to a stored round from its kept sentences (no network)."""
    r = dict(r)
    amt = TEXT_AMOUNT.search(r.get("title") or "")
    st = stage_near(r.get("title") or "")
    if not st and r.get("stage_ctx") and r.get("stage_ctx") != r.get("title"):
        st = stage_near(r["stage_ctx"], amt.group("num") if amt else "")
    r["stage"] = st or (r.get("stage") if not r.get("stage_ctx") else "")
    if r.get("total_ctx") is not None:
        r["total"], r["total_currency"], r["total_at_least"] = total_in(r.get("total_ctx") or "")
    return r


def summarise(rounds: list[dict]) -> dict:
    """Latest stage, total (stated to date, else at least the sum of rounds in one currency), latest round date and source."""
    if not rounds:
        return {}
    rs = sorted(rounds, key=lambda r: r.get("date") or "")
    last = rs[-1]
    stage = next((r["stage"] for r in reversed(rs) if r.get("stage")), "")
    stated = next((r for r in reversed(rs) if r.get("total")), None)
    if stated and (stated.get("date") or "") >= (last.get("date") or ""):
        total, cur, at_least = stated["total"], stated.get("total_currency") or stated.get("currency"), bool(stated.get("total_at_least"))
    else:
        cur = last.get("currency") or "EUR"
        total = sum(r["amount"] for r in rs if r.get("amount") and (r.get("currency") or "EUR") == cur)
        at_least = True
    return {"stage": stage, "total": round(total) if total else None, "currency": cur, "at_least": at_least,
            "date": last.get("date", ""), "source": last.get("url", ""), "rounds": len(rs)}


def matches(slug_company: str, company: dict) -> bool:
    a = _fold(slug_company)
    return bool(a) and len(a) >= 3 and a in (_fold(company.get("name") or ""), _fold(company["domain"].split(".")[0]))
