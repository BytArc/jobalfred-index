"""Refresh the stock-index constituent lists from Wikipedia into data/companies/indices.json (source URL and retrieval date per list).

Usage: companies_refresh.py [CODE ...]      (all configured indices when none given)
Only /wiki/ pages, which robots.txt allows for our user agent, one request every 3 seconds, with our honest User-Agent. The article pages
are fetched with requests directly because the polite client's challenge detector reads words in article text as a bot check; nothing
is bypassed. Curated lists (big tech, AI labs, Big 4, consultancies) live in data/companies/curated.json and are edited by hand.
"""
import json, re, sys, time
from html.parser import HTMLParser
from pathlib import Path
import requests

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index.polite import Client, USER_AGENT

# code, label, HQ country, Wikipedia page, expected size (a sanity range is checked)
INDICES = [
    ("sp500", "S&P 500", "US", "List_of_S%26P_500_companies", 480, 510),
    ("psi20", "PSI 20", "PT", "PSI-20", 15, 22),
    ("dax", "DAX", "DE", "DAX", 38, 42),
    ("cac40", "CAC 40", "FR", "CAC_40", 38, 42),
    ("ftse100", "FTSE 100", "GB", "FTSE_100_Index", 95, 105),
    ("nikkei225", "Nikkei 225", "JP", "Nikkei_225", 200, 230),
    ("ibex35", "IBEX 35", "ES", "IBEX_35", 33, 37),
    ("ftsemib", "FTSE MIB", "IT", "FTSE_MIB", 38, 42),
    ("aex", "AEX", "NL", "AEX_index", 23, 27),
    ("smi", "SMI", "CH", "Swiss_Market_Index", 18, 22),
    ("omxs30", "OMXS30", "SE", "OMX_Stockholm_30", 28, 32),
    ("kospi200", "KOSPI 200", "KR", "KOSPI_200", 180, 210),
    ("nifty50", "NIFTY 50", "IN", "NIFTY_50", 48, 52),
    ("asx200", "S&P/ASX 200", "AU", "S%26P/ASX_200", 180, 210),
    ("tsx60", "S&P/TSX 60", "CA", "S%26P/TSX_60", 55, 65),
    ("bovespa", "Ibovespa", "BR", "Ibovespa", 70, 100),
    ("ipc", "S&P/BMV IPC", "MX", "S%26P/BMV_IPC", 30, 40),
    ("omxc25", "OMX Copenhagen 25", "DK", "OMX_Copenhagen_25", 23, 27),
    ("obx", "OBX", "NO", "OBX_Index", 23, 27),
    ("bel20", "BEL 20", "BE", "BEL_20", 18, 22),
    ("atx", "ATX", "AT", "Austrian_Traded_Index", 18, 25),
    ("omxh25", "OMX Helsinki 25", "FI", "OMX_Helsinki_25", 23, 27),
    ("wig20", "WIG20", "PL", "WIG20", 18, 22),
    ("ise100", "ISEQ 20", "IE", "ISEQ_20", 18, 22),
    ("hsi", "Hang Seng Index", "HK", "Hang_Seng_Index", 70, 100),
    ("sti", "Straits Times Index", "SG", "Straits_Times_Index", 28, 32),
    ("sse50", "SSE 50", "CN", "SSE_50_Index", 48, 52),
    ("tadawul", "Tadawul All Share (top)", "SA", "Tadawul_All_Share_Index", 0, 400),
    ("jse40", "FTSE/JSE Top 40", "ZA", "FTSE/JSE_Top_40_Index", 38, 42),
    ("ftse_athex", "Athex Large Cap", "GR", "Athens_General_Composite_Index", 0, 400),
]
NAME_HEADERS = ("company", "name", "constituent", "security", "issuer", "firm", "corporation")


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._t, self._row, self._cell, self._depth = [], None, None, None, 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._t = []
        elif tag == "tr" and self._t is not None and self._depth == 1:
            self._row = []
        elif tag in ("td", "th") and self._row is not None and self._depth == 1:
            self._cell = []
        elif tag in ("sup", "style", "script") and self._cell is not None:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("sup", "style", "script") and self._skip:
            self._skip -= 1
        elif tag in ("td", "th") and self._cell is not None and self._depth == 1:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
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


def members_from_html(html: str) -> list[str]:
    p = Tables()
    p.feed(html)
    best: list[str] = []
    for t in p.tables:
        if len(t) < 5:
            continue
        head = [h.lower() for h in t[0]]
        col = next((i for pri in NAME_HEADERS for i, h in enumerate(head) if pri in h and "sector" not in h and "industry" not in h), None)
        if col is None:
            continue
        names = [r[col] for r in t[1:] if len(r) > col and r[col] and not re.fullmatch(r"[\d.,% ]+", r[col])]
        if len(names) > len(best):
            best = names
    seen, out = set(), []
    for n in best:
        n = re.sub(r"\[.*?\]", "", n).strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def main():
    want = set(sys.argv[1:])
    polite = Client()
    out_path = root / "data" / "companies" / "indices.json"
    doc = json.loads(out_path.read_text()) if out_path.exists() else {"version": 1, "lists": {}}
    for code, label, cc, page, lo, hi in INDICES:
        if want and code not in want:
            continue
        url = "https://en.wikipedia.org/wiki/" + page
        if not polite.robots_allows(url):
            print(code, "robots.txt disallows; skipped"); continue
        time.sleep(3)
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        except requests.RequestException as e:
            print(code, type(e).__name__, "- skipped for this run"); continue
        if r.status_code != 200:
            print(code, "HTTP", r.status_code, "- skipped for this run"); continue
        names = members_from_html(r.text)
        flag = "" if lo <= len(names) <= hi else "  <-- outside the expected size, check by hand"
        print(f"{code}: {len(names)} members{flag}")
        if lo <= len(names) <= hi and names:
            doc["lists"][code] = {"label": label, "hq": cc, "source": url, "retrieved": time.strftime("%Y-%m-%d"),
                                  "members": [{"name": n} for n in names]}
            out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
