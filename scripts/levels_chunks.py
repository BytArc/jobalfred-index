"""Write blind labelling batches for the gold set: title, company, country and an excerpt of the posting, never a rule's answer.

Usage: levels_chunks.py SIZE SEED      -> work/levels/chunks/chunk-NN.jsonl and work/levels/split.json (30% dev, 70% test)
The excerpt keeps the start of the posting and every line that mentions years, months or experience, so a reader sees every number
the rules could read.
"""
import json
import random
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
W = root / "work" / "levels"
YR = re.compile(r"(?i)\b(?:years?|yrs?|anos?|años?|ans|années?|jahre?n?|jährige|jaar|jaren|anni|months?|meses|mois|monate?n?|mesi|"
                r"experien|expérien|erfahrung|esperienz|ervaring|no experience|sem experi|sin experi|sans expérience|senior|junior|"
                r"entry|intern|estágio|stage|praktik|tirocin|report(?:s|ing)? to|direct reports|manage a team|supervis|lead a team)")


def excerpt(text: str, head: int = 1300, budget: int = 3200) -> str:
    text = re.sub(r"\n{2,}", "\n", text or "").strip()
    if len(text) <= budget:
        return text
    out = [text[:head]]
    used = head
    rest = text[head:]
    for line in re.split(r"\n|(?<=[.!?])\s+", rest):
        line = line.strip()
        if line and YR.search(line):
            piece = line[:400]
            if used + len(piece) > budget + 1500:
                break
            out.append(piece)
            used += len(piece)
    return "\n".join(out[:1]) + "\n[...]\n" + "\n".join(out[1:]) if len(out) > 1 else text[:budget]


def main(size: int, seed: int):
    import os
    rd = os.environ.get("LEVELS_ROUND", "")      # "2": the fresh second sample, ids h0000.., chunks 20.., all of it the test split "test2"
    draw = {p["url"]: p for p in json.load(open(W / f"draw{rd}.json"))["picks"]}
    pages = [json.loads(l) for l in open(W / f"pages{rd}.jsonl")]
    items = []
    for pg in pages:
        if len(pg["text"]) < 300 or pg["url"] not in draw:
            continue
        p = draw[pg["url"]]
        native = {k: v for k, v in (pg.get("native") or {}).items()
                  if k in ("experience_code", "minimumExperience", "experienceRequirements", "JobLevel", "JobGrade")}
        md = (pg.get("native") or {}).get("metadata") or []
        for m in md if isinstance(md, list) else []:
            if isinstance(m, dict) and m.get("value") and re.search(r"(?i)senior|level|experience|grade|career|campus", str(m.get("name"))):
                native["field: " + str(m.get("name"))] = m.get("value")
        items.append({"title": p["title"], "company": p["company"], "country": p["cc"], "location": p["loc"][:80],
                      "posting_fields": native, "text": excerpt(pg["text"]), "url": p["url"]})
    rnd = random.Random(seed)
    rnd.shuffle(items)
    for i, it in enumerate(items):
        it["id"] = f"{'h' if rd else 'g'}{i:04d}"
    split = {it["id"]: ("test2" if rd else ("dev" if rnd.random() < 0.30 else "test")) for it in items}
    (W / "chunks").mkdir(exist_ok=True)
    first = 20 if rd else 0
    for old in (W / "chunks").glob(f"chunk-{'2' if rd else '[01]'}*.jsonl"):
        old.unlink()
    n = 0
    for k in range(0, len(items), size):
        with open(W / "chunks" / f"chunk-{first + k // size:02d}.jsonl", "w") as fh:
            for it in items[k:k + size]:
                fh.write(json.dumps({x: it[x] for x in ("id", "title", "company", "country", "location", "posting_fields", "text")},
                                    ensure_ascii=False) + "\n")
        n += 1
    json.dump({"split": split, "url": {it["id"]: it["url"] for it in items}}, open(W / f"split{rd}.json", "w"))
    print(len(items), "items in", n, "chunks;", sum(v == "dev" for v in split.values()), "dev")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
