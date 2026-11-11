"""Fill the homepage cache for the biggest companies (data/industry/homepages.json.gz).

Usage: industry_homepages.py N [offset]      companies ranked by number of rows, from work/ind/companies.pkl
The same fetcher runs inside the nightly build for any company that has no fresh entry; this script only warms the cache.
"""
import pickle, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry
from jobalfred_index.polite import Client

n, off = int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 0
comp = pickle.load(open(root / "work" / "ind" / "companies.pkl", "rb"))
ranked = [(k, c) for k, c in sorted(comp.items(), key=lambda kv: -kv[1]["rows"])
          if not industry.group_key(c["name"], "").startswith("~")][off:off + n]
hp = industry.Homepages(client=Client(), budget=10**9)
t0 = time.time()
def one(kc):
    k, c = kc
    dom = industry.own_domain("https://" + h + "/" for h in c["hosts"])
    hp.ensure("c:" + k, c["name"], dom)
with ThreadPoolExecutor(14) as ex:
    list(ex.map(one, ranked))
hp.save()
ok = sum(1 for k, _ in ranked if hp.get("c:" + k))
print(f"{len(ranked)} companies, {hp.fetched} fetched, {ok} with a homepage, {int(time.time() - t0)}s")
