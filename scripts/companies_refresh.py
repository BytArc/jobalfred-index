"""Refresh the stock-index constituent lists into data/companies/indices.json, with source URL and retrieval date per list.

Usage: companies_refresh.py [CODE ...] [--dry] [--no-articles] [--aliases-only]
  CODE           only these lists (all configured lists when none given)
  --dry          print what each page gives, write nothing
  --no-articles  do not read the members' own Wikipedia articles (website and head-office country)
  --aliases-only recompute the cleaned-name aliases offline, read nothing

Read from Wikipedia /wiki/ pages only, which robots.txt allows for our user agent (its /w/ API and the Wikidata query service are
disallowed, so they are not used), one request every 2.5 seconds with our honest User-Agent. For each member the list page links
to, its article's infobox gives the official website (the domain used to find its careers system) and the head-office country (the
language inferred when a posting states none). A member keeps what an earlier refresh found, so a monthly run only reads new members.
Lists are ordered by the country's GDP, richest first (IMF World Economic Outlook, nominal, 2025), so batches roll out in that order.
Curated lists (big tech, AI labs, Big 4, consultancies) live in data/companies/curated.json and are edited by hand.
"""
import json, re, sys, time
from html import unescape as html_unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import geo
from jobalfred_index.polite import CHALLENGE, Client

WIKI = "https://en.wikipedia.org/wiki/"
# code, label, country, Wikipedia page, expected size range. Ordered by the country's nominal GDP, richest first.
INDICES = [
    ("sp500", "S&P 500", "US", "List_of_S%26P_500_companies", 480, 510),
    ("sse50", "SSE 50", "CN", "SSE_50_Index", 45, 52),
    ("dax", "DAX", "DE", "DAX", 38, 42),
    ("nikkei225", "Nikkei 225", "JP", "Nikkei_225", 200, 230),
    ("nifty50", "NIFTY 50", "IN", "NIFTY_50", 45, 52),
    ("ftse100", "FTSE 100", "GB", "FTSE_100_Index", 95, 105),
    ("cac40", "CAC 40", "FR", "CAC_40", 38, 42),
    ("ftsemib", "FTSE MIB", "IT", "FTSE_MIB", 38, 42),
    ("tsx60", "S&P/TSX 60", "CA", "S%26P/TSX_60", 55, 65),
    ("ibovespa", "Ibovespa", "BR", "Ibovespa", 50, 100),
    ("moex", "MOEX Russia Index", "RU", "MOEX_Russia_Index", 10, 60),
    ("ibex35", "IBEX 35", "ES", "IBEX_35", 33, 37),
    ("ipc", "S&P/BMV IPC", "MX", "S%26P/BMV_IPC", 30, 40),
    ("kospi200", "KOSPI 200", "KR", "KOSPI_200", 180, 210),
    ("asx200", "S&P/ASX 200", "AU", "S%26P/ASX_200", 180, 210),
    ("lq45", "IDX LQ45", "ID", "LQ45", 40, 50),
    ("bist30", "BIST 30", "TR", "BIST_30", 25, 35),
    ("aex", "AEX", "NL", "AEX_index", 23, 27),
    ("smi", "SMI", "CH", "Swiss_Market_Index", 18, 22),
    ("wig20", "WIG20", "PL", "WIG20", 18, 22),
    ("taiwan50", "FTSE TWSE Taiwan 50", "TW", "FTSE_TWSE_Taiwan_50_Index", 45, 55),
    ("bel20", "BEL 20", "BE", "BEL_20", 18, 22),
    ("omxs30", "OMX Stockholm 30", "SE", "OMX_Stockholm_30", 28, 32),
    ("iseq20", "ISEQ 20", "IE", "ISEQ_20", 18, 22),
    ("merval", "S&P MERVAL", "AR", "S%26P_MERVAL", 15, 35),
    ("ta35", "TA-35", "IL", "TA-35_Index", 33, 37),
    ("atx", "ATX", "AT", "Austrian_Traded_Index", 18, 25),
    ("sti", "Straits Times Index", "SG", "Straits_Times_Index", 28, 32),
    ("set50", "SET50", "TH", "SET50_Index", 45, 55),
    ("obx", "OBX", "NO", "OBX_Index", 23, 27),
    ("psei", "PSE Composite Index", "PH", "PSE_Composite_Index", 28, 32),
    ("vn30", "VN30", "VN", "VN30_Index", 28, 32),
    ("omxc25", "OMX Copenhagen 25", "DK", "OMX_Copenhagen_25", 23, 27),
    ("klci", "FTSE Bursa Malaysia KLCI", "MY", "FTSE_Bursa_Malaysia_KLCI", 28, 32),
    ("colcap", "COLCAP", "CO", "COLCAP", 15, 30),
    ("hsi", "Hang Seng Index", "HK", "Hang_Seng_Index", 70, 100),
    ("jse40", "FTSE/JSE Top 40", "ZA", "FTSE/JSE_Top_40_Index", 38, 42),
    ("bet", "BET", "RO", "BET_index", 15, 25),
    ("egx30", "EGX 30", "EG", "EGX_30", 28, 32),
    ("kse100", "KSE 100", "PK", "KSE_100_Index", 90, 110),
    ("ipsa", "S&P IPSA", "CL", "S%26P_IPSA", 25, 35),
    ("px", "PX", "CZ", "PX_Index", 8, 25),
    ("psi20", "PSI 20", "PT", "PSI-20", 15, 22),
    ("omxh25", "OMX Helsinki 25", "FI", "OMX_Helsinki_25", 23, 27),
    ("nzx50", "S&P/NZX 50", "NZ", "S%26P/NZX_50_Index", 45, 55),
    ("athex", "FTSE/Athex Large Cap", "GR", "FTSE/Athex_Large_Cap", 20, 30),
    ("bux", "BUX", "HU", "BUX", 10, 30),
]
NAME_HEADERS = ("company", "name", "constituent", "security", "issuer", "firm", "corporation", "stock")
NOT_NAME = ("sector", "industry", "ticker", "symbol", "code", "weight", "exchange", "isin")
# share classes and legal forms, removed for the alias used in matching (the listed name is kept as it is)
LEGAL = re.compile(r"(?i)[\s,]+(?:\((?:class|series|ser\.?)\s*[a-z]\)|class [a-z]|ser\.\s*[a-z]|[ab]|inc\.?|incorporated|corporation|corp\.?|company|"
                   r"co\.?|plc|p\.l\.c\.|ltd\.?|limited|ag|s\.?a\.?|s\.?e\.?|n\.?v\.?|asa|a/s|ab|oyj|abp|s\.?p\.?a\.?|spa|ltda\.?|tbk|pjsc|"
                   r"berhad|bhd|holdings?|group|international|\(publ\)|public company limited|pcl|sa/nv|nv/sa|kgaa|& co\.? kgaa|se & co\.? kgaa|"
                   r"gmbh|bv|l\.?p\.?|reit|trust|international ag|international plc)\s*$")


def clean_name(n: str) -> str:
    n = re.sub(r"\[.*?\]", "", n).strip()
    n = re.sub(r"^the\s+|\s*\(the\)$", "", n, flags=re.I)
    prev = None
    while prev != n:
        prev, n = n, re.sub(r"\s*&$", "", LEGAL.sub("", n).strip(" ,."))
    return n


class Tables(HTMLParser):
    """Top-level tables as rows of (text, first /wiki/ link) cells."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._t, self._row, self._cell, self._link, self._depth, self._skip = [], None, None, None, None, 0, 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._t = []
        elif tag == "tr" and self._t is not None and self._depth == 1:
            self._row = []
        elif tag in ("td", "th") and self._row is not None and self._depth == 1:
            self._cell, self._link = [], None
        elif tag in ("sup", "style", "script") and self._cell is not None:
            self._skip += 1
        elif tag == "a" and self._cell is not None and self._link is None and not self._skip:
            href = re.sub(r"^https://en\.wikipedia\.org", "", html_unescape(dict(attrs).get("href") or ""))
            if href.startswith("/wiki/") and ":" not in href[6:] and "?" not in href:     # red links have no article
                self._link = unquote(href[6:].split("#")[0])

    def handle_endtag(self, tag):
        if tag in ("sup", "style", "script") and self._skip:
            self._skip -= 1
        elif tag in ("td", "th") and self._cell is not None and self._depth == 1:
            self._row.append((re.sub(r"\s+", " ", "".join(self._cell)).strip(), self._link))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._depth == 1:
            self._t.append(self._row)
            self._row = None
        elif tag == "table":
            if self._depth == 1 and self._t is not None:
                self.tables.append(self._t)
                self._t = None
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data):
        if self._cell is not None and not self._skip:
            self._cell.append(data)


SECTION = re.compile(r'<h2[^>]*>(?:(?!</h2>).)*(?:Component|Constituent|Composition|Members|Listed companies)(?:(?!</h2>).)*</h2>(.*?)(?=<h2|$)', re.S | re.I)
LI_LINK = re.compile(r'<li[^>]*>\s*(?:<[^a][^>]*>\s*)*<a [^>]*?href="(?:https://en\.wikipedia\.org)?/wiki/([^"#:]+)"[^>]*>([^<]+)</a>', re.S)


def _tables(html: str) -> list[list[tuple[str, str | None]]]:
    """Name cells of every table that has a company-name column (navigation boxes left out)."""
    p = Tables()
    p.feed(html)
    out = []
    for t in p.tables:
        if len(t) < 5:
            continue
        if len(t[0]) == 1 and len(t[1]) > 1:          # a caption row ("TA-35 Components") above the real header
            t = t[1:]
        head = [h.lower() for h, _ in t[0]]
        if any(h.startswith("vte") or "indices" in h for h in head):
            continue
        col = next((i for pri in NAME_HEADERS for i, h in enumerate(head) if pri in h and not any(x in h for x in NOT_NAME)), None)
        if col is None:
            continue
        out.append([r[col] for r in t[1:] if len(r) > col and r[col][0] and not re.fullmatch(r"[\d.,% ]+", r[col][0])])
    return out


def _section_list(html: str) -> list[tuple[str, str | None]]:
    """The linked list items of a "Components" or "Constituents" section, for pages that list members as bullets."""
    m = SECTION.search(html)
    if not m:
        return []
    return [(html_unescape(TAGS.sub("", text)).strip(), unquote(html_unescape(link))) for link, text in LI_LINK.findall(m.group(1))]


def members_from_html(html: str, lo: int = 0, hi: int = 10 ** 6) -> list[dict]:
    cands = _tables(html) + [_section_list(html)]
    fit = [c for c in cands if lo <= len(c) <= hi]
    best = fit[0] if fit else max(cands, key=len)        # the current-members table comes before the former-members one
    seen, out = set(), []
    for n, link in best:
        n = re.sub(r"\[.*?\]", "", n).strip()
        key = clean_name(n).lower()
        if n and key not in seen:
            seen.add(key)
            m = {"name": n}
            if link:
                m["wiki"] = link
            out.append(m)
    return out


INFOBOX = re.compile(r'<table class="infobox[^"]*vcard[^"]*".*?</table>', re.S)
ROW = re.compile(r'<th scope="row" class="infobox-label"[^>]*>(.*?)</th>\s*<td class="infobox-data[^"]*"[^>]*>(.*?)</td>', re.S)
TAGS = re.compile(r"<[^>]+>")


def infobox(html: str) -> dict:
    """Website domain and head-office country from an article's infobox."""
    m = INFOBOX.search(html)
    if not m:
        return {}
    out = {}
    for label, data in ROW.findall(m.group(0)):
        label = TAGS.sub("", label).strip().lower()
        if label == "website" and "domain" not in out:
            href = re.search(r'href="(https?://[^"]+)"', data)
            if href:
                host = (urlsplit(href.group(1)).hostname or "").lower()
                host = re.sub(r"^(www\d?|global|corporate|corp|group|en|about)\.", "", host)
                if host and "wikipedia" not in host:
                    out["domain"] = host
        elif label in ("headquarters", "headquarters location", "head office") and "hq" not in out:
            text = re.sub(r"\s+", " ", TAGS.sub(", ", re.sub(r"<sup.*?</sup>", "", data, flags=re.S))).replace("&#160;", " ")
            cc = geo.country_of(text)
            if cc:
                out["hq"] = cc
        elif label in ("trade name", "formerly", "also known as") and "aliases" not in out:
            text = TAGS.sub(" ", re.sub(r"<sup.*?</sup>", "", data, flags=re.S)).strip()
            names = [x.strip() for x in re.split(r"<br\s*/?>|\n|;", text) if 2 < len(x.strip()) < 60]
            if label == "trade name" and names:
                out["aliases"] = names[:3]
    return out


def realias(doc: dict) -> None:
    """Every member's cleaned name as an alias ("Coca-Cola" for "Coca-Cola Company (The)"); offline, also run alone with --aliases-only."""
    for lst in doc["lists"].values():
        for m in lst["members"]:
            alias = clean_name(m["name"])
            if alias and alias.lower() != m["name"].lower():
                m["aliases"] = sorted(set(m.get("aliases", [])) | {alias})


def main():
    want = {a for a in sys.argv[1:] if not a.startswith("--")}
    if "--aliases-only" in sys.argv:
        out_path = root / "data" / "companies" / "indices.json"
        doc = json.loads(out_path.read_text())
        realias(doc)
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        return
    dry, articles = "--dry" in sys.argv, "--no-articles" not in sys.argv
    client = Client(default_gap=2.5, inflight=1)
    out_path = root / "data" / "companies" / "indices.json"
    doc = json.loads(out_path.read_text()) if out_path.exists() else {"version": 1, "lists": {}}
    doc["basis"] = ("Constituents read from the English Wikipedia list or index article (source per list); website and head-office country "
                    "from each member's own article infobox. Ordered by the country's nominal GDP, richest first (IMF WEO 2025).")
    for rank, (code, label, cc, page, lo, hi) in enumerate(INDICES, 1):
        if want and code not in want:
            continue
        url = WIKI + page
        r = client.get(url)
        if r.status != 200:
            print(f"{code}: HTTP {r.status} {r.reason} - skipped for this run")
            continue
        members = members_from_html(r.text, lo, hi)
        ok = lo <= len(members) <= hi
        print(f"{code}: {len(members)} members{'' if ok else '  <-- outside ' + str(lo) + '-' + str(hi) + ', kept the earlier list'}")
        if dry or not ok:
            continue
        old = {m["name"]: m for m in doc["lists"].get(code, {}).get("members", [])}
        for m in members:
            prev = old.get(m["name"], {})
            for k in ("domain", "hq", "aliases", "checked"):
                if k in prev:
                    m[k] = prev[k]
            alias = clean_name(m["name"])
            if alias and alias.lower() != m["name"].lower():
                m["aliases"] = sorted(set(m.get("aliases", [])) | {alias})
            if articles and m.get("wiki") and "checked" not in m:
                a = client.get(WIKI + m["wiki"])
                if a.status != 200:
                    print(f"   {m['wiki']}: HTTP {a.status} {a.reason}")
                    if a.reason == "bot challenge":
                        head = (a.content or b"")[:6000]
                        hit = re.search(rb".{0,80}(?:" + CHALLENGE.pattern + rb").{0,40}", head, re.I | re.S)
                        print("   matched:", hit.group(0)[:200] if hit else None)
                if a.status == 200:
                    info = infobox(a.text)
                    for k in ("domain", "hq"):
                        if info.get(k):
                            m[k] = info[k]
                    if info.get("aliases"):
                        m["aliases"] = sorted(set(m.get("aliases", [])) | set(info["aliases"]))
                    m["checked"] = time.strftime("%Y-%m-%d")
        doc["lists"][code] = {"label": label, "hq": cc, "gdp_rank": rank, "source": url, "retrieved": time.strftime("%Y-%m-%d"),
                              "members": members}
        found = sum(1 for m in members if m.get("domain"))
        print(f"   {found}/{len(members)} with a website, {sum(1 for m in members if m.get('hq'))} with a head-office country")
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    if not dry and not want:
        for code in [c for c in doc["lists"] if c not in {i[0] for i in INDICES}]:
            print(f"{code}: no longer configured, removed")
            del doc["lists"][code]
    if not dry:
        realias(doc)
        doc["lists"] = dict(sorted(doc["lists"].items(), key=lambda kv: kv[1].get("gdp_rank", 999)))
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print("http", dict(client.stats), "blocked", client.blocked)


if __name__ == "__main__":
    main()
