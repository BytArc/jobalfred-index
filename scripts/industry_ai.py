"""Industry labels from claude-haiku-5-5, one per company (see jobalfred_index/ailabel.py).

Usage: industry_ai.py estimate SHARD_DIR            count the companies still to label and estimate the Batches API cost (no key needed)
       industry_ai.py smoke SHARD_DIR N             label N companies now (needs ANTHROPIC_API_KEY) and print what came back
       industry_ai.py submit SHARD_DIR [--max-usd 50]   submit the bulk run to the Message Batches API (needs the key; refuses above --max-usd)
       industry_ai.py collect SHARD_DIR             read the finished batches into data/industry/ai-labels.json.gz
The key is read from the environment by the SDK; this script never prints or stores it.
"""
import gzip, json, os, sys, time
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import ailabel, industry, shards

BATCH_FILE = root / "work" / "ai-batches.json"


def load_units(shard_dir, ai):
    shard_dir = Path(shard_dir)
    man = json.loads((shard_dir / "manifest.json").read_text())
    rows = []
    for s in man["shards"]:
        d = json.loads(gzip.decompress((shard_dir / s["file"]).read_bytes()))
        at = {k: i for i, k in enumerate(d["f"])}
        for r in d["rows"]:
            rows.append([r[at[k]] if k in at else "" for k in ("t", "c", "l", "cc", "r", "u", "p", "a")])
    groups = industry.group_rows(rows)
    hp = industry.Homepages()
    units = []
    for k, g in groups.items():
        entry = hp.get(k) if k.startswith("c:") else None
        domain = industry.own_domain(g["urls"]) or (entry or {}).get("d", "")
        key = ailabel.unit_key(k, domain)
        if industry.hand_label(k) is None and ai.get(key) is None and ai.get(k) is None:
            units.append({"key": key, "rows": g["rows"], "text": ailabel.user_text(g["name"], domain, entry, g["titles"])})
    # one unit per key (two groups can share a domain)
    seen, out = set(), []
    for u in sorted(units, key=lambda u: -u["rows"]):
        if u["key"] not in seen:
            seen.add(u["key"])
            out.append(u)
    return groups, out


def main():
    cmd, shard_dir = sys.argv[1], sys.argv[2]
    ai = ailabel.AiLabels()
    groups, units = load_units(shard_dir, ai)
    if cmd == "estimate":
        e = ailabel.estimate(units)
        print(f"companies in the index: {len(groups)}; hand-labelled: {sum(1 for k in groups if industry.hand_label(k))}; "
              f"already AI-labelled: {len(ai.data)}; still to label: {e['companies']}")
        print(json.dumps(e))
        print("sample prompt:\n" + units[0]["text"])
        return
    client = ailabel.make_client(timeout=60)
    if client is None:
        sys.exit("ANTHROPIC_API_KEY is not set in this shell (or the anthropic package is missing). Not looking for a key anywhere else.")
    if cmd == "smoke":
        n = int(sys.argv[3])
        picks = units[:n // 2] + units[len(units) // 2: len(units) // 2 + n - n // 2]
        ailabel.label_new(ai, picks, cap=n, client=client)
        for u in picks:
            print(u["key"], ai.get(u["key"]), "|", u["text"].splitlines()[0])
    elif cmd == "submit":
        cap = float(sys.argv[sys.argv.index("--max-usd") + 1]) if "--max-usd" in sys.argv else 50.0
        e = ailabel.estimate(units)
        if e["usd_batch"] > cap:
            sys.exit(f"estimate ${e['usd_batch']} is above ${cap}; not submitting")
        ids = ailabel.bulk_submit(units, client)
        BATCH_FILE.parent.mkdir(exist_ok=True)
        BATCH_FILE.write_text(json.dumps({"ids": ids, "n": len(units), "keys": [u["key"] for u in units], "submitted": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
        print("submitted", ids, e)
    elif cmd == "collect":
        b = json.loads(BATCH_FILE.read_text())
        for bid in b["ids"]:
            st = client.messages.batches.retrieve(bid)
            print(bid, st.processing_status, st.request_counts)
            if st.processing_status != "ended":
                sys.exit("not finished yet")
        print(ailabel.bulk_collect(ai, [{"key": k} for k in b["keys"]], client, b["ids"]))


if __name__ == "__main__":
    main()
