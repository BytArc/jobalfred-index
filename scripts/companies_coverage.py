"""How many members of each list already have roles in the index, and which have none (the ones to probe).

Usage: companies_coverage.py SHARD_DIR        a downloaded copy of the published shards (manifest.json and *.json.gz)
Writes work/companies_coverage.json: per list, members with their role counts and the members with no roles.
"""
import collections, gzip, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import companies

src = Path(sys.argv[1])
man = json.loads((src / "manifest.json").read_text())
ix = companies.index()
rows_per_group = collections.Counter()
cache = {}
for s in man["shards"]:
    d = json.loads(gzip.decompress((src / s["file"]).read_bytes()))
    at = {k: i for i, k in enumerate(d["f"])}
    for r in d["rows"]:
        key = (r[at["c"]], r[at["a"]], companies.board_of(r[at["u"]]), r[at["cc"]])
        if key not in cache:
            cache[key] = companies.match(r[at["c"]], r[at["u"]], r[at["a"]], r[at["cc"]])
        if cache[key] is not None:
            rows_per_group[cache[key]] += 1
out = {}
for code, lst in companies.lists().items():
    found, missing = {}, []
    for m in lst["members"]:
        gid = ix["member_gid"].get((code, m["name"]))
        n = rows_per_group.get(gid, 0) if gid is not None else 0
        if n:
            found[m["name"]] = n
        else:
            missing.append(m["name"])
    out[code] = {"members": len(lst["members"]), "with_roles": len(found), "roles": sum(found.values()), "missing": missing, "found": found}
    print(f"{code:10} {len(found):4}/{len(lst['members']):4} members have roles, {sum(found.values()):7} roles")
(root / "work").mkdir(exist_ok=True)
(root / "work" / "companies_coverage.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("rows on any list:", sum(rows_per_group.values()))
