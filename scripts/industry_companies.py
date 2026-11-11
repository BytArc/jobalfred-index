"""Summarise a shards directory per company (rows, job-title words, hosts) into work/ind/companies.pkl, the training and sampling input.
Usage: industry_companies.py SHARD_DIR"""
import collections, gzip, json, pickle, re, sys
from pathlib import Path
from urllib.parse import urlsplit
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry as I

src = Path(sys.argv[1])
man = json.loads((src / "manifest.json").read_text())
comp = {}
for s in man["shards"]:
    d = json.loads(gzip.decompress((src / s["file"]).read_bytes()))
    at = {k: i for i, k in enumerate(d["f"])}
    for r in d["rows"]:
        name, url = r[at["c"]], r[at["u"]]
        gk = I.group_key(name, url)
        c = comp.get(gk[2:] if gk.startswith("c:") else gk)
        k = gk[2:] if gk.startswith("c:") else gk
        c = comp.get(k)
        if c is None:
            c = comp[k] = {"name": collections.Counter(), "rows": 0, "ats": collections.Counter(), "hosts": collections.Counter(),
                           "cc": collections.Counter(), "words": collections.Counter(), "titles": []}
        c["name"][name] += 1
        c["rows"] += 1
        c["ats"][r[at["a"]]] += 1
        c["cc"][r[at["cc"]]] += 1
        c["hosts"][urlsplit(url).hostname or ""] += 1
        if len(c["titles"]) < 25:
            c["titles"].append(r[at["t"]])
        if c["rows"] <= 60 or c["rows"] % 20 == 0:
            for w in I.words(r[at["t"]]):
                c["words"][w] += 1
for c in comp.values():
    c["name"] = c["name"].most_common(1)[0][0]
Path(root / "work" / "ind").mkdir(parents=True, exist_ok=True)
pickle.dump(comp, open(root / "work" / "ind" / "companies.pkl", "wb"))
print(len(comp), "companies,", sum(c["rows"] for c in comp.values()), "rows")
