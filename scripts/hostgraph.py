"""Find ATS tenants in Common Crawl's host-level web graph (public data over HTTPS, no key).

The graph's "vertices" files list every host name Common Crawl has seen, one per line (id TAB reversed host).
Each part (about 27 MB gzipped) is streamed and filtered on the fly; nothing is stored except the matching
host names. One part at a time, one second apart, honest User-Agent. data.commoncrawl.org's robots.txt is
for crawlers; this is the dataset's distribution host, which the dataset exists to serve.

Usage: hostgraph.py OUT.json RELEASE [RELEASE ...]     e.g. cc-main-2026-jul-aug-sep
"""
import gzip, io, json, re, sys, time
import requests

UA = "JobAlfredBot/1.0 (+https://jobalfred.com/bot)"
BASE = "https://data.commoncrawl.org"
SKIP = {"www", "app", "api", "cdn", "mail", "static", "assets", "login", "sso", "support", "help", "blog", "status", "docs",
        "careers", "jobs", "my", "info", "email", "m", "wd", "impl", "community", "preview", "partner", "test"}

WD = re.compile(r"^([a-z0-9-]+)\.(wd\d{1,3})\.myworkdayjobs\.com$")
ORA = re.compile(r"^[a-z0-9-]+\.fa\.(?:[a-z0-9-]+\.)?oraclecloud\.com$")
SUB = {"icims": re.compile(r"^([a-z0-9-]+)\.icims\.com$"), "recruitee": re.compile(r"^([a-z0-9-]+)\.recruitee\.com$"),
       "teamtailor": re.compile(r"^([a-z0-9-]+)\.teamtailor\.com$"), "breezy": re.compile(r"^([a-z0-9-]+)\.breezy\.hr$"),
       "bamboohr": re.compile(r"^([a-z0-9-]+)\.bamboohr\.com$"), "jazzhr": re.compile(r"^([a-z0-9-]+)\.applytojob\.com$"),
       "gupy": re.compile(r"^([a-z0-9-]+)\.gupy\.io$"), "jobs2web": re.compile(r"^([a-z0-9-]+)\.jobs2web\.com$")}


def classify(host: str):
    m = WD.match(host)
    if m and m.group(1) not in SKIP:
        return "workday", f"{m.group(1)}.{m.group(2)}", {"tenant": m.group(1), "wd": m.group(2), "host": host}
    if ORA.match(host):
        return "oracle", host, {"host": host}
    for ats, rx in SUB.items():
        m = rx.match(host)
        if m and m.group(1) not in SKIP and len(m.group(1)) > 1:
            return ats, m.group(1), {}
    return None


def main():
    out, releases = sys.argv[1], sys.argv[2:]
    found = {}
    s = requests.Session(); s.trust_env = False; s.headers["User-Agent"] = UA
    got = 0
    for rel in releases:
        paths = gzip.decompress(s.get(f"{BASE}/projects/hyperlinkgraph/{rel}/host/{rel}-host-vertices.paths.gz", timeout=60).content).decode().split()
        print(rel, len(paths), "parts", flush=True)
        for i, p in enumerate(paths):
            for attempt in range(3):
                try:
                    r = s.get(f"{BASE}/{p}", stream=True, timeout=120)
                    r.raise_for_status()
                    n = 0
                    with gzip.GzipFile(fileobj=r.raw) as gz:
                        for raw in io.BufferedReader(gz, 1 << 20):
                            parts = raw.decode("utf-8", "replace").rstrip("\n").split("\t")
                            if len(parts) < 2:
                                continue
                            host = ".".join(reversed(parts[1].split(".")))
                            c = classify(host)
                            if c:
                                n += 1
                                found.setdefault((c[0], c[1]), {"ats": c[0], "key": c[1], "data": c[2], "source": f"hostgraph:{rel}"})
                    got += 1
                    print(f"  {rel} part {i}: {n} matches, total {len(found)}", flush=True)
                    break
                except Exception as e:
                    print("  retry", i, type(e).__name__, flush=True)
                    time.sleep(20)
            time.sleep(1)
            json.dump({"tenants": list(found.values())}, open(out, "w"))
    print("done", len(found), "tenants from", got, "parts")


main()
