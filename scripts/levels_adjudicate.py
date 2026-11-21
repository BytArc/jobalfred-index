"""Blind adjudication of disagreements between the gold label and the cascade.

  levels_adjudicate.py packet SPLIT CFG          write work/levels/adjud/packet-SPLIT.jsonl: every posting where the cascade states a level or
                                                  years that differ from the label, with the two answers as A and B in random order
  levels_adjudicate.py show SPLIT START COUNT     print packet items for the adjudicator
  levels_adjudicate.py put                        read decisions on stdin -> data/levels/adjudicated.jsonl
       {"id": "g0123", "level": "A"|"B"|<level name>, "years": "A"|"B"|<number>|null, "why": "short reason"}
The adjudicator never learns which answer came from the rules.
"""
import json
import random
import sys
import textwrap
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
W = root / "work" / "levels"
OUT = root / "data" / "levels" / "adjudicated.jsonl"
CODE = {1: "internship", 2: "early", 3: "mid", 4: "senior", 5: "lead", 6: "manager", 7: "director", 8: "executive"}
LEVELS = set(CODE.values())


def packet(split: str, cfg: str):
    from jobalfred_index import levels as LV
    gold = {json.loads(l)["id"]: json.loads(l) for l in open(root / "data" / "levels" / "gold.jsonl")}
    pred = json.load(open(W / f"pred-{split}.json"))[cfg]
    chunks = {}
    for f in (W / "chunks").glob("chunk-*.jsonl"):
        for l in open(f):
            it = json.loads(l)
            chunks[it["id"]] = it
    done = set()
    if OUT.exists():
        done = {json.loads(l)["id"] for l in open(OUT) if l.strip()}
    rnd = random.Random(11)
    items = []
    for p in pred:
        g = gold[p["id"]]
        if p["id"] in done:
            continue
        lv_dis = p["ss"] in ("n", "t", "d") and CODE[p["sl"]] != g["level"]
        gy = LV.interval(g["years"]) if g["years"] is not None else 0
        yr_dis = p["ys"] == "s" and p["yx"] != gy
        if not (lv_dis or yr_dis):
            continue
        it = chunks[p["id"]]
        q = {"id": p["id"], "title": it["title"], "company": it["company"], "country": it["country"], "posting_fields": it["posting_fields"],
             "text": it["text"]}
        if lv_dis:
            a, b = g["level"], CODE[p["sl"]]
            if rnd.random() < 0.5:
                a, b = b, a
            q["level_A"], q["level_B"] = a, b
        if yr_dis:
            sys_y = LV.YEARS[p["yx"]] + " (interval of the minimum years required)"
            gold_y = "none stated" if g["years"] is None else f"{g['years']} years"
            a, b = gold_y, sys_y
            if rnd.random() < 0.5:
                a, b = b, a
            q["years_A"], q["years_B"] = a, b
        items.append(q)
    (W / "adjud").mkdir(exist_ok=True)
    with open(W / "adjud" / f"packet-{split}.jsonl", "w") as fh:
        for q in items:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(len(items), "to adjudicate")


def show(split: str, start: int, count: int):
    items = [json.loads(l) for l in open(W / "adjud" / f"packet-{split}.jsonl")]
    for q in items[start:start + count]:
        print("=" * 100)
        print(f"ID {q['id']} | TITLE: {q['title']} | COMPANY: {q['company']} | COUNTRY: {q['country']}")
        if q["posting_fields"]:
            print("POSTING'S OWN FIELDS:", json.dumps(q["posting_fields"], ensure_ascii=False))
        if "level_A" in q:
            print(f"LEVEL: A = {q['level_A']}   B = {q['level_B']}")
        if "years_A" in q:
            print(f"YEARS: A = {q['years_A']}   B = {q['years_B']}")
        print("TEXT:", textwrap.shorten(q["text"].replace("\n", " / "), 3600, placeholder=" ..."))


def put():
    have = set()
    if OUT.exists():
        have = {json.loads(l)["id"] for l in open(OUT) if l.strip()}
    packets = {}
    for f in (W / "adjud").glob("packet-*.jsonl"):
        for l in open(f):
            q = json.loads(l)
            packets[q["id"]] = q
    ok = bad = 0
    with open(OUT, "a") as fh:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                q = packets[d["id"]]
                rec = {"id": d["id"], "why": str(d.get("why", ""))[:200]}
                if "level_A" in q:
                    v = d["level"]
                    rec["level"] = q["level_A"] if v == "A" else q["level_B"] if v == "B" else v
                    assert rec["level"] in LEVELS, "level must be A, B or one of " + ",".join(sorted(LEVELS))
                if "years_A" in q:
                    v = d["years"]
                    if v in ("A", "B"):
                        s = q["years_A"] if v == "A" else q["years_B"]
                        if s.startswith("none"):
                            rec["years"] = None
                        elif "interval" in s:
                            raise AssertionError("for an interval answer give the number of years the posting requires, not A or B")
                        else:
                            rec["years"] = float(s.split()[0])
                    else:
                        assert v is None or isinstance(v, (int, float)), "years must be A, B, a number or null"
                        rec["years"] = v
                if d["id"] in have:
                    continue
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                have.add(d["id"])
                ok += 1
            except (KeyError, ValueError, AssertionError) as e:
                bad += 1
                print("REJECTED:", line[:120], "->", e)
    print(f"saved {ok}, rejected {bad}; {len(have)} adjudicated in all")


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "packet":
        packet(sys.argv[2], sys.argv[3])
    elif c == "show":
        show(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        put()
