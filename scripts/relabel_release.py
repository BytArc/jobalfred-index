"""Add the labels that did not exist when the published shards were built (industry, function, sub-role).

Reads a downloaded copy of the published shards (DIR), brings every row up to the current fields (shards.complete: the function
and sub-role come from the title; the industry is assigned per company by industry.assign) and writes complete shards, a manifest,
industries.json and functions.json to OUT. Nothing else about a row changes.
Usage: relabel_release.py DIR OUT [HOMEPAGE_BUDGET]
"""
import gzip, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry, shards
from jobalfred_index.polite import Client

src, out = Path(sys.argv[1]), Path(sys.argv[2])
budget = int(sys.argv[3]) if len(sys.argv) > 3 else 0
man = json.loads((src / "manifest.json").read_text())


def rows():
    for s in man["shards"]:
        d = json.loads(gzip.decompress((src / s["file"]).read_bytes()))
        keep = [k for k in d["f"] if k in shards.FIELDS]
        at = {k: i for i, k in enumerate(d["f"])}
        for r in d["rows"]:
            yield [r[at[k]] if k in at else "" for k in shards.FIELDS]


hp = industry.Homepages(client=Client() if budget else None, budget=budget)
res = shards.build((shards.complete(r) for r in rows()), out, homepages=hp)
print("rebuilt", res["manifest"]["total"], "rows; published total was", man["total"])
