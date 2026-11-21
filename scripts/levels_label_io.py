"""Helpers for the people (or agents) labelling the gold set.

  levels_label_io.py show CHUNK START COUNT    print COUNT postings of work/levels/chunks/chunk-CHUNK.jsonl from START (0-based)
  levels_label_io.py put CHUNK                 read label lines (JSON) on stdin, check them, append to work/levels/labels/chunk-CHUNK.jsonl
  levels_label_io.py status CHUNK              how many of the chunk's postings have a label
"""
import json
import sys
import textwrap
from pathlib import Path

root = Path(__file__).resolve().parent.parent
W = root / "work" / "levels"
LEVELS = {"internship", "early", "mid", "senior", "lead", "manager", "director", "executive"}


def _name(n):
    return str(n) if str(n).startswith("check") else f"chunk-{int(n):02d}"


def _labels_dir(n):
    return W / ("labels-check" if str(n).startswith("check") else "labels")


def chunk(n):
    return [json.loads(l) for l in open(W / "chunks" / f"{_name(n)}.jsonl")]


def show(n, start, count):
    for it in chunk(n)[start:start + count]:
        print("=" * 100)
        print(f"ID {it['id']} | TITLE: {it['title']} | COMPANY: {it['company']} | COUNTRY: {it['country']} | LOCATION: {it['location']}")
        if it["posting_fields"]:
            print("POSTING'S OWN FIELDS:", json.dumps(it["posting_fields"], ensure_ascii=False))
        print("TEXT:")
        print(textwrap.shorten(it["text"].replace("\n", " / "), 3600, placeholder=" ..."))


def put(n):
    ids = {it["id"] for it in chunk(n)}
    out = _labels_dir(n)
    out.mkdir(exist_ok=True)
    path = out / f"{_name(n)}.jsonl"
    have = set()
    if path.exists():
        have = {json.loads(l)["id"] for l in open(path) if l.strip()}
    ok = bad = 0
    with open(path, "a") as fh:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                assert d["id"] in ids, "unknown id"
                assert d["level"] in LEVELS, "level must be one of " + ",".join(sorted(LEVELS))
                assert d.get("level_conf") in ("clear", "judgement"), "level_conf must be clear or judgement"
                y = d.get("years")
                assert y is None or (isinstance(y, (int, float)) and 0 <= y <= 40), "years must be a number or null"
                if d["id"] in have:
                    continue
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
                have.add(d["id"])
                ok += 1
            except (ValueError, KeyError, AssertionError) as e:
                bad += 1
                print("REJECTED:", line[:120], "->", e)
    print(f"saved {ok}, rejected {bad}; chunk {n} now has {len(have)} of {len(ids)} labelled")


def status(n):
    ids = [it["id"] for it in chunk(n)]
    path = _labels_dir(n) / f"{_name(n)}.jsonl"
    have = {json.loads(l)["id"] for l in open(path) if l.strip()} if path.exists() else set()
    missing = [i for i in ids if i not in have]
    print(f"{len(have)} of {len(ids)} labelled; first missing: {missing[:10]}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "show":
        show(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif cmd == "put":
        put(sys.argv[2])
    else:
        status(sys.argv[2])
