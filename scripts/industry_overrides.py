"""Write data/industry/overrides.json from every reader label (labels.jsonl and eval-r*.jsonl).

A company the reader has labelled keeps that label exactly; the model decides only the rest."""
import glob, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import industry as I

D = root / "data" / "industry"
out = {}
for f in [D / "labels.jsonl"] + [Path(p) for p in sorted(glob.glob(str(D / "eval-r*.jsonl")))]:
    for line in f.read_text().splitlines():
        o = json.loads(line)
        if o["key"].startswith("c:") and o["ind"] in I.taxonomy():
            out[o["key"][2:]] = o["ind"]
(D / "overrides.json").write_text(json.dumps(dict(sorted(out.items())), ensure_ascii=False, separators=(",", ":")))
print(len(out), "labelled companies")
