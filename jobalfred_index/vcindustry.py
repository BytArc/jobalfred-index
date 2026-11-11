"""Industry of VC-backed startups from public evidence, with plain rules (no AI, no network).

A source alongside industry.py's, used for vc-eu.json.gz. Evidence, in order:
  1. a funding article's own description of the company, e.g. "Buena, a German PropTech startup, has raised...",
     or an industry word in the headline such as "Belgian insurtech Qover raises..." (data/funding_eu.json)
  2. Y Combinator's public tags for the company (work/yc_companies.json, or the evidence kept in the company list)
The phrase table (data/industry/vc_phrases.json) is reviewed by hand. The industry named earliest in the evidence wins;
the generic Software codes decide only when nothing more specific is named. Every label keeps its evidence.
Priority in vceu.build: a reader's hand label, then this source, then the local model above its cutoff, then Not stated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHRASES = ROOT / "data" / "industry" / "vc_phrases.json"
YC = ROOT / "work" / "yc_companies.json"

# "X, a Berlin-based fintech startup", "X is a Danish insurtech company", "X, an AI-powered legal tech platform"
DESC = re.compile(r"(?:,|\bis)\s+(?:an?|the)\s+(?P<d>[^,.;:()\"“”]{2,90}?)\s+(?:startup|start-up|company|scale-?up|platform|provider|"
                  r"firm|spin-?out|spin-?off|developer|maker|manufacturer|operator|business|marketplace|unicorn|venture|player|"
                  r"specialist|pioneer|leader|innovator)s?\b", re.I)
# headline compounds that name an industry on their own: "Belgian insurtech Qover", "DefenceTech unicorn TEKEVER"
TITLE_TECH = re.compile(r"\b(?P<d>[a-z]+-?tech)\b", re.I)


def _table():
    d = json.loads(PHRASES.read_text())
    def compile_(pairs):
        return [(re.compile(r"(?<![\w-])" + re.escape(p).replace(r"\ ", r"[\s-]") + r"(?![\w-])", re.I), c, p) for p, c in pairs]
    return compile_(d["specific"]), compile_(d["generic"])


_T = None


def table():
    global _T
    if _T is None:
        _T = _table()
    return _T


def code_of(text: str, last: bool = False) -> tuple[str, str]:
    """(code, phrase) for the industry named in text: the earliest named (a list of tags), or with last=True the one nearest
    the end (a description, where the head noun comes last: "a green mobility insurance firm" is an insurer).
    Generic Software only when nothing specific is named."""
    specific, generic = table()
    best = None
    for rx, code, phrase in specific:
        for m in rx.finditer(text or ""):
            pos = m.end() if last else -m.start()
            if best is None or pos > best[0] or (pos == best[0] and len(phrase) > len(best[2])):
                best = (pos, code, phrase)
            if not last:
                break
    if best:
        return best[1], best[2]
    for rx, code, phrase in generic:
        if rx.search(text or ""):
            return code, phrase
    return "", ""


def from_article(company: str, title: str, text: str) -> tuple[str, str] | None:
    """(code, evidence) from a funding article: the description right after the company name, else a -tech word in the
    headline. None when the article says nothing about the company's industry in those places."""
    for m in DESC.finditer(text or ""):
        before = (text or "")[max(0, m.start() - 60): m.start()].lower()
        if company and company.lower()[:6] not in before and company.lower()[:6] not in m.group(0).lower():
            continue                                   # a description of someone else (an investor, a customer)
        code, phrase = code_of(m.group("d"), last=True)
        if code:
            return code, m.group(0).strip(" ,")[:160]
    for m in TITLE_TECH.finditer(title or ""):
        code, phrase = code_of(m.group("d"))
        if code and code != "sw":
            return code, (title or "")[:160]
    return None


YC_TAGS_IGNORE = {"b2b", "consumer", "marketplace", "enterprise", "smb", "remote work", "community", "subscriptions",
                  "social", "social network", "mobile", "web3"}


def from_yc_tags(tags: list[str]) -> tuple[str, str] | None:
    tags = [t for t in (tags or []) if t and t.lower() not in YC_TAGS_IGNORE]
    if not tags:
        return None
    code, phrase = code_of(" , ".join(tags))
    return (code, "YC tags: " + ", ".join(tags[:5])) if code else None


def labels(companies: list[dict], funding_rounds: dict | None = None, yc: dict | None = None) -> dict[str, dict]:
    """{domain: {"code", "source", "evidence", "url"}} for the companies this public evidence covers."""
    if funding_rounds is None:
        p = ROOT / "data" / "funding_eu.json"
        funding_rounds = json.loads(p.read_text()).get("rounds", {}) if p.exists() else {}
    if yc is None:
        yc = {}
        if YC.exists():
            for slug, c in json.loads(YC.read_text()).get("companies", {}).items():
                yc[f"https://www.ycombinator.com/companies/{slug}"] = c
    out: dict[str, dict] = {}
    for c in companies:
        dom = c["domain"]
        for r in sorted(funding_rounds.get(dom, []), key=lambda r: r.get("date") or "", reverse=True):
            got = from_article(c.get("name") or dom.split(".")[0], r.get("title") or "",
                               " ".join(x for x in (r.get("lede"), r.get("stage_ctx")) if x))
            if got:
                out[dom] = {"code": got[0], "source": "funding article", "evidence": got[1], "url": r.get("url", "")}
                break
        if dom in out:
            continue
        for ev in c.get("evidence") or []:
            yc_c = yc.get(ev)
            if yc_c:
                got = from_yc_tags(yc_c.get("tags") or [])
                if got:
                    out[dom] = {"code": got[0], "source": "yc", "evidence": got[1], "url": ev}
                    break
    return out
