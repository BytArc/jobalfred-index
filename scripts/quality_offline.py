"""Offline quality numbers from the stored rows and the built shards. Writes work/quality-offline.json."""
import collections, glob, gzip, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import shards
from jobalfred_index.state import State

st = State(root / "work" / "index.db", "q")
stored = collections.Counter(); canon_seen = {}; dup_by_src = collections.Counter()
by_ten = collections.Counter()
for ats, key, rows in st.iter_rows():
    for r in rows:
        stored[r[7]] += 1
        k = shards.canon_url(r[5])
        if k in canon_seen:
            dup_by_src[r[7]] += 1
        else:
            canon_seen[k] = r[7]
total_stored = sum(stored.values())
out = {"stored_rows_before_dedupe": total_stored, "stored_by_source": dict(stored),
       "same_posting_dropped_by_source": dict(dup_by_src), "same_posting_dropped_total": sum(dup_by_src.values())}

m = json.load(open(root / "dist" / "manifest.json"))
rows_all = []
for s in m["shards"]:
    rows_all += [(s["id"], r) for r in json.loads(gzip.decompress((root / "dist" / s["file"]).read_bytes()))["rows"]]
n = len(rows_all)
out["built_total"] = n
out["no_title"] = sum(1 for _, r in rows_all if not r[0].strip())
out["no_company"] = sum(1 for _, r in rows_all if not r[1].strip())
out["no_location"] = sum(1 for _, r in rows_all if not r[2].strip())
out["no_country_and_not_remote"] = sum(1 for sid, r in rows_all if sid == "XX")
out["no_posted_date"] = sum(1 for _, r in rows_all if not r[6])
out["company_looks_like_slug"] = sum(1 for _, r in rows_all if r[7] in ("oracle",) and len(r[1]) <= 5)
xx = collections.Counter(r[7] for sid, r in rows_all if sid == "XX")
out["xx_by_source"] = dict(xx.most_common(10))
# the same role (company, title, location) present more than once with different URLs
g = collections.Counter((shards.norm(r[1]), shards.norm(r[0]), shards.norm(r[2]), r[7]) for _, r in rows_all)
out["same_company_title_location_extra_rows"] = sum(v - 1 for v in g.values() if v > 1)
out["same_company_title_location_extra_by_source"] = dict(collections.Counter(
    {k[3]: 0 for k in g}) )
ex = collections.Counter()
for k, v in g.items():
    if v > 1:
        ex[k[3]] += v - 1
out["same_company_title_location_extra_by_source"] = dict(ex.most_common(8))
# different sources, same company+title
g2 = collections.defaultdict(set)
for _, r in rows_all:
    g2[(shards.norm(r[1]), shards.norm(r[0]))].add(r[7])
out["company_title_on_two_or_more_sources"] = sum(1 for v in g2.values() if len(v) > 1)
Path(root / "work" / "quality-offline.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
