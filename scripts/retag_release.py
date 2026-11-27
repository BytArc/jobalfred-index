"""Add the level and years tags (sl, ss, yx, ys) to the index already published, without changing which roles it holds.

Made on 27 Nov 2026, when the tags reached main but the nightly could not publish (the Workday and Oracle feed was held on the
server). Rows read before the tags get the level their title states, else the level their careers system stated, else the trained
model's guess (levels.assign, as in the nightly). No description is stored, so their years are inferred from the level and marked
"i", never "s". The next nightly that publishes replaces all of this with rows read under the new rules.

    python3 scripts/retag_release.py work/retag            # download, tag and check; writes WORK/out, uploads nothing
    python3 scripts/retag_release.py work/retag --upload   # the same, then upload the shards and, last, the manifest

Checks before any upload: the same shards, the same number of rows in each, every old field of every row unchanged, every row
with all four tags, no shard over the size limit. The downloaded release stays in WORK/in as a backup. Needs about 4 GB of memory.
"""
from __future__ import annotations

import argparse
import collections
import gc
import gzip
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobalfred_index import levels, shards  # noqa: E402

TAG = "index-latest"
REPO = "BytArc/jobalfred-index"


def gh(*args: str) -> None:
    subprocess.run(["gh", *args, "-R", REPO], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", type=Path)
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    src, out = a.work / "in", a.work / "out"
    if src.exists():
        shutil.rmtree(src)
    if out.exists():
        shutil.rmtree(out)
    src.mkdir(parents=True)
    out.mkdir(parents=True)

    gh("release", "download", TAG, "--pattern", "manifest.json", "--dir", str(src))
    manifest = json.loads((src / "manifest.json").read_text())
    files = [s["file"] for s in manifest["shards"]]
    gh("release", "download", TAG, *sum((["--pattern", f] for f in files), []), "--dir", str(src))
    print(f"downloaded {len(files)} shards, manifest built {manifest['built']}, total {manifest['total']}", flush=True)

    gc.disable()        # two million small lists: the cyclic collector would rescan them all, again and again
    F = shards.FIELDS
    rows, spans = [], []
    for f in files:
        d = json.loads(gzip.decompress((src / f).read_bytes()))
        old_f = d["f"]
        ix = {k: i for i, k in enumerate(old_f)}
        start = len(rows)
        rows.extend([r[ix[k]] if k in ix else "" for k in F] for r in d["rows"])
        spans.append((f, start, len(rows), old_f))
        del d
    if len(rows) != manifest["total"]:
        print(f"refusing: {len(rows)} rows in the shards against {manifest['total']} in the manifest", file=sys.stderr)
        return 1

    t0 = time.time()
    for r in rows:
        shards.complete(r)
    stats = levels.assign(rows, log=lambda m: None)
    print(f"tagged {len(rows)} rows in {time.time() - t0:.0f} s", flush=True)

    SL, SS, YX, YS = (F.index(k) for k in ("sl", "ss", "yx", "ys"))
    problems = []
    for f, s, e, old_f in spans:
        ix = {k: F.index(k) for k in old_f}
        before = json.loads(gzip.decompress((src / f).read_bytes()))["rows"]     # the published file, read again to compare
        if len(before) != e - s:
            problems.append(f"{f}: {e - s} rows against {len(before)} published")
            continue
        for i in range(s, e):
            r = rows[i]
            if [r[ix[k]] for k in old_f] != before[i - s]:
                problems.append(f"{f}: row {i - s} changed an old field")
            if not (r[SL] and r[SS] and r[YX] and r[YS]):
                problems.append(f"{f}: row {i - s} lacks a tag")
            if r[YS] == "s":
                problems.append(f"{f}: row {i - s} claims stated years")
            if len(problems) > 20:
                break
        del before
    new_shards = []
    for (f, s, e, _), meta in zip(spans, manifest["shards"]):
        blob = shards._gz(rows[s:e])
        if len(blob) > shards.MAX_GZ:
            problems.append(f"{f}: {len(blob)} bytes, over the {shards.MAX_GZ} limit")
        (out / f).write_bytes(blob)
        new_shards.append({**meta, "bytes": len(blob)})
        if meta["count"] != e - s:
            problems.append(f"{f}: {e - s} rows against {meta['count']} in the manifest")
    if problems:
        print("refusing:\n  " + "\n  ".join(problems[:20]), file=sys.stderr)
        return 1

    manifest["shards"] = new_shards
    manifest["tagged"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (out / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    report = {
        "rows": len(rows),
        "level_source": dict(collections.Counter(r[SS] for r in rows).most_common()),
        "levels": {levels.NAMES[k]: v for k, v in sorted(collections.Counter(r[SL] for r in rows).items())},
        "years_source": dict(collections.Counter(r[YS] for r in rows)),
        "years": {levels.YEARS[k]: v for k, v in sorted(collections.Counter(r[YX] for r in rows).items())},
        "bytes_before": sum(m["bytes"] for m in json.loads((src / "manifest.json").read_text())["shards"]),
        "bytes_after": sum(m["bytes"] for m in new_shards),
        "assign": stats,
    }
    (a.work / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "assign"}, indent=1, ensure_ascii=False), flush=True)

    if a.upload:
        # shards first and the manifest last, as publish_release.sh does; the file names and counts do not change
        gh("release", "upload", TAG, *[str(out / f) for f in files], "--clobber")
        gh("release", "upload", TAG, str(out / "manifest.json"), "--clobber")
        print("uploaded", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
