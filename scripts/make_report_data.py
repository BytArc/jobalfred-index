"""Print real numbers for REPORT.md from a finished run: manifest + the newest work/report-*.json + the state DB."""
import collections, glob, gzip, json, sqlite3, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
m = json.load(open(root / "dist" / "manifest.json"))
rep = sorted(glob.glob(str(root / "work" / "report-*.json")))[-1]
r = json.load(open(rep))
print("report file:", rep, "elapsed s:", r.get("elapsed_seconds"))
print("TOTAL", m["total"], "shards", len(m["shards"]))
print("BY SOURCE", json.dumps(m["sources"]))
cc = collections.Counter(); rem = 0; unknown = 0
rem_by_cc = collections.Counter()
for s in m["shards"]:
    rows = json.loads(gzip.decompress((root / "dist" / s["file"]).read_bytes()))["rows"]
    for row in rows:
        if row[4] == 2:
            rem += 1
        if row[3]:
            cc[row[3]] += 1
        else:
            unknown += 1
print("REMOTE (r=2) rows:", rem, " rows with no country:", unknown)
for c in "PT ES GB DE FR NL IE IN US BR".split():
    print("  ", c, cc.get(c, 0))
print("TENANTS", json.dumps(r.get("tenant_counts"), indent=0))
print("FETCH", json.dumps(r.get("fetch"), indent=0))
print("DEDUPE", r.get("dedupe"))
print("HTTP", r.get("http"))
print("BLOCKED", json.dumps(r.get("blocked_hosts"))[:1500])
print("ROBOTS DENIED", json.dumps(r.get("robots_denied_hosts"))[:1500])
print("CDX", json.dumps(r.get("cdx")), "CRT", json.dumps(r.get("crtsh")), "PROBE", r.get("probe"))
