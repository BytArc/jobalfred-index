"""How many members of each list already have roles in the index.

Usage: companies_coverage.py            uses work/ind/companies.pkl (scripts/industry_companies.py SHARD_DIR builds it)
Writes work/companies_coverage.json: per list, members found with their role counts and the members with no roles (the ones to probe).
"""
import collections, json, pickle, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import companies
from jobalfred_index.industry import norm

comp = pickle.load(open(root / "work" / "ind" / "companies.pkl", "rb"))
rows_by = collections.defaultdict(int)
member_rows = collections.defaultdict(lambda: collections.defaultdict(int))
for k, c in comp.items():
    codes, _ = companies.membership(c["name"], ["https://" + h + "/" for h in c["hosts"]])
    for code in codes:
        member_rows[code][c["name"]] += c["rows"]
ix = companies.lists()
out, total = {}, 0
for code, lst in ix.items():
    found, missing = {}, []
    for m in lst["members"]:
        keys = {norm(n) for n in [m["name"]] + list(m.get("aliases") or [])}
        rows = sum(r for name, r in member_rows[code].items() if norm(name) in keys)
        if rows:
            found[m["name"]] = rows
        else:
            missing.append(m["name"])
    out[code] = {"members": len(lst["members"]), "with_roles": len(found), "roles": sum(found.values()), "missing": missing, "found": found}
    total += sum(found.values())
    print(f"{code:10} {len(found):4}/{len(lst['members']):4} members have roles, {sum(found.values()):7} roles")
(root / "work" / "companies_coverage.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
